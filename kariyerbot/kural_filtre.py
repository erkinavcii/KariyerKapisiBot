"""LLM'siz 'temel' filtre: ilan metninde anahtar kelime arar, yaş/dil şartı için uyarı üretir.

Kesin karar vermez; eşleşen ilanı gönderir, şüpheli şartları uyarı olarak ekler.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .metin import ekleri_bul, temizle, tr_lower

_YAS = re.compile(r"(\d{2})\s*(?:\(\s*[^)]{0,20}\)\s*)?yaşını\s*(?:doldurmamış|tamamlamamış|bitirmemiş)",
                  re.I)
# Sadece somut puan/düzey şartı: "YDS ... en az 70 puan", "(C) düzeyinde ... Yabancı Dil" vb.
# Düz "yabancı dil" geçişi (bilişim ilanlarında "İngilizce doküman okuyabilmek" gibi) uyarı üretmez.
_DIL = re.compile(
    r"(?:yds|yökdil|yabancı\s+dil(?:\s+bilgisi)?\s+seviye)[^.;]{0,160}?"
    r"(?:\(\s*[a-e]\s*\)\s*düzey|en\s+az\s*\(?\s*\d{2}|\d{2}\s*\)?\s*puan|asgari)"
    r"|\(\s*[a-e]\s*\)\s*düzey[^.;]{0,160}?(?:yds|yökdil|yabancı\s+dil)",
    re.I,
)
_KPSS = re.compile(r"kpss\s*(?:\(|-)?\s*(p\s?\d{1,2})", re.I)


@dataclass
class KuralSonucu:
    eslesti: bool
    eslesen_kelimeler: list[str] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)
    ornek: str = ""
    ekler: list[str] = field(default_factory=list)


def _tam_metin(ilan: dict, detay: dict, altlar: list[dict]) -> str:
    parcalar = [ilan.get("ilanBaslik", ""), temizle(detay.get("ilanMetni") or "")]
    for a in altlar:
        parcalar += [a.get("ilanBaslik") or "", a.get("unvan") or "", temizle(a.get("ilanMetni") or "")]
    return "\n".join(p for p in parcalar if p)


def _ornek(metin: str, kucuk: str, kelime: str, genislik: int = 110) -> str:
    i = kucuk.find(kelime)
    if i < 0:
        return ""
    bas, son = max(0, i - genislik), min(len(metin), i + len(kelime) + genislik)
    return ("…" if bas else "") + metin[bas:son].replace("\n", " ").strip() + ("…" if son < len(metin) else "")


def kural_degerlendir(ilan: dict, detay: dict, altlar: list[dict], ayar: dict,
                      dogum_yili: int | None = None) -> KuralSonucu:
    metin = _tam_metin(ilan, detay, altlar)
    kucuk = tr_lower(metin)  # tr_lower uzunluğu korur, indeksler metinle hizalı kalır

    kelimeler = [tr_lower(k) for k in ayar.get("anahtar_kelimeler") or []]
    eslesen = [k for k in kelimeler if k in kucuk]
    if kelimeler and not eslesen:
        return KuralSonucu(eslesti=False)

    uyarilar = []
    if dogum_yili:
        yil = int((ilan.get("bitTarih") or "0000")[:4] or 0) or None
        sinirlar = sorted({int(m.group(1)) for m in _YAS.finditer(metin)})
        if yil and sinirlar:
            yas = yil - dogum_yili
            gecemeyen = [s for s in sinirlar if yas >= s]
            if len(gecemeyen) == len(sinirlar):
                uyarilar.append(f"Yaş sınırı {'/'.join(map(str, sinirlar))}: ~{yas} yaşında aşılıyor olabilir")
            elif gecemeyen:
                uyarilar.append(f"Bazı pozisyonlarda yaş sınırı {'/'.join(map(str, gecemeyen))}")
    if ayar.get("yabanci_dil_yok") and _DIL.search(metin):
        uyarilar.append("⛔ Yabancı dil puan şartı var (en az bir pozisyonda)")
    puan_turleri = sorted({m.group(1).upper().replace(" ", "") for m in _KPSS.finditer(metin)})
    if puan_turleri:
        uyarilar.append("KPSS puan türü: " + ", ".join(puan_turleri))

    ekler = ekleri_bul(detay.get("ilanMetni") or "")
    for a in altlar:
        ekler += ekleri_bul(a.get("ilanMetni") or "")
    return KuralSonucu(eslesti=True, eslesen_kelimeler=eslesen, uyarilar=uyarilar,
                       ornek=_ornek(metin, kucuk, eslesen[0]) if eslesen else "",
                       ekler=list(dict.fromkeys(ekler)))
