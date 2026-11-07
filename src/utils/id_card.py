"""Create a printable resident ID card (PNG) with a QR code of the resident ID.

Needs:  uv add opencv-python pillow
The QR code holds only the resident ID (e.g. BRGY-0001). The scanner or camera reads that
text, and the system looks the resident up in its own database.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARD_DIR = os.path.join(ROOT, "id_cards")


def _font(size, bold=False):
    from PIL import ImageFont
    names = (["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _qr_image(text, target=300):
    """Return a crisp black-and-white QR code as a PIL image."""
    import cv2
    from PIL import Image
    modules = cv2.QRCodeEncoder.create().encode(text)          # one pixel per QR module
    n = modules.shape[0]
    scale = max(1, target // n)
    return Image.fromarray(modules).resize((n * scale, n * scale), Image.NEAREST).convert("RGB")


def make_id_card(resident, barangay_name, logo_path=None):
    """Save id_cards/<ID>.png and return its path. resident is a dict from the database."""
    from PIL import Image, ImageDraw
    W, H = 856, 540                                            # credit-card shape
    card = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(card)

    # header band with optional logo
    d.rectangle([0, 0, W, 110], fill="#0a7d4b")
    x = 32
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((84, 84))
            card.paste(logo, (28, 13), logo)
            x = 128
        except Exception:
            pass
    d.text((x, 20), barangay_name.upper(), font=_font(34, True), fill="white")
    d.text((x, 66), "Health Center  -  Resident ID", font=_font(22), fill="#d8f5e6")

    # details (left side)
    size = 40
    while d.textlength(resident["full_name"], font=_font(size, True)) > 450 and size > 20:
        size -= 2
    d.text((40, 150), "NAME", font=_font(16), fill="#6b7780")
    d.text((40, 172), resident["full_name"], font=_font(size, True), fill="#111111")
    d.text((40, 250), "CATEGORY", font=_font(16), fill="#6b7780")
    d.text((40, 272), resident["category"], font=_font(30), fill="#0a7d4b")
    d.text((40, 340), "ADDRESS", font=_font(16), fill="#6b7780")
    d.text((40, 362), resident["address"] or "-", font=_font(26), fill="#111111")

    # QR code (right side) with a white quiet zone
    qr = _qr_image(resident["scanned_id"])
    box = 340
    qx, qy = W - box - 30, 130
    d.rectangle([qx, qy, qx + box, qy + box], fill="white", outline="#d0d7db", width=2)
    card.paste(qr, (qx + (box - qr.width) // 2, qy + (box - qr.height) // 2))
    id_font = _font(34, True)
    id_w = d.textlength(resident["scanned_id"], font=id_font)
    d.text((qx + (box - id_w) / 2, qy + box + 14), resident["scanned_id"], font=id_font, fill="#111111")

    d.rectangle([0, 0, W - 1, H - 1], outline="#0a7d4b", width=4)
    os.makedirs(CARD_DIR, exist_ok=True)
    path = os.path.join(CARD_DIR, f"{resident['scanned_id']}.png")
    card.save(path)
    return path


def open_file(path):
    """Open the card in the default image viewer so it can be printed."""
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)