import requests
import os
import datetime
import time
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

WIDTH = 800
HEIGHT = 480

STOCKS = [
    {"id": "OKLO",  "label": "OKLO"},
    {"id": "BRK.B", "label": "BRK.B"},
    {"id": "GOOGL", "label": "GOOGL"},
]

def get_quote(symbol, api_key):
    r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}", timeout=8)
    d = r.json()
    return {
        "price":     d.get("c", 0),
        "change":    d.get("d", 0),
        "changePct": d.get("dp", 0),
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
    img = Image.new("RGB", (WIDTH, HEIGHT), color="white")
    draw = ImageDraw.Draw(img)

    try:
        BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f_ticker = ImageFont.truetype(BOLD, 100)
        f_price  = ImageFont.truetype(BOLD, 56)
        f_change = ImageFont.truetype(BOLD, 40)
    except:
        f_ticker = f_price = f_change = ImageFont.load_default()

    row_h = HEIGHT // 3  # 160px na radek

    for i, s in enumerate(STOCKS):
        q = quotes.get(s["id"], {})
        cy = i * row_h

        if i > 0:
            draw.line([0, cy, WIDTH, cy], fill="black", width=3)

        # Ticker vlevo nahore
        draw.text((8, cy + 4), s["label"], font=f_ticker, fill="black")

        # Cena vpravo nahore
        price_txt = fp(q.get("price"))
        draw.text((370, cy + 4), price_txt, font=f_price, fill="black")

        # Zmena vpravo dole
        chg_txt = fc(q.get("change"), q.get("changePct", 0))
        draw.text((370, cy + 100), chg_txt, font=f_change, fill="black")

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