Kariyer Kapısı İlan Takip Botu

Bu proje, kariyerkapisi.gov.tr üzerinde yayınlanan kamu iş ilanlarını otomatik olarak kontrol eder ve yeni ilanları tespit ettiğinde Telegram üzerinden bildirim gönderir.

Proje tamamen Python ile yazılmıştır ve günlük otomatik tarama için GitHub Actions'a uygundur.

🚀 Özellikler

Kariyer Kapısı ilanlarını otomatik olarak çeker

Daha önce gönderilen ilanları database.json içinde tutar

Yeni ilan gördüğünde Telegram’a ileti gönderir

Aynı ilanı ikinci kez asla göndermez

Tamamen ücretsiz ve API kullanmaz

GitHub Actions ile dakikada/günde/ayda bir otomatik çalışabilir

📦 Gereksinimler

Aşağıdaki paketler gereklidir:

httpx
bs4
python-dotenv


Kurmak için:

pip install -r requirements.txt

🔧 Kurulum
1) Depoyu klonla
git clone https://github.com/kullaniciadi/kariyer-kapisi-bot.git
cd kariyer-kapisi-bot

2) .env dosyası oluştur
TELEGRAM_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

3) Botu çalıştır
python bot.py

📲 Telegram Bot Kurulum Adımları

Bu botun bildirim gönderebilmesi için bir Telegram Bot Token ve Chat ID’ye ihtiyacınız vardır.
Aşağıdaki adımları takip ederek dakikalar içinde oluşturabilirsiniz.

1) Telegram’da Bot Oluştur

Telegram’da @BotFather aratın

/start yazın

Yeni bot oluşturmak için:

/newbot


Botunuza bir isim verin

Kullanıcı adı verin (bot sonunda “bot” olmalı — örn: kapisiNotifierBot)

BotFather size şöyle bir token verecektir:

1234567890:AAAbbbCCCdddEEE111222


Bu token’i .env dosyasına yazacaksınız:

TELEGRAM_TOKEN=1234567890:AAAbbbCCCdddEEE111222

2) Chat ID Nasıl Alınır? (En Kolay Yöntem)
Yöntem A — Kullanıcı Chat ID (En hızlı)

Botunuzla bir konuşma açın ve /start yazın.

Sonra tarayıcıda bu URL’ye gidin:

https://api.telegram.org/bot<TELEGRAM_TOKEN>/getUpdates


Örnek:

https://api.telegram.org/bot1234567890:AAAbbbCCCdddEEE111222/getUpdates


Dönen JSON içinde:

"chat":{"id":123456789}


Bu sayıyı .env içine yazın:

TELEGRAM_CHAT_ID=123456789

3) Test Et

Terminalde:

python bot.py


Bot doğru kurulmuşsa Telegram’a bir test mesajı gelir:

Bot başlatıldı.


📁 Dosya Yapısı
/
|-- bot.py
|-- database.json
|-- requirements.txt
|-- README.md

🔄 Nasıl Çalışıyor?

bot.py siteyi tarar

database.json içindeki son gönderilen ilanlara bakar

Yeni ilan varsa → Telegram gönderir

Yeni ilanlar veritabanına eklenir

🤖 GitHub Actions (Opsiyonel)

Proje, GitHub Actions ile otomatik çalışmaya uygundur.
