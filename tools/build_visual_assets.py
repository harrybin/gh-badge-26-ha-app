"""Build badge-sized Octocat artwork and native color emoji PNGs."""

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "office"
SOURCE = ROOT / "tools" / "assets" / "octocat-source.jpg"
EMOJI_FONT = Path(r"C:\Windows\Fonts\seguiemj.ttf")


def octocat(source, size):
    with Image.open(source) as original:
        # The supplied thumbnail has a white margin around its circular mark.
        gray = original.convert("L")
        bounds = gray.point(lambda value: 255 if value < 100 else 0).getbbox()
        if bounds is None:
            raise ValueError("Octocat source contains no visible artwork")
        art = original.convert("RGBA").crop(bounds)
    if abs(art.width - art.height) > 3:
        raise ValueError("Expected the supplied circular Octocat artwork")
    mask = Image.new("L", art.size)
    ImageDraw.Draw(mask).ellipse((0, 0, art.width - 1, art.height - 1), fill=255)
    art.putalpha(ImageChops.multiply(art.getchannel("A"), mask))
    result = Image.new("RGBA", (size, size))
    art.thumbnail((size, size), Image.Resampling.LANCZOS)
    result.alpha_composite(art, ((size - art.width) // 2, (size - art.height) // 2))
    return result


def emoji(character, size=24):
    canvas = Image.new("RGBA", (128, 128))
    draw = ImageDraw.Draw(canvas)
    face = ImageFont.truetype(str(EMOJI_FONT), 96)
    bounds = draw.textbbox((0, 0), character, font=face)
    draw.text((-bounds[0], -bounds[1]), character, font=face, embedded_color=True)
    bounds = canvas.getbbox()
    if bounds is None:
        raise ValueError("Emoji glyph is missing")
    glyph = canvas.crop(bounds)
    glyph.thumbnail((size - 2, size - 2), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", (size, size))
    result.alpha_composite(glyph, ((size - glyph.width) // 2, (size - glyph.height) // 2))
    return result


def build_assets(source=SOURCE):
    APP.mkdir(parents=True, exist_ok=True)
    octocat(source, 48).save(APP / "cat.png")
    icon = Image.new("RGBA", (48, 48), (55, 39, 89))
    icon.alpha_composite(octocat(source, 42), (3, 3))
    icon.convert("P", palette=Image.Palette.ADAPTIVE, colors=64).save(APP / "icon.png")
    emoji("\U0001f321").save(APP / "temperature.png")
    emoji("\U0001f4a7").save(APP / "humidity.png")
    print("Built requested Octocat artwork and color thermometer/droplet emoji assets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    build_assets(parser.parse_args().source)
