"""Genere l'icone de l'appli (PWA + Android) - un simple chapeau de diplome
blanc sur fond vert de la marque. Script ponctuel, pas partie de l'appli
elle-meme - a lancer une fois, pas au demarrage du serveur.
"""
import math
import os

from PIL import Image, ImageDraw

GREEN = (13, 122, 95, 255)  # #0d7a5f
WHITE = (255, 255, 255, 255)

BASE = os.path.join(os.path.dirname(__file__), "..")
FRONTEND_ICONS = os.path.join(BASE, "frontend", "icons")
ANDROID_RES = os.path.join(BASE, "android", "app", "src", "main", "res")

os.makedirs(FRONTEND_ICONS, exist_ok=True)


def draw_cap(size: int, transparent_bg: bool = False, scale: float = 1.0) -> Image.Image:
    bg = (0, 0, 0, 0) if transparent_bg else GREEN
    img = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2 * 0.96
    size = size * scale

    # Planche du chapeau (mortarboard), vue de dessus = losange
    cap_r = size * 0.30
    diamond = [
        (cx, cy - cap_r),
        (cx + cap_r, cy),
        (cx, cy + cap_r),
        (cx - cap_r, cy),
    ]
    draw.polygon(diamond, fill=WHITE)

    # Bouton central
    btn_r = size * 0.035
    draw.ellipse([cx - btn_r, cy - btn_r, cx + btn_r, cy + btn_r], fill=GREEN)

    # Pompon (tassel) : ligne + petit cercle, vers le bas-droite
    end_x = cx + cap_r * 0.55
    end_y = cy + cap_r * 0.95
    draw.line([(cx, cy), (end_x, end_y)], fill=WHITE, width=max(2, int(size * 0.018)))
    tassel_r = size * 0.045
    draw.ellipse(
        [end_x - tassel_r, end_y - tassel_r, end_x + tassel_r, end_y + tassel_r],
        fill=WHITE,
    )

    # Base du chapeau (petit rectangle arrondi sous le losange, suggère la tete)
    band_w = size * 0.30
    band_h = size * 0.10
    band_top = cy + cap_r * 0.35
    draw.rounded_rectangle(
        [cx - band_w / 2, band_top, cx + band_w / 2, band_top + band_h],
        radius=band_h / 2,
        fill=WHITE,
    )

    return img


def save_png(img: Image.Image, size: int, path: str) -> None:
    img.resize((size, size), Image.LANCZOS).save(path)


if __name__ == "__main__":
    master = draw_cap(1024)

    # PWA / manifest.json
    save_png(master, 192, os.path.join(FRONTEND_ICONS, "icon-192.png"))
    save_png(master, 512, os.path.join(FRONTEND_ICONS, "icon-512.png"))
    # Favicon simple (utilise aussi comme apple-touch-icon)
    save_png(master, 180, os.path.join(FRONTEND_ICONS, "apple-touch-icon.png"))

    # Icones Android (remplace les icones par defaut de Capacitor)
    densities = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    for folder, size in densities.items():
        target_dir = os.path.join(ANDROID_RES, folder)
        if not os.path.isdir(target_dir):
            continue
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            save_png(master, size, os.path.join(target_dir, name))
        # foreground de l'icone adaptative : fond transparent, motif reduit pour
        # rester dans la zone de securite (~66%) quel que soit le masque applique
        foreground = draw_cap(1024, transparent_bg=True, scale=0.62)
        save_png(foreground, size, os.path.join(target_dir, "ic_launcher_foreground.png"))

    print("Icones generees.")
