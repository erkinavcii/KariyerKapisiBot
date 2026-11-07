"""İlan metnini temizleme ve LLM'e gidecek özeti hazırlama."""

from __future__ import annotations

import html
import re

_URL_ETIKETI = re.compile(r"\[url=([^\]]+)\](.*?)\[/url\]", re.I | re.S)
_URL_ETIKETI_YALIN = re.compile(r"\[url\](.*?)\[/url\]", re.I | re.S)
_BBCODE = re.compile(r"\[/?[a-z*]+(?:=[^\]]{0,40})?\]", re.I)
_HTML = re.compile(r"<[^>]+>")
_BOSLUK = re.compile(r"[ \t\r\f\v]+")
_COK_SATIR = re.compile(r"\n\s*\n+")

_GENEL_SART = re.compile(r"GENEL\s+ŞARTLAR?", re.I)
_OZEL_SART = re.compile(r"ÖZEL\s+ŞARTLAR?|ARANAN\s+(?:ÖZEL\s+)?(?:ŞART|NİTELİK)", re.I)

# Genel şartlar bloğu bundan uzunsa içinde özel bilgi de olabilir, dokunma.
_GENEL_BLOK_UST_SINIR = 6000


def tr_lower(s: str) -> str:
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def ekleri_bul(ham: str) -> list[str]:
    """Metindeki ek linkleri (çoğunlukla PDF tablo/kılavuz)."""
    linkler = [m.group(1).strip() for m in _URL_ETIKETI.finditer(ham or "")]
    linkler += [m.group(1).strip() for m in _URL_ETIKETI_YALIN.finditer(ham or "")]
    return list(dict.fromkeys(linkler))


def temizle(ham: str) -> str:
    """BBCode/HTML'i atıp okunabilir düz metin döndürür. Linkler '(link: ...)' olarak kalır."""
    t = ham or ""
    t = _URL_ETIKETI.sub(lambda m: f"{m.group(2)} (link: {m.group(1)})", t)
    t = _URL_ETIKETI_YALIN.sub(lambda m: f"(link: {m.group(1)})", t)
    t = _BBCODE.sub(" ", t)
    t = _HTML.sub(" ", t)
    t = html.unescape(t)
    t = _BOSLUK.sub(" ", t)
    t = _COK_SATIR.sub("\n", t)
    return t.strip()


def genel_sartlari_cikar(metin: str) -> str:
    """657/48. madde tarzı her ilanda aynı olan 'GENEL ŞARTLAR' bloğunu atar.

    Sadece blok, ardından bir 'ÖZEL ŞARTLAR' başlığı geliyorsa ve makul uzunluktaysa atılır;
    aksi halde metin aynen döner (bilgi kaybetmemek için).
    """
    g = _GENEL_SART.search(metin)
    if not g:
        return metin
    o = _OZEL_SART.search(metin, g.end())
    if not o or (o.start() - g.start()) > _GENEL_BLOK_UST_SINIR:
        return metin
    return metin[: g.start()] + "[GENEL ŞARTLAR (standart) çıkarıldı]\n" + metin[o.start():]


_CUMLE = re.compile(r"(?<=[.;:])\s+")


def _parcalar(metin: str) -> list[str]:
    """Satırlara, uzun satırları da cümlelere böler."""
    out = []
    for satir in metin.split("\n"):
        out.extend(_CUMLE.split(satir) if len(satir) > 300 else [satir])
    return [p.strip() for p in out if p.strip()]


def tekrarlari_at(metin: str, gorulen: set[str]) -> str:
    """`gorulen` içinde olan (>=25 karakterlik) satır/cümleleri atar, yenilerini kümeye ekler."""
    kalan = []
    for p in _parcalar(metin):
        anahtar = re.sub(r"\W+", "", tr_lower(p))
        if len(anahtar) >= 25:
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
        kalan.append(p)
    return "\n".join(kalan)


def llm_girdisi(ilan: dict, detay: dict, altlar: list[dict]) -> tuple[str, list[str]]:
    """LLM'e gönderilecek ilan özetini ve ek linklerini döndürür."""
    ham_ana = detay.get("ilanMetni") or ""
    ekler = ekleri_bul(ham_ana)
    ana = genel_sartlari_cikar(temizle(ham_ana))

    parcalar = [
        f"KURUM: {ilan.get('kurumAdi', '')} / {ilan.get('birimAdi', '')}",
        f"BAŞLIK: {ilan.get('ilanBaslik', '')}",
        f"İLAN TÜRÜ: {ilan.get('ilanTuru', '')}",
        f"BAŞVURU: {(ilan.get('basTarih') or '')[:10]} - {(ilan.get('bitTarih') or '')[:10]}",
    ]
    if ana:
        parcalar.append("\n=== ANA İLAN METNİ ===\n" + ana)
    else:
        parcalar.append("\n(İlan metni sitede yok; sadece başlık ve dış link mevcut.)")

    gorulen: set[str] = set()
    tekrarlari_at(ana, gorulen)  # ana metnin cümlelerini kaydet
    for i, alt in enumerate(altlar, 1):
        ham_alt = alt.get("ilanMetni") or ""
        ekler += ekleri_bul(ham_alt)
        tam_alt = genel_sartlari_cikar(temizle(ham_alt))
        # Alt ilan metni çoğu zaman ana metnin / diğer pozisyonların kopyası; tekrarları gönderme.
        alt_metin = tekrarlari_at(tam_alt, gorulen)
        tekrar = bool(tam_alt) and not alt_metin.strip()
        kontenjan = ", ".join(f"{k.get('il')}: {k.get('kontenjan')}" for k in alt.get("kontenjanList") or [])
        degerleme = ", ".join(
            f"{d.get('asamaAdi')} %{d.get('agirlik')}" for d in alt.get("degerlemeAsamaList") or []
        )
        satirlar = [
            f"\n=== POZİSYON {i}: {alt.get('ilanBaslik', '')} ===",
            f"Unvan: {alt.get('unvan') or '-'} | Hizmet sınıfı: {alt.get('hizmetSinifi') or '-'}",
            f"Kontenjan: {kontenjan or '-'}",
            f"Değerlendirme: {degerleme or '-'}",
        ]
        if alt_metin and not tekrar:
            satirlar.append(alt_metin)
        elif tekrar:
            satirlar.append("(Pozisyon metni ana ilan metniyle aynı.)")
        parcalar.append("\n".join(satirlar))

    ekler = list(dict.fromkeys(ekler))
    if ekler:
        parcalar.append(
            "\n=== EKLER (içerikleri bu metinde YOK; bölüm/şart tabloları burada olabilir) ===\n"
            + "\n".join(ekler)
        )
    return "\n".join(parcalar), ekler
