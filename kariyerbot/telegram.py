"""Telegram bildirimleri."""

from __future__ import annotations

import html
import time

import requests

_LIMIT = 4000  # Telegram mesaj sınırı 4096


def e(s) -> str:
    return html.escape(str(s or ""), quote=False)


class Telegram:
    def __init__(self, token: str | None, chat_id: str | None, kuru: bool = False):
        self.token = token
        self.chat_id = chat_id
        self.kuru = kuru or not (token and chat_id)
        if not (token and chat_id) and not kuru:
            print("⚠️ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID yok; mesajlar sadece konsola yazılacak.")

    def gonder(self, mesaj: str) -> bool:
        if len(mesaj) > _LIMIT:
            mesaj = mesaj[: _LIMIT - 20] + "\n…(kısaltıldı)"
        if self.kuru:
            print("----- [TELEGRAM] -----\n" + mesaj + "\n----------------------")
            return True
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": mesaj, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=30,
            )
            if r.status_code == 429:
                time.sleep(int(r.json().get("parameters", {}).get("retry_after", 5)))
                return self.gonder(mesaj)
            r.raise_for_status()
            time.sleep(1)
            return True
        except requests.RequestException as ex:
            print(f"Telegram hatası: {ex}")
            return False


_ROZET = {"uygun": "✅ UYGUN", "belirsiz": "🟡 KONTROL ET", "uygun_degil": "❌ UYGUN DEĞİL",
          "eslesti": "🔎 ANAHTAR KELİME EŞLEŞTİ", None: "📢 YENİ İLAN"}


def ilan_mesaji(ilan: dict, link: str, karar: str | None, d=None) -> str:
    satirlar = [
        f"<b>{_ROZET.get(karar, karar)}</b>",
        f"🏢 <b>{e(ilan.get('kurumAdi'))}</b>",
        f"💼 {e(ilan.get('ilanBaslik'))}",
        f"🏷 {e(ilan.get('ilanTuru'))}",
        f"📅 {e((ilan.get('basTarih') or '')[:10])} → <b>{e((ilan.get('bitTarih') or '')[:10])}</b>",
    ]
    if d is not None and hasattr(d, "eslesen_kelimeler"):  # kural modu
        satirlar.append("🔑 " + e(", ".join(d.eslesen_kelimeler)))
        if d.ornek:
            satirlar.append("📝 <i>" + e(d.ornek) + "</i>")
        for u in d.uyarilar:
            satirlar.append("⚠️ " + e(u))
    elif d is not None:  # llm modu
        if d.uygun_pozisyonlar:
            satirlar.append("🎯 " + e("; ".join(d.uygun_pozisyonlar)))
        if d.gerekce:
            satirlar.append("💬 " + e(d.gerekce))
        if d.eksik_veya_belirsiz_sartlar:
            satirlar.append("⚠️ " + e("; ".join(d.eksik_veya_belirsiz_sartlar)))
        if d.hata:
            satirlar.append("🛠 LLM: " + e(d.hata))
    satirlar.append(f"🔗 <a href=\"{e(link)}\">İlana git</a>")
    return "\n".join(satirlar)
