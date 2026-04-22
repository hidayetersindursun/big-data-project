import json
import urllib.request
import urllib.parse
import time
import os
from datetime import datetime

def fetch_fuel_prices():
    # Altın Liste: API'nin kabul ettiği doğrulanmış şehir isimleri
    # Bazıları sadece İngilizce (ISTANBUL), bazıları sadece Türkçe (ŞANLIURFA) karakterle çalışıyor.
    cities_map = {
        "ADANA": "ADANA", "ADIYAMAN": "ADIYAMAN", "AFYONKARAHİSAR": "AFYON", "AĞRI": "AGRI", 
        "AKSARAY": "AKSARAY", "AMASYA": "AMASYA", "ANKARA": "ANKARA", "ANTALYA": "ANTALYA", 
        "ARDAHAN": "ARDAHAN", "ARTVİN": "ARTVIN", "AYDIN": "AYDIN", "BALIKESİR": "BALIKESIR", 
        "BARTIN": "BARTIN", "BATMAN": "BATMAN", "BAYBURT": "BAYBURT", "BİLECİK": "BILECIK", 
        "BİNGÖL": "BINGOL", "BİTLİS": "BITLIS", "BOLU": "BOLU", "BURDUR": "BURDUR", 
        "BURSA": "BURSA", "ÇANAKKALE": "CANAKKALE", "ÇANKIRI": "CANKIRI", "ÇORUM": "CORUM", 
        "DENİZLİ": "DENIZLI", "DİYARBAKIR": "DIYARBAKIR", "DÜZCE": "DUZCE", "EDİRNE": "EDIRNE", 
        "ELAZIĞ": "ELAZIĞ", "ERZİNCAN": "ERZINCAN", "ERZURUM": "ERZURUM", "ESKİŞEHİR": "ESKISEHIR", 
        "GAZİANTEP": "GAZİANTEP", "GİRESUN": "GIRESUN", "GÜMÜŞHANE": "GUMUSHANE", "HAKKARİ": "HAKKARI", 
        "HATAY": "HATAY", "IĞDIR": "IGDIR", "ISPARTA": "ISPARTA", "İSTANBUL": "ISTANBUL", 
        "İZMİR": "IZMIR", "KAHRAMANMARAŞ": "K.MARAS", "KARABÜK": "KARABUK", "KARAMAN": "KARAMAN", 
        "KARS": "KARS", "KASTAMONU": "KASTAMONU", "KAYSERİ": "KAYSERI", "KIRIKKALE": "KIRIKKALE", 
        "KIRKLARELİ": "KIRKLARELI", "KIRŞEHİR": "KIRSEHIR", "KİLİS": "KILIS", "KOCAELİ": "KOCAELI", 
        "KONYA": "KONYA", "KÜTAHYA": "KUTAHYA", "MALATYA": "MALATYA", "MANİSA": "MANISA", 
        "MARDİN": "MARDİN", "MERSİN": "İÇEL", "MUĞLA": "MUGLA", "MUŞ": "MUS", 
        "NEVŞEHİR": "NEVSEHIR", "NİĞDE": "NİĞDE", "ORDU": "ORDU", "OSMANİYE": "OSMANIYE", 
        "RİZE": "RIZE", "SAKARYA": "SAKARYA", "SAMSUN": "SAMSUN", "SİİRT": "SIIRT", 
        "SİNOP": "SİNOP", "SİVAS": "SIVAS", "ŞANLIURFA": "ŞANLIURFA", "ŞIRNAK": "SIRNAK", 
        "TEKİRDAĞ": "TEKIRDAG", "TOKAT": "TOKAT", "TRABZON": "TRABZON", "TUNCELİ": "TUNCELI", 
        "UŞAK": "USAK", "VAN": "VAN", "YALOVA": "YALOVA", "YOZGAT": "YOZGAT", "ZONGULDAK": "ZONGULDAK"
    }

    all_data = {}
    
    print(f"Toplam {len(cities_map)} şehir için veri çekilmeye başlanıyor...")

    for display_name, api_name in cities_map.items():
        try:
            # URL encoding for Turkish characters
            encoded_city = urllib.parse.quote(api_name)
            api_url = f"http://hasanadiguzel.com.tr/api/akaryakit/sehir={encoded_city}"
            
            print(f"Veri çekiliyor: {display_name} ({api_name})...", end="\r")
            
            with urllib.request.urlopen(api_url, timeout=10) as response:
                result = response.read().decode('utf-8')
                data = json.loads(result)
                
                if "data" in data:
                    all_data[display_name] = data["data"]
                else:
                    print(f"\n[UYARI] {display_name} için veri formatı beklenenden farklı.")
            
            # Rate limiting
            time.sleep(0.2)
            
        except Exception as e:
            print(f"\n[HATA] {display_name} verisi çekilemedi: {e}")

    # Output path with date - script ile aynı dizine kaydedilir
    current_date = datetime.now().strftime("%Y_%m_%d")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, f"akaryakit_fiyatlari_{current_date}.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
    
    print(f"\nİşlem tamamlandı. Veriler '{output_file}' dosyasına kaydedildi.")
    print(f"Toplam çekilen şehir sayısı: {len(all_data)}")

if __name__ == "__main__":
    fetch_fuel_prices()
