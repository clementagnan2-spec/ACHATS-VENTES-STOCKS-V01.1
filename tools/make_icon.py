"""Génère assets/coin.ico (pièce de monnaie). Lancé automatiquement par le workflow GitHub."""
import os
from PIL import Image, ImageDraw, ImageFont

S = 512
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.ellipse((16, 16, S - 16, S - 16), fill=(160, 110, 10, 255))
d.ellipse((28, 28, S - 28, S - 28), fill=(236, 186, 40, 255))
d.ellipse((60, 60, S - 60, S - 60), outline=(176, 124, 16, 255), width=18)
d.ellipse((78, 78, S - 78, S - 78), fill=(250, 214, 80, 255))
d.arc((40, 40, S - 40, S - 40), 200, 290, fill=(255, 243, 170, 255), width=14)

font = None
for p in ("arialbd.ttf", "C:/Windows/Fonts/arialbd.ttf", "DejaVuSans-Bold.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
    try:
        font = ImageFont.truetype(p, 230)
        break
    except OSError:
        pass
if font is None:
    font = ImageFont.load_default(size=230)
b = d.textbbox((0, 0), "$", font=font)
d.text(((S - (b[2] - b[0])) / 2 - b[0], (S - (b[3] - b[1])) / 2 - b[1]), "$", font=font, fill=(150, 100, 8, 255))

os.makedirs("assets", exist_ok=True)
im.save("assets/coin.png")
im.save("assets/coin.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("assets/coin.ico généré")
