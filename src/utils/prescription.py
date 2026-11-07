"""Prescription slip (a PNG picture with a QR code) and the combined release receipt (text)."""
import os
from datetime import datetime

from src.utils import receipt

WIDTH = 42          # characters per line on the text receipt


# ---------- prescription slip with QR ----------
def _font(size, bold=False):
    from PIL import ImageFont
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _qr_image(code, size):
    """The QR picture for `code`, or None when the qrcode package is missing."""
    try:
        import qrcode
    except ImportError:
        return None
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = getattr(img, "get_image", lambda: img)()
    return img.convert("RGB").resize((size, size))


def save_slip(rx):
    """Draw receipts/prescription_<code>.png for a prescription from database.get_prescription().

    Returns (path, has_qr). The QR holds only the prescription code. Prices and the
    discount are looked up again at the pharmacy, so they cannot be edited on paper.
    """
    from PIL import Image, ImageDraw
    os.makedirs(receipt.RECEIPT_DIR, exist_ok=True)
    W, M = 620, 36
    f_head, f_sub = _font(28, True), _font(20)
    f_bold, f_text, f_small = _font(20, True), _font(20), _font(16)
    img = Image.new("RGB", (W, 1000 + 36 * len(rx["items"])), "white")
    d = ImageDraw.Draw(img)

    def center(text, font, y, fill="black"):
        d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)

    def rule(y):
        d.line([(M, y), (W - M, y)], fill="black", width=2)

    y = M
    center(receipt.HEADER, f_head, y)
    y += 42
    center("Check-up Prescription Slip", f_sub, y)
    y += 40
    rule(y)
    y += 16
    for label, value in [("Date", rx["created_at"]), ("Resident", rx["resident_name"]),
                         ("Resident ID", rx["scanned_id"]), ("Category", rx["category"]),
                         ("Check-up by", rx.get("staff_name") or "-")]:
        d.text((M, y), f"{label}:", font=f_bold, fill="black")
        d.text((M + 170, y), str(value), font=f_text, fill="black")
        y += 32
    y += 6
    rule(y)
    y += 14
    d.text((M, y), "Medicines", font=f_bold, fill="black")
    y += 34
    for item in rx["items"]:
        d.text((M, y), item["medicine_name"], font=f_text, fill="black")
        qty = f"x {item['quantity']}"
        d.text((W - M - d.textlength(qty, font=f_text), y), qty, font=f_text, fill="black")
        y += 32
    y += 8
    rule(y)
    y += 20

    qr = _qr_image(rx["code"], 300)
    if qr is not None:
        img.paste(qr, ((W - 300) // 2, y))
        y += 310
    else:
        center("(QR code not available)", f_text, y + 100)
        y += 240
    center(rx["code"], f_head, y)
    y += 50
    center("Show this slip at the pharmacy.", f_small, y)
    y += 24
    center("Prices and discount are shown when it is scanned.", f_small, y)
    y += 24 + M

    img = img.crop((0, 0, W, y))
    path = os.path.join(receipt.RECEIPT_DIR, f"prescription_{rx['code']}.png")
    img.save(path)
    return path, qr is not None


# ---------- release receipt after dispensing (text) ----------
def build_release_text(rx, transactions):
    """One receipt for the whole prescription. transactions come from database.get_transaction()."""
    rule = "-" * WIDTH
    first = transactions[0]

    def row(label, value):
        return f"{label:<14}{value}"

    def money(label, amount):
        return f"{label:<24}PHP {amount:>10,.2f}"

    gross = sum(t["gross_amount"] for t in transactions)
    subsidy = sum(t["subsidy_amount"] for t in transactions)
    total = sum(t["total_amount"] for t in transactions)

    lines = [
        receipt.HEADER.center(WIDTH),
        "Medicine Release Receipt".center(WIDTH),
        rule,
        row("Prescription:", rx["code"]),
        row("Date:", first["created_at"]),
        row("Resident:", first["resident_name"]),
        row("Resident ID:", first["scanned_id"]),
        row("Category:", first["category"]),
        rule,
    ]
    for t in transactions:
        lines += [f"{t['medicine_name']} x {t['quantity']}",
                  f"  Batch: {t['batch_info']}",
                  money("  Amount", t["total_amount"])]
    lines += [
        rule,
        money("Gross amount", gross),
        money(f"Subsidy ({first['subsidy_rate'] * 100:.0f}%)", -subsidy),
        money("Amount due", total),
        rule,
        row("Released by:", first.get("staff_name") or "-"),
        "",
        "Thank you!".center(WIDTH),
    ]
    return "\n".join(lines) + "\n"


def save_release(rx, transactions):
    """Write receipts/release_<code>.txt and return the path."""
    os.makedirs(receipt.RECEIPT_DIR, exist_ok=True)
    path = os.path.join(receipt.RECEIPT_DIR, f"release_{rx['code']}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_release_text(rx, transactions))
    return path