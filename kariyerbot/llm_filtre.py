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
- Ek dosyaların (PDF) içeriği sana VERİLMEZ ve okunmayacak. Belirleyici şart (ör. kabul edilen bölümler
  tablosu) ekteyse, metin eksikse veya profil o şart hakkında bilgi içermiyorsa karar "belirsiz"; neyin
  belirsiz olduğunu "eksik_veya_belirsiz_sartlar"a yaz (ör. "Kabul edilen bölümler PDF ekte").
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


# ---------------------------------------------------------------------------
# DeepSeek (OpenAI uyumlu Chat Completions API)
# ---------------------------------------------------------------------------

# $ / 1M token, YOĞUN saat fiyatı (girdi-önbellek-ıskası, çıktı, girdi-önbellek-isabeti).
# Yoğun dışı saatlerde yarı fiyat. Kaynak: api-docs.deepseek.com/quick_start/pricing (Kasım 2026).
DEEPSEEK_FIYATLAR = {
    "deepseek-flash": (0.30, 1.20, 0.006),
    "deepseek-v4-pro": (1.32, 3.96, 0.044),
}

JSON_ORNEGI = """
Yanıtı SADECE şu biçimde geçerli bir json nesnesi olarak ver:
{
  "karar": "uygun" | "belirsiz" | "uygun_degil",
  "uygun_pozisyonlar": ["..."],
  "karsilanan_sartlar": ["..."],
  "eksik_veya_belirsiz_sartlar": ["..."],
  "gerekce": "en fazla 2 kısa cümle"
}
"""


def deepseek_yogun_saat_mi(an=None) -> bool:
    """Hafta içi 01-04 ve 06-10 UTC yoğun saat (Çin resmi tatilleri hesaba katılmıyor)."""
    from datetime import datetime, timezone
    an = an or datetime.now(timezone.utc)
    return an.weekday() < 5 and (1 <= an.hour < 4 or 6 <= an.hour < 10)


class DeepSeekFiltre:
    def __init__(self, profil: str, model: str = "deepseek-flash", dusunme: bool = False,
                 effort: str = "low", max_tokens: int | None = None):
        from openai import OpenAI  # sadece deepseek seçilince gerekir

        import os
        self.client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
        self.model = model
        self.dusunme = dusunme
        self.effort = effort if dusunme else "kapalı"
        self.max_tokens = max_tokens or (8000 if dusunme else 1500)
        # Sabit sistem mesajı: DeepSeek önbelleği aynı önekleri otomatik ucuzlatır.
        self.sistem = TALIMAT.format(profil=profil.strip()) + JSON_ORNEGI
        self.toplam_maliyet = 0.0
        self.toplam_girdi = 0
        self.toplam_cikti = 0

    def _maliyet(self, usage) -> float:
        g, c, cr = DEEPSEEK_FIYATLAR.get(self.model, DEEPSEEK_FIYATLAR["deepseek-v4-pro"])
        if not deepseek_yogun_saat_mi():
            g, c, cr = g / 2, c / 2, cr / 2
        toplam_girdi = usage.prompt_tokens or 0
        isabet = getattr(usage, "prompt_cache_hit_tokens", None) or 0
        iska = getattr(usage, "prompt_cache_miss_tokens", None)
        iska = toplam_girdi - isabet if iska is None else iska
        cikti = usage.completion_tokens or 0  # düşünme tokenları dahil
        self.toplam_girdi += toplam_girdi
        self.toplam_cikti += cikti
        return (iska * g + isabet * cr + cikti * c) / 1_000_000

    def _istek(self, ilan_metni: str):
        ek = {"thinking": {"type": "enabled" if self.dusunme else "disabled"}}
        args = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": self.sistem},
                      {"role": "user", "content": f"Değerlendirilecek ilan:\n\n{ilan_metni}"}],
            extra_body=ek,
        )
        if self.dusunme:
            args["reasoning_effort"] = self.effort
        return self.client.chat.completions.create(**args)

    def degerlendir(self, ilan_metni: str) -> Degerlendirme:
        import openai

        maliyet = 0.0
        for deneme in range(2):  # JSON modu bazen boş içerik döndürebiliyor -> bir kez tekrar
            try:
                yanit = self._istek(ilan_metni)
            except openai.APIConnectionError as e:
                return Degerlendirme(karar="belirsiz", maliyet_usd=maliyet, hata=f"bağlantı hatası: {e}")
            except openai.RateLimitError as e:
                return Degerlendirme(karar="belirsiz", maliyet_usd=maliyet, hata=f"rate limit: {e}")
            except openai.APIStatusError as e:
                return Degerlendirme(karar="belirsiz", maliyet_usd=maliyet,
                                     hata=f"API {e.status_code}: {e.message}")

            m = self._maliyet(yanit.usage)
            maliyet += m
            self.toplam_maliyet += m
            secim = yanit.choices[0]
            if secim.finish_reason == "length":
                return Degerlendirme(karar="belirsiz", maliyet_usd=maliyet, hata="max_tokens'a takıldı")
            metin = (secim.message.content or "").strip()
            if not metin:
                continue
            try:
                veri = json.loads(metin)
            except json.JSONDecodeError:
                continue
            if veri.get("karar") not in KARARLAR:
                veri["karar"] = "belirsiz"
            return Degerlendirme(
                karar=veri["karar"],
                uygun_pozisyonlar=list(veri.get("uygun_pozisyonlar") or []),
                karsilanan_sartlar=list(veri.get("karsilanan_sartlar") or []),
                eksik_veya_belirsiz_sartlar=list(veri.get("eksik_veya_belirsiz_sartlar") or []),
                gerekce=str(veri.get("gerekce") or ""),
                maliyet_usd=maliyet,
            )
        return Degerlendirme(karar="belirsiz", maliyet_usd=maliyet, hata="geçerli JSON gelmedi")


# ---------------------------------------------------------------------------
# Sağlayıcı seçimi
# ---------------------------------------------------------------------------

SAGLAYICI_ANAHTARI = {"anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}


def filtre_olustur(profil: str, llm_ayar: dict):
    """ayarlar.json 'llm' bölümüne göre filtreyi kurar. (filtre, None) ya da (None, sebep) döner."""
    import os

    saglayici = llm_ayar.get("saglayici", "anthropic")
    anahtar = SAGLAYICI_ANAHTARI.get(saglayici)
    if anahtar is None:
        return None, f"bilinmeyen sağlayıcı: {saglayici} (anthropic | deepseek)"
    if not os.getenv(anahtar):
        return None, f"{anahtar} yok"
    a = llm_ayar.get(saglayici, {})
    if saglayici == "deepseek":
        return DeepSeekFiltre(profil, model=a.get("model", "deepseek-flash"),
                              dusunme=bool(a.get("dusunme", False)), effort=a.get("effort", "low")), None
    return LLMFiltre(profil, model=a.get("model", "claude-haiku-5-5"), effort=a.get("effort", "low")), None
