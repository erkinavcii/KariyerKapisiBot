"""İlanı aday profiline göre Claude ile değerlendirir (yapılandırılmış JSON çıktı)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic

# $ / 1M token (girdi, çıktı, önbellekten okuma). Haiku 5.5: 100K token üstü prompt'ta 2 katı.
FIYATLAR = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
}

KARARLAR = ("uygun", "belirsiz", "uygun_degil")

SEMA = {
    "type": "object",
    "properties": {
        "karar": {"type": "string", "enum": list(KARARLAR)},
        "uygun_pozisyonlar": {"type": "array", "items": {"type": "string"}},
        "karsilanan_sartlar": {"type": "array", "items": {"type": "string"}},
        "eksik_veya_belirsiz_sartlar": {"type": "array", "items": {"type": "string"}},
        "gerekce": {"type": "string"},
    },
    "required": ["karar", "uygun_pozisyonlar", "karsilanan_sartlar",
                 "eksik_veya_belirsiz_sartlar", "gerekce"],
    "additionalProperties": False,
}

TALIMAT = """Sen bir kamu iş ilanı uygunluk değerlendiricisisin. Aşağıda adayın profili var.
Sana verilen her ilan için adayın BAŞVURU ŞARTLARINI karşılayıp karşılamadığına karar ver.

Kurallar:
- Sadece ilan metnindeki somut şartlara bak: mezuniyet düzeyi ve bölüm, KPSS puan türü/yılı/taban puan,
  yabancı dil (YDS/YÖKDİL) seviyesi, yaş sınırı, deneyim, sertifika, ehliyet, cinsiyet/askerlik vb.
- İlanda birden fazla pozisyon varsa her birine ayrı bak; aday en az birine uyuyorsa karar "uygun"dur
  ve uyduğu pozisyonları "uygun_pozisyonlar"a yaz.
- Adayın kesin olarak karşılamadığı (bölüm listede yok, yaş sınırı aşılmış, istenen puan türü yok vb.)
  bir şart varsa ve hiçbir pozisyona uymuyorsa karar "uygun_degil".
- Belirleyici şart ek dosyada (PDF tablo) duruyorsa, metin eksikse veya profil o şart hakkında bilgi
  içermiyorsa karar "belirsiz"; neyin belirsiz olduğunu "eksik_veya_belirsiz_sartlar"a yaz.
- Profildeki "istemediklerim" kısmı da bağlayıcıdır (şehir, kurum türü vb.).
- Standart "genel şartlar"ı (vatandaşlık, sabıka, sağlık vb.) adayın karşıladığını varsay.
- gerekce en fazla 2 kısa cümle, Türkçe.

=== ADAY PROFİLİ ===
{profil}
"""


@dataclass
class Degerlendirme:
    karar: str
    uygun_pozisyonlar: list[str] = field(default_factory=list)
    karsilanan_sartlar: list[str] = field(default_factory=list)
    eksik_veya_belirsiz_sartlar: list[str] = field(default_factory=list)
    gerekce: str = ""
    maliyet_usd: float = 0.0
    hata: str | None = None


class LLMFiltre:
    def __init__(self, profil: str, model: str = "claude-haiku-5-5", effort: str = "low",
                 max_tokens: int = 4000):
        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.sistem = [{
            "type": "text",
            "text": TALIMAT.format(profil=profil.strip()),
            # Profil her çağrıda aynı; yeterince uzunsa önbellekten okunur.
            "cache_control": {"type": "ephemeral"},
        }]
        self.toplam_maliyet = 0.0
        self.toplam_girdi = 0
        self.toplam_cikti = 0

    def _maliyet(self, usage) -> float:
        g, c, cr = FIYATLAR.get(self.model, FIYATLAR["claude-opus-5-5"])
        girdi = usage.input_tokens or 0
        yazma = getattr(usage, "cache_creation_input_tokens", 0) or 0
        okuma = getattr(usage, "cache_read_input_tokens", 0) or 0
        cikti = usage.output_tokens or 0
        if self.model == "claude-haiku-5-5" and (girdi + yazma + okuma) > 100_000:
            g, c = g * 2, c * 2
        self.toplam_girdi += girdi + yazma + okuma
        self.toplam_cikti += cikti
        return (girdi * g + yazma * g * 1.25 + okuma * cr + cikti * c) / 1_000_000

    def degerlendir(self, ilan_metni: str) -> Degerlendirme:
        try:
            yanit = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.sistem,
                messages=[{"role": "user", "content": f"Değerlendirilecek ilan:\n\n{ilan_metni}"}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": SEMA},
                },
            )
        except anthropic.APIConnectionError as e:
            return Degerlendirme(karar="belirsiz", hata=f"bağlantı hatası: {e}")
        except anthropic.RateLimitError as e:
            return Degerlendirme(karar="belirsiz", hata=f"rate limit: {e.message}")
        except anthropic.APIStatusError as e:
            return Degerlendirme(karar="belirsiz", hata=f"API {e.status_code}: {e.message}")

        maliyet = self._maliyet(yanit.usage)
        self.toplam_maliyet += maliyet

        if yanit.stop_reason == "refusal":
            return Degerlendirme(karar="belirsiz", maliyet_usd=maliyet, hata="model reddetti")
        if yanit.stop_reason == "max_tokens":
            return Degerlendirme(karar="belirsiz", maliyet_usd=maliyet, hata="max_tokens'a takıldı")

        metin = next((b.text for b in yanit.content if b.type == "text"), "")
        try:
            veri = json.loads(metin)
        except json.JSONDecodeError:
            return Degerlendirme(karar="belirsiz", maliyet_usd=maliyet, hata="JSON çözülemedi")
        if veri.get("karar") not in KARARLAR:
            veri["karar"] = "belirsiz"
        return Degerlendirme(maliyet_usd=maliyet, **{k: veri.get(k) for k in SEMA["required"]})
