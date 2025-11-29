# 🚀 Kariyer Kapısı İlan Takip Botu

Bu proje, **[kariyerkapisi.gov.tr/isealim](https://kariyerkapisi.gov.tr/isealim)** adresini simüle edilmiş bir tarayıcı (Playwright) ile ziyaret eder, dinamik olarak yüklenen kamu iş ilanlarını tarar ve yeni ilanları **Telegram** üzerinden bildirir.

Bot, JavaScript ile yüklenen içerikleri ve açılır pencereleri (popup) otomatik olarak yönetebilecek yetenekte tasarlanmıştır.

## 🌟 Özellikler

- **Dinamik Tarama:** JavaScript tabanlı site içeriğini Playwright ile sorunsuz işler.
- **Popup Savar:** Site açılışındaki duyuru/popup ekranlarını otomatik kapatır.
- **Akıllı Başlık Analizi:** Karmaşık HTML yapısı içinden Kurum ve İlan Başlığını en doğru şekilde ayrıştırır.
- **Risk Modu:** Site erişim hatası olursa hafızayı temizler, böylece site düzeldiğinde hiçbir ilanın kaçırılmamasını sağlar (Mükerrer gönderim pahasına veri kaybını önler).
- **Git Scraping:** Geçmiş verileri `active_jobs.json` dosyasında tutar.
- **GitHub Actions:** Sunucusuz (Serverless) olarak her gün otomatik çalışır.

---

## 📦 Gereksinimler

Proje `Playwright` kütüphanesi üzerine kuruludur.

**`requirements.txt` içeriği:**
```text
playwright
requests
python-dotenv

## 🔧 Kurulum (Yerel Bilgisayar)

Botu kendi bilgisayarınızda çalıştırmak veya test etmek için aşağıdaki adımları izleyin:

1. **Depoyu Klonlayın:**
   ```bash
   git clone https://github.com/erkinavcii/KariyerKapisiBot.git
   cd KariyerKapisiBot

2.**Gerekli Paketleri Yükleyin:**
```Bash
   pip install -r requirements.txt
3.**Tarayıcı Motorunu İndirin (Önemli): Playwright'ın çalışması için gerekli Chromium tarayıcısını kurun:
    playwright install chromium
4.**.env Dosyasını Oluşturun: Proje ana dizininde .env adında bir dosya oluşturun ve bilgilerinizi girin:
    TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
    TELEGRAM_CHAT_ID=123456789      
5.**Botu Çalıştırın:
    python main.py    
 ## GitHub Actions KurulumuBotun bilgisayarınız kapalıyken bile her sabah otomatik çalışması için:Bu projeyi GitHub hesabınıza yükleyin (Push).GitHub reponuzda Settings > Secrets and variables > Actions menüsüne gidin."New repository secret" butonuna tıklayarak aşağıdaki 2 değişkeni ekleyin:Secret Adı Açıklama TELEGRAM_BOT_TOKEN **BotFather'dan aldığınız token.TELEGRAM_CHAT_ID Mesajın geleceği kişinin ID'si.
 **Not: Bot her sabah Türkiye saatiyle 09:00 civarında otomatik çalışacaktır.