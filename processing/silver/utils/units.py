"""
Birim normalizasyonu helpers — market unitPrice ve title'larından per-kg fiyat çıkarımı.

Market verisi örnekleri:
  unitPrice = "99,00 ₺/Kg"          -> unitPriceValue zaten per-kg
  unitPrice = "59,00 ₺/Adet"        -> per-kg değil (yumurta gibi)
  unitPrice = "116,33 ₺/Kg"         -> unitPriceValue per-kg (kaynaklı: 34.9 TL / 0.3 Kg)
  title    = "Domates 500 Gr"       -> 500/1000 = 0.5 Kg
  title    = "Yumurta 10 Adet"      -> Adet birim, per-kg uygulanmaz

Hal verisi en_dusuk/en_yuksek zaten per-kg (kasa/çuval hal bürosunda zaten kg'a çevrilmiş haldedir).
"""

from pyspark.sql import Column
from pyspark.sql import functions as F


def is_per_kg(unit_price_col: Column) -> Column:
    """unitPrice string'i '/Kg' ile bitiyor mu? (case-insensitive)"""
    return F.lower(unit_price_col).rlike(r"/\s*kg\s*$")


def is_per_adet(unit_price_col: Column) -> Column:
    return F.lower(unit_price_col).rlike(r"/\s*adet\s*$")


def is_per_litre(unit_price_col: Column) -> Column:
    return F.lower(unit_price_col).rlike(r"/\s*(lt|litre|l)\s*$")


def parse_weight_kg(title_col: Column) -> Column:
    """
    Title'dan ağırlık çıkar (kg cinsinden).
      "Domates 500 Gr"   -> 0.5
      "Et 1.5 Kg"        -> 1.5
      "Yumurta 10 Adet"  -> null (kg değil)
      "Süt 1 Lt"         -> null (litre, kg değil)
    """
    title_lower = F.lower(title_col)
    grams = F.regexp_extract(title_lower, r"(\d+[\.,]?\d*)\s*(gr|gram)\b", 1)
    kg = F.regexp_extract(title_lower, r"(\d+[\.,]?\d*)\s*kg\b", 1)

    grams_val = F.when(grams != "", F.regexp_replace(grams, ",", ".").cast("double") / 1000.0)
    kg_val = F.when(kg != "", F.regexp_replace(kg, ",", ".").cast("double"))

    return F.coalesce(kg_val, grams_val)


def price_per_kg(unit_price_value_col: Column, unit_price_str_col: Column,
                 price_col: Column, title_col: Column) -> Column:
    """
    Bir market satırı için per-kg fiyatı döndür.

    Strateji:
      1. unitPrice "₺/Kg" ile bitiyorsa -> unitPriceValue zaten per-kg, onu kullan.
      2. unitPrice "₺/Adet" ise -> bu kg-eşdeğeri DEĞİL, null döndür (Gold tarafında ayrı tutulur).
      3. unitPrice yoksa ama title'da "1 Kg" / "500 Gr" varsa -> price / weight_kg.
      4. Hiçbiri -> null.
    """
    weight_kg = parse_weight_kg(title_col)
    fallback = F.when(weight_kg.isNotNull() & (weight_kg > 0),
                      price_col / weight_kg)
    return (
        F.when(is_per_kg(unit_price_str_col), unit_price_value_col)
         .when(is_per_adet(unit_price_str_col), F.lit(None).cast("double"))
         .when(is_per_litre(unit_price_str_col), F.lit(None).cast("double"))
         .otherwise(fallback)
    )
