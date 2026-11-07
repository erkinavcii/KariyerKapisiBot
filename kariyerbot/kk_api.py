"""kariyerkapisi.gov.tr'nin herkese açık JSON API istemcisi.

Site, ilanları tarayıcıda şu uçlardan çekiyor (giriş gerektirmez):
  POST /ilan/GetIseAlimPage                  -> aktif ilan listesi
  POST /ilan/GetIlanPreviewPublic            -> ilanın uzun metni
  POST /altilan/GetAltIlanInfoByIlanIdPublic -> pozisyon bazlı alt ilanlar
"""

from __future__ import annotations

import time
from datetime import datetime

import requests

API_URL = "https://api.kariyerkapisi.gov.tr/api"
SITE_URL = "https://kariyerkapisi.gov.tr"

# Liste yanıtındaki ilanTipi değerleri
ILAN_TIPI_BASVURULU = 1   # metni sitede, başvuru e-Devlet/Kariyer Kapısı üzerinden
ILAN_TIPI_DUYURU = 2      # sadece dış link; metin yok

_HEADERS = {
    "Content-Type": "application/json",
    "Origin": SITE_URL,
    "Referer": f"{SITE_URL}/isealim",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class KariyerKapisiHatasi(RuntimeError):
    pass


class KariyerKapisiClient:
    def __init__(self, timeout: float = 30.0, deneme: int = 3, bekleme: float = 0.3):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        self.timeout = timeout
        self.deneme = deneme
        self.bekleme = bekleme  # ardışık istekler arası nezaket beklemesi

    def _post(self, yol: str, govde: dict):
        son_hata = None
        for i in range(self.deneme):
            try:
                r = self.session.post(f"{API_URL}{yol}", json=govde, timeout=self.timeout)
                if r.status_code == 204:
                    return None
                r.raise_for_status()
                time.sleep(self.bekleme)
                return r.json()
            except (requests.RequestException, ValueError) as e:
                son_hata = e
                time.sleep(2 ** i)
        raise KariyerKapisiHatasi(f"{yol} başarısız: {son_hata}")

    def aktif_ilanlar(self) -> list[dict]:
        """Sitede listelenen ilanlar (bitiş tarihi geçmişler site gibi elenir)."""
        sonuc = self._post("/ilan/GetIseAlimPage",
                           {"krM_ID": 0, "searchText": "", "il": "0", "ilanTuru": "0"})
        if not sonuc or "searchIlan" not in sonuc:
            raise KariyerKapisiHatasi("GetIseAlimPage beklenen formatta değil")
        simdi = datetime.now()
        aktif = []
        for ilan in sonuc["searchIlan"]:
            bit = ilan.get("bitTarih")
            if bit:
                try:
                    bit_dt = datetime.fromisoformat(bit).replace(hour=23, minute=59, second=59)
                    if bit_dt < simdi:
                        continue
                except ValueError:
                    pass
            aktif.append(ilan)
        return aktif

    def ilan_detay(self, guid: str) -> dict:
        return self._post("/ilan/GetIlanPreviewPublic", {"ilanGuid": guid}) or {}

    def alt_ilanlar(self, guid: str) -> list[dict]:
        return self._post("/altilan/GetAltIlanInfoByIlanIdPublic", {"ilanGuid": guid}) or []


def ilan_linki(ilan: dict) -> str:
    if ilan.get("ilanTipi") == ILAN_TIPI_BASVURULU or not ilan.get("basvuruLinki"):
        return f"{SITE_URL}/IlanDetay?i={ilan['guid']}"
    return ilan["basvuruLinki"]
