# 🚀 Kariyer Kapısı İlan Takip Botu

Bu proje, **[kariyerkapisi.gov.tr](https://kariyerkapisi.gov.tr/isealim)** üzerinde yayınlanan kamu iş ilanlarını otomatik olarak takip eden, yeni bir ilan tespit ettiğinde detaylı analiz yaparak **Telegram** üzerinden anlık bildirim gönderen açık kaynaklı bir bottur.

Proje, modern web kazıma (scraping) teknolojileri kullanılarak Python ile geliştirilmiştir ve **GitHub Actions** entegrasyonu sayesinde hiçbir sunucu maliyeti olmadan kendi kendine çalışabilir.

## 🌟 Özellikler

- **Akıllı Tarama:** JavaScript tabanlı dinamik site içeriğini (Playwright ile) sorunsuz tarar.
- **Detaylı Analiz:** İlan başlıklarını ve kurum isimlerini HTML yapısından akıllıca ayrıştırır.
- **Hafıza Sistemi:** Gönderilen ilanları `active_jobs.json` dosyasında tutar, aynı ilanı asla tekrar göndermez.
- **Git Scraping:** Veritabanını GitHub üzerinde güncelleyerek veri kaybını önler.
- **Sıfır Maliyet:** Sunucu gerektirmez, GitHub Actions üzerinde ücretsiz çalışır.

---

## 📦 Gereksinimler

Projenin çalışması için aşağıdaki Python kütüphaneleri gereklidir:

- `playwright` (Tarayıcı otomasyonu için)
- `requests` (API istekleri için)
- `python-dotenv` (Çevresel değişkenler için)

**`requirements.txt` içeriği:**
```text
playwright
requests
python-dotenv**
🔧 Kurulum (Yerel Bilgisayar)Botu kendi bilgisayarınızda test etmek veya çalıştırmak için:1. Depoyu KlonlayınBashgit clone [https://github.com/KULLANICI_ADINIZ/kariyer-kapisi-bot.git](https://github.com/KULLANICI_ADINIZ/kariyer-kapisi-bot.git)
cd kariyer-kapisi-bot
2. Gerekli Paketleri YükleyinBashpip install -r requirements.txt
3. Tarayıcı Motorunu KurunBotun çalışması için gerekli olan Chromium tarayıcısını indirin:Bashplaywright install chromium
4. .env Dosyasını OluşturunProje ana dizininde .env adında bir dosya oluşturun ve içine Telegram bilgilerinizi girin:Ini, TOMLTELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=123456789
TARGET_URL=[https://kariyerkapisi.gov.tr/isealim](https://kariyerkapisi.gov.tr/isealim)
5. Botu ÇalıştırınBashpython kariyerkapisibot.py
##📲 Telegram Bot Kurulumu
Bildirim alabilmek için kendi botunuzu oluşturmanız gerekir. Bu işlem 1 dakika sürer:Bot Oluşturma:Telegram'da @BotFather kullanıcısını bulun./newbot komutunu gönderin.Botunuza bir isim ve kullanıcı adı verin.Size verilen API Token'ı kopyalayın (Örn: 123456:ABC-DEF...).Chat ID Öğrenme:Oluşturduğunuz bota Telegram'dan bir "Merhaba" mesajı atın.Tarayıcınızdan şu adrese gidin: https://api.telegram.org/bot<TOKENINIZ>/getUpdatesÇıkan sayfada "chat": {"id": 123456789} kısmındaki sayıyı alın.
##🤖 GitHub Actions ile Otomatik Çalıştırma
Bilgisayarınızı açık tutmaya gerek kalmadan, botun her gün otomatik çalışması için:Bu projeyi kendi GitHub hesabınıza Push'layın.GitHub'da reponuzun Settings > Secrets and variables > Actions sekmesine gidin.New repository secret butonuna tıklayarak aşağıdaki 4 değişkeni ekleyin:Secret AdıDeğer (Örnek)TELEGRAM_BOT_TOKEN123456:ABC-DEF...TELEGRAM_CHAT_ID987654321TARGET_URLhttps://kariyerkapisi.gov.tr/isealimDB_NAMEactive_jobs.jsonActions sekmesine gidin, sol taraftaki workflow'un çalıştığını (veya belirtilen saatte çalışacağını) kontrol edin. Bot her sabah 09:00'da (veya ayarladığınız saatte) çalışacaktır.
##📁 Dosya Yapısı/
|-- .github/workflows/
|   |-- daily_bot.yml      # GitHub Actions zamanlayıcısı
|-- kariyerkapisibot.py    # Ana bot kodları
|-- active_jobs.json       # İlan veritabanı (Otomatik oluşur)
|-- requirements.txt       # Kütüphane listesi
|-- .gitignore             # Gizli dosyalar
|-- README.md              # Dokümantasyon

##⚠️ Yasal UyarıBu proje eğitim ve kişisel kullanım amaçlı geliştirilmiştir. kariyerkapisi.gov.tr sitesine aşırı istek göndermekten kaçının. Varsayılan ayarlar siteye zarar vermeyecek şekilde (günde 1 kez) yapılandırılmıştır.