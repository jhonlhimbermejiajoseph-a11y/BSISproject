"""Build, save and print the medicine release receipt (plain text)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RECEIPT_DIR = os.path.join(ROOT, "receipts")
WIDTH = 42
HEADER = "BARANGAY HEALTH CENTER"      # app.py sets this from your barangay name


def build_receipt_text(t):
    """t is a transaction dict from database.get_transaction()."""
    rule = "-" * WIDTH

    def row(label, value):
        return f"{label:<13}{value}"

    def money(label, amount):
        return f"{label:<24}PHP {amount:>10,.2f}"

    lines = [
        HEADER.center(WIDTH),
        "Medicine Release Receipt".center(WIDTH),
        rule,
        row("Receipt no:", f"{t['id']:06d}"),
        row("Date:", t["created_at"]),
        row("Resident:", t["resident_name"]),
        row("Resident ID:", t["scanned_id"]),
        row("Category:", t["category"]),
        rule,
        row("Medicine:", t["medicine_name"]),
        row("SKU:", t["sku"]),
        row("Quantity:", t["quantity"]),
        row("Batch:", t["batch_info"]),
        rule,
        money("Gross amount", t["gross_amount"]),
        money(f"Subsidy ({t['subsidy_rate'] * 100:.0f}%)", -t["subsidy_amount"]),
        money("Amount due", t["total_amount"]),
        rule,
        row("Released by:", t.get("staff_name") or "-"),
        "",
        "Thank you!".center(WIDTH),
    ]
    return "\n".join(lines) + "\n"


def build_registration_text(resident, staff_name, date_text):
    """Slip given to a newly registered resident, showing the generated Resident ID."""
    rule = "-" * WIDTH

    def row(label, value):
        return f"{label:<13}{value}"

    lines = [
        HEADER.center(WIDTH),
        "Resident Registration Slip".center(WIDTH),
        rule,
        row("Date:", date_text),
        row("Name:", resident["full_name"]),
        row("Category:", resident["category"]),
        row("Address:", resident["address"] or "-"),
        rule,
        "RESIDENT ID".center(WIDTH),
        resident["scanned_id"].center(WIDTH),
        rule,
        "Keep this slip. Show your Resident ID".center(WIDTH),
        "(or ID card) when requesting medicine.".center(WIDTH),
        "",
        row("Staff:", staff_name or "-"),
    ]
    return "\n".join(lines) + "\n"


def save_registration(resident, staff_name):
    """Write receipts/registration_<ID>.txt and return the path."""
    from datetime import datetime
    os.makedirs(RECEIPT_DIR, exist_ok=True)
    path = os.path.join(RECEIPT_DIR, f"registration_{resident['scanned_id']}.txt")
    text = build_registration_text(resident, staff_name, datetime.now().strftime("%Y-%m-%d %H:%M"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def save_receipt(t):
    """Write the receipt to receipts/receipt_000001.txt and return the path."""
    os.makedirs(RECEIPT_DIR, exist_ok=True)
    path = os.path.join(RECEIPT_DIR, f"receipt_{t['id']:06d}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_receipt_text(t))
    return path


def print_receipt(path):
    """Send the receipt to the default printer (Windows), or open/print elsewhere."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path, "print")
        elif sys.platform == "darwin":
            subprocess.run(["lp", path], check=False)
        else:
            subprocess.run(["lp", path], check=False)
    except OSError:
        if sys.platform.startswith("win"):
            os.startfile(path)   # no printer set up: just open the file