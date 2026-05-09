import requests
import os
import datetime
import time
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

WIDTH  = 800
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

def fp(n):
    if not n:
        return "--"
    return f"${n:,.2f}"

def fc(change, pct):
    if change is None:
        return "--"
    sign = "+" if change >= 0 else "-"
    return f"{sign}${abs(change):.2f} ({'+' if change>=0 else ''}{pct:.1f}%)"

def generate_image(quotes):
    img  = Image.new("RGB", (WIDTH, HEIGHT), color="white")
    draw = ImageDraw.Draw(img)

    try:
        BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        f_ticker = ImageFont.truetype(BOLD, 52)
        f_price  = ImageFont.truetype(BOLD, 56)
        f_change = ImageFont.truetype(BOLD, 30)
        f_label  = ImageFont.truetype(BOLD, 24)
        f_value  = ImageFont.truetype(BOLD, 28)
        f_name   = ImageFont.truetype(REG,  22)
        f_header = ImageFont.truetype(BOLD, 20)
    except:
        f_ticker = f_price = f_change = f_label = f_value = f_name = f_header = ImageFont.load_default()

    # Zahlaví
    draw.rectangle([0, 0, WIDTH, 44], fill="black")
    draw.text((14, 10), "PREHLED AKCII", font=f_header, fill="white")
    now = datetime.datetime.now().strftime("%d.%m.%Y  %H:%M")
    draw.text((WIDTH - 210, 10), now, font=f_header, fill="white")

    card_w = (WIDTH - 40) // 3   # ~253px
    card_y = 50
    card_h = HEIGHT - card_y - 4
    margin = 10

    for i, s in enumerate(STOCKS):
        cx = margin + i * (card_w + margin)
        cy = card_y
        q  = quotes.get(s["id"], {})

        # Ramecek
        draw.rectangle([cx, cy, cx + card_w, cy + card_h], outline="black", width=3)

        # Ticker
        draw.text((cx + 8, cy + 6), s["label"], font=f_ticker, fill="black")

        # Nazev firmy
        draw.text((cx + 8, cy + 62), s["name"], font=f_name, fill="black")

        # Oddelovac
        draw.line([cx + 4, cy + 90, cx + card_w - 4, cy + 90], fill="black", width=2)

        # Cena
        draw.text((cx + 8, cy + 96), fp(q.get("price")), font=f_price, fill="black")

        # Zmena
        draw.text((cx + 8, cy + 158), fc(q.get("change"), q.get("changePct", 0)), font=f_change, fill="black")

        # Oddelovac
        draw.line([cx + 4, cy + 196, cx + card_w - 4, cy + 196], fill="black", width=2)

        # Max
        draw.text((cx + 8,  cy + 204), "Max:", font=f_label, fill="black")
        draw.text((cx + 8,  cy + 232), fp(q.get("high")), font=f_value, fill="black")

        # Min
        draw.text((cx + 8,  cy + 270), "Min:", font=f_label, fill="black")
        draw.text((cx + 8,  cy + 298), fp(q.get("low")),  font=f_value, fill="black")

        # Open
        draw.text((cx + 8,  cy + 336), "Open:", font=f_label, fill="black")
        draw.text((cx + 8,  cy + 364), fp(q.get("open")), font=f_value, fill="black")

    return img

def app(environ, start_response):
    api_key = os.environ.get("FINNHUB_API_KEY", "")

    if not api_key:
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [b"Chybi FINNHUB_API_KEY"]

    try:
        quotes = {}
        for s in STOCKS:
            try:
                quotes[s["id"]] = get_quote(s["id"], api_key)
            except:
                quotes[s["id"]] = {}

        img = generate_image(quotes)
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
