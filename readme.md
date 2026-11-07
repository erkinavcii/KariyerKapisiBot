# 🚀 Kariyer Kapısı İlan Takip ve Filtreleme Botu

[kariyerkapisi.gov.tr/isealim](https://kariyerkapisi.gov.tr/isealim) ilanlarını sitenin herkese açık JSON API'sinden çeker,
uzun ilan metinlerindeki başvuru şartlarını **Claude** ile senin profiline göre değerlendirir ve sadece
**uygun / kontrol edilmesi gereken** ilanları **Telegram**'a gönderir.

## Akış

```
API: aktif ilanlar ──► yeni mi? (seen_jobs_<mod>.json) ──► ön filtre (ayarlar.json, ücretsiz)
      ──► detay + alt ilanlar ──► genel şartlar atılır ──► Claude (profil.md) ──► Telegram
```

| Uç (POST `api.kariyerkapisi.gov.tr/api`) | İçerik |
|---|---|
| `/ilan/GetIseAlimPage` | Aktif ilan listesi |
| `/ilan/GetIlanPreviewPublic` `{"ilanGuid"}` | İlanın uzun metni |
| `/altilan/GetAltIlanInfoByIlanIdPublic` `{"ilanGuid"}` | Pozisyonlar, kontenjan, değerlendirme |

Tarayıcı (Playwright) gerekmez. Eski sürüm `kariyerkapisibot_legacy.py` içinde duruyor.

## Modlar

`ayarlar.json` içindeki `"mod"` ya da `--mod` ile seçilir. Her mod kendi `seen_jobs_<mod>.json` dosyasını
tutar; istersen birden fazlasını aynı anda (ayrı Telegram sohbetlerine: `TELEGRAM_CHAT_ID_DUZ`,
`TELEGRAM_CHAT_ID_KURAL`, `TELEGRAM_CHAT_ID_LLM`) çalıştırabilirsin.

| Mod | Ne yapar | Maliyet |
|---|---|---|
| `duz` | Filtre yok, her yeni ilan gider (eski davranış) | 0 |
| `kural` (varsayılan) | Ön filtre + ilan metninde anahtar kelime; yaş sınırı, yabancı dil puan şartı ve KPSS puan türü için uyarı | 0 |
| `llm` | Ön filtre + Claude ile profile göre uygun / belirsiz / uygun değil kararı | ~$0.001/ilan |

`llm` modunda API anahtarı ya da profil yoksa bot otomatik olarak `kural` moduna düşer.

## Dosyalar

| Dosya | Ne işe yarar |
|---|---|
| `kariyerkapisibot.py` | Ana akış ve komut satırı |
| `kariyerbot/kk_api.py` | Site API istemcisi |
| `kariyerbot/metin.py` | BBCode temizleme, genel şartları atma, LLM girdisi |
| `kariyerbot/on_filtre.py` | İlan türü / başlık kelimesi ile ücretsiz eleme |
| `kariyerbot/llm_filtre.py` | Claude ile yapılandırılmış (JSON) uygunluk kararı + maliyet takibi |
| `kariyerbot/telegram.py` | Mesaj biçimi ve gönderim |
| `ayarlar.json` | Ön filtre, model, maliyet sınırları, hangi kararların bildirileceği |
| `profil.ornek.md` | Profil şablonu → `profil.md` olarak kopyala (git dışı) |
| `kariyerbot/kural_filtre.py` | LLM'siz anahtar kelime + yaş/dil/KPSS uyarıları |
| `seen_jobs_<mod>.json` | Her modun daha önce işlediği ilanlar (Actions commit'ler) |

## Maliyet

Ölçüm: Kasım 2026'daki 27 aktif ilan; tekrarlar ve genel şartlar atıldıktan sonra ilan başına ~5.2K token
girdi + ~0.9K talimat/profil; çıktı (JSON + düşünme) 400–1500 token aralığı varsayıldı.

| Model | İlan başı | Ayda ~60 ilan | 1000 ilan |
|---|---|---|---|
| `claude-haiku-5-5` (llm modunda varsayılan) | $0.0008–0.0014 | $0.05–0.08 | $0.8–1.4 |
| `claude-sonnet-5-5` | $0.016–0.027 | $1.0–1.6 | $16–27 |
| `claude-opus-5-5` | $0.032–0.054 | $1.9–3.3 | $32–54 |
| `deepseek-flash` (yoğun saat / dışı) | $0.0023–0.0036 / $0.0012–0.0018 | $0.14–0.22 / $0.07–0.11 | $2.3–3.6 / $1.2–1.8 |
| `deepseek-v4-pro` (yoğun saat / dışı) | $0.0096–0.014 / $0.0048–0.0070 | $0.58–0.84 / $0.29–0.42 | $9.6–14 / $4.8–7.0 |

DeepSeek yoğun saatleri hafta içi 01–04 ve 06–10 UTC; bu workflow'un 06:00 UTC cron'u yoğun saate denk gelir.
Fiyatlar Kasım 2026 itibarıyladır; tokenizer farkı nedeniyle Türkçe metinde gerçek sayılar ±%30 oynayabilir.

Sitede günde ortalama 1–2 (en yoğun ~7) yeni ilan çıkıyor. Her çalışmada `calisma_basina_max_ilan` ve
`calisma_basina_max_usd` sınırları uygulanır; aşan ilanlar sonraki çalışmaya kalır. Gerçek maliyet her
çalışmanın sonunda konsola ve Telegram özetine yazılır.

## Kurulum (yerel)

```bash
pip install -r requirements.txt
cp profil.ornek.md profil.md   # doldur, en üstteki <DOLDUR> işaretini sil
```

`.env`:
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
ANTHROPIC_API_KEY=...
```

```bash
python kariyerkapisibot.py --dry-run --limit 3   # Telegram'a atmadan, 3 ilanla dene
python kariyerkapisibot.py --guid <GUID>         # tek ilanı test et
python kariyerkapisibot.py --sadece-kaydet       # ilk kurulumda mevcut ilanları sessizce kaydet
python kariyerkapisibot.py                       # normal çalışma
```

`ANTHROPIC_API_KEY` ya da doldurulmuş profil yoksa bot LLM'siz çalışır ve ön filtreden geçen her yeni ilanı bildirir.

## GitHub Actions

Settings → Secrets and variables → Actions altında şu secret'ları ekle:

| Secret | Açıklama |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather token'ı |
| `TELEGRAM_CHAT_ID` | Mesajın gideceği sohbet |
| `ANTHROPIC_API_KEY` | Claude API anahtarı |
| `ADAY_PROFILI` | `profil.md`'nin tüm içeriği (profil repoya girmesin diye) |
| `DOGUM_YILI` | (isteğe bağlı) kural modunda yaş sınırı uyarısı için, ör. 1999 |

Bot her gün 09:00 (TR) civarında çalışır; site/API hatasında durum dosyasına dokunmadan hata ile çıkar.

## Bilinen sınırlar

- Bazı ilanlarda kabul edilen bölümler PDF ek tablolarda; bu içerik modele gitmez. Model bu durumda
  "🟡 KONTROL ET" der ve ek linkleri mesajda belirtir.
- "Duyuru" tipindeki ilanların sitede metni yok (sadece dış link); bunlar başlıktan değerlendirilir.
