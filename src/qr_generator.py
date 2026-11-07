"""
qr_generator.py  -  put this file inside your  src/  folder.

Install once:
    pip install qrcode[pil]

Usage inside pharmacy_app.py:
    from src.qr_generator import generate_qr, open_qr_folder

    path = generate_qr("MED-0001", label="Paracetamol 500mg")
    open_qr_folder()
"""

import os
import re
import sys
import subprocess

import qrcode
from PIL import Image, ImageDraw, ImageFont

# Folder where all QR images are saved (created automatically)
QR_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qrcodes")


def _safe_name(text: str) -> str:
    """Make a text safe to use as a file name."""
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", text).strip("_") or "qr"


def generate_qr(data: str, label: str = "", folder: str = QR_FOLDER) -> str:
    """
    Create a QR code image for `data` (e.g. medicine ID or barcode number)
    and save it as a PNG inside `folder`.

    data  : what the QR code contains (this is what the camera will read)
    label : optional text printed under the QR (e.g. medicine name)
    Returns the full path of the saved image.
    """
    os.makedirs(folder, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Add the label under the QR code
    if label:
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except OSError:
            font = ImageFont.load_default()
        w, h = img.size
        canvas = Image.new("RGB", (w, h + 50), "white")
        canvas.paste(img, (0, 0))
        draw = ImageDraw.Draw(canvas)
        text_w = draw.textlength(label, font=font)
        draw.text(((w - text_w) / 2, h + 10), label, fill="black", font=font)
        img = canvas

    file_name = _safe_name(f"{data}_{label}" if label else data) + ".png"
    path = os.path.join(folder, file_name)
    img.save(path)
    return path


def generate_many(items, folder: str = QR_FOLDER) -> list:
    """
    Generate QR codes for many medicines at once.
    items = [("MED-0001", "Paracetamol"), ("MED-0002", "Amoxicillin"), ...]
    """
    return [generate_qr(code, name, folder) for code, name in items]


def open_qr_folder(folder: str = QR_FOLDER) -> None:
    """Open the QR folder in File Explorer / Finder."""
    os.makedirs(folder, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(folder)
    elif sys.platform == "darwin":
        subprocess.run(["open", folder])
    else:
        subprocess.run(["xdg-open", folder])


if __name__ == "__main__":
    # Quick test: run  python src/qr_generator.py
    p = generate_qr("MED-0001", "Paracetamol 500mg")
    print("Saved:", p)
    open_qr_folder()