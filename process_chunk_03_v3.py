#!/usr/bin/env python3
import json
import re

def normalize_to_slug(text):
    """Convert text to lowercase slug with Turkish char mapping."""
    mapping = {
        'Ç': 'c', 'ç': 'c',
        'Ş': 's', 'ş': 's',
        'Ğ': 'g', 'ğ': 'g',
        'Ü': 'u', 'ü': 'u',
        'Ö': 'o', 'ö': 'o',
        'İ': 'i', 'ı': 'i', 'I': 'i'
    }
    text = text.lower()
    for k, v in mapping.items():
        text = text.replace(k, v)
    # Replace non-alphanumeric with space then collapse to underscore
    text = re.sub(r'[^a-z0-9_]', ' ', text)
    text = re.sub(r'\s+', '_', text.strip())
    return text

def get_base_product(text):
    """Extract base product name (remove varieties, sizes, brands)."""
    # Remove sizes like "1 Kg", "500 Gr", "400 Gr", "250 Gr", etc.
    text = re.sub(r'\s*\d+\s*(?:kg|gr|adet|litre|demet).*$', '', text.lower(), flags=re.IGNORECASE)
    # Remove common brands
    brands = ['superfresh', 'feast', 'paket', 'gurme', 'ayşe kadın', 'plate', 'nimet',
              'çokça', 'lavi', 'tarım', 'kredi', 'torpat', 'alatat', 'yurtalan', 'erüst',
              'mutlu', 'muti', 'eurofresh', 'akdeniz', 'sek', 'peynes', 'milkten', 'ahir',
              'pınar', 'sütaş', 'kaanlar', 'hastavuk', 'banvit', 'lezita', 'torku', 'seyidoğlu',
              'avşarlar', 'freshers', 'tagem', 'eko']
    for brand in brands:
        text = re.sub(r'\b' + brand + r'\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def eval_match(hal_product, market_product, market_category):
    """Evaluate confidence level and details for a match."""
    hal_norm = normalize_to_slug(hal_product)
    market_norm = normalize_to_slug(market_product)

    hal_base_norm = normalize_to_slug(get_base_product(hal_product))
    market_base_norm = normalize_to_slug(get_base_product(market_product))

    hal_lower = hal_product.lower()
    market_lower = market_product.lower()

    # Domain rules: reject processed products (not taze)
    processed_keywords = ['salca', 'tursu', 'konserve', 'kurutulmus', 'recel', 'marmelat', 'pekmez', 'durulmus']
    if any(kw in market_norm for kw in processed_keywords):
        if not any(kw in hal_norm for kw in processed_keywords):
            return {
                'confidence': 'reject',
                'product_canonical': hal_norm,
                'reason': 'Islenmi_ urun taze hal ile eslesmez'
            }

    # Frozen products matching (but same variety)
    if 'dondurulmus' in market_norm:
        if 'dondurulmus' not in hal_norm:
            # Check if base products match
            if hal_base_norm == market_base_norm and hal_base_norm:
                return {
                    'confidence': 'weak',
                    'product_canonical': hal_norm,
                    'reason': 'Dondurulmus taze cesit karsilastirma'
                }
            return {
                'confidence': 'reject',
                'product_canonical': None,
                'reason': 'Islenmi_ urun taze hal ile eslesmez'
            }
        # Frozen same variety
        return {
            'confidence': 'kg_equivalent',
            'product_canonical': hal_norm,
            'reason': 'Dondurulmus aynı cesit kg degi_tirilebilir'
        }

    # Exact match
    if market_norm == hal_norm:
        return {
            'confidence': 'exact',
            'product_canonical': hal_norm,
            'reason': 'Tam esles'
        }

    # Base product match (after removing brands/sizes)
    if market_base_norm == hal_base_norm and market_base_norm and hal_base_norm:
        # Check for variety differences that should be 'weak' not 'kg_equivalent'
        if ('pembe' in market_lower and 'salkım' in hal_lower) or \
           ('pembe' in market_lower and 'salcalik' in hal_lower) or \
           ('salkım' in market_lower and 'salcalik' in hal_lower) or \
           ('papaz' in market_lower and 'anjelik' in hal_lower) or \
           ('yeşil' in market_lower and 'anjelik' in hal_lower) or \
           ('starking' in market_lower and 'golden' in market_lower and 'granny' in market_lower):
            return {
                'confidence': 'weak',
                'product_canonical': hal_norm,
                'reason': 'Cesit farki ama ayni kategori'
            }

        # Same product different packaging/size
        return {
            'confidence': 'kg_equivalent',
            'product_canonical': hal_norm,
            'reason': 'Ayni urun degisik paket boyut'
        }

    # Check if market variety matches hal variety
    # e.g., "Çalı Fasulye" market → "Fasülye (Çalı)" hal
    # or "Sivri Biber 1 Kg" → "Biber(Sivri Kıl)" hal
    if 'fasulye' in hal_norm and 'fasulye' in market_norm:
        hal_variety_match = re.search(r'\((.+?)\)', hal_product)
        if hal_variety_match:
            hal_variety = normalize_to_slug(hal_variety_match.group(1))
            if hal_variety in market_norm or hal_variety.replace('_', '') in market_norm.replace('_', ''):
                return {
                    'confidence': 'kg_equivalent',
                    'product_canonical': hal_norm,
                    'reason': 'Ayni cesit aynı kategori paket farki'
                }

    # Biber variety matching: "Sivri Biber" market → "Biber(Sivri Kıl)" hal
    if 'biber' in hal_norm and 'biber' in market_norm:
        # Extract variety from hal like (Sivri Kıl) -> check if first word matches
        hal_variety_match = re.search(r'\((.+?)\)', hal_product)
        if hal_variety_match:
            hal_variety_words = hal_variety_match.group(1).lower().split()
            hal_variety_first = normalize_to_slug(hal_variety_words[0]) if hal_variety_words else ''
            market_words = market_lower.split()
            if market_words and hal_variety_first == normalize_to_slug(market_words[0]):
                return {
                    'confidence': 'kg_equivalent',
                    'product_canonical': hal_norm,
                    'reason': 'Ayni cesit aynı kategori paket farki'
                }

    # For fruits/veggies with varieties in parentheses:
    # Check if base name (without parentheses) matches
    hal_without_parens = re.sub(r'\s*\(.+?\)', '', hal_product).lower()
    hal_without_parens_norm = normalize_to_slug(hal_without_parens)

    if hal_without_parens_norm == market_base_norm and hal_without_parens_norm:
        # This is same product, different origin/variety
        if any(word in hal_lower for word in ['yerli', 'ithal', 'mısır', 'deveci', 'santa maria']):
            return {
                'confidence': 'kg_equivalent',
                'product_canonical': hal_norm,
                'reason': 'Ayni cesit farkli mensei paket boyut'
            }

    # Different products
    return {
        'confidence': 'reject',
        'product_canonical': None,
        'reason': 'Farkli urun'
    }

# Load chunk JSON
input_path = r'C:\Users\PC_4719\PROJELER\big-data\processing\silver\lookups\_chunks\chunk_03.json'
output_path = r'C:\Users\PC_4719\PROJELER\big-data\processing\silver\lookups\_chunks\mapping_03.csv'

with open(input_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Build CSV rows
rows = ['"hal_product","market_product","product_canonical","confidence","unit_conversion_factor","reason"']
total_hal = 0
total_rows = 0

for hal_product, hal_data in data.items():
    total_hal += 1
    candidates = hal_data.get('candidates', [])

    for candidate in candidates:
        market_product = candidate.get('market_product', '')
        market_category = candidate.get('market_category', '')

        result = eval_match(hal_product, market_product, market_category)

        canonical = result['product_canonical'] if result['product_canonical'] else ''
        confidence = result['confidence']
        reason = result['reason'].replace(',', ' ').replace('"', '')

        row = f'"{hal_product}","{market_product}","{canonical}","{confidence}","1.0","{reason}"'
        rows.append(row)
        total_rows += 1

# Write CSV
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(rows))

print(f"Processed {total_hal} hal products, wrote {total_rows} CSV rows")
