"""LLM'e gitmeden önce ücretsiz, kural tabanlı eleme (ayarlar.json -> on_filtre)."""

from __future__ import annotations

from .metin import tr_lower


def _iceriyor(metin: str, kelimeler: list[str]) -> str | None:
    m = tr_lower(metin)
    for k in kelimeler or []:
        if k and tr_lower(k) in m:
            return k
    return None


def on_filtre(ilan: dict, ayar: dict) -> tuple[bool, str]:
    """(geçti_mi, sebep). Boş listeler 'kısıt yok' demektir."""
    tur = ilan.get("ilanTuru") or ""
    baslik = f"{ilan.get('kurumAdi', '')} {ilan.get('ilanBaslik', '')}"

    if (k := _iceriyor(tur, ayar.get("haric_ilan_turleri"))):
        return False, f"ilan türü hariç: {k}"
    dahil = ayar.get("dahil_ilan_turleri") or []
    if dahil and not _iceriyor(tur, dahil):
        return False, f"ilan türü listede değil: {tur}"
    if (k := _iceriyor(baslik, ayar.get("haric_baslik_kelimeleri"))):
        return False, f"başlıkta hariç kelime: {k}"
    zorunlu = ayar.get("zorunlu_baslik_kelimeleri") or []
    if zorunlu and not _iceriyor(baslik, zorunlu):
        return False, "başlıkta zorunlu kelimelerden hiçbiri yok"
    return True, ""
