import requests
import os
import datetime
import time
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

WIDTH = 800
HEIGHT = 480

STOCKS = [
    {"id": "OKLO",  "label": "OKLO",  "name": "Oklo Inc."},
    {"id": "BRK.B", "label": "BRK.B", "name": "Berkshire B"},
    {"id": "GOOGL", "label": "GOOGL", "name": "Alphabet"},
]

def get_quote(symbol, api_key):
    r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}", timeout=8)
    d = r.json()
    return {
        "price":     d.get("c", 0),
        "change":    d.get("d", 0),
        "changePct": d.get("dp", 0),
        "open":      d.get("o", 0),
        "high":      d.get("h", 0),
        "low":       d.get("l", 0),
    }

def get_candles(symbol, api_key):
    to_ts = int(time.time())
    from_ts = to_ts - 60 * 60 * 24 * 35
    r = requests.get(
        f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}&token={api_key}",
        timeout=8
    )
    d = r.json()
    if d.get("s") == "ok":
        return [v for v in d.get("c", []) if v]
    return []

def draw_sparkline(draw, closes, x, y, w, h):
    if len(closes) < 2:
        return
    mn, mx = min(closes), max(closes)
    rng = mx - mn or 1
    pad = 6
    pts = []
    for i, v in enumerate(closes):
        px = x + pad + int(i / (len(closes) - 1) * (w - pad * 2))
        py = y + h - pad - int((v - mn) / rng * (h - pad * 2))
        pts.append((px, py))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i+1]], fill="black", width=4)
    lx, ly = pts[-1]
    draw.ellipse([lx-5, ly-5, lx+5, ly+5], fill="black")

def fp(n):
    if not n:
        return "--"
    return f"${n:,.2f}"

def fc(change, pct):
    if change is None:
        return "--"
    sign = "+" if change >= 0 else "-"
    return f"{sign}${abs(change):.2f}  ({'+' if change >= 0 else ''}{pct:.1f}%)"

def generate_image(quotes, candles):
    # Ciste bila, rezim "1" = ciste cernobily bez antialiasingu
    img = Image.new("RGB", (WIDTH, HEIGHT), color="white")
    draw = ImageDraw.Draw(img)

    try:
        BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f_ticker  = ImageFont.truetype(BOLD, 42)   # OKLO
        f_price   = ImageFont.truetype(BOLD, 46)   # $12.34
        f_change  = ImageFont.truetype(BOLD, 24)   # +1.23
        f_label   = ImageFont.truetype(BOLD, 18)   # Max / Min
        f_value   = ImageFont.truetype(BOLD, 22)   # hodnoty
        f_header  = ImageFont.truetype(BOLD, 18)   # zahlaví
    except:
        f_ticker = f_price = f_change = f_label = f_value = f_header = ImageFont.load_default()

    BLACK = "black"
    WHITE = "white"

    # ── Záhlaví ──────────────────────────────────────────────
    draw.rectangle([0, 0, WIDTH, 42], fill=BLACK)
    draw.text((14, 10), "AKCIE", font=f_header, fill=WHITE)
    now = datetime.datetime.now().strftime("%d.%m.%Y   %H:%M")
    draw.text((WIDTH - 200, 10), now, font=f_header, fill=WHITE)

    # ── 3 karty ──────────────────────────────────────────────
    card_w  = (WIDTH - 40) // 3   # 253px
    card_y  = 50
    card_h  = HEIGHT - card_y - 4
    margin  = 10

    for i, s in enumerate(STOCKS):
        cx = margin + i * (card_w + margin)
        cy = card_y
        q  = quotes.get(s["id"], {})

        # Rámeček – silný
        draw.rectangle([cx, cy, cx + card_w, cy + card_h], outline=BLACK, width=4)

        # Ticker – velký tučný
        draw.text((cx + 10, cy + 8), s["label"], font=f_ticker, fill=BLACK)

        # Oddělovač
        draw.line([cx + 4, cy + 58, cx + card_w - 4, cy + 58], fill=BLACK, width=3)

        # Cena
        draw.text((cx + 10, cy + 64), fp(q.get("price")), font=f_price, fill=BLACK)

        # Změna
        draw.text((cx + 10, cy + 116), fc(q.get("change"), q.get("changePct", 0)), font=f_change, fill=BLACK)

        # Oddělovač
        draw.line([cx + 4, cy + 148, cx + card_w - 4, cy + 148], fill=BLACK, width=2)

        # Max
        draw.text((cx + 10, cy + 154), "Max:", font=f_label, fill=BLACK)
        draw.text((cx + 10, cy + 175), fp(q.get("high")), font=f_value, fill=BLACK)

        # Min
        draw.text((cx + card_w//2, cy + 154), "Min:", font=f_label, fill=BLACK)
        draw.text((cx + card_w//2, cy + 175), fp(q.get("low")), font=f_value, fill=BLACK)

        # Open
        draw.text((cx + 10, cy + 204), "Open:", font=f_label, fill=BLACK)
        draw.text((cx + 10, cy + 225), fp(q.get("open")), font=f_value, fill=BLACK)

        # Oddělovač před grafem
        draw.line([cx + 4, cy + 252, cx + card_w - 4, cy + 252], fill=BLACK, width=2)

        # Sparkline
        draw_sparkline(draw, candles.get(s["id"], []),
                       cx + 6, cy + 256, card_w - 12, card_h - 260)

    return img

def app(environ, start_response):
    api_key = os.environ.get("FINNHUB_API_KEY", "")

    if not api_key:
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [b"Chybi FINNHUB_API_KEY"]

    try:
        quotes, candles = {}, {}
        for s in STOCKS:
            try:
                quotes[s["id"]]  = get_quote(s["id"], api_key)
                candles[s["id"]] = get_candles(s["id"], api_key)
            except:
                quotes[s["id"]]  = {}
                candles[s["id"]] = []

        img = generate_image(quotes, candles)
        buf = BytesIO()
        img.save(buf, format="PNG")
        png_data = buf.getvalue()

        start_response("200 OK", [
            ("Content-Type", "image/png"),
            ("Content-Length", str(len(png_data))),
            ("Cache-Control", "no-cache, no-store, must-revalidate"),
        ])
        return [png_data]

    except Exception as e:
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [str(e).encode()]
