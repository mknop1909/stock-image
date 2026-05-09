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
        "prevClose": d.get("pc", 0),
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
    pad = 4
    pts = []
    for i, v in enumerate(closes):
        px = x + pad + int(i / (len(closes) - 1) * (w - pad * 2))
        py = y + h - pad - int((v - mn) / rng * (h - pad * 2))
        pts.append((px, py))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i+1]], fill=0, width=3)
    lx, ly = pts[-1]
    draw.ellipse([lx-4, ly-4, lx+4, ly+4], fill=0)

def fp(n):
    if not n:
        return "--"
    return f"${n:,.2f}"

def fc(change, pct):
    if change is None:
        return "--"
    sign = "+" if change >= 0 else "-"
    return f"{sign} ${abs(change):.2f} ({'+' if change >= 0 else ''}{pct:.2f}%)"

def generate_image(quotes, candles):
    img = Image.new("L", (WIDTH, HEIGHT), color=255)
    draw = ImageDraw.Draw(img)

    try:
        BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_ticker = ImageFont.truetype(BOLD, 36)
        font_price  = ImageFont.truetype(BOLD, 40)
        font_change = ImageFont.truetype(BOLD, 20)
        font_label  = ImageFont.truetype(BOLD, 16)
        font_value  = ImageFont.truetype(BOLD, 18)
        font_header = ImageFont.truetype(BOLD, 16)
    except:
        font_ticker = font_price = font_change = font_label = font_value = font_header = ImageFont.load_default()

    # Zahlaví
    draw.rectangle([0, 0, WIDTH, 38], fill=0)
    draw.text((14, 10), "PREHLED AKCII", font=font_header, fill=255)
    now = datetime.datetime.now().strftime("%d.%m.%Y  %H:%M")
    draw.text((WIDTH - 155, 10), now, font=font_header, fill=255)

    card_w = (WIDTH - 40) // 3
    card_y = 46
    card_h = HEIGHT - card_y - 28
    margin = 10

    for i, s in enumerate(STOCKS):
        cx = margin + i * (card_w + margin)
        cy = card_y
        q = quotes.get(s["id"], {})

        draw.rectangle([cx, cy, cx + card_w, cy + card_h], outline=0, width=3)

        draw.text((cx + 10, cy + 8),  s["label"], font=font_ticker, fill=0)
        draw.text((cx + 10, cy + 50), s["name"],  font=font_label,  fill=60)

        draw.line([cx + 6, cy + 72, cx + card_w - 6, cy + 72], fill=0, width=2)

        draw.text((cx + 10, cy + 78),  fp(q.get("price")), font=font_price,  fill=0)
        draw.text((cx + 10, cy + 124), fc(q.get("change"), q.get("changePct", 0)), font=font_change, fill=0)

        draw.line([cx + 6, cy + 152, cx + card_w - 6, cy + 152], fill=100, width=1)

        draw.text((cx + 10, cy + 158), "Max:",      font=font_label, fill=80)
        draw.text((cx + 60, cy + 158), fp(q.get("high")), font=font_value, fill=0)

        draw.text((cx + 10, cy + 180), "Min:",      font=font_label, fill=80)
        draw.text((cx + 60, cy + 180), fp(q.get("low")),  font=font_value, fill=0)

        draw.text((cx + 10, cy + 202), "Open:",     font=font_label, fill=80)
        draw.text((cx + 75, cy + 202), fp(q.get("open")), font=font_value, fill=0)

        draw.line([cx + 6, cy + 226, cx + card_w - 6, cy + 226], fill=150, width=1)

        draw_sparkline(draw, candles.get(s["id"], []), cx + 8, cy + 230, card_w - 16, card_h - 234)

    draw.line([0, HEIGHT - 24, WIDTH, HEIGHT - 24], fill=100, width=1)
    draw.text((10, HEIGHT - 20), "Finnhub.io | zivyobraz.eu", font=font_label, fill=120)

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
