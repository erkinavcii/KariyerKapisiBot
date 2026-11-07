"""Kariyer Kapısı ilan botu.

Modlar (ayarlar.json "mod" ya da --mod):
  duz   : filtre yok, her yeni ilan Telegram'a
  kural : ön filtre + ilan metninde anahtar kelime, yaş/dil uyarıları (LLM yok, ücretsiz)
  llm   : ön filtre + Claude ile profile uygunluk; uygun/belirsiz olanlar Telegram'a

Kullanım:
  python kariyerkapisibot.py                 # normal çalışma
  python kariyerkapisibot.py --dry-run       # Telegram'a atmaz, durumu kaydetmez
  python kariyerkapisibot.py --mod kural     # modu bu çalışma için değiştir (duz/kural/llm)
  python kariyerkapisibot.py --guid <GUID>   # tek ilanı test et (durumu yok sayar, kaydetmez)
  python kariyerkapisibot.py --limit 3       # bu çalışmada en fazla 3 yeni ilan işle
  python kariyerkapisibot.py --sadece-kaydet # mevcut ilanları bildirmeden 'görüldü' işaretle
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from kariyerbot import durum as durum_mod
from kariyerbot.kk_api import KariyerKapisiClient, KariyerKapisiHatasi, ilan_linki
from kariyerbot.kural_filtre import kural_degerlendir
from kariyerbot.metin import llm_girdisi
from kariyerbot.on_filtre import on_filtre
from kariyerbot.telegram import Telegram, e, ilan_mesaji

KOK = os.path.dirname(os.path.abspath(__file__))
AYAR_DOSYASI = os.path.join(KOK, "ayarlar.json")
PROFIL_DOSYASI = os.path.join(KOK, "profil.md")
MODLAR = ("duz", "kural", "llm")
DOLDURULMADI_ISARETI = "<DOLDUR>"


def argumanlar():
    p = argparse.ArgumentParser(description="Kariyer Kapısı ilan botu")
    p.add_argument("--dry-run", action="store_true", help="Telegram'a atma, durumu kaydetme")
    p.add_argument("--mod", choices=MODLAR, help="Çalışma modu (varsayılan: ayarlar.json)")
    p.add_argument("--no-llm", action="store_true", help="--mod kural ile aynı")
    p.add_argument("--guid", help="Sadece bu ilanı işle (test)")
    p.add_argument("--limit", type=int, help="Bu çalışmada işlenecek en fazla yeni ilan")
    p.add_argument("--sadece-kaydet", action="store_true",
                   help="Mevcut ilanları bildirim göndermeden görüldü olarak işaretle")
    return p.parse_args()


def profil_oku() -> str | None:
    """Önce ADAY_PROFILI ortam değişkeni (GitHub secret), yoksa yerel profil.md (git dışı)."""
    metin = os.getenv("ADAY_PROFILI")
    if not metin and os.path.exists(PROFIL_DOSYASI):
        with open(PROFIL_DOSYASI, "r", encoding="utf-8") as f:
            metin = f.read()
    if not metin or DOLDURULMADI_ISARETI in metin:
        return None
    return metin


def main() -> int:
    load_dotenv()
    a = argumanlar()
    with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
        ayar = json.load(f)
    llm_ayar = ayar.get("llm", {})
    bildirim_ayar = ayar.get("bildirim", {})

    mod = a.mod or ("kural" if a.no_llm else ayar.get("mod", "llm"))
    if mod not in MODLAR:
        print(f"❌ Geçersiz mod: {mod} (seçenekler: {', '.join(MODLAR)})")
        return 2

    kuru = a.dry_run or bool(a.guid)
    # Her modun kendi sohbeti olabilir: TELEGRAM_CHAT_ID_DUZ / _KURAL / _LLM, yoksa TELEGRAM_CHAT_ID.
    chat_id = os.getenv(f"TELEGRAM_CHAT_ID_{mod.upper()}") or os.getenv("TELEGRAM_CHAT_ID")
    tg = Telegram(os.getenv("TELEGRAM_BOT_TOKEN"), chat_id, kuru=kuru)
    # Modlar ayrı durum dosyası tutar; böylece birden fazla mod aynı anda çalışabilir.
    DURUM_DOSYASI = os.path.join(KOK, f"seen_jobs_{mod}.json")
    durum = durum_mod.yukle(DURUM_DOSYASI)
    kk = KariyerKapisiClient()

    # 1) Aktif ilanlar. Site/API hatasında durum dosyasına dokunmadan çık.
    try:
        ilanlar = kk.aktif_ilanlar()
    except KariyerKapisiHatasi as ex:
        print(f"❌ İlan listesi alınamadı: {ex}")
        return 1
    print(f"✅ Sitede {len(ilanlar)} aktif ilan, kayıtta {len(durum)} ilan var.")

    if a.guid:
        yeni = [i for i in ilanlar if i["guid"] == a.guid]
        if not yeni:
            print("Bu GUID aktif listede yok.")
            return 1
    else:
        yeni = [i for i in ilanlar if i["guid"] not in durum]
    yeni.sort(key=lambda i: i.get("bitTarih") or "9999")  # son başvurusu yakın olan önce
    print(f"🆕 Yeni ilan: {len(yeni)}")

    bugun = datetime.now().strftime("%Y-%m-%d")

    def isaretle(ilan, karar, **ek):
        durum[ilan["guid"]] = {
            "kurum": ilan.get("kurumAdi"), "baslik": ilan.get("ilanBaslik"),
            "bitTarih": ilan.get("bitTarih"), "ilk_gorulme": bugun, "karar": karar, **ek,
        }

    if a.sadece_kaydet:
        for ilan in yeni:
            isaretle(ilan, "atlandi")
        if not a.dry_run:
            durum_mod.kaydet(DURUM_DOSYASI, durum)
        print(f"✔ {len(yeni)} ilan bildirim gönderilmeden kaydedildi.")
        return 0

    # 2) LLM modu istendiyse kullanılabilir mi? Değilse kural moduna düş.
    llm = None
    if mod == "llm":
        profil = profil_oku()
        if profil is None:
            print("⚠️ Profil yok ya da doldurulmamış (profil.md / ADAY_PROFILI); 'kural' moduna geçiliyor.")
            mod = "kural"
        else:
            from kariyerbot.llm_filtre import filtre_olustur
            llm, sebep = filtre_olustur(profil, llm_ayar)
            if llm is None:
                print(f"⚠️ LLM kurulamadı ({sebep}); 'kural' moduna geçiliyor.")
                mod = "kural"
            else:
                print(f"🤖 LLM filtresi: {llm.model} (effort/düşünme={llm.effort})")
    kural_ayar = ayar.get("kural_filtre", {})
    dogum_yili = os.getenv("DOGUM_YILI") or kural_ayar.get("dogum_yili")
    dogum_yili = int(dogum_yili) if dogum_yili else None
    print(f"⚙️ Mod: {mod}")

    # 3) Bu çalışmanın üst sınırları (maliyet koruması)
    limit = a.limit or llm_ayar.get("calisma_basina_max_ilan", 60)
    max_usd = float(llm_ayar.get("calisma_basina_max_usd", 0.50))
    if mod == "llm" and len(yeni) > limit:
        print(f"⚠️ {len(yeni)} yeni ilandan ilk {limit} tanesi işlenecek, kalanlar sonraki çalışmaya.")
        yeni = yeni[:limit]
    elif a.limit:
        yeni = yeni[: a.limit]

    gonderilecek = set(bildirim_ayar.get("gonderilecek_kararlar", ["uygun", "belirsiz"]))
    sayac = {"uygun": 0, "belirsiz": 0, "uygun_degil": 0, "on_filtre": 0, "bildirildi": 0,
             "eslesti": 0, "eslesmedi": 0}

    for ilan in yeni:
        link = ilan_linki(ilan)

        # --- düz mod: filtre yok, her yeni ilan gider ---
        if mod == "duz":
            if tg.gonder(ilan_mesaji(ilan, link, None)):
                sayac["bildirildi"] += 1
                isaretle(ilan, "bildirildi")
            continue

        gecti, sebep = on_filtre(ilan, ayar.get("on_filtre", {}))
        if not gecti:
            sayac["on_filtre"] += 1
            print(f"  ⏭ {ilan['ilanBaslik'][:70]} — {sebep}")
            isaretle(ilan, "on_filtre", sebep=sebep)
            continue

        if llm is not None and llm.toplam_maliyet >= max_usd:
            print(f"⚠️ Çalışma maliyet sınırı (${max_usd}) aşıldı; kalanlar sonraki çalışmaya.")
            break

        try:
            detay = kk.ilan_detay(ilan["guid"])
            altlar = kk.alt_ilanlar(ilan["guid"])
        except KariyerKapisiHatasi as ex:
            print(f"  ⚠️ Detay alınamadı, sonraki çalışmada denenecek: {ex}")
            continue

        # --- kural modu: anahtar kelime + yaş/dil uyarıları, LLM yok ---
        if mod == "kural":
            k = kural_degerlendir(ilan, detay, altlar, kural_ayar, dogum_yili)
            karar = "eslesti" if k.eslesti else "eslesmedi"
            sayac[karar] += 1
            print(f"  {karar:10s} {ilan['ilanBaslik'][:70]}"
                  + (f"  [{', '.join(k.eslesen_kelimeler)}]" if k.eslesti else ""))
            if k.eslesti:
                if not tg.gonder(ilan_mesaji(ilan, link, "eslesti", k)):
                    print("  ⚠️ Bildirim gönderilemedi; ilan sonraki çalışmada tekrar denenecek.")
                    continue
                sayac["bildirildi"] += 1
            isaretle(ilan, karar)
            continue

        # --- llm modu ---
        girdi, ekler = llm_girdisi(ilan, detay, altlar)
        d = llm.degerlendir(girdi)
        sayac[d.karar] += 1
        print(f"  {d.karar:12s} ${d.maliyet_usd:.5f}  {ilan['ilanBaslik'][:70]}"
              + (f"  [hata: {d.hata}]" if d.hata else ""))

        if d.karar in gonderilecek:
            if not tg.gonder(ilan_mesaji(ilan, link, d.karar, d, ekler=ekler)):
                print("  ⚠️ Bildirim gönderilemedi; ilan sonraki çalışmada tekrar denenecek.")
                continue
            sayac["bildirildi"] += 1
        # Gerekçe profil detayı içerebilir; repoya commit'lenen durum dosyasına yazılmaz.
        isaretle(ilan, d.karar, hata=d.hata)

    # 4) Özet
    if yeni and bildirim_ayar.get("ozet_gonder", True):
        satir = [f"📊 <b>Kariyer Kapısı özeti</b> ({e(bugun)}, mod: {e(mod)})",
                 f"Yeni ilan: {len(yeni)} | Ön filtrede elenen: {sayac['on_filtre']}"]
        if mod == "kural":
            satir.append(f"🔎 Eşleşen: {sayac['eslesti']} | Eşleşmeyen: {sayac['eslesmedi']}")
        if llm:
            satir.append(f"✅ {sayac['uygun']}  🟡 {sayac['belirsiz']}  ❌ {sayac['uygun_degil']}")
            satir.append(f"💰 LLM maliyeti: ${llm.toplam_maliyet:.4f} "
                         f"({llm.toplam_girdi:,} girdi / {llm.toplam_cikti:,} çıktı token)")
        tg.gonder("\n".join(satir))

    silinen = durum_mod.suresi_gecenleri_sil(durum)
    if kuru:
        print("ℹ️ Kuru çalışma: durum dosyası kaydedilmedi.")
    else:
        durum_mod.kaydet(DURUM_DOSYASI, durum)
        print(f"✔ Durum kaydedildi ({len(durum)} kayıt, {silinen} eski kayıt silindi).")
    if llm:
        print(f"💰 Toplam LLM maliyeti: ${llm.toplam_maliyet:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
