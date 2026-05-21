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

def eval_match(hal_product, market_product, market_category):
    """Evaluate confidence level and details for a match."""
    hal_norm = normalize_to_slug(hal_product)
    market_norm = normalize_to_slug(market_product)

    hal_lower = hal_product.lower()
    market_lower = market_product.lower()

    # Domain rules: reject processed products (not taze)
    processed_keywords = ['salca', 'tursu', 'konserve', 'kurutulmus', 'recel', 'marmelat', 'pekmez']
    market_is_processed = any(kw in market_norm for kw in processed_keywords)
    hal_is_processed = any(kw in hal_norm for kw in processed_keywords)

    if market_is_processed and not hal_is_processed:
        return {
            'confidence': 'reject',
            'product_canonical': hal_norm,
            'reason': 'Islenmi_ urun taze hal ile eslesmez'
        }

    # Frozen products matching
    if 'dondurulmus' in market_norm:
        if 'dondurulmus' not in hal_norm:
            # Check if base products match
            market_tokens = set(market_lower.split())
            hal_tokens = set(hal_lower.replace('(', ' ').replace(')', ' ').split())
            # Remove size/quantity tokens
            market_tokens = {t for t in market_tokens if not re.match(r'\d+$|kg|gr|adet|litre|demet', t)}
            hal_tokens = {t for t in hal_tokens if not re.match(r'\d+$|kg|gr|adet|litre|demet', t)}

            # Remove brands
            brands = ['superfresh', 'feast', 'paket', 'gurme', 'ayşe', 'kadın', 'plate', 'nimet',
                      'çokça', 'lavi', 'tarım', 'kredi', 'torpat', 'alatat', 'yurtalan', 'erüst',
                      'mutlu', 'muti', 'eurofresh', 'akdeniz', 'taze', 'dondurulmus']
            for brand in brands:
                market_tokens.discard(brand)
                hal_tokens.discard(brand)

            # Check core product match
            if market_tokens & hal_tokens:  # any intersection
                return {
                    'confidence': 'weak',
                    'product_canonical': hal_norm,
                    'reason': 'Dondurulmus taze cesit karsilastirma'
                }
        # Frozen same variety (both have dondurulmus)
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

    # Extract main product (first meaningful token)
    def get_main_product(text):
        """Get main product name (first non-brand, non-quantity word)."""
        tokens = text.lower().split()
        brands = {'superfresh', 'feast', 'paket', 'gurme', 'ayşe', 'kadın', 'plate', 'nimet',
                  'çokça', 'lavi', 'tarım', 'kredi', 'torpat', 'alatat', 'yurtalan', 'erüst',
                  'mutlu', 'muti', 'eurofresh', 'akdeniz', 'taze', 'sek', 'peynes', 'milkten',
                  'ahir', 'pınar', 'sütaş', 'kaanlar'}
        for token in tokens:
            if token not in brands and not re.match(r'^\d+$', token) and token not in ['kg', 'gr', 'adet', 'litre', 'demet']:
                return token
        return tokens[0] if tokens else ''

    market_main = get_main_product(market_product)
    hal_main_base = hal_product.replace('(', ' ').replace(')', ' ')
    hal_main = get_main_product(hal_main_base)

    # Same main product?
    if market_main and hal_main and market_main == hal_main:
        # Check for specific variety differences
        if ('pembe' in market_lower and any(v in hal_lower for v in ['salkım', 'salcalik'])) or \
           ('salkım' in market_lower and 'salcalik' in hal_lower) or \
           ('papaz' in market_lower and 'anjelik' in hal_lower) or \
           ('yeşil' in market_lower and 'anjelik' in hal_lower) or \
           ('deveci' in market_lower and 'santa maria' in hal_lower) or \
           ('golden' in market_lower and 'starkin' in hal_lower):
            return {
                'confidence': 'weak',
                'product_canonical': hal_norm,
                'reason': 'Cesit farki ama ayni kategori'
            }

        # Same product different packaging
        return {
            'confidence': 'kg_equivalent',
            'product_canonical': hal_norm,
            'reason': 'Ayni urun degisik paket boyut'
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
