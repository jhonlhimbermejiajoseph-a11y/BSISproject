import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox

from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.utils import database as db


class DeliveriesView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.med_labels = {}
        self._build()
        self.refresh()

    def _build(self):
        T.header(self, "Deliveries",
                 "Record incoming stock. Each delivery becomes its own batch with an expiry date.").pack(
            fill="x", padx=28, pady=(22, 12))

        form = T.card(self)
        form.pack(fill="x", padx=28)
        T.label(form, "Record a delivery", 11, True).pack(anchor="w", padx=16, pady=(14, 6))
        row = tk.Frame(form, bg=T.CARD)
        row.pack(fill="x", padx=16, pady=(0, 8))
        box, self.med_combo = T.labeled_combo(row, "Medicine", 30)
        box.pack(side="left", padx=(0, 10))
        box, self.batch_entry = T.labeled_entry(row, "Batch no.", 14)
        box.pack(side="left", padx=(0, 10))
        box, self.qty_entry = T.labeled_entry(row, "Quantity", 10)
        box.pack(side="left", padx=(0, 10))
        box, self.expiry_entry = T.labeled_entry(row, "Expiry (YYYY-MM-DD)", 16)
        box.pack(side="left", padx=(0, 10))
        T.button(row, "Record delivery", self.record).pack(side="left", anchor="s")
        self.msg = T.label(form, "", 9, color=T.MUTED)
        self.msg.pack(anchor="w", padx=16, pady=(0, 12))

        T.label(self, "Recent deliveries", 11, True).pack(anchor="w", padx=28, pady=(14, 6))
        frame, self.tree = T.table(self, [
            ("received", "Received", 130), ("medicine", "Medicine", 200), ("batch", "Batch", 110),
            ("delivered", "Delivered", 80), ("remaining", "Remaining", 80), ("expiry", "Expiry date", 110),
        ], height=12)
        frame.pack(fill="both", expand=True, padx=28, pady=(0, 22))

    def refresh(self):
        meds = db.get_medicines()
        self.med_labels = {f"{m['sku']} - {m['name']}": m["sku"] for m in meds}
        self.med_combo["values"] = list(self.med_labels)

        batches = merge_sort(db.get_batches(), key=lambda b: b["id"], reverse=True)   # newest first
        T.fill(self.tree, [
            (b["id"], (b["received_date"], b["medicine_name"], b["batch_no"], b["delivered_qty"],
                       b["quantity"], b["expiry_date"]), None)
            for b in batches
        ])

    def _say(self, text, color):
        self.msg.config(text=text, fg=color)

    def record(self):
        sku = self.med_labels.get(self.med_combo.get())
        batch_no = self.batch_entry.get().strip()
        if not sku or not batch_no:
            self._say("Choose a medicine and enter a batch number.", T.RED)
            return
        try:
            qty = int(self.qty_entry.get().strip())
        except ValueError:
            qty = 0
        if qty <= 0:
            self._say("Quantity must be a whole number above 0.", T.RED)
            return
        try:
            expiry = datetime.strptime(self.expiry_entry.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            self._say("Expiry date must look like 2027-06-30.", T.RED)
            return
        if expiry < date.today():
            self._say("That expiry date has already passed.", T.RED)
            return

        db.add_batch(sku, batch_no, qty, expiry.isoformat())
        for e in (self.batch_entry, self.qty_entry, self.expiry_entry):
            e.delete(0, "end")
        self._say("Delivery recorded. Use 'Re-check stock' in Requests to release pending requests.", T.GREEN)
        self.refresh()