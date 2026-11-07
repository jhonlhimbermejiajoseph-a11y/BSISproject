import tkinter as tk
from tkinter import messagebox

from src.ui import theme as T
from src.ui.requests_view import allocate_fefo
from src.ui.scan_dialog import open_scanner
from src.utils import auth, database as db, prescription, receipt, subsidy
from src.utils.scanner import bind_scanner


class DispenseView(tk.Frame):
    """Pharmacy: scan the QR on the patient's slip, see the prices, dispense."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.rx = None
        self.rows = []                   # one dict per medicine: item, calc, shortfall
        self._build()
        self.render()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Pharmacy",
                 "Scan the QR on the patient's slip, check the prices, then dispense.").pack(
            fill="x", padx=28, pady=(22, 12))
        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 22))

        top = T.card(body)
        top.pack(fill="x")
        T.label(top, "Scan prescription QR", 11, True).pack(anchor="w", padx=16, pady=(14, 2))
        T.label(top, "Use the scanner, or type the code (like RX-00001) and press Enter.", 9,
                color=T.MUTED).pack(anchor="w", padx=16)
        row = tk.Frame(top, bg=T.CARD)
        row.pack(fill="x", padx=16, pady=(10, 14))
        self.scan_entry = T.entry(row, 24)
        self.scan_entry.pack(side="left", ipady=6)
        handle = bind_scanner(self.scan_entry, self.on_scan)
        T.button(row, "Find", handle).pack(side="left", padx=(8, 0))
        T.button(row, "Use camera", lambda: open_scanner(self, self.on_scan), "ghost").pack(
            side="left", padx=(8, 0))

        self.info_label = T.label(body, "", 11, True, justify="left")
        self.info_label.pack(anchor="w", pady=(14, 0))
        self.status_label = T.label(body, "", 10, color=T.MUTED, wraplength=760, justify="left")
        self.status_label.pack(anchor="w", pady=(2, 8))

        frame, self.tree = T.table(body, [
            ("medicine", "Medicine", 200), ("qty", "Qty", 50), ("price", "Price", 80),
            ("gross", "Gross", 90), ("disc", "Discount", 90), ("pay", "You pay", 90),
            ("stock", "Stock", 110),
        ], height=8)
        frame.pack(fill="both", expand=True)

        self.total_label = T.label(body, "", 12, True)
        self.total_label.pack(anchor="e", pady=(10, 0))

        bottom = tk.Frame(body, bg=T.BG)
        bottom.pack(fill="x", pady=(10, 0))
        self.id_var = tk.BooleanVar()
        T.checkbox(bottom, "Resident ID / eligibility verified", self.id_var).pack(side="left")
        T.button(bottom, "Dispense & receipt", self.dispense).pack(side="right")
        T.button(bottom, "Clear", self.clear, "ghost").pack(side="right", padx=8)
        self.msg_label = T.label(body, "", 9, color=T.MUTED, wraplength=760, justify="left")
        self.msg_label.pack(anchor="w", pady=(8, 0))

    def _say(self, text, color=T.MUTED):
        self.msg_label.config(text=text, fg=color)

    # ---------- scanning ----------
    def on_scan(self, code):
        rx = db.get_prescription(code)
        if rx is None:
            self.rx = None
            self.rows = []
            self.render()
            self._say(f"No prescription with the code '{code}'. Scan the QR on the Check-up slip.", T.RED)
            return
        self.rx = rx
        self.id_var.set(False)
        self._say("")
        self.compute()
        self.render()

    def compute(self):
        """Prices, discount and FEFO stock check for each medicine on the prescription."""
        self.rows = []
        for item in self.rx["items"]:
            calc = subsidy.calculate(item["unit_price"], item["quantity"], self.rx["category"])
            allocations, shortfall = allocate_fefo(item["sku"], item["quantity"])
            self.rows.append({"item": item, "calc": calc, "shortfall": shortfall,
                              "stock": db.available_stock(item["sku"])})

    def clear(self):
        self.rx = None
        self.rows = []
        self.id_var.set(False)
        self._say("")
        self.render()
        self.scan_entry.focus_set()

    # ---------- display ----------
    def render(self):
        if not self.rx:
            self.info_label.config(text="")
            self.status_label.config(text="No prescription scanned yet.", fg=T.MUTED)
            self.total_label.config(text="")
            T.fill(self.tree, [])
            return
        rx = self.rx
        rate = subsidy.subsidy_rate(rx["category"]) * 100
        self.info_label.config(
            text=f"{rx['code']}  \u2022  {rx['resident_name']} ({rx['scanned_id']})")
        short = [r["item"]["medicine_name"] for r in self.rows if r["shortfall"] > 0]
        if rx["status"] == "Dispensed":
            self.status_label.config(
                text=f"Already dispensed on {rx['dispensed_at']}. This QR cannot be used again.", fg=T.RED)
        elif rx["status"] == "Cancelled":
            self.status_label.config(text="This prescription was cancelled.", fg=T.RED)
        elif short:
            self.status_label.config(
                text="Not enough stock for: " + ", ".join(short) + ". Restock first, or ask Check-up "
                     "to change the prescription.", fg=T.RED)
        else:
            self.status_label.config(
                text=f"{rx['category']}  \u2022  {rate:.0f}% subsidy  \u2022  Ready to dispense.", fg=T.GREEN)

        T.fill(self.tree, [
            (i, (r["item"]["medicine_name"], r["item"]["quantity"],
                 f"{r['item']['unit_price']:,.2f}", f"{r['calc']['gross']:,.2f}",
                 f"-{r['calc']['subsidy']:,.2f}", f"{r['calc']['total']:,.2f}",
                 f"Short ({r['stock']})" if r["shortfall"] > 0 else f"OK ({r['stock']})"),
             "warn" if r["shortfall"] > 0 else None)
            for i, r in enumerate(self.rows)
        ])
        total = sum(r["calc"]["total"] for r in self.rows)
        saved = sum(r["calc"]["subsidy"] for r in self.rows)
        self.total_label.config(text=f"Discount: PHP {saved:,.2f}     Resident pays: PHP {total:,.2f}")

    # ---------- dispense ----------
    def dispense(self):
        if not self.rx:
            self._say("Scan a prescription first.", T.RED)
            return
        if self.rx["status"] != "Open":
            self._say(f"This prescription is {self.rx['status'].lower()}. It cannot be dispensed.", T.RED)
            return
        if not self.id_var.get():
            messagebox.showwarning("Verification needed", "Tick the ID / eligibility check first.")
            return

        # Re-check the stock right now (FEFO, earliest expiry first), then dispense everything.
        lines = []
        for item in self.rx["items"]:
            allocations, shortfall = allocate_fefo(item["sku"], item["quantity"])
            if shortfall > 0:
                self.compute()
                self.render()
                self._say(f"Not enough stock for {item['medicine_name']}. Nothing was dispensed.", T.RED)
                return
            lines.append({
                "sku": item["sku"], "quantity": item["quantity"],
                "allocations": [(b["id"], n) for b, n in allocations],
                "calc": subsidy.calculate(item["unit_price"], item["quantity"], self.rx["category"]),
                "batch_info": ", ".join(f"{b['batch_no']} x{n}" for b, n in allocations),
            })
        try:
            tids = db.dispense_prescription(self.rx, lines, auth.current_user()["id"])
        except ValueError as err:
            messagebox.showerror("Could not dispense", str(err))
            self.on_scan(self.rx["code"])
            return

        path = prescription.save_release(self.rx, [db.get_transaction(t) for t in tids])
        code = self.rx["code"]
        self.on_scan(code)                                   # shows the status as Dispensed
        self._say(f"Dispensed. Receipt saved: {path}", T.GREEN)
        if messagebox.askyesno("Receipt ready", f"Receipt saved:\n{path}\n\nPrint it now?"):
            receipt.print_receipt(path)
        self.scan_entry.focus_set()