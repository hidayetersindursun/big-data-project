#!/usr/bin/env python3
import json
import re
import sys

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

    hal_base = hal_product.lower()
    market_base = market_product.lower()

    # Domain rules: reject processed products (not taze)
    processed_keywords = ['salca', 'tursu', 'konserve', 'kurutulmus', 'recel', 'marmelat', 'pekmez']
    if any(kw in market_norm for kw in processed_keywords):
        if not any(kw in hal_norm for kw in processed_keywords):
            return {
                'confidence': 'reject',
                'product_canonical': None,
                'reason': 'Islenmi_ urun taze hal ile eslesmez'
            }

    # Frozen products matching
    if 'dondurulmus' in market_norm:
        if 'dondurulmus' not in hal_norm:
            return {
                'confidence': 'weak',
                'product_canonical': hal_norm,
                'reason': 'Dondurulmus taze cesit karsilastirma'
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

    # Same main product, different packaging
    market_tokens = market_base.split()
    hal_tokens = hal_base.split('(')[0].split()

    market_main = market_tokens[0] if market_tokens else ''
    hal_main = hal_tokens[0] if hal_tokens else ''

    if market_main and hal_main and market_main == hal_main:
        # Check variety differences
        if 'pembe' in market_base and 'salkım' in hal_base:
            return {
                'confidence': 'weak',
                'product_canonical': hal_norm,
                'reason': 'Cesit farki Pembe vs Salkım'
            }
        if 'salkım' in market_base and 'salcalik' in hal_base:
            return {
                'confidence': 'weak',
                'product_canonical': hal_norm,
                'reason': 'Cesit farki Salkım vs Salcalik'
            }

        # Same product different packaging/size
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
