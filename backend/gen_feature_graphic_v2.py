"""Image de presentation Google Play (1024x500) sans mot promotionnel.

Part de frontend/icons/feature-graphic.png (meme fond degrade, meme icone, meme titre)
et remplace seulement la ligne « Ton assistant IA gratuit pour les devoirs » (le mot
« gratuit » est un motif de refus « Metadonnees ») par une phrase qui decrit ce que
fait l'appli. Resultat : frontend/icons/feature-graphic-v2.png
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "frontend", "icons", "feature-graphic.png")
DST = os.path.join(HERE, "..", "frontend", "icons", "feature-graphic-v2.png")
FONT = r"C:\Windows\Fonts\segoeui.ttf"

img = Image.open(SRC).convert("RGB")
px = img.load()
W, H = img.size

# 1) Efface l'ancienne phrase en reconstruisant le degrade : pour chaque ligne,
#    interpolation entre un pixel propre a gauche du texte et un a droite.
Y0, Y1, XL, XR = 316, 410, 468, 1018
for y in range(Y0, Y1):
    left, right = px[XL, y], px[XR, y]
    for x in range(XL, XR + 1):
        t = (x - XL) / (XR - XL)
        px[x, y] = tuple(round(left[i] + (right[i] - left[i]) * t) for i in range(3))

# 2) Nouvelle phrase, meme style (blanc, Segoe UI), sur deux lignes.
draw = ImageDraw.Draw(img)
font = ImageFont.truetype(FONT, 31)
x = 482
draw.text((x, 326), "Aide aux devoirs expliquée", font=font, fill=(255, 255, 255))
draw.text((x, 364), "étape par étape", font=font, fill=(255, 255, 255))

img.save(DST, "PNG", optimize=True)
print("ecrit :", os.path.abspath(DST), img.size, os.path.getsize(DST) // 1024, "Ko")
