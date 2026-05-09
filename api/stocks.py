from http.server import BaseHTTPRequestHandler
import requests
import json
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import datetime

# Rozlišení pro 7.3" 3-barevný e-ink (800x480)
WIDTH = 800
HEIGHT = 480

STOCKS = [
    {"id": "OKLO",  "label": "OKLO",  "name": "Oklo Inc."},
    {"id": "BRK.B", "label": "BRK.B", "name": "Berkshire B"},
    {"id": "GOOGL", "label": "GOOGL", "name": "Alphabet"},
]

def get_quote(symbol, api_key):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
    r = requests.get(url, timeout=8)
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
    import time
    to_ts = int(time.time())
    from_ts = to_ts - 60 * 60 * 24 * 35
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}&token={api_key}"
    r = requests.get(url, timeout=8)
    d = r.json()
    if d.get("s") == "ok":
        return [v for v in d.get("c", []) if v]
    return []

def draw_sparkline(draw, closes, x, y, w, h):
    if len(closes) < 2:
        draw.text((x + 4, y + h // 2), "—", fill=0)
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
        draw.line([pts[i], pts[i+1]], fill=0, width=2)
    # Tečka na konci
    lx, ly = pts[-1]
    draw.ellipse([lx-3, ly-3, lx+3, ly+3], fill=0)

def fmt_price(n):
    if n is None or n == 0:
        return "—"
    return f"${n:,.2f}"

def fmt_change(n, pct):
    if n is None:
        return "—"
    arrow = "▲" if n >= 0 else "▼"
    sign = "+" if n >= 0 else ""
    return f"{arrow} {sign}{n:.2f} ({sign}{pct:.2f}%)"

def generate_image(quotes, candles):
    img = Image.new("L", (WIDTH, HEIGHT), color=255)  # bílé pozadí, grayscale
    draw = ImageDraw.Draw(img)

    # Pokus o načtení fontu, fallback na výchozí
    try:
        font_big   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_med   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        font_tiny  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        font_big = font_med = font_small = font_tiny = font_title = ImageFont.load_default()

    # Záhlaví
    draw.rectangle([0, 0, WIDTH, 32], fill=0)
    draw.text((16, 7), "PŘEHLED AKCIÍ", font=font_title, fill=255)
    now = datetime.datetime.now().strftime("%d.%m.%Y  %H:%M")
    draw.text((WIDTH - 130, 7), now, font=font_title, fill=255)

    # 3 sloupce karet
    card_w = (WIDTH - 40) // 3  # ~253px
    card_h = 230
    card_y = 44
    margin = 10

    for i, s in enumerate(STOCKS):
        cx = margin + i * (card_w + margin)
        cy = card_y

        # Rámeček karty
        draw.rectangle([cx, cy, cx + card_w, cy + card_h], outline=0, width=2)

        q = quotes.get(s["id"], {})
        price = q.get("price", 0)
        change = q.get("change", 0)
        pct = q.get("changePct", 0)

        # Ticker
        draw.text((cx + 10, cy + 8), s["label"], font=font_med, fill=0)
        # Název
        draw.text((cx + 10, cy + 30), s["name"], font=font_tiny, fill=80)

        # Oddělovač
        draw.line([cx + 8, cy + 46, cx + card_w - 8, cy + 46], fill=180, width=1)

        # Cena
        draw.text((cx + 10, cy + 52), fmt_price(price), font=font_big, fill=0)

        # Změna
        chg_text = fmt_change(change, pct)
        draw.text((cx + 10, cy + 86), chg_text, font=font_small, fill=0)

        # Meta hodnoty
        draw.text((cx + 10, cy + 108), "Otevření", font=font_tiny, fill=120)
        draw.text((cx + 10, cy + 121), fmt_price(q.get("open")), font=font_small, fill=0)

        draw.text((cx + card_w//2, cy + 108), "Max / Min", font=font_tiny, fill=120)
        draw.text((cx + card_w//2, cy + 121), f"{fmt_price(q.get('high'))} / {fmt_price(q.get('low'))}", font=font_tiny, fill=0)

        draw.text((cx + 10, cy + 142), "Předchozí zavření", font=font_tiny, fill=120)
        draw.text((cx + 10, cy + 155), fmt_price(q.get("prevClose")), font=font_small, fill=0)

        # Oddělovač před grafem
        draw.line([cx + 8, cy + 172, cx + card_w - 8, cy + 172], fill=200, width=1)

        # Sparkline graf
        spark_data = candles.get(s["id"], [])
        draw.text((cx + 10, cy + 176), "30 dní", font=font_tiny, fill=150)
        draw_sparkline(draw, spark_data, cx + 8, cy + 188, card_w - 16, 36)

    # Patička
    draw.line([0, HEIGHT - 22, WIDTH, HEIGHT - 22], fill=180, width=1)
    draw.text((10, HEIGHT - 17), "Zdroj: Finnhub.io", font=font_tiny, fill=150)
    draw.text((WIDTH - 180, HEIGHT - 17), "zivyobraz.eu / e-ink displej", font=font_tiny, fill=150)

    return img

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        api_key = os.environ.get("FINNHUB_API_KEY", "")

        if not api_key:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Chybi FINNHUB_API_KEY env promenna")
            return

        try:
            quotes = {}
            candles = {}
            for s in STOCKS:
                try:
                    quotes[s["id"]] = get_quote(s["id"], api_key)
                    candles[s["id"]] = get_candles(s["id"], api_key)
                except Exception as e:
                    quotes[s["id"]] = {}
                    candles[s["id"]] = []

            img = generate_image(quotes, candles)

            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            png_data = buf.read()

            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png_data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(png_data)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def log_message(self, format, *args):
        pass
