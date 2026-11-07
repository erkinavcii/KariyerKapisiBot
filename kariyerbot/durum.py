"""Görülen ilanların kalıcı kaydı (GitHub Actions bunu repoya commit'ler)."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta


def yukle(yol: str) -> dict:
    if not os.path.exists(yol):
        return {}
    with open(yol, "r", encoding="utf-8") as f:
        veri = json.load(f)  # bozuksa sessizce sıfırlama: hata verip dur
    return veri if isinstance(veri, dict) else {}


def kaydet(yol: str, durum: dict) -> None:
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(durum, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(gecici, yol)


def suresi_gecenleri_sil(durum: dict, gun: int = 7) -> int:
    """Bitiş tarihinin üstünden `gun` gün geçmiş kayıtları siler."""
    sinir = date.today() - timedelta(days=gun)
    silinecek = []
    for guid, k in durum.items():
        try:
            if datetime.fromisoformat(k.get("bitTarih") or "").date() < sinir:
                silinecek.append(guid)
        except ValueError:
            pass
    for guid in silinecek:
        del durum[guid]
    return len(silinecek)
