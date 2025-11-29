import sqlite3
import requests
import os
import time
from playwright.sync_api import sync_playwright
from datetime import datetime
from dotenv import load_dotenv

# --- ENV YÜKLEME ---
load_dotenv()

# --- AYARLAR ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DB_NAME = os.getenv("DB_NAME", "kariyer_kapisi.db")
URL = os.getenv("TARGET_URL", "https://kariyerkapisi.gov.tr/isealim")

# --- VERİTABANI İŞLEMLERİ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id TEXT PRIMARY KEY, raw_text TEXT, first_seen TEXT)''')
    conn.commit()
    conn.close()

def is_job_exist(job_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def save_job(job_id, raw_text):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO jobs VALUES (?, ?, ?)", (job_id, raw_text, date_now))
    conn.commit()
    conn.close()

# --- TELEGRAM BİLDİRİM ---
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"Mesaj (Token Yok): {message[:50]}...")
        return
    
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
        if response.status_code != 200:
            print(f"Telegram Hatası: {response.text}")
    except Exception as e:
        print(f"Telegram Bağlantı Hatası: {e}")

# --- ANA SCRAPER ---
def check_jobs():
    print(f"👀 {URL} taranıyor...")
    
    new_jobs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # İzlemek için False, sonra True yapabilirsin
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(URL, timeout=60000) 
            
            # --- POPUP TEMİZLİK ---
            print("🛡️ Popup kontrolü...")
            time.sleep(3)
            page.keyboard.press("Escape")
            try:
                close_xpath = "xpath=/html/body/div[1]/div/div[1]/button"
                if page.locator(close_xpath).is_visible(timeout=2000):
                    page.locator(close_xpath).click()
                else:
                    page.mouse.click(10, 10)
            except: pass
            
            time.sleep(2)

            # --- TARAMA ---
            print("🔍 İlanlar analiz ediliyor...")
            job_buttons = page.locator("a[href*='IlanDetay']").all()
            print(f"✅ Toplam {len(job_buttons)} ilan bulundu.")
            
            for btn in job_buttons:
                try:
                    href = btn.get_attribute("href")
                    if not href or "i=" not in href: continue
                    
                    job_id = href.split("i=")[1]
                    full_link = f"https://kariyerkapisi.gov.tr/{href}"
                    
                    if not is_job_exist(job_id):
                        # Parent elementten metni al
                        parent = btn.locator("xpath=../..")
                        raw_text = parent.inner_text().replace("\n", "|").strip()
                        
                        # --- METİN AYRIŞTIRMA (PARSING) ---
                        # Metni '|' işaretlerinden böl ve boşlukları temizle
                        # Örnek: "TÜBİTAK | UZMAN YRD | 2025" -> ["TÜBİTAK", "UZMAN YRD", "2025"]
                        parts = [part.strip() for part in raw_text.split('|') if part.strip()]
                        
                        kurum_adi = parts[0] if len(parts) > 0 else "Bilinmiyor"
                        ilan_basligi = parts[1] if len(parts) > 1 else raw_text
                        
                        # Bazen tarih de araya karışabilir, ama genelde ilk 2 parça yeterlidir.
                        
                        print(f"🆕 EKLENDİ: {kurum_adi} - {ilan_basligi[:30]}...")
                        
                        save_job(job_id, raw_text)
                        new_jobs.append({
                            "kurum": kurum_adi,
                            "baslik": ilan_basligi,
                            "link": full_link
                        })
                        
                except Exception as inner_e:
                    print(f"İlan hatası: {inner_e}")
                    continue

        except Exception as e:
            print(f"❌ Kritik Hata: {e}")
            
        finally:
            browser.close()

    # --- RAPORLAMA (Batch Sending) ---
    if new_jobs:
        print(f"📢 Toplam {len(new_jobs)} yeni ilan raporlanıyor...")
        
        # Telegram'ın mesaj limiti ~4000 karakterdir.
        # Bu yüzden ilanları 10'arlı gruplar (paketler) halinde göndereceğiz.
        batch_size = 10
        
        for i in range(0, len(new_jobs), batch_size):
            batch = new_jobs[i : i + batch_size]
            
            msg = f"📢 <b>YENİ İLAN RAPORU ({i+1} - {i+len(batch)})</b>\n\n"
            
            for job in batch:
                msg += f"🏢 <b>{job['kurum']}</b>\n"
                msg += f"💼 {job['baslik']}\n"
                msg += f"🔗 <a href='{job['link']}'>İlana Git</a>\n"
                msg += "-------------------------\n"
            
            send_telegram_message(msg)
            time.sleep(1) # Mesajlar arası 1 sn bekle (Telegram engellemesin)
            
    else:
        print("Yeni ilan yok.")

if __name__ == "__main__":
    init_db()
    check_jobs()