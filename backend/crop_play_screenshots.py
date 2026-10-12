"""Recadre des captures d'ecran telephone pour Google Play : retire la barre d'etat + la barre du
navigateur (haut) et les boutons Android (bas), pour ne garder que l'appli, avec un rapport
long/court inferieur a 2 (limite Play). Sortie : PNG 24 bits sans transparence.

Usage : python crop_play_screenshots.py <dossier_sortie> <image1> <image2> ...
"""
import os
import sys

from PIL import Image

TOP, BOTTOM = 222, 1884      # pixels a garder (mesures sur des captures 923 x 2000)
out_dir = sys.argv[1]
os.makedirs(out_dir, exist_ok=True)
sheet = []
for i, path in enumerate(sys.argv[2:], start=1):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    top = round(TOP * h / 2000)
    bottom = round(BOTTOM * h / 2000)
    cropped = im.crop((0, top, w, bottom))
    ratio = max(cropped.size) / min(cropped.size)
    out = os.path.join(out_dir, "capture-%d.png" % i)
    cropped.save(out, "PNG", optimize=True)
    sheet.append(cropped)
    print("capture-%d.png  %dx%d  rapport %.2f  %s" % (i, cropped.width, cropped.height, ratio,
          "OK (<= 2)" if ratio <= 2 and min(cropped.size) >= 320 and max(cropped.size) <= 3840 else "HORS LIMITES"))

# planche-contact pour verification visuelle
th = 700
tiles = [s.resize((round(s.width * th / s.height), th)) for s in sheet]
planche = Image.new("RGB", (sum(t.width for t in tiles) + 12 * (len(tiles) + 1), th + 24), (230, 233, 231))
x = 12
for t in tiles:
    planche.paste(t, (x, 12))
    x += t.width + 12
planche.save(os.path.join(out_dir, "_planche.png"))
