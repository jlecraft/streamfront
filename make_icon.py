"""
Generate icon.ico for TwitchLauncher.

Reads the Twitch Glitch logo from icon.ico (black on transparent),
recolors it to Twitch purple (#9146FF), and saves a multi-resolution
ICO with sizes 16, 32, 48, 64, 128, and 256.
"""

from PIL import Image
from pathlib import Path

TWITCH_PURPLE = (145, 70, 255)
SIZES = [16, 32, 48, 64, 128, 256]
BASE_DIR = Path(__file__).parent


def recolor(img: Image.Image, rgb: tuple) -> Image.Image:
    """Replace all RGB channels with the given color, preserving the alpha channel."""
    img = img.convert("RGBA")
    _, _, _, a = img.split()
    colored = Image.new("RGBA", img.size, rgb + (255,))
    cr, cg, cb, _ = colored.split()
    return Image.merge("RGBA", (cr, cg, cb, a))


# Load the source Twitch Glitch logo (32x32 black on transparent)
src = Image.open(BASE_DIR / "icon.ico").convert("RGBA")

frames = [recolor(src.resize((s, s), Image.LANCZOS), TWITCH_PURPLE) for s in SIZES]

out = BASE_DIR / "icon.ico"
frames[0].save(out, format="ICO", append_images=frames[1:])
print(f"Saved {out}")
