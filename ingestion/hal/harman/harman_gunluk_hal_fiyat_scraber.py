# -*- coding: utf-8 -*-
"""
Harmanapps.com Günlük Hal Fiyat Çekici
- Cloudflare bypass: curl_cffi / chrome110
- Çıktı: harman_hal_fiyat_DD_MM_YYYY.csv
- Sütunlar: tarih, sehir, urun, kategori, en_dusuk, en_yuksek, veri_turu
  (sentetik format ile uyumlu)
"""

import re
import pandas as pd
from curl_cffi import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ─────────────────────────────────────────────────────────────────
# ÜRÜN ADI NORMALİZASYON TABLOSU
# Ham harman adı (küçük harf, normalize) → standart ad
# ─────────────────────────────────────────────────────────────────
URUN_MAP = {
    # DOMATES
    "domates":                      ("Domates",            "Sebze"),
    "domates 1.sinif":              ("Domates",            "Sebze"),
    "domates 2.sinif":              ("Domates",            "Sebze"),
    "domates ii":                   ("Domates",            "Sebze"),
    "domates diğer":                ("Domates",            "Sebze"),
    "domates ayaş":                 ("Domates",            "Sebze"),
    "domates beef":                 ("Domates",            "Sebze"),
    "domates köy yerli":            ("Domates",            "Sebze"),
    "domates salçalık":             ("Domates",            "Sebze"),
    "domates pembe":                ("Domates",            "Sebze"),
    "domates (pembe)":              ("Domates",            "Sebze"),
    "domates pembe":                ("Domates",            "Sebze"),
    "domates salkım":               ("Domates",            "Sebze"),
    "domates salkım (kutu)":        ("Domates",            "Sebze"),
    "domates (salkım)":             ("Domates",            "Sebze"),
    "domatessalkım":                ("Domates",            "Sebze"),
    "salk. domates":                ("Domates",            "Sebze"),
    "salkım domates":               ("Domates",            "Sebze"),
    "organik domates":              ("Domates",            "Sebze"),
    "domates(antalya)":             ("Domates",            "Sebze"),
    "domates(salkim)":              ("Domates",            "Sebze"),
    "domates(salkim)":              ("Domates",            "Sebze"),
    "domates (kokteyl)":            ("Domates",            "Sebze"),
    "domates kokteyl":              ("Domates",            "Sebze"),
    "domates cherry":               ("Domates (Cherry)",   "Sebze"),
    "domates (cherry)":             ("Domates (Cherry)",   "Sebze"),
    "domates(cherry)":              ("Domates (Cherry)",   "Sebze"),
    "domates chery":                ("Domates (Cherry)",   "Sebze"),
    "domates çeri":                 ("Domates (Cherry)",   "Sebze"),
    "domates (çeri)":               ("Domates (Cherry)",   "Sebze"),
    "domates (ceri)":               ("Domates (Cherry)",   "Sebze"),
    "domates (cery)":               ("Domates (Cherry)",   "Sebze"),
    "kokty domates (çeri)":         ("Domates (Cherry)",   "Sebze"),
    # BİBER
    "biber (sivri)":                ("Biber (Sivri)",      "Sebze"),
    "biber sivri":                  ("Biber (Sivri)",      "Sebze"),
    "biber(sivri)":                 ("Biber (Sivri)",      "Sebze"),
    "biber(sivri sera)":            ("Biber (Sivri)",      "Sebze"),
    "biber(sivri kıl)":             ("Biber (Sivri)",      "Sebze"),
    "biber kıl":                    ("Biber (Sivri)",      "Sebze"),
    "biber kıl aci":                ("Biber (Sivri)",      "Sebze"),
    "biber acı":                    ("Biber (Sivri)",      "Sebze"),
    "biber acı cin":                ("Biber (Sivri)",      "Sebze"),
    "biber(acı cin)":               ("Biber (Sivri)",      "Sebze"),
    "biber köy":                    ("Biber (Sivri)",      "Sebze"),
    "biber (köy)":                  ("Biber (Sivri)",      "Sebze"),
    "biber üçburun":                ("Biber (Sivri)",      "Sebze"),
    "biber(üç burun köy)":          ("Biber (Sivri)",      "Sebze"),
    "biber lopez":                  ("Biber (Sivri)",      "Sebze"),
    "fini biber":                   ("Biber (Sivri)",      "Sebze"),
    "biber (dolma)":                ("Biber (Dolmalık)",   "Sebze"),
    "biber dolma":                  ("Biber (Dolmalık)",   "Sebze"),
    "biber dolmalık":               ("Biber (Dolmalık)",   "Sebze"),
    "biber dolmalik":               ("Biber (Dolmalık)",   "Sebze"),
    "bi̇ber dolmalik":              ("Biber (Dolmalık)",   "Sebze"),
    "biber (çarlı)":                ("Biber (Çarliston)",  "Sebze"),
    "biber çarlı":                  ("Biber (Çarliston)",  "Sebze"),
    "biber çarliston":              ("Biber (Çarliston)",  "Sebze"),
    "biber (çarliston)":            ("Biber (Çarliston)",  "Sebze"),
    "biber(çarliston)":             ("Biber (Çarliston)",  "Sebze"),
    "biberçarliston":               ("Biber (Çarliston)",  "Sebze"),
    "biber süs":                    ("Biber (Çarliston)",  "Sebze"),
    "biber kapya":                  ("Biber Kapya",        "Sebze"),
    "biber (kırmızı kapya)":        ("Biber Kapya",        "Sebze"),
    "biber capya":                  ("Biber Kapya",        "Sebze"),
    # PATLICAN
    "patlican":                     ("Patlıcan",           "Sebze"),
    "patlıcan":                     ("Patlıcan",           "Sebze"),
    "patlıcan (kebaplık)":          ("Patlıcan",           "Sebze"),
    "patlıcan (topak)":             ("Patlıcan",           "Sebze"),
    "patlıcan bostan (topak)":      ("Patlıcan",           "Sebze"),
    "patlıcan i.":                  ("Patlıcan",           "Sebze"),
    "patlican (diğer)":             ("Patlıcan",           "Sebze"),
    "patlican kemer":               ("Patlıcan",           "Sebze"),
    "patlicankemer":                ("Patlıcan",           "Sebze"),
    "patlican topak":               ("Patlıcan",           "Sebze"),
    # KABAK
    "kabak":                        ("Kabak",              "Sebze"),
    "kabak (diğer)":                ("Kabak",              "Sebze"),
    "kabak diğer":                  ("Kabak",              "Sebze"),
    "kabak dolmalık":               ("Kabak",              "Sebze"),
    "kabak ampul":                  ("Kabak",              "Sebze"),
    "kabak kara":                   ("Kabak",              "Sebze"),
    "kabak taze":                   ("Kabak",              "Sebze"),
    "kabaktaze":                    ("Kabak",              "Sebze"),
    "kabak bal":                    ("Kabak",              "Sebze"),
    "kabak (bal)":                  ("Kabak",              "Sebze"),
    "kabak sakiz":                  ("Kabak",              "Sebze"),
    "kabak (sakız)":                ("Kabak",              "Sebze"),
    "s. kabak":                     ("Kabak",              "Sebze"),
    # SALATALIK
    "salatalik":                    ("Salatalık",          "Sebze"),
    "salatalık":                    ("Salatalık",          "Sebze"),
    "salatalık (silor)":            ("Salatalık",          "Sebze"),
    "hıyar":                        ("Salatalık",          "Sebze"),
    "hıyar (slor paket)":          ("Salatalık",          "Sebze"),
    "salatalık diğer":              ("Salatalık",          "Sebze"),
    "salatalık i.":                 ("Salatalık",          "Sebze"),
    "salatalik (diğer)":            ("Salatalık",          "Sebze"),
    "salatalik çengelköy":          ("Salatalık",          "Sebze"),
    # PATATES
    "patates":                      ("Patates",            "Sebze"),
    "patates diğer":                ("Patates",            "Sebze"),
    "patates ii":                   ("Patates",            "Sebze"),
    "patates taze":                 ("Patates",            "Sebze"),
    "patatestaze":                  ("Patates",            "Sebze"),
    "patates 2.kalite":             ("Patates",            "Sebze"),
    "patates (diğer)":              ("Patates",            "Sebze"),
    "t. patates":                   ("Patates",            "Sebze"),
    "tatli patates":                ("Patates",            "Sebze"),
    # SOĞAN
    "soğan kuru":                   ("Soğan (Kırmızı)",   "Sebze"),
    "soğan kuru diğer":             ("Soğan (Kırmızı)",   "Sebze"),
    "soğankuru":                    ("Soğan (Kırmızı)",   "Sebze"),
    "soğan":                        ("Soğan (Kırmızı)",   "Sebze"),
    "soğan(kırmızı)":              ("Soğan (Kırmızı)",   "Sebze"),
    "soğan kirmizi":                ("Soğan (Kırmızı)",   "Sebze"),
    "soğan (mor) (kg)":             ("Soğan (Kırmızı)",   "Sebze"),
    "soğan (kırmızı balık)":        ("Soğan (Kırmızı)",   "Sebze"),
    "soğan (balık mor)":            ("Soğan (Kırmızı)",   "Sebze"),
    "k.soğan":                      ("Soğan (Kırmızı)",   "Sebze"),
    "kir. soğan":                   ("Soğan (Kırmızı)",   "Sebze"),
    "soğan kuru (diğer)":           ("Soğan (Kırmızı)",   "Sebze"),
    "soğan(beyaz)":                 ("Soğan (Beyaz)",     "Sebze"),
    "soğan taze":                   ("Yeşil Soğan",       "Sebze"),
    "soğan yeşil":                  ("Yeşil Soğan",       "Sebze"),
    "soğan (yeşil)":                ("Yeşil Soğan",       "Sebze"),
    "yeşil soğan":                  ("Yeşil Soğan",       "Sebze"),
    "y. soğan":                     ("Yeşil Soğan",       "Sebze"),
    "soğanyerliyeşil":              ("Yeşil Soğan",       "Sebze"),
    "soğanmer.yeşil (yerli)":       ("Yeşil Soğan",       "Sebze"),
    # SARIMSAK
    "sarimsak kuru":                ("Sarımsak (Kuru)",   "Sebze"),
    "sarimsak taze":                ("Sarımsak (Taze)",   "Sebze"),
    "sarımsak kuru":                ("Sarımsak (Kuru)",   "Sebze"),
    "sarımsakkuru":                 ("Sarımsak (Kuru)",   "Sebze"),
    "sarımsak (kuru)":              ("Sarımsak (Kuru)",   "Sebze"),
    "sarimsak kuru":                ("Sarımsak (Kuru)",   "Sebze"),
    "sarımsak (taze)":              ("Sarımsak (Taze)",   "Sebze"),
    "sarımsak (yerli)":             ("Sarımsak (Kuru)",   "Sebze"),
    "sarımsak (yeşil)":             ("Sarımsak (Taze)",   "Sebze"),
    "t. sarımsak":                  ("Sarımsak (Taze)",   "Sebze"),
    "sarimsak yeşil":               ("Sarımsak (Taze)",   "Sebze"),
    # HAVUÇ
    "havuç":                        ("Havuç",             "Sebze"),
    "havuç (kırmızı)":              ("Havuç",             "Sebze"),
    "havuç diğer":                  ("Havuç",             "Sebze"),
    "havuç beypazarı":              ("Havuç",             "Sebze"),
    "havuç (beypazarı)":            ("Havuç",             "Sebze"),
    "havuç iri (takoz)":            ("Havuç",             "Sebze"),
    "havuç(sari)":                  ("Havuç",             "Sebze"),
    "havuç(siyah)":                 ("Havuç",             "Sebze"),
    # LAHANA
    "lahana (beyaz)":               ("Lahana (Beyaz)",    "Sebze"),
    "lahana beyaz":                 ("Lahana (Beyaz)",    "Sebze"),
    "lahanabeyaz":                  ("Lahana (Beyaz)",    "Sebze"),
    "lahana(beyaz)":                ("Lahana (Beyaz)",    "Sebze"),
    "beyaz lahana":                 ("Lahana (Beyaz)",    "Sebze"),
    "lahana (beyaz)":               ("Lahana (Beyaz)",    "Sebze"),
    "kelem beyaz":                  ("Lahana (Beyaz)",    "Sebze"),
    "lahana (kırmızı)":             ("Lahana (Kırmızı)",  "Sebze"),
    "lahana kırmızı":               ("Lahana (Kırmızı)",  "Sebze"),
    "kırmızı lahana":               ("Lahana (Kırmızı)",  "Sebze"),
    "lahana(kırmızı)":              ("Lahana (Kırmızı)",  "Sebze"),
    "lahana(kirmizi)":              ("Lahana (Kırmızı)",  "Sebze"),
    "lahana (kırmızı) (kg)":        ("Lahana (Kırmızı)",  "Sebze"),
    "lahana kara":                  ("Lahana (Beyaz)",    "Sebze"),
    "lahana kara (bağ)":            ("Lahana (Beyaz)",    "Sebze"),
    "karalahana":                   ("Lahana (Beyaz)",    "Sebze"),
    "kara lahana":                  ("Lahana (Beyaz)",    "Sebze"),
    # MARUL
    "marul":                        ("Marul (Düz)",       "Sebze"),
    "marul (düz)":                  ("Marul (Düz)",       "Sebze"),
    "marul(düz)":                   ("Marul (Düz)",       "Sebze"),
    "marul göbekli":                ("Marul (Düz)",       "Sebze"),
    "marul (göbek)":                ("Marul (Düz)",       "Sebze"),
    "marul göbekli marul göbekli( yağlı-kop salat)": ("Marul (Düz)", "Sebze"),
    "marul kaşik":                  ("Marul (Düz)",       "Sebze"),
    "amerikan marul":               ("Marul (Düz)",       "Sebze"),
    "kirmizi marul":                ("Marul (Düz)",       "Sebze"),
    "kiv. marul":                   ("Marul (Kıvırcık)",  "Sebze"),
    "marul kıvırcık":               ("Marul (Kıvırcık)",  "Sebze"),
    "marul (kıvırcık)":             ("Marul (Kıvırcık)",  "Sebze"),
    "marul kivircik":               ("Marul (Kıvırcık)",  "Sebze"),
    "marul(kivircik)":              ("Marul (Kıvırcık)",  "Sebze"),
    "marul kıvırcık diğer":         ("Marul (Kıvırcık)",  "Sebze"),
    "marul kıvırcık (adet)":        ("Marul (Kıvırcık)",  "Sebze"),
    "marulkıvırcık":                ("Marul (Kıvırcık)",  "Sebze"),
    "marul kivircik (kivircik kırmızı(lolorosso))": ("Marul (Kıvırcık)", "Sebze"),
    "marul lolorosso":              ("Marul (Kıvırcık)",  "Sebze"),
    "marul(lolorosso)":             ("Marul (Kıvırcık)",  "Sebze"),
    "marul aysberg":                ("Marul (Aysberg)",   "Sebze"),
    "marul (aysberg)":              ("Marul (Aysberg)",   "Sebze"),
    "marul(aysberg)":               ("Marul (Aysberg)",   "Sebze"),
    "marul aysberg (adet)":         ("Marul (Aysberg)",   "Sebze"),
    "marul (aysberk)":              ("Marul (Aysberg)",   "Sebze"),
    "marul iceberg":                ("Marul (Aysberg)",   "Sebze"),
    "marul (iceberk)":              ("Marul (Aysberg)",   "Sebze"),
    "marul iceberk":                ("Marul (Aysberg)",   "Sebze"),
    "marul iceberg":                ("Marul (Aysberg)",   "Sebze"),
    # ISPANAK
    "ispanak":                      ("Ispanak",           "Sebze"),
    "ıspanak":                      ("Ispanak",           "Sebze"),
    # MAYDANOZ
    "maydanoz":                     ("Maydanoz",          "Sebze"),
    "maydanos":                     ("Maydanoz",          "Sebze"),
    "maydonoz":                     ("Maydanoz",          "Sebze"),
    "maydanoz (bağ)":               ("Maydanoz",          "Sebze"),
    "maydanoz (70-100 gr)":         ("Maydanoz",          "Sebze"),
    "y.maydonoz":                   ("Maydanoz",          "Sebze"),
    # ROKA
    "roka":                         ("Roka",              "Sebze"),
    "roka (bağ)":                   ("Roka",              "Sebze"),
    "roka (70-100gr)":              ("Roka",              "Sebze"),
    "y.roka":                       ("Roka",              "Sebze"),
    # NANE
    "nane":                         ("Nane",              "Sebze"),
    "nane (bağ)":                   ("Nane",              "Sebze"),
    "nane (tekli)":                 ("Nane",              "Sebze"),
    "nane taze":                    ("Nane",              "Sebze"),
    "y.nane":                       ("Nane",              "Sebze"),
    # TERE
    "tere":                         ("Tere",              "Sebze"),
    "tere (diğer)":                 ("Tere",              "Sebze"),
    "y.tere":                       ("Tere",              "Sebze"),
    # DEREOTU
    "dereotu":                      ("Dereotu",           "Sebze"),
    "dere otu":                     ("Dereotu",           "Sebze"),
    "dere":                         ("Dereotu",           "Sebze"),
    "dereotu (bağ)":                ("Dereotu",           "Sebze"),
    "dereotu (yaş-taze)":           ("Dereotu",           "Sebze"),
    "y.dereotu":                    ("Dereotu",           "Sebze"),
    # FASULYE
    "fasulye":                      ("Fasulye (Taze)",    "Sebze"),
    "fasulye taze":                 ("Fasulye (Taze)",    "Sebze"),
    "fasulye (taze)":               ("Fasulye (Taze)",    "Sebze"),
    "fasulye(taze)":                ("Fasulye (Taze)",    "Sebze"),
    "fasulye taze diğer":           ("Fasulye (Taze)",    "Sebze"),
    "fasulye taze (diğer)":         ("Fasulye (Taze)",    "Sebze"),
    "fasulye taze (çalı)":          ("Fasulye (Taze)",    "Sebze"),
    "fasulye taze cino":            ("Fasulye (Taze)",    "Sebze"),
    "fasulye ayşe kadin":           ("Fasulye (Taze)",    "Sebze"),
    "fasulye ayşe kadın":           ("Fasulye (Taze)",    "Sebze"),
    "fasulye taze ayşe kadın":      ("Fasulye (Taze)",    "Sebze"),
    "fasulye taze boncuk":          ("Fasulye (Taze)",    "Sebze"),
    "fasulye (sarıkız)":            ("Fasulye (Taze)",    "Sebze"),
    "fasulye sırık":                ("Fasulye (Taze)",    "Sebze"),
    "fasülye (ayşekadin)":          ("Fasulye (Taze)",    "Sebze"),
    "fasulye   ayse":               ("Fasulye (Taze)",    "Sebze"),
    "fasulye   cali":               ("Fasulye (Taze)",    "Sebze"),
    # BEZELYE
    "bezelye":                      ("Bezelye",           "Sebze"),
    "bezelye taze":                 ("Bezelye",           "Sebze"),
    "bezelye taze (araka)":         ("Bezelye",           "Sebze"),
    "bezelye taze araka":           ("Bezelye",           "Sebze"),
    "bezelye taze diğer":           ("Bezelye",           "Sebze"),
    # BAKLA
    "bakla":                        ("Bakla (Taze)",      "Sebze"),
    "bakla taze":                   ("Bakla (Taze)",      "Sebze"),
    "bakla (taze)":                 ("Bakla (Taze)",      "Sebze"),
    "bakla taze (diğer)":           ("Bakla (Taze)",      "Sebze"),
    # KARNABAHAR
    "karnabahar":                   ("Karnabahar",        "Sebze"),
    "karnabahar diğer":             ("Karnabahar",        "Sebze"),
    "karnabahar (diğer)":           ("Karnabahar",        "Sebze"),
    "karnıbahar":                   ("Karnabahar",        "Sebze"),
    # BROKOLİ
    "brokoli":                      ("Brokoli",           "Sebze"),
    "brokoli̇":                     ("Brokoli",           "Sebze"),
    "brüksel lahanası":             ("Brokoli",           "Sebze"),
    # KEREVİZ
    "kereviz":                      ("Kereviz",           "Sebze"),
    "kereviz":                      ("Kereviz",           "Sebze"),
    # PIRASA
    "pirasa":                       ("Pırasa",            "Sebze"),
    "pırasa":                       ("Pırasa",            "Sebze"),
    # PANCAR
    "pancar":                       ("Pancar",            "Sebze"),
    # MANTAR
    "mantar":                       ("Mantar (Kültür)",   "Sebze"),
    "mantar kültür":                ("Mantar (Kültür)",   "Sebze"),
    # SEMİZOTU
    "semizotu":                     ("Semizotu",          "Sebze"),
    "semiz otu":                    ("Semizotu",          "Sebze"),
    "semizotu (bağ)":               ("Semizotu",          "Sebze"),
    # ENGİNAR
    "enginar":                      ("Enginar",           "Sebze"),
    "enginar (salamura)":           ("Enginar",           "Sebze"),
    "enginar(canak)":               ("Enginar",           "Sebze"),
    # BARBUNYA
    "barbunya taze":                ("Barbunya (Taze)",   "Sebze"),
    "barbunya":                     ("Barbunya (Taze)",   "Sebze"),
    # BÖRÜLCE
    "börülce taze":                 ("Börülce (Taze)",    "Sebze"),
    "deniz börülcesi":              ("Deniz Börülcesi",   "Sebze"),
    "deniz börülcesi(deniz otu ege otu) deniz börülcesi (deniz otu ege otu)": ("Deniz Börülcesi", "Sebze"),
    # BAMYA
    "bamya taze":                   ("Bamya",             "Sebze"),
    # FESLEĞEN
    "fesleğen":                     ("Fesleğen",          "Sebze"),
    "fesleğen(reyhan)":             ("Fesleğen",          "Sebze"),
    "biberiye rozmarin":            ("Biberiye",          "Sebze"),
    "biberiye diğer":               ("Biberiye",          "Sebze"),
    "yaprak taze":                  ("Asma Yaprağı",      "Sebze"),
    "yeşillik (maydanoz, nane, tere, roka, dere)": ("Yeşillik", "Sebze"),
    # ─── MEYVE ───────────────────────────────────────────────────
    # ELMA
    "elma":                         ("Elma (Golden)",     "Meyve"),
    "elma (golden)":                ("Elma (Golden)",     "Meyve"),
    "elma golden":                  ("Elma (Golden)",     "Meyve"),
    "elma golden ( yerli )":        ("Elma (Golden)",     "Meyve"),
    "elma(golden)":                 ("Elma (Golden)",     "Meyve"),
    "elma gransmıth":               ("Elma (Granny Smith)","Meyve"),
    "elma (grann smith)":           ("Elma (Granny Smith)","Meyve"),
    "elma(grannysmith)":            ("Elma (Granny Smith)","Meyve"),
    "elma granny":                  ("Elma (Granny Smith)","Meyve"),
    "elma starkings ( yerli )":     ("Elma (Starking)",   "Meyve"),
    "elma starki̇n":                ("Elma (Starking)",   "Meyve"),
    "elma(starkin)":                ("Elma (Starking)",   "Meyve"),
    "elma(starkıng)":               ("Elma (Starking)",   "Meyve"),
    "elma arapkızı":                ("Elma (Starking)",   "Meyve"),
    "elma ankara":                  ("Elma (Golden)",     "Meyve"),
    "cennet elmasi":                ("Elma (Golden)",     "Meyve"),
    "elma (diğer)":                 ("Elma (Golden)",     "Meyve"),
    "elma arjantin":                ("Elma (Golden)",     "Meyve"),
    # ARMUT
    "armut":                        ("Armut (Deveci)",    "Meyve"),
    "armut (deveci)":               ("Armut (Deveci)",    "Meyve"),
    "armut deveci":                 ("Armut (Deveci)",    "Meyve"),
    "armut(deveci)":                ("Armut (Deveci)",    "Meyve"),
    "armutdeveci":                  ("Armut (Deveci)",    "Meyve"),
    "armut devecibursa":            ("Armut (Deveci)",    "Meyve"),
    "armut muhtelif":               ("Armut (Deveci)",    "Meyve"),
    "armut akça":                   ("Armut (Deveci)",    "Meyve"),
    "armut (diğer)":                ("Armut (Deveci)",    "Meyve"),
    "armut s.maria":                ("Armut (Santamaria)","Meyve"),
    "armut ( santamarİa)":          ("Armut (Santamaria)","Meyve"),
    "armut santami̇ra":              ("Armut (Santamaria)","Meyve"),
    "armut santamari̇":              ("Armut (Santamaria)","Meyve"),
    "armut ankara":                 ("Armut (Deveci)",    "Meyve"),
    "armut (margarin)":             ("Armut (Deveci)",    "Meyve"),
    # PORTAKAL
    "portakal":                     ("Portakal",          "Meyve"),
    "portakal diğer":               ("Portakal",          "Meyve"),
    "portakal (diğer)":             ("Portakal",          "Meyve"),
    "portakal finike":              ("Portakal",          "Meyve"),
    "portakal antalya":             ("Portakal",          "Meyve"),
    "portakal (waşington)":         ("Portakal",          "Meyve"),
    "portakal finiki":              ("Portakal",          "Meyve"),
    "portakal valencia":            ("Portakal",          "Meyve"),
    "portakal(sıkmalık)":           ("Portakal (Sıkmalık)","Meyve"),
    "portakal(sikmalik)":           ("Portakal (Sıkmalık)","Meyve"),
    "portakal(yatak)":              ("Portakal (Sıkmalık)","Meyve"),
    # MANDALİNA
    "mandalina":                    ("Mandalina",         "Meyve"),
    "mandalina diğer":              ("Mandalina",         "Meyve"),
    "mandalina (diğer)":            ("Mandalina",         "Meyve"),
    "mandalina mersin":             ("Mandalina",         "Meyve"),
    # LİMON
    "limon":                        ("Limon",             "Meyve"),
    "limon diğer":                  ("Limon",             "Meyve"),
    "limon (lamas)":                ("Limon",             "Meyve"),
    "limon lamas":                  ("Limon",             "Meyve"),
    "limon dökme":                  ("Limon",             "Meyve"),
    "limon yatak sn.":              ("Limon",             "Meyve"),
    "limonfile":                    ("Limon",             "Meyve"),
    "lime limon":                   ("Limon",             "Meyve"),
    "li̇mon (kg) yeni̇":            ("Limon",             "Meyve"),
    # GREYFURT
    "greyfurt":                     ("Greyfurt",          "Meyve"),
    "greyfurt diğer":               ("Greyfurt",          "Meyve"),
    "greyfurt (diğer)":             ("Greyfurt",          "Meyve"),
    # MUZ
    "muz yerli":                    ("Muz (Yerli)",       "Meyve"),
    "muz (yerli)":                  ("Muz (Yerli)",       "Meyve"),
    "muz muz yerli (anamur)":       ("Muz (Yerli)",       "Meyve"),
    "muz muz yerli(anamur)":        ("Muz (Yerli)",       "Meyve"),
    "muz(anamur)":                  ("Muz (Yerli)",       "Meyve"),
    "muzanamur":                    ("Muz (Yerli)",       "Meyve"),
    "muz yerli̇":                   ("Muz (Yerli)",       "Meyve"),
    "yerli muz":                    ("Muz (Yerli)",       "Meyve"),
    "muz ithal":                    ("Muz (İthal)",       "Meyve"),
    "muz (diğer)":                  ("Muz (İthal)",       "Meyve"),
    "muz ithal (koli)":             ("Muz (İthal)",       "Meyve"),
    "muzithal":                     ("Muz (İthal)",       "Meyve"),
    "ithal muz":                    ("Muz (İthal)",       "Meyve"),
    "muz  ithal":                   ("Muz (İthal)",       "Meyve"),
    "muz 1. kalite":                ("Muz (Yerli)",       "Meyve"),
    # ÜZÜM
    "üzüm":                         ("Üzüm (Beyaz)",      "Meyve"),
    "üzüm (beyaz)":                 ("Üzüm (Beyaz)",      "Meyve"),
    "üzüm beyaz":                   ("Üzüm (Beyaz)",      "Meyve"),
    "üzüm beyaz diğer":             ("Üzüm (Beyaz)",      "Meyve"),
    "üzüm beyaz (kırmızı)":         ("Üzüm (Beyaz)",      "Meyve"),
    "üzüm aşikara":                 ("Üzüm (Beyaz)",      "Meyve"),
    "üzüm muhtelif":                ("Üzüm (Beyaz)",      "Meyve"),
    "üzüm çeki̇rdeksi̇z":           ("Üzüm (Beyaz)",      "Meyve"),
    "üzüm çekirdeksiz":             ("Üzüm (Beyaz)",      "Meyve"),
    # KARPUZ
    "karpuz":                       ("Karpuz",            "Meyve"),
    "karpuz diğer":                 ("Karpuz",            "Meyve"),
    "karpuz (diğer)":               ("Karpuz",            "Meyve"),
    "karpuz (1.kalite)":            ("Karpuz",            "Meyve"),
    "karpuz vaşington":             ("Karpuz",            "Meyve"),
    "karpuz çekirdeksiz":           ("Karpuz",            "Meyve"),
    "karpuz (ithal)":               ("Karpuz",            "Meyve"),
    # KAVUN
    "kavun":                        ("Kavun",             "Meyve"),
    "kavun diğer":                  ("Kavun",             "Meyve"),
    "kavun (diğer)":                ("Kavun",             "Meyve"),
    "kavun (galya)":                ("Kavun",             "Meyve"),
    "kavun ankara":                 ("Kavun",             "Meyve"),
    "kavun(kırkağaç)":              ("Kavun",             "Meyve"),
    "kavun (ithal)":                ("Kavun",             "Meyve"),
    # ÇİLEK
    "çilek":                        ("Çilek",             "Meyve"),
    "cilek":                        ("Çilek",             "Meyve"),
    "çi̇lek":                       ("Çilek",             "Meyve"),
    "çi̇lek kğ":                    ("Çilek",             "Meyve"),
    # KİRAZ
    "kiraz":                        ("Kiraz",             "Meyve"),
    "kiraz diğer":                  ("Kiraz",             "Meyve"),
    "kiraz (napolyon)":             ("Kiraz",             "Meyve"),
    "kiraz burlent":                ("Kiraz",             "Meyve"),
    # ŞEFTALİ
    "şeftali":                      ("Şeftali",           "Meyve"),
    "şeftali̇":                     ("Şeftali",           "Meyve"),
    "nektarin":                     ("Nektarin",          "Meyve"),
    "nektari̇n":                    ("Nektarin",          "Meyve"),
    "nektarin kırmızı":             ("Nektarin",          "Meyve"),
    # KAYISI
    "kayısı":                       ("Kayısı",            "Meyve"),
    "kayısı diğer":                 ("Kayısı",            "Meyve"),
    "kayısı i.":                    ("Kayısı",            "Meyve"),
    "kayısı mut":                   ("Kayısı",            "Meyve"),
    "çağla":                        ("Kayısı",            "Meyve"),
    "çağla (kayısı)":               ("Kayısı",            "Meyve"),
    # ERİK
    "erik":                         ("Erik",              "Meyve"),
    "erik (papaz)":                 ("Erik",              "Meyve"),
    "erik papaz (can)":             ("Erik",              "Meyve"),
    "erik (can)":                   ("Erik",              "Meyve"),
    "erik (yeşil)":                 ("Erik",              "Meyve"),
    "erik alyanak":                 ("Erik",              "Meyve"),
    "erik anjelik":                 ("Erik",              "Meyve"),
    "erik yeşil":                   ("Erik",              "Meyve"),
    "erik  papaz":                  ("Erik",              "Meyve"),
    "erik papaz (can)":             ("Erik",              "Meyve"),
    "eri̇k papaz (can)":            ("Erik",              "Meyve"),
    "anjeli̇ka mürdüm":             ("Erik",              "Meyve"),
    # NAR
    "nar":                          ("Nar",               "Meyve"),
    # AYVA
    "ayva":                         ("Ayva",              "Meyve"),
    # KİVİ
    "kivi":                         ("Kivi",              "Meyve"),
    "kivi (yerli)":                 ("Kivi",              "Meyve"),
    # YENİ DÜNYA
    "yeni dünya":                   ("Yeni Dünya (Malta)", "Meyve"),
    "yeni̇ dünya (malta eri̇ği̇)":  ("Yeni Dünya (Malta)", "Meyve"),
    "yeni dünya (malta)":           ("Yeni Dünya (Malta)", "Meyve"),
    "yeni dünya(malta eriği) (yeni dünya (malta eriği))": ("Yeni Dünya (Malta)", "Meyve"),
    "yeni dünya(malta eriği) yeni dünya (malta eriği)":   ("Yeni Dünya (Malta)", "Meyve"),
    "maltaeriği":                   ("Yeni Dünya (Malta)", "Meyve"),
    "malta":                        ("Yeni Dünya (Malta)", "Meyve"),
    # DUT
    "dut":                          ("Dut",               "Meyve"),
    "dut (kara)":                   ("Dut",               "Meyve"),
    "dut kara":                     ("Dut",               "Meyve"),
    "dut diğer":                    ("Dut",               "Meyve"),
    "karadut":                      ("Dut",               "Meyve"),
    # ANANAS / EKZOTİK
    "ananas":                       ("Ananas",            "Meyve"),
    "avokado":                      ("Avokado",           "Meyve"),
    "avakado":                      ("Avokado",           "Meyve"),
    "mango":                        ("Mango",             "Meyve"),
    "hindistan cevizi":             ("Hindistan Cevizi",  "Meyve"),
    "blue berry":                   ("Yaban Mersini",     "Meyve"),
    "frenk üzümü":                  ("Frenk Üzümü",      "Meyve"),
    "altınçilek (gooseberry)":      ("Frenk Üzümü",      "Meyve"),
    "ejder meyvesi̇ (pi̇tahaya)":   ("Ejder Meyvesi",    "Meyve"),
    "çağla badem":                  ("Badem",             "Meyve"),
    "badem":                        ("Badem",             "Meyve"),
}

# Normalizer yardımcı fonksiyonu
_ws = re.compile(r"\s+")

def _norm_key(s: str) -> str:
    s = s.lower().strip()
    s = _ws.sub(" ", s)
    return s

def urun_normalize(raw: str):
    """Ham ürün adını standart ada ve kategoriye çevir.
    Döndürür: (standart_ad, kategori) veya (temiz_ad, 'Diğer')"""
    key = _norm_key(raw)
    if key in URUN_MAP:
        return URUN_MAP[key]
    # Kısmi eşleştirme — key içinde geçen ilk eşleşme
    for k, v in URUN_MAP.items():
        if k in key or key in k:
            return v
    # Bulunamazsa temiz hâliyle döndür
    return (raw.strip().title(), "Diğer")

# ─────────────────────────────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────────────────────────────
def tarih_parse(s: str):
    """DD.MM.YYYY → YYYY-MM-DD"""
    s = s.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s  # bilinmeyen format → olduğu gibi bırak

def scrape_harman_prices():
    print("Harmanapps.com veri çekme başlatılıyor... (curl_cffi Cloudflare bypass)")

    base_url = "https://harmanapps.com/hal-borsa-fiyatlari"
    all_data = []

    try:
        print("Ana sayfa yükleniyor...")
        response = requests.get(base_url, impersonate="chrome110", timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        city_elements = soup.select("a[href*='/hal-borsa-fiyatlari/']")
        cities = []
        seen = set()
        for c in city_elements:
            name = c.get_text(strip=True)
            href = c.get("href")
            if name and href and href not in seen:
                seen.add(href)
                cities.append({"name": name, "url": href})

        # Türkiye Geneli sayfasını çıkar
        cities = [c for c in cities if "türkiye" not in c["name"].lower()]
        print(f"Toplam {len(cities)} şehir bulundu.")

        for city in cities:
            page = 1
            print(f"  -> {city['name']} ... ", end="", flush=True)
            city_rows = 0
            prev_page_signature = None

            while True:
                url = f"{city['url']}?page={page}"
                res = requests.get(url, impersonate="chrome110", timeout=15)
                page_soup = BeautifulSoup(res.text, "html.parser")

                price_grids = page_soup.select(".price-grid")
                if not price_grids:
                    break

                # Sayfa içeriğini imzala — aynı imza gelirse son sayfayı tekrar gördük, dur
                page_signature = frozenset(
                    g.parent.get_text(strip=True)[:60] for g in price_grids
                )
                if page_signature == prev_page_signature:
                    break
                prev_page_signature = page_signature

                for grid in price_grids:
                    try:
                        card = grid.parent
                        text = card.get_text(separator='\n', strip=True)
                        lines = [l.strip() for l in text.split('\n') if l.strip()]

                        if len(lines) < 3:
                            continue

                        product_raw = lines[0]
                        min_p = max_p = date_s = ""

                        for i, line in enumerate(lines):
                            if "En Düşük" in line and (i + 1) < len(lines):
                                val = lines[i + 1].split()[0]
                                if "," in val or "." in val or val.isdigit():
                                    min_p = val.replace(",", ".")
                            if "En Yüksek" in line and (i + 1) < len(lines):
                                val = lines[i + 1].split()[0]
                                if "," in val or "." in val or val.isdigit():
                                    max_p = val.replace(",", ".")
                            if "." in line and len(line) >= 10:
                                if line.count(".") == 2 and len(line.split()[0]) == 10:
                                    date_s = line.split()[0]

                        try:
                            ed = float(min_p) if min_p else None
                            ey = float(max_p) if max_p else None
                            if ed is not None and ey is not None and ed > ey:
                                ed, ey = ey, ed
                            if not ed or not ey or ed <= 0 or ey <= 0:
                                continue
                        except ValueError:
                            continue

                        tarih_iso = tarih_parse(date_s) if date_s else datetime.today().strftime("%Y-%m-%d")
                        urun_std, kategori = urun_normalize(product_raw)

                        all_data.append({
                            "tarih":     tarih_iso,
                            "sehir":     city["name"],
                            "urun":      urun_std,
                            "kategori":  kategori,
                            "en_dusuk":  round(ed, 2),
                            "en_yuksek": round(ey, 2),
                            "veri_turu": "gercek",
                        })
                        city_rows += 1
                    except Exception:
                        continue

                page += 1

            print(f"{city_rows} satır ({page-1} sayfa)")

    except Exception as e:
        print(f"\nHata: {e}")
        raise

    if all_data:
        today_str = datetime.now().strftime("%d_%m_%Y")
        output_file = f"harman_hal_fiyat_{today_str}.csv"
        df = pd.DataFrame(all_data)
        df = df.sort_values(["sehir", "kategori", "urun"]).reset_index(drop=True)
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\nToplam {len(df)} satır -> {output_file}")
        print(f"Normalize edilen ürünler: {df['urun'].nunique()} benzersiz")
        print(f"Kategoriler: {df['kategori'].value_counts().to_dict()}")
    else:
        print("\nVeri çekilemedi.")


if __name__ == "__main__":
    scrape_harman_prices()
