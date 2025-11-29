import json
import os
import time
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime
from dotenv import load_dotenv

# --- AYARLAR ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") # .env içinde bu isimle olsun
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
JSON_FILE = "active_jobs.json"
# Hedef URL artık mecburen ana sayfa
URL = "https://kariyerkapisi.gov.tr/isealim" 

# --------------------------------------------------
# Telegram Fonksiyonu
# --------------------------------------------------
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Token eksik, mesaj atılmadı.")
        return
    
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
    except Exception as e:
        print(f"Telegram Hatası: {e}")

# --------------------------------------------------
# JSON İşlemleri
# --------------------------------------------------
def load_saved_jobs():
    if not os.path.exists(JSON_FILE):
        return [] # Liste olarak döndür
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_current_jobs(jobs_list):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs_list, f, ensure_ascii=False, indent=2)

# --------------------------------------------------
# ANA SCRAPER (PLAYWRIGHT)
# --------------------------------------------------
def check_jobs():
    print(f"👀 {URL} taranıyor (Playwright Mode)...")
    
    # Eskileri yükle
    saved_jobs = load_saved_jobs()
    print(f"💾 Kayıtlı İlan Sayısı: {len(saved_jobs)}")
    
    current_jobs = []
    
    with sync_playwright() as p:
        # GitHub Actions'ta çalışması için headless=True ŞART
        browser = p.chromium.launch(headless=True) 
        
        # SSL hatalarını yoksay (ignore_https_errors)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True 
        )
        page = context.new_page()
        
        try:
            page.goto(URL, timeout=60000) 
            
            # --- POPUP SAVAR ---
            time.sleep(4) # Sayfa kendine gelsin
            page.keyboard.press("Escape")
            try:
                # X butonunu dener
                if page.locator("xpath=/html/body/div[1]/div/div[1]/button").is_visible(timeout=2000):
                    page.locator("xpath=/html/body/div[1]/div/div[1]/button").click()
                else:
                    # Boşluğa tıklar
                    page.mouse.click(10, 10)
            except: pass
            time.sleep(2)

            # --- İLANLARI TOPLA ---
            # Sadece 'IlanDetay' linki olan butonları bul
            job_buttons = page.locator("a[href*='IlanDetay']").all()
            print(f"✅ Sitede Bulunan İlan: {len(job_buttons)}")
            
            for btn in job_buttons:
                try:
                    href = btn.get_attribute("href")
                    if not href or "i=" not in href: continue
                    
                    full_link = f"https://kariyerkapisi.gov.tr/{href}"
                    
                    # İçeriği Analiz Et (Akıllı Parsing)
                    # Butonun bulunduğu satırı (Grandparent) al
                    row = btn.locator("xpath=../..")
                    full_text = row.inner_text()
                    
                    # Satırları temizle
                    lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 2]
                    
                    if not lines: continue

                    # 1. Kurum (Genelde ilk satır)
                    kurum = lines[0]
                    
                    # 2. Başlık (En uzun satır stratejisi)
                    possible_titles = [l for l in lines if "İlana Git" not in l and "İlan" not in l[:5]]
                    baslik = max(possible_titles, key=len) if possible_titles else (lines[1] if len(lines)>1 else "Başlık Yok")

                    # Listeye ekle
                    current_jobs.append({
                        "url": full_link, # Eşsiz anahtar
                        "kurum": kurum,
                        "baslik": baslik,
                        "date": datetime.now().strftime("%Y-%m-%d") # Sitede tarih parsing zor ise bugünü at
                    })
                        
                except Exception:
                    continue

        except Exception as e:
            print(f"❌ Kritik Hata: {e}")
            # Hata varsa boş liste dönecek, bu da aşağıda kaydı sıfırlayacak (İstediğin Risk Modu)
            current_jobs = [] 
        finally:
            browser.close()

    # --- KARŞILAŞTIRMA (URL Bazlı Diff) ---
    saved_urls = {job["url"] for job in saved_jobs}
    
    new_items = []
    for job in current_jobs:
        if job["url"] not in saved_urls:
            new_items.append(job)

    # --- BİLDİRİM ---
    if new_items:
        print(f"📢 {len(new_items)} yeni ilan bulundu!")
        
        batch_size = 10
        for i in range(0, len(new_items), batch_size):
            batch = new_items[i : i + batch_size]
            msg = f"📢 <b>YENİ İLAN RAPORU ({i+1} - {i+len(batch)})</b>\n\n"
            for job in batch:
                msg += f"🏢 <b>{job['kurum']}</b>\n"
                msg += f"💼 {job['baslik']}\n"
                msg += f"🔗 <a href='{job['url']}'>İlana Git</a>\n"
                msg += "-------------------------\n"
            
            send_telegram_message(msg)
            time.sleep(1)
    else:
        print("💤 Yeni ilan yok.")

    # --- KAYDETME (RİSK MODU) ---
    # Liste boş olsa bile kaydet. Bir sonraki çalışmada her şeyi yeni sanacak.
    save_current_jobs(current_jobs)
    print("✔ JSON güncellendi.")

if __name__ == "__main__":
    check_jobs()