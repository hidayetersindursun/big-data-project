import time
import pandas as pd
from curl_cffi import requests
from bs4 import BeautifulSoup

def scrape_harman_prices():
    print("Harmanapps.com veri çekme işlemi başlatılıyor... (curl_cffi ile Cloudflare bypass)")
    
    base_url = "https://harmanapps.com/public/hal-borsa-fiyatlari"
    all_data = []
    
    try:
        print("Ana sayfa yükleniyor...")
        response = requests.get(base_url, impersonate="chrome110", timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Şehir linklerini bul
        city_elements = soup.select("a[href*='/hal-borsa-fiyatlari/']")
        cities = []
        for c in city_elements:
            name = c.get_text(strip=True)
            href = c.get("href")
            if name and href and href not in [city['url'] for city in cities]:
                cities.append({"name": name, "url": href})
        
        print(f"Toplam {len(cities)} farklı bölge/şehir bulundu.")

        for city in cities:
            page = 1
            print(f"-> {city['name']} verileri çekiliyor...", end="", flush=True)
            while True:
                url = f"{city['url']}?page={page}"
                res = requests.get(url, impersonate="chrome110", timeout=15)
                page_soup = BeautifulSoup(res.text, "html.parser")
                
                # We need to find the cards.
                # Every card seems to have a price-grid class. The card itself is probably a parent div block.
                price_grids = page_soup.select(".price-grid")
                if not price_grids:
                    break
                
                for grid in price_grids:
                    try:
                        # find the card container
                        card = grid.parent
                        
                        text = card.get_text(separator='\n', strip=True)
                        lines = [l.strip() for l in text.split('\n') if l.strip()]
                        
                        if len(lines) < 3:
                            continue
                        
                        product = lines[0]
                        location = lines[1]
                        
                        min_p = ""
                        max_p = ""
                        date_s = ""
                        
                        for i, line in enumerate(lines):
                            if "En Düşük" in line and (i+1) < len(lines): 
                                val = lines[i+1].split()[0]
                                if "," in val or "." in val or val.isdigit():
                                    min_p = val.replace(",", ".")
                            if "En Yüksek" in line and (i+1) < len(lines): 
                                val = lines[i+1].split()[0]
                                if "," in val or "." in val or val.isdigit():
                                    max_p = val.replace(",", ".")
                            if "." in line and len(line) >= 10: 
                                # usually dates like 10.04.2026
                                # Let's just find something that looks like date if needed, or just take the end
                                if line.count(".") == 2 and len(line.split()[0]) == 10:
                                    date_s = line.split()[0]
                        
                        all_data.append({
                            "Sehir": city['name'], 
                            "Urun": product, 
                            "Konum": location,
                            "En_Dusuk": min_p, 
                            "En_Yuksek": max_p, 
                            "Tarih": date_s
                        })
                    except Exception as e:
                        continue
                
                # Check pagination
                # Looking for active page or next page
                # If we get less than some number of price grids we can also break
                pagination = page_soup.select("nav ul.pagination, div.pagination")
                if not pagination:
                    # just try to guess if we have full cards limit (like 12 or 24 per page)
                    # or break if page > 100 to avoid inf loop
                    if len(price_grids) < 10 or page > 50:
                        break
                    page += 1
                else:
                    # There is pagination logic, check if current page is last
                    sayfa_texts = [p.get_text(strip=True) for p in page_soup.select("span.page-link, a.page-link")]
                    # If there's an anchor with string '›' or something for next
                    next_link = page_soup.select("a[rel='next']")
                    if next_link:
                        page += 1
                    else:
                        break
                        
            print(f" Tamamlandı. (Son Sayfa: {page})")
            
    except Exception as e:
        print(f"\nHata: {e}")
    
    if all_data:
        from datetime import datetime
        today_str = datetime.now().strftime("%d_%m_%Y")
        output_file = f"harman_hal_fiyat_{today_str}.csv"
        df = pd.DataFrame(all_data)
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\nToplam {len(df)} satır veri {output_file} dosyasına kaydedildi.")
    else:
        print("\nVeri çekilemedi.")

if __name__ == "__main__":
    scrape_harman_prices()
