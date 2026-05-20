"""
Şehir adı normalizer — market ve hal'daki şehir kolonlarını ortak biçime getirir.

S3 inspection (2026-05-20):
  bronze/market._city  -> "İstanbul", "İzmir", "Konya", ...    (Title Case, TR karakter)
  bronze/hal_all.sehir -> "Adana", "Adıyaman", "Ankara", ...   (Title Case, TR karakter)

İkisi de aynı görünüyor ama Adana market/Adana hal'da default değer / boşluk vs durumlarına karşı
defensive bir normalizer şart. Bazı kaynak dosyalarda "ISTANBUL" upper-case veya "Istanbul" latinized
gelebilir; aşağıdaki map ile her durumda standart "İstanbul" formatına çevrilir.
"""

from pyspark.sql import Column
from pyspark.sql import functions as F

# Latinize -> resmi TR Title Case eşleştirme (81 il)
_CANONICAL = {
    "adana": "Adana", "adiyaman": "Adıyaman", "afyonkarahisar": "Afyonkarahisar", "afyon": "Afyonkarahisar",
    "agri": "Ağrı", "aksaray": "Aksaray", "amasya": "Amasya", "ankara": "Ankara", "antalya": "Antalya",
    "ardahan": "Ardahan", "artvin": "Artvin", "aydin": "Aydın", "balikesir": "Balıkesir",
    "bartin": "Bartın", "batman": "Batman", "bayburt": "Bayburt", "bilecik": "Bilecik",
    "bingol": "Bingöl", "bitlis": "Bitlis", "bolu": "Bolu", "burdur": "Burdur",
    "bursa": "Bursa", "canakkale": "Çanakkale", "cankiri": "Çankırı", "corum": "Çorum",
    "denizli": "Denizli", "diyarbakir": "Diyarbakır", "duzce": "Düzce", "edirne": "Edirne",
    "elazig": "Elazığ", "erzincan": "Erzincan", "erzurum": "Erzurum", "eskisehir": "Eskişehir",
    "gaziantep": "Gaziantep", "giresun": "Giresun", "gumushane": "Gümüşhane", "hakkari": "Hakkâri",
    "hatay": "Hatay", "igdir": "Iğdır", "isparta": "Isparta", "istanbul": "İstanbul",
    "izmir": "İzmir", "kahramanmaras": "Kahramanmaraş", "k.maras": "Kahramanmaraş",
    "karabuk": "Karabük", "karaman": "Karaman", "kars": "Kars", "kastamonu": "Kastamonu",
    "kayseri": "Kayseri", "kirikkale": "Kırıkkale", "kirklareli": "Kırklareli",
    "kirsehir": "Kırşehir", "kilis": "Kilis", "kocaeli": "Kocaeli", "konya": "Konya",
    "kutahya": "Kütahya", "malatya": "Malatya", "manisa": "Manisa", "mardin": "Mardin",
    "mersin": "Mersin", "icel": "Mersin", "mugla": "Muğla", "mus": "Muş",
    "nevsehir": "Nevşehir", "nigde": "Niğde", "ordu": "Ordu", "osmaniye": "Osmaniye",
    "rize": "Rize", "sakarya": "Sakarya", "samsun": "Samsun", "siirt": "Siirt",
    "sinop": "Sinop", "sivas": "Sivas", "sanliurfa": "Şanlıurfa", "urfa": "Şanlıurfa",
    "sirnak": "Şırnak", "tekirdag": "Tekirdağ", "tokat": "Tokat", "trabzon": "Trabzon",
    "tunceli": "Tunceli", "usak": "Uşak", "van": "Van", "yalova": "Yalova",
    "yozgat": "Yozgat", "zonguldak": "Zonguldak",
}


def latinize_expr(col: Column) -> Column:
    """TR karakterleri ascii'ye çevir (lookup için)."""
    return F.lower(
        F.translate(col, "ÇĞİıÖŞÜçğöşü", "CGIIOSUcgiosu")
    )


def normalize_city_expr(col: Column) -> Column:
    """
    Bir city kolonunu standart Türkçe Title Case'e çevir.
    Önce trim+latinize, sonra map'ten lookup; bilinmeyenler initcap(lower(col)) ile fallback.
    """
    key = latinize_expr(F.trim(col))
    mapping_expr = F.create_map(*[lit for kv in _CANONICAL.items()
                                  for lit in (F.lit(kv[0]), F.lit(kv[1]))])
    return F.coalesce(mapping_expr.getItem(key), F.initcap(F.lower(F.trim(col))))


def normalize_city_py(value: str) -> str:
    """Python-side normalizer (pandas/test için)."""
    if value is None:
        return None
    s = value.strip().lower()
    translate = str.maketrans("çğıiöşü", "cgiiosu")
    s = s.translate(translate)
    return _CANONICAL.get(s, value.strip().title())
