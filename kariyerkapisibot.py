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

# --- VERİTABANI ---
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

# --- TELEGRAM ---
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
    except Exception as e:
        print(f"Telegram Hatası: {e}")

# --- ANA SCRAPER ---
def check_jobs():
    print(f"👀 {URL} taranıyor...")
    
    new_jobs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(URL, timeout=60000) 
            
            # --- POPUP ---
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

            print("🔍 İlanlar analiz ediliyor (Akıllı Ayrıştırma)...")
            job_buttons = page.locator("a[href*='IlanDetay']").all()
            print(f"✅ Toplam {len(job_buttons)} ilan bulundu.")
            
            for btn in job_buttons:
                try:
                    href = btn.get_attribute("href")
                    if not href or "i=" not in href: continue
                    
                    job_id = href.split("i=")[1]
                    full_link = f"https://kariyerkapisi.gov.tr/{href}"
                    
                    if not is_job_exist(job_id):
                        # --- STRATEJİ: SATIRIN TAMAMINI OKU VE ANALİZ ET ---
                        # Butonun dedesine (Row) çık ve tüm metni al
                        row_element = btn.locator("xpath=../..")
                        full_text = row_element.inner_text()
                        
                        # Metni satır satır böl ve boşlukları temizle
                        lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 2]
                        
                        kurum_adi = "Belirsiz Kurum"
                        ilan_basligi = "Başlık Bulunamadı"

                        if lines:
                            # 1. KURUM BULMA:
                            # Genelde listenin ilk elemanıdır.
                            kurum_adi = lines[0]
                            
                            # 2. BAŞLIK BULMA (EN UZUN SATIR STRATEJİSİ):
                            # İlan başlığı her zaman "İlana Git" veya tarihten daha uzundur.
                            # İçinde 'İlana Git' geçmeyen en uzun satırı buluyoruz.
                            possible_titles = [l for l in lines if "İlana Git" not in l and "İlan" not in l[:5]]
                            
                            if possible_titles:
                                # En uzun metni başlık olarak seç
                                ilan_basligi = max(possible_titles, key=len)
                            else:
                                # Bulamazsa 2. satırı al (Varsa)
                                if len(lines) > 1: ilan_basligi = lines[1]
                        
                        # Loglama
                        print(f"🆕 {kurum_adi} -> {ilan_basligi[:40]}...")
                        
                        save_job(job_id, ilan_basligi)
                        new_jobs.append({
                            "kurum": kurum_adi,
                            "baslik": ilan_basligi,
                            "link": full_link
                        })
                        
                except Exception as inner_e:
                    print(f"İlan hatası: {inner_e}")
                    continue

        except Exception as e:
            print(f"Genel Hata: {e}")
        finally:
            browser.close()

    # --- RAPORLAMA ---
    if new_jobs:
        print(f"📢 {len(new_jobs)} ilan raporlanıyor...")
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
            time.sleep(1)
    else:
        print("Yeni ilan yok.")

if __name__ == "__main__":
    init_db()
    check_jobs()