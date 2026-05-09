import requests
import os
import datetime
import time
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

WIDTH  = 800
HEIGHT = 480

STOCKS = [
    {"id": "OKLO",  "label": "OKLO"},
    {"id": "BRK.B", "label": "BRK.B"},
    {"id": "GOOGL",  "label": "GOOGL"},
]

def get_quote(symbol, api_key):
    r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}", timeout=8)
    d = r.json()
    return {
        "price":     d.get("c", 0),
        "change":    d.get("d", 0),
        "changePct": d.get("dp", 0),
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
        f_ticker = ImageFont.truetype(BOLD, 72)
        f_price  = ImageFont.truetype(BOLD, 64)
        f_change = ImageFont.truetype(BOLD, 36)
        f_label  = ImageFont.truetype(BOLD, 28)
        f_value  = ImageFont.truetype(BOLD, 32)
    except:
        f_ticker = f_price = f_change = f_label = f_value = ImageFont.load_default()

    # 3 sloupce, bez zahlaví – plná výška
    col_w  = WIDTH // 3        # 266px
    col_h  = HEIGHT            # 480px

    for i, s in enumerate(STOCKS):
        cx = i * col_w
        q  = quotes.get(s["id"], {})

        # Svislý oddělovač
        if i > 0:
            draw.line([cx, 0, cx, HEIGHT], fill="black", width=3)

        # Ticker
        draw.text((cx + 8, 4), s["label"], font=f_ticker, fill="black")

        # Vodorovný oddělovač
        draw.line([cx + 4, 80, cx + col_w - 4, 80], fill="black", width=2)

        # Cena
        draw.text((cx + 8, 86), fp(q.get("price")), font=f_price, fill="black")

        # Zmena
        draw.text((cx + 8, 158), fc(q.get("change"), q.get("changePct", 0)), font=f_change, fill="black")

        # Oddelovac
        draw.line([cx + 4, 202, cx + col_w - 4, 202], fill="black", width=2)

        # Max
        draw.text((cx + 8, 208), "Max:", font=f_label, fill="black")
        draw.text((cx + 8, 240), fp(q.get("high")), font=f_value, fill="black")

        # Min
        draw.text((cx + 8, 282), "Min:", font=f_label, fill="black")
        draw.text((cx + 8, 314), fp(q.get("low")),  font=f_value, fill="black")

        # Datum vpravo dole v poslednim sloupci
        if i == 2:
            now = datetime.datetime.now().strftime("%d.%m.%Y  %H:%M")
            draw.text((cx + 8, HEIGHT - 36), now, font=f_label, fill="black")

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
