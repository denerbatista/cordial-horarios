from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
W, H = 1200, 630


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for path in (
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("/usr/share/fonts/dejavu") / name,
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def rounded_rect(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def shadowed_panel(base: Image.Image, box, radius: int, fill, shadow=(4, 18, 70, 70)):
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    x1, y1, x2, y2 = box
    sd.rounded_rectangle((x1, y1 + 14, x2, y2 + 18), radius=radius, fill=shadow)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(20))
    base.alpha_composite(shadow_layer)
    ImageDraw.Draw(base).rounded_rectangle(box, radius=radius, fill=fill)


def draw_bus_icon(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, fill):
    s = scale
    draw.rounded_rectangle((x, y, x + 56 * s, y + 54 * s), radius=int(12 * s), fill=fill)
    draw.rounded_rectangle((x + 10 * s, y + 11 * s, x + 46 * s, y + 30 * s), radius=int(4 * s), fill="#0024F8")
    draw.ellipse((x + 10 * s, y + 38 * s, x + 22 * s, y + 50 * s), fill="#0024F8")
    draw.ellipse((x + 34 * s, y + 38 * s, x + 46 * s, y + 50 * s), fill="#0024F8")


def draw_route_panel(base: Image.Image):
    draw = ImageDraw.Draw(base)
    panel = (705, 105, 1110, 548)
    shadowed_panel(base, panel, 34, (255, 255, 255, 246))

    draw.text((745, 145), "Próximas saídas", font=font(30, True), fill="#0B0F2C")
    draw.text((745, 186), "Hoje • horários da Cordial", font=font(18), fill="#5B6380")

    # Search route card
    rounded_rect(draw, (745, 230, 1070, 330), 22, "#F4F6FF", "#E4E7F2", 2)
    draw.ellipse((775, 260, 791, 276), fill="#0024F8")
    draw.line((783, 276, 783, 301), fill="#C9CEE0", width=4)
    draw.ellipse((775, 301, 791, 317), outline="#0024F8", width=4)
    draw.text((810, 250), "Aracruz", font=font(23, True), fill="#0B0F2C")
    draw.text((810, 289), "São Mateus", font=font(23, True), fill="#0B0F2C")
    draw.text((1000, 269), "→", font=font(35, True), fill="#0024F8", anchor="mm")

    times = [("06:00", "linha 001"), ("07:20", "via Jacupemba"), ("08:40", "linha 015")]
    y = 360
    for i, (time, label) in enumerate(times):
        fill = "#DDF5E4" if i == 0 else "#EEF0F8"
        accent = "#23C04F" if i == 0 else "#0024F8"
        rounded_rect(draw, (745, y, 1070, y + 52), 18, fill)
        draw.text((770, y + 9), time, font=font(29, True), fill=accent)
        draw.text((875, y + 14), label, font=font(20, True), fill="#2A2F4A")
        if i == 0:
            rounded_rect(draw, (982, y + 13, 1048, y + 39), 13, "#23C04F")
            draw.text((1015, y + 17), "agora", font=font(14, True), fill="white", anchor="ma")
        y += 60


def make_image() -> Image.Image:
    img = Image.new("RGBA", (W, H), "#071470")
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = x / (W - 1)
            v = y / (H - 1)
            r = int(0 + 10 * (1 - v) + 8 * t)
            g = int(24 + 22 * (1 - v) + 8 * t)
            b = int(150 + 85 * (1 - v) - 25 * t)
            px[x, y] = (r, g, b, 255)

    draw = ImageDraw.Draw(img)
    draw.ellipse((790, -175, 1285, 380), fill=(39, 78, 255, 64))
    draw.ellipse((-180, 390, 360, 850), fill=(13, 29, 125, 120))
    for i in range(0, 1200, 56):
        y = 72 + 22 * math.sin(i / 90)
        draw.line((i, y, i + 34, y), fill=(255, 255, 255, 28), width=2)

    # Brand
    rounded_rect(draw, (88, 84, 172, 168), 22, "white")
    draw.text((130, 125), "C", font=font(66, True), fill="#0024F8", anchor="mm")
    draw_bus_icon(draw, 210, 96, 0.78, "white")
    draw.text((88, 206), "Cordial", font=font(86, True), fill="white")
    draw.text((88, 294), "Horários", font=font(86, True), fill="white")

    draw.text(
        (92, 395),
        "Ônibus por origem, destino e dia",
        font=font(36),
        fill=(244, 246, 255, 245),
    )
    draw.text(
        (92, 448),
        "Aracruz • São Mateus • Domingos Martins",
        font=font(25, True),
        fill="#D9FF00",
    )

    rounded_rect(draw, (90, 515, 646, 568), 26, (255, 255, 255, 34), (255, 255, 255, 52), 2)
    draw.text((116, 531), "denerbatista.github.io/cordial-horarios", font=font(20, True), fill=(224, 231, 255, 245))

    draw_route_panel(img)
    return img.convert("RGB")


if __name__ == "__main__":
    image = make_image()
    image.save(SITE / "og-image-v2.png", optimize=True, quality=95)
    image.save(SITE / "og-image.png", optimize=True, quality=95)
