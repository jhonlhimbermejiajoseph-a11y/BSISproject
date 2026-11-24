import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox

from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.ui.inventory_view import stat_tile
from src.utils import database as db

BLUE = "#3aa0ff"


class DeliveriesView(tk.Frame):
    """Admin: record incoming stock. Each delivery becomes its own batch with an expiry date."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.med_labels = {}
        self._build()
        self.refresh()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Deliveries",
                 "Record incoming stock. Each delivery becomes its own batch with an expiry date.").pack(
            fill="x", padx=28, pady=(22, 12))

        tiles = tk.Frame(self, bg=T.BG)
        tiles.pack(fill="x", padx=28)
        self.tile = {}
        for i, (key, text, accent) in enumerate([
            ("batches", "Deliveries recorded", T.GREEN), ("units", "Units received", BLUE),
            ("month", "Received this month", T.YELLOW), ("soon", "Batches expiring in 90 days", T.RED),
        ]):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            box, value = stat_tile(tiles, text, accent)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            self.tile[key] = value

        form = T.card(self)
        form.pack(fill="x", padx=28, pady=(14, 0))
        top = tk.Frame(form, bg=T.CARD)
        top.pack(fill="x", padx=18, pady=(14, 6))
        T.label(top, "Record a delivery", 12, True, bg=T.CARD).pack(side="left")
        T.label(top, "New medicine? Add it first in Inventory.", 9, color=T.MUTED, bg=T.CARD).pack(side="right")
        row = tk.Frame(form, bg=T.CARD)
        row.pack(fill="x", padx=18, pady=(0, 6))
        box, self.med_combo = T.labeled_combo(row, "Medicine", 30)
        box.pack(side="left", padx=(0, 12))
        box, self.batch_entry = T.labeled_entry(row, "Batch no.", 14)
        box.pack(side="left", padx=(0, 12))
        box, self.qty_entry = T.labeled_entry(row, "Quantity", 10)
        box.pack(side="left", padx=(0, 12))
        box, self.expiry_entry = T.labeled_entry(row, "Expiry (YYYY-MM-DD)", 16)
        box.pack(side="left", padx=(0, 12))
        T.button(row, "Record delivery", self.record).pack(side="left", anchor="s")
        self.msg = T.label(form, "", 9, color=T.MUTED, bg=T.CARD, wraplength=900, justify="left")
        self.msg.pack(anchor="w", padx=18, pady=(2, 14))
        for entry in (self.batch_entry, self.qty_entry, self.expiry_entry):
            entry.bind("<Return>", lambda e: self.record())

        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=28, pady=(16, 6))
        T.label(top, "Recent deliveries", 12, True).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.render())
        search = T.entry(top, 24)
        search.config(textvariable=self.search_var)
        search.pack(side="right", ipady=4)
        T.label(top, "Search medicine or batch", 9, color=T.MUTED).pack(side="right", padx=(0, 8))
        frame, self.tree = T.table(self, [
            ("received", "Received", 130), ("medicine", "Medicine", 200), ("batch", "Batch", 110),
            ("delivered", "Delivered", 80), ("remaining", "Remaining", 80), ("expiry", "Expiry date", 110),
            ("status", "Status", 110),
        ], height=12)
        frame.pack(fill="both", expand=True, padx=28, pady=(0, 22))

    # ---------- data ----------
    def refresh(self):
        meds = db.get_medicines()
        self.med_labels = {f"{m['sku']} - {m['name']}": m["sku"] for m in meds}
        self.med_combo["values"] = list(self.med_labels)

        self.batches = merge_sort(db.get_batches(), key=lambda b: b["id"], reverse=True)   # newest first
        month = date.today().strftime("%Y-%m")
        self.tile["batches"].config(text=str(len(self.batches)))
        self.tile["units"].config(text=f"{sum(b['delivered_qty'] for b in self.batches):,}")
        self.tile["month"].config(text=f"{sum(b['delivered_qty'] for b in self.batches if str(b['received_date'])[:7] == month):,}")
        self.tile["soon"].config(text=str(sum(1 for b in self.batches
                                              if b["quantity"] > 0 and db.expiry_status(b["expiry_date"]) != "OK")))
        self.render()

    def render(self):
        text = self.search_var.get().strip().lower()
        rows = []
        for b in self.batches:
            if text and text not in f"{b['medicine_name']} {b['batch_no']}".lower():
                continue
            status = "Used up" if b["quantity"] <= 0 else db.expiry_status(b["expiry_date"])
            tag = {"Expired": "bad", "Expiring soon": "warn"}.get(status)
            rows.append((b["id"], (b["received_date"], b["medicine_name"], b["batch_no"], b["delivered_qty"],
                                   b["quantity"], b["expiry_date"], status), tag))
        T.fill(self.tree, rows)

    def _say(self, text, color):
        self.msg.config(text=text, fg=color)

    # ---------- record ----------
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
        released = self.release_pending()
        note = (f"  {released} waiting order(s) moved to the BHW's service queue." if released else "")
        self._say(f"Delivery recorded.{note}", T.GREEN)
        self.refresh()

    def release_pending(self):
        """New stock arrived: move Pending requests (oldest first) to the service queue if free stock covers them."""
        reserved = {}                                           # stock already promised to queued requests
        for r in db.get_requests("Queued"):
            reserved[r["sku"]] = reserved.get(r["sku"], 0) + r["quantity"]
        moved = 0
        for r in db.get_requests("Pending"):                    # arrival order
            free = db.available_stock(r["sku"]) - reserved.get(r["sku"], 0)
            if free >= r["quantity"]:
                db.set_request_status(r["id"], "Queued")
                reserved[r["sku"]] = reserved.get(r["sku"], 0) + r["quantity"]
                moved += 1
        return moved