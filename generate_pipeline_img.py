import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(20, 11))
fig.patch.set_facecolor("#0f1117")
ax.set_facecolor("#0f1117")
ax.set_xlim(0, 20)
ax.set_ylim(0, 11)
ax.axis("off")

# ── PALETTE ──────────────────────────────────────────────────────────
C_BRONZE_HDR = "#92400e"
C_BRONZE_BOX = "#1c1208"
C_BRONZE_BOR = "#78350f"
C_BRONZE_TXT = "#fde68a"
C_BRONZE_SUB = "#d97706"

C_SILVER_HDR = "#1e3a5f"
C_SILVER_BOX = "#0c1929"
C_SILVER_BOR = "#2563eb"
C_SILVER_TXT = "#bfdbfe"
C_SILVER_SUB = "#60a5fa"

C_TRUNK_HDR  = "#064e3b"
C_TRUNK_BOX  = "#022c1e"
C_TRUNK_BOR  = "#059669"
C_TRUNK_TXT  = "#6ee7b7"

C_GOLD_HDR   = "#78350f"
C_GOLD_BOX   = "#1a1200"
C_GOLD_BOR   = "#d97706"
C_GOLD_TXT   = "#fbbf24"
C_GOLD_SUB   = "#f59e0b"

C_ARROW      = "#4b5563"
C_ARROW2     = "#059669"
C_BG_DARK    = "#161b22"
WHITE        = "#f1f5f9"
GREY         = "#94a3b8"
LGREY        = "#64748b"

def hdr(ax, x, y, w, h, color, txt, txt_color):
    r = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                       fc=color, ec=color, zorder=3)
    ax.add_patch(r)
    ax.text(x + w/2, y + h/2, txt, ha="center", va="center",
            fontsize=11, fontweight="bold", color=txt_color, zorder=4)

def box(ax, x, y, w, h, fc, ec, lines, sizes=None, colors=None):
    r = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                       fc=fc, ec=ec, linewidth=1.2, zorder=3)
    ax.add_patch(r)
    n = len(lines)
    pad = 0.13
    step = (h - 2*pad) / max(n, 1)
    for i, line in enumerate(lines):
        yy = y + h - pad - step*(i+0.5)
        sz = sizes[i] if sizes else 8.5
        co = colors[i] if colors else WHITE
        ax.text(x + 0.12, yy, line, ha="left", va="center",
                fontsize=sz, color=co, zorder=4, fontfamily="monospace")

def arrow(ax, x1, y1, x2, y2, color=C_ARROW, lw=2.5, head=0.25):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=f"-|>,head_width={head},head_length=0.15",
                                color=color, lw=lw),
                zorder=5)

def label_arrow(ax, x, y, txt, color=LGREY):
    ax.text(x, y, txt, ha="center", va="center",
            fontsize=7.5, color=color, zorder=6, fontstyle="italic")

# ═══════════════════════════════════════════════════════════════════
# TITLE
# ═══════════════════════════════════════════════════════════════════
ax.text(10, 10.6, "GıdaRadar — Medallion Data Pipeline",
        ha="center", va="center", fontsize=16, fontweight="bold",
        color=WHITE, zorder=5)
ax.text(10, 10.25, "s3://s3-bbuckett/   ·   Apache Spark on AWS EMR   ·   2019 – 2026",
        ha="center", va="center", fontsize=8.5, color=LGREY, zorder=5)

# ═══════════════════════════════════════════════════════════════════
# COLUMN POSITIONS
# ═══════════════════════════════════════════════════════════════════
# Bronze: x=0.25..4.6   Silver: x=5.2..9.5   Trunk: x=10.5..13.4  Gold: x=14.7..19.7
B_X, B_W = 0.25, 4.35
S_X, S_W = 5.20, 4.35
T_X, T_W = 10.40, 3.10
G_X, G_W = 14.30, 5.45
COL_TOP = 9.90
COL_BOT = 0.30

# ── COLUMN BACKGROUNDS ───────────────────────────────────────────
for cx, cw, cc in [
    (B_X-0.1, B_W+0.2, "#1a0d00"),
    (S_X-0.1, S_W+0.2, "#060f1e"),
    (T_X-0.1, T_W+0.2, "#021109"),
    (G_X-0.1, G_W+0.2, "#120d00"),
]:
    bg = FancyBboxPatch((cx, COL_BOT-0.05), cw, COL_TOP-COL_BOT+0.1,
                        boxstyle="round,pad=0.1", fc=cc, ec="#21262d",
                        linewidth=0.8, zorder=1)
    ax.add_patch(bg)

# ── HEADERS ──────────────────────────────────────────────────────
hdr(ax, B_X, 9.45, B_W, 0.50, C_BRONZE_HDR, "[ BRONZE ]  Ham Veri", C_BRONZE_TXT)
hdr(ax, S_X, 9.45, S_W, 0.50, C_SILVER_HDR, "[ SILVER ]  Temiz & Standart", C_SILVER_TXT)
hdr(ax, T_X, 9.45, T_W, 0.50, C_TRUNK_HDR,  "[ SILVER TRUNK ]", C_TRUNK_TXT)
hdr(ax, G_X, 9.45, G_W, 0.50, C_GOLD_HDR,   "[ GOLD ]  Analytics-Ready", C_GOLD_TXT)

# ═══════════════════════════════════════════════════════════════════
# BRONZE BOXES
# ═══════════════════════════════════════════════════════════════════
bronze_items = [
    # (label, sublabel, y, h)
    ("bronze/hal_all",           "İBB + Harman Hal · ~8 M satır · 2019-2026",  8.85, 0.52),
    ("bronze/market",            "marketfiyati.org.tr scraper · ~2 M · 2026",  8.22, 0.52),
    ("bronze/market_synthetic",  "Sentetik geçmiş · ~18 M satır · 2019-2025",  7.59, 0.52),
    ("bronze/tcmb",              "TCMB EVDS · USD/TRY, TÜFE · ~25 K · 2019+",  6.96, 0.52),
    ("bronze/epias/{dataset}",   "26 dataset · ~4 M/dataset · saatlik · 2019+", 6.33, 0.52),
    ("bronze/weather",           "Open-Meteo · 81 şehir · ~12 M · saatlik",     5.70, 0.52),
    ("bronze/gdelt",             "GDELT S3 · haber · ~30 M · 2017-2026 (gap)", 5.07, 0.52),
    ("bronze/akaryakit",         "Akaryakıt scraper · ~600 K satır · 2019+",    4.44, 0.52),
    ("bronze/commodities",       "Global emtia · Wheat/Brent · ~60 K · 2019+",  3.81, 0.52),
]

for path, sub, y, h in bronze_items:
    box(ax, B_X+0.05, y, B_W-0.1, h,
        C_BRONZE_BOX, C_BRONZE_BOR,
        [path, sub],
        sizes=[9, 7.5],
        colors=[C_BRONZE_TXT, C_BRONZE_SUB])

# ═══════════════════════════════════════════════════════════════════
# SILVER BOXES
# ═══════════════════════════════════════════════════════════════════
silver_items = [
    ("silver/hal_prices",     "date,city,product_name,price_min/max/avg · ~8 M",   8.60, 0.65),
    ("silver/market_prices",  "UNION real+synth · per-kg · ~20 M · year/month/day", 7.84, 0.65),
    ("silver/tcmb",           "tall format · series_name,value,date · ~25 K",       7.08, 0.65),
    ("silver/epias/...",      "26 tablo · timestamp→TIMESTAMP · year/month",         6.32, 0.65),
    ("silver/weather_daily",  "saatlik→günlük agg · temp_min/max,precip · ~500 K",  5.56, 0.65),
    ("silver/gdelt_daily",    "makale→günlük özet · food/turkey flag · ~3 K",        4.80, 0.65),
    ("silver/akaryakit",      "date,city,brand,fuel_type,price_tl · ~600 K",         4.04, 0.65),
    ("silver/commodities",    "commodity_name,price_usd · 10 emtia · ~60 K",         3.28, 0.65),
]

for path, sub, y, h in silver_items:
    box(ax, S_X+0.05, y, S_W-0.1, h,
        C_SILVER_BOX, C_SILVER_BOR,
        [path, sub],
        sizes=[9, 7.5],
        colors=[C_SILVER_TXT, C_SILVER_SUB])

# ═══════════════════════════════════════════════════════════════════
# SILVER TRUNK
# ═══════════════════════════════════════════════════════════════════
trunk_y = 4.50
trunk_h = 4.70
r = FancyBboxPatch((T_X+0.05, trunk_y), T_W-0.1, trunk_h,
                   boxstyle="round,pad=0.07",
                   fc=C_TRUNK_BOX, ec=C_TRUNK_BOR, linewidth=2.0, zorder=3)
ax.add_patch(r)

trunk_lines = [
    ("silver/market_hal_joined", 11.5, C_TRUNK_TXT),
    ("", 8, C_TRUNK_TXT),
    ("silver/market_prices", 8.5, "#93c5fd"),
    ("  JOIN hal_market_mapping.csv", 8, LGREY),
    ("  JOIN silver/hal_prices", 8.5, "#93c5fd"),
    ("", 7, ""),
    ("JOIN KEY:", 8, LGREY),
    ("(date, city, product_canonical)", 8, WHITE),
    ("", 7, ""),
    ("FULL OUTER JOIN", 8, "#fbbf24"),
    ("~6 M satır · 2019-2026", 8, LGREY),
    ("Partition: year / month", 8, LGREY),
    ("", 7, ""),
    ("Sütunlar:", 8, LGREY),
    ("hal_price_per_kg", 8, WHITE),
    ("market_price_per_kg", 8, WHITE),
    ("margin_abs, margin_pct", 8, "#fbbf24"),
]

n = len(trunk_lines)
pad = 0.15
step = (trunk_h - 2*pad) / n
for i, (txt, sz, co) in enumerate(trunk_lines):
    yy = trunk_y + trunk_h - pad - step*(i+0.5)
    if txt:
        bold = i == 0
        ax.text(T_X+0.18, yy, txt, ha="left", va="center",
                fontsize=sz, color=co, zorder=4, fontfamily="monospace",
                fontweight="bold" if bold else "normal")

ax.text(T_X+T_W/2, trunk_y+trunk_h+0.18,
        "* Tüm Gold tablolarının kaynağı",
        ha="center", va="center", fontsize=7.5,
        color=C_TRUNK_TXT, style="italic", zorder=5)

# entity resolution note
note_y = 3.60
note_h = 0.75
rn = FancyBboxPatch((T_X+0.05, note_y), T_W-0.1, note_h,
                    boxstyle="round,pad=0.06",
                    fc="#1a0a2e", ec="#7c3aed", linewidth=1.0, zorder=3)
ax.add_patch(rn)
ax.text(T_X+0.18, note_y+note_h-0.18,
        "Entity Resolution (Claude Haiku)",
        ha="left", va="center", fontsize=8, color="#c4b5fd",
        zorder=4, fontweight="bold")
ax.text(T_X+0.18, note_y+note_h*0.42,
        '"Domates Sofralık Sera"',
        ha="left", va="center", fontsize=7.5, color="#a78bfa", zorder=4,
        fontfamily="monospace")
ax.text(T_X+0.18, note_y+0.12,
        '  ↔  "salkim-domates-1-kg"',
        ha="left", va="center", fontsize=7.5, color="#a78bfa", zorder=4,
        fontfamily="monospace")

# ═══════════════════════════════════════════════════════════════════
# GOLD BOXES
# ═══════════════════════════════════════════════════════════════════
gold_items = [
    # (path, script, girdi kısa, soru, y, h)
    ("gold/daily_margin",            "daily_margin.py",       "← market_hal_joined",
     "Hal↔Market marjı + 7-gün rolling  ·  ~6 M satır",          8.60, 0.78),
    ("gold/price_inequality_*/",     "price_inequality.py",   "← market + hal prices",
     "81 şehir fiyat eşitsizliği · CV, spread_pct  ·  ~2 M",      7.71, 0.78),
    ("gold/rockets_feathers",        "rockets_feathers.py",   "← market_hal_joined",
     "Asimetrik fiyat geçişi (β⁺ vs β⁻)  ·  ~120 satır",          6.82, 0.78),
    ("gold/shock_propagation",       "shock_propagation.py",  "← weather + market_hal",
     "Hava şoku → hal → market lag günü  ·  ~50 K",                5.93, 0.78),
    ("gold/news_price_corr",         "news_price_corr.py",    "← gdelt_daily + market_hal",
     "Haber tonu × fiyat değişimi lag corr  ·  ~5 K",              5.04, 0.78),
    ("gold/price_forecast",          "prophet_forecast.py",   "← hal_prices",
     "Prophet tahmin · is_changepoint (pandemi)  ·  top-20 ürün",  4.15, 0.78),
    ("gold/macro_price_corr",        "macro_price_corr.py",   "← hal + tcmb + akaryakit + emtia + epias",
     "Döviz/yakıt/emtia → gıda gecikmesi  ·  ~50 K",               3.26, 0.78),
    ("gold/pandemic_gap",            "pandemic_gap.py",       "← market_hal_joined",
     "2019 baseline vs 2021-2024 marj genişlemesi  ·  ~2 K",       2.37, 0.78),
]

for path, script, src, desc, y, h in gold_items:
    r = FancyBboxPatch((G_X+0.05, y), G_W-0.1, h,
                       boxstyle="round,pad=0.04",
                       fc=C_GOLD_BOX, ec=C_GOLD_BOR,
                       linewidth=1.2, zorder=3)
    ax.add_patch(r)
    pad_i = 0.10
    ax.text(G_X+0.15, y+h-pad_i,      path,   ha="left", va="top",
            fontsize=9, color=C_GOLD_TXT, zorder=4,
            fontfamily="monospace", fontweight="bold")
    ax.text(G_X+0.15, y+h*0.62,       src,    ha="left", va="center",
            fontsize=7.5, color="#6b7280", zorder=4, fontfamily="monospace")
    ax.text(G_X+0.15, y+pad_i+0.05,   desc,   ha="left", va="bottom",
            fontsize=7.5, color=LGREY, zorder=4)
    # script badge
    ax.text(G_X+G_W-0.15, y+h-pad_i, script, ha="right", va="top",
            fontsize=7, color="#374151", zorder=4, fontstyle="italic")

# ═══════════════════════════════════════════════════════════════════
# ARROWS — Bronze → Silver
# ═══════════════════════════════════════════════════════════════════
arrow_pairs_bs = [
    # (bronze_y_mid, silver_y_mid)
    (8.85+0.26, 8.60+0.325),   # hal_all → hal_prices
    (8.22+0.26, 7.84+0.325),   # market → market_prices
    (7.59+0.26, 7.84+0.325),   # market_synthetic → market_prices
    (6.96+0.26, 7.08+0.325),   # tcmb → tcmb
    (6.33+0.26, 6.32+0.325),   # epias → epias
    (5.70+0.26, 5.56+0.325),   # weather → weather_daily
    (5.07+0.26, 4.80+0.325),   # gdelt → gdelt_daily
    (4.44+0.26, 4.04+0.325),   # akaryakit → akaryakit
    (3.81+0.26, 3.28+0.325),   # commodities → commodities
]

for by, sy in arrow_pairs_bs:
    arrow(ax, B_X+B_W+0.05, by, S_X-0.05, sy,
          color=C_ARROW, lw=1.0, head=0.10)

# Spark label on bronze→silver
ax.text((B_X+B_W + S_X)/2, 9.10, "Spark ETL",
        ha="center", va="center", fontsize=7.5, color=LGREY, style="italic")

# ═══════════════════════════════════════════════════════════════════
# ARROWS — Silver → Trunk
# ═══════════════════════════════════════════════════════════════════
# hal_prices → trunk
arrow(ax, S_X+S_W+0.05, 8.60+0.325, T_X-0.05, 7.80, color=C_ARROW2, lw=1.5, head=0.12)
# market_prices → trunk
arrow(ax, S_X+S_W+0.05, 7.84+0.325, T_X-0.05, 7.20, color=C_ARROW2, lw=1.5, head=0.12)

ax.text((S_X+S_W + T_X)/2, 9.10, "silver_joined.py",
        ha="center", va="center", fontsize=7.5, color="#6ee7b7", style="italic")

# ═══════════════════════════════════════════════════════════════════
# ARROWS — Trunk → Gold (main trunk → daily_margin etc.)
# ═══════════════════════════════════════════════════════════════════
trunk_mid_x = T_X + T_W + 0.05
trunk_mid_y = trunk_y + trunk_h / 2

gold_targets = [
    8.60+0.39, 7.71+0.39, 6.82+0.39, 5.93+0.39, 5.04+0.39, 4.15+0.39, 3.26+0.39, 2.37+0.39
]

for gy in gold_targets:
    arrow(ax, trunk_mid_x, trunk_mid_y, G_X-0.05, gy,
          color=C_GOLD_BOR, lw=0.9, head=0.10)

ax.text((T_X+T_W + G_X)/2, 9.10, "Spark Agg",
        ha="center", va="center", fontsize=7.5, color=C_GOLD_SUB, style="italic")

# ── extra arrows for non-trunk gold sources ─────────────────────
# weather → shock_propagation
arrow(ax, S_X+S_W+0.05, 5.56+0.325, G_X-0.05, 5.93+0.39,
      color="#94a3b8", lw=0.7, head=0.08)
# gdelt → news_price_corr
arrow(ax, S_X+S_W+0.05, 4.80+0.325, G_X-0.05, 5.04+0.39,
      color="#94a3b8", lw=0.7, head=0.08)
# hal → price_forecast
arrow(ax, S_X+S_W+0.05, 8.60+0.325, G_X-0.05, 4.15+0.39,
      color="#94a3b8", lw=0.7, head=0.08)
# macro (tcmb/akaryakit/commodities/epias) → macro_price_corr
for sy in [7.08+0.325, 6.32+0.325, 4.04+0.325, 3.28+0.325]:
    arrow(ax, S_X+S_W+0.05, sy, G_X-0.05, 3.26+0.39,
          color="#94a3b8", lw=0.7, head=0.08)

# ═══════════════════════════════════════════════════════════════════
# BOTTOM LEGEND
# ═══════════════════════════════════════════════════════════════════
legend_items = [
    ("#92400e", "Bronze: Ham, dönüşüm yok"),
    ("#2563eb", "Silver: Temizlenmiş, standart şema"),
    ("#059669", "Silver Trunk: Merkezi JOIN tablosu"),
    ("#d97706", "Gold: Analiz-ready aggregate"),
    ("#7c3aed", "Sentetik: 2019-2025 üretilmiş veri"),
]
lx = 0.4
for color, label in legend_items:
    r = FancyBboxPatch((lx, 0.08), 0.22, 0.22, boxstyle="round,pad=0.02",
                       fc=color, ec=color, zorder=5)
    ax.add_patch(r)
    ax.text(lx+0.30, 0.19, label, va="center", fontsize=7.5, color=LGREY, zorder=5)
    lx += 3.6

plt.tight_layout(pad=0.3)
plt.savefig("pipeline_diagram.png", dpi=180, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Kaydedildi: pipeline_diagram.png")
