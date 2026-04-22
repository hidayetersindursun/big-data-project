import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
import time
from datetime import datetime

def scrape_hal_fiyatlari():
    url = "https://tarim.ibb.istanbul/tr/istatistik/124/hal-fiyatlari.html"
    
    # Chrome ayarları (headless mod isteğe bağlıdır)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") 
    options.add_argument("--log-level=3") # Sadece hataları göster
    
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    wait = WebDriverWait(driver, 10)

    all_data = []
    categories = ["Meyve", "Sebze", "İthal Ürünler"]
    
    for cat in categories:
        print(f"Kategori çekiliyor: {cat}")
        try:
            # Kategori seçimi
            select_elem = wait.until(EC.presence_of_element_located((By.ID, "cbGunlukKategori")))
            select = Select(select_elem)
            select.select_by_visible_text(cat)
            
            # 'Göster' butonuna tıklama
            show_btn = driver.find_element(By.ID, "btnGunlukGoster")
            show_btn.click()
            
            # Tablonun güncellenmesi için bekleme
            time.sleep(3) 
            
            # Satırları okuma
            rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 4:
                    all_data.append({
                        "Kategori": cat,
                        "Urun Adı": cols[0].text.strip(),
                        "Birim": cols[1].text.strip(),
                        "En Düşük Fiyat": cols[2].text.strip().replace(" TL", "").replace(",", "."),
                        "En Yüksek Fiyat": cols[3].text.strip().replace(" TL", "").replace(",", "."),
                        "Tarih": datetime.now().strftime("%d.%m.%Y")
                    })
        except Exception as e:
            print(f"Hata ({cat}): {e}")

    if all_data:
        df = pd.DataFrame(all_data)
        today_str = datetime.now().strftime("%d_%m_%Y")
        output_file = f"istanbul_hal_fiyat_{today_str}.csv"
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"CSV başarıyla kaydedildi: {output_file}. Toplam {len(df)} satır.")
    else:
        print("Veri bulunamadı.")
    
    driver.quit()

if __name__ == "__main__":
    scrape_hal_fiyatlari()
