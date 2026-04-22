BASE_API_URL = "https://api.marketfiyati.org.tr/api/v2"
HARITA_API_URL = "https://harita.marketfiyati.org.tr/Service/api/v1"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

COMMON_HEADERS = {
    "Referer": "https://marketfiyati.org.tr/",
    "Origin": "https://marketfiyati.org.tr",
}

PAGE_SIZE = 25               # API hard limit per page
DEPOT_RADIUS_KM = 1          # Radius to search for nearby depots
STALE_HOURS = 24             # Hours before a (location, category) pair is re-scraped
PAGE_DELAY = (0.3, 0.8)      # Random range (seconds) between paginated requests
CATEGORY_DELAY = (1.0, 2.0)  # Random range (seconds) between categories (sequential fallback)

# ---------------------------------------------------------------------------
# Cities and their districts (ilçeler)
# To add a new city, just add an entry here — no other file needs changing.
# ---------------------------------------------------------------------------
CITIES = {
    "İstanbul": [
        "Adalar", "Arnavutköy", "Ataşehir", "Avcılar", "Bağcılar",
        "Bahçelievler", "Bakırköy", "Başakşehir", "Bayrampaşa", "Beşiktaş",
        "Beykoz", "Beylikdüzü", "Beyoğlu", "Büyükçekmece", "Çatalca",
        "Çekmeköy", "Esenler", "Esenyurt", "Eyüpsultan", "Fatih",
        "Gaziosmanpaşa", "Güngören", "Kadıköy", "Kağıthane", "Kartal",
        "Küçükçekmece", "Maltepe", "Pendik", "Sancaktepe", "Sarıyer",
        "Şile", "Şişli", "Silivri", "Sultanbeyli", "Sultangazi",
        "Tuzla", "Ümraniye", "Üsküdar", "Zeytinburnu",
    ],
    "İzmir": [
        "Aliağa", "Balçova", "Bayındır", "Bayraklı", "Bergama",
        "Beydağ", "Bornova", "Buca", "Çeşme", "Çiğli",
        "Dikili", "Foça", "Gaziemir", "Güzelbahçe", "Karabağlar",
        "Karaburun", "Karşıyaka", "Kemalpaşa", "Kınık", "Kiraz",
        "Konak", "Menderes", "Menemen", "Narlıdere", "Ödemiş",
        "Seferihisar", "Selçuk", "Tire", "Torbalı", "Urla",
    ],
    "Adana": [
        "Aladağ", "Ceyhan", "Çukurova", "Feke", "İmamoğlu",
        "Karaisalı", "Karataş", "Kozan", "Pozantı", "Saimbeyli",
        "Sarıçam", "Seyhan", "Tufanbeyli", "Yumurtalık", "Yüreğir",
    ],
    "Antalya": [
        "Akseki", "Aksu", "Alanya", "Demre", "Döşemealtı",
        "Elmalı", "Finike", "Gazipaşa", "Gündoğmuş", "İbradı",
        "Kaş", "Kemer", "Kepez", "Konyaaltı", "Korkuteli",
        "Kumluca", "Manavgat", "Muratpaşa", "Serik",
    ],
    "Balıkesir": [
        "Altıeylül", "Ayvalık", "Balya", "Bandırma", "Bigadiç",
        "Burhaniye", "Dursunbey", "Edremit", "Erdek", "Gömeç",
        "Gönen", "Havran", "İvrindi", "Karesi", "Kepsut",
        "Manyas", "Marmara", "Savaştepe", "Sındırgı", "Susurluk",
    ],
    "Ankara": [
        "Akyurt", "Altındağ", "Ayaş", "Bala", "Beypazarı",
        "Çamlıdere", "Çankaya", "Çubuk", "Elmadağ", "Etimesgut",
        "Evren", "Gölbaşı", "Güdül", "Haymana", "Kalecik",
        "Kahramankazan", "Keçiören", "Kızılcahamam", "Mamak", "Nallıhan",
        "Polatlı", "Pursaklar", "Sincan", "Şereflikoçhisar", "Yenimahalle",
    ],
    "Gaziantep": [
        "Araban", "İslahiye", "Karkamış", "Nizip", "Nurdağı",
        "Oğuzeli", "Şahinbey", "Şehitkamil", "Yavuzeli",
    ],
    "Samsun": [
        "Alaçam", "Asarcık", "Atakum", "Ayvacık", "Bafra",
        "Canik", "Çarşamba", "Havza", "İlkadım", "Kavak",
        "Ladik", "Ondokuzmayıs", "Salıpazarı", "Tekkeköy",
        "Terme", "Vezirköprü", "Yakakent",
    ],
    "Manisa": [
        "Ahmetli", "Akhisar", "Alaşehir", "Demirci", "Gölmarmara",
        "Gördes", "Kırkağaç", "Köprübaşı", "Kula", "Salihli",
        "Sarıgöl", "Saruhanlı", "Selendi", "Soma", "Şehzadeler",
        "Turgutlu", "Yunusemre",
    ],
    "Mersin": [
        "Akdeniz", "Anamur", "Aydıncık", "Bozyazı", "Çamlıyayla",
        "Erdemli", "Gülnar", "Mezitli", "Mut", "Silifke",
        "Tarsus", "Toroslar", "Yenişehir",
    ],
    "Trabzon": [
        "Akçaabat", "Araklı", "Arsin", "Beşikdüzü", "Çarşıbaşı",
        "Çaykara", "Dernekpazarı", "Düzköy", "Hayrat", "Köprübaşı",
        "Maçka", "Of", "Ortahisar", "Şalpazarı", "Sürmene",
        "Tonya", "Vakfıkebir", "Yomra",
    ],
}

CATEGORIES = [
    "Meyve",
    "Sebze",
    "Süt Ürünleri ve Kahvaltılık",
    "Et",        # Şarküteri, Beyaz Et, Kırmızı Et, Deniz Ürünleri dahil
    "İçecek",
    "Temizlik",
    "Kişisel Bakım",
]
