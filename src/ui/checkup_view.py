import tkinter as tk
from tkinter import messagebox, ttk

from src.dsa.hash_table import HashTable
from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.ui.catalog_view import STATUS_COLOR, stock_status
from src.ui.inventory_view import load_medicine_photo
from src.ui.scan_dialog import open_scanner
from src.utils import auth, database as db, prescription, receipt, subsidy
from src.utils.scanner import bind_scanner

CARD_W, CARD_H = 168, 212
PIC_W, PIC_H = CARD_W - 20, 96


class CheckupView(tk.Frame):
    """The doctor's screen: pick the resident, click medicine pictures, print a slip with a QR code."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.residents = HashTable()     # scanned ID -> resident
        self.medicines = HashTable()     # SKU -> medicine
        self.resident = None
        self.items = []                  # [{"sku", "name", "qty"}]
        self.res_labels = {}
        self.meds = []
        self.stock = {}
        self.cards = []
        self.photos = {}                 # keeps the pictures alive (Tk drops unreferenced images)
        self.cols = 3
        self.recent = []
        self.recent_tree = None
        self._build()
        self.bind_all("<MouseWheel>", self.on_wheel)
        self.refresh()

    def destroy(self):
        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        super().destroy()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Check-up",
                 "Pick the resident, click the medicines, then print the slip with its QR code.").pack(
            fill="x", padx=28, pady=(22, 12))
        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 18))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=T.BG, width=330)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        left.pack_propagate(False)
        right = tk.Frame(body, bg=T.BG)
        right.grid(row=0, column=1, sticky="nsew")

        # left 1: resident
        c1 = T.card(left)
        c1.pack(fill="x")
        T.label(c1, "1. Resident", 11, True).pack(anchor="w", padx=16, pady=(14, 2))
        T.label(c1, "Scan the ID card, type the ID and press Enter, or choose by name.", 9,
                color=T.MUTED, wraplength=290, justify="left").pack(anchor="w", padx=16)
        row = tk.Frame(c1, bg=T.CARD)
        row.pack(fill="x", padx=16, pady=(10, 6))
        self.scan_entry = T.entry(row, 14)
        self.scan_entry.pack(side="left", fill="x", expand=True, ipady=6)
        handle = bind_scanner(self.scan_entry, self.on_scan)
        T.button(row, "Find", handle).pack(side="left", padx=(8, 0))
        T.button(row, "Camera", lambda: open_scanner(self, self.on_scan), "ghost").pack(
            side="left", padx=(6, 0))
        box, self.res_combo = T.labeled_combo(c1, "Or choose by name", 30)
        box.pack(fill="x", padx=16)
        self.res_combo.bind("<<ComboboxSelected>>", lambda e: self.on_pick())
        self.resident_label = T.label(c1, "No resident selected.", 10, color=T.MUTED,
                                      justify="left", wraplength=290)
        self.resident_label.pack(anchor="w", padx=16, pady=(8, 14))

        # left 2: the prescription being written
        c2 = T.card(left)
        c2.pack(fill="both", expand=True, pady=(14, 0))
        T.label(c2, "2. Prescription", 11, True).pack(anchor="w", padx=16, pady=(14, 8))
        frame, self.item_tree = T.table(c2, [
            ("n", "#", 30), ("medicine", "Medicine", 150), ("qty", "Qty", 40), ("stock", "Stock", 56),
        ], height=6)
        frame.pack(fill="both", expand=True, padx=16)
        btns = tk.Frame(c2, bg=T.CARD)
        btns.pack(fill="x", padx=16, pady=(10, 0))
        T.button(btns, "Remove", self.remove_item, "ghost").pack(side="left")
        T.button(btns, "Save & print slip", self.save).pack(side="right")
        self.msg_label = T.label(c2, "", 9, color=T.MUTED, wraplength=290, justify="left")
        self.msg_label.pack(anchor="w", padx=16, pady=(8, 0))
        T.button(c2, "Recent slips", self.open_recent, "ghost").pack(fill="x", padx=16, pady=(8, 14))

        # right: medicine pictures
        bar = tk.Frame(right, bg=T.BG)
        bar.pack(fill="x", pady=(0, 10))
        T.label(bar, "Search", 9, color=T.MUTED).pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.render_cards())
        search = T.entry(bar, 22)
        search.config(textvariable=self.search_var)
        search.pack(side="left", ipady=5)
        T.label(bar, "Quantity", 9, color=T.MUTED).pack(side="left", padx=(16, 8))
        self.qty_entry = T.entry(bar, 6)
        self.qty_entry.pack(side="left", ipady=5)
        self.qty_entry.insert(0, "1")
        T.label(bar, "Click a medicine to add it.", 9, color=T.MUTED).pack(side="right")

        wrap = tk.Frame(right, bg=T.BG)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=T.BG, highlightthickness=0)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.grid_frame = tk.Frame(self.canvas, bg=T.BG)
        self.window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.bind("<Configure>", self.on_resize)
        self.grid_frame.bind("<Configure>",
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def on_resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        cols = max(1, event.width // (CARD_W + 12))
        if cols != self.cols:
            self.cols = cols
            self.layout()

    def on_wheel(self, event):
        try:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except tk.TclError:
            pass

    def layout(self):
        cols = max(1, self.cols)
        for i, card in enumerate(self.cards):
            card.grid(row=i // cols, column=i % cols, padx=(0, 12), pady=(0, 12), sticky="n")

    # ---------- data ----------
    def refresh(self):
        residents = db.get_residents()
        self.meds = db.get_medicines()
        self.stock = db.stock_by_sku()
        self.residents.clear()
        self.residents.load(residents, "scanned_id")
        self.medicines.clear()
        self.medicines.load(self.meds, "sku")
        self.res_labels = {f"{r['scanned_id']} - {r['full_name']}": r for r in residents}
        self.res_combo["values"] = list(self.res_labels)
        self.photos.clear()
        self.render_cards()
        self.render_items()

    def _say(self, text, color=T.MUTED):
        self.msg_label.config(text=text, fg=color)

    # ---------- medicine pictures ----------
    def render_cards(self):
        for card in self.cards:
            card.destroy()
        self.cards = []
        text = self.search_var.get().strip().lower()
        shown = [m for m in self.meds if not text or text in f"{m['sku']} {m['name']}".lower()]
        shown = merge_sort(shown, key=lambda m: m["name"].lower())          # Merge Sort by name
        if not shown:
            empty = T.label(self.grid_frame, "No medicines match your search.", 11, color=T.MUTED)
            empty.grid(row=0, column=0, pady=30, sticky="w")
            self.cards.append(empty)
            return
        for m in shown:
            self.cards.append(self.make_card(m))
        self.layout()

    def make_card(self, m):
        stock = self.stock.get(m["sku"], 0)
        status = stock_status(stock, m["low_stock_level"])
        card = T.card(self.grid_frame, width=CARD_W, height=CARD_H)
        card.pack_propagate(False)

        pic = tk.Frame(card, bg=T.FIELD, width=PIC_W, height=PIC_H)
        pic.pack(padx=10, pady=(10, 6))
        pic.pack_propagate(False)
        if m["sku"] not in self.photos:
            self.photos[m["sku"]] = load_medicine_photo(m["sku"], (PIC_W, PIC_H))
        photo = self.photos[m["sku"]]
        if photo:
            tk.Label(pic, image=photo, bg=T.FIELD).place(relx=0.5, rely=0.5, anchor="center")
        else:
            tk.Label(pic, text="No picture", bg=T.FIELD, fg=T.MUTED, font=T.FONT).place(
                relx=0.5, rely=0.5, anchor="center")

        T.label(card, m["name"], 10, True, wraplength=CARD_W - 22, justify="left").pack(anchor="w", padx=12)
        T.label(card, f"PHP {m['unit_price']:,.2f} each", 9).pack(anchor="w", padx=12, pady=(2, 0))
        label = "Out of stock" if status == "Out of stock" else f"{status}  •  {stock}"
        T.label(card, label, 9, True, STATUS_COLOR[status]).pack(anchor="w", padx=12, pady=(4, 0))

        def bind_click(widget):                      # the whole card is clickable
            widget.bind("<Button-1>", lambda e, sku=m["sku"]: self.pick_medicine(sku))
            for child in widget.winfo_children():
                bind_click(child)
        card.configure(cursor="hand2")
        bind_click(card)
        return card

    def pick_medicine(self, sku):
        try:
            qty = int(self.qty_entry.get().strip())
        except ValueError:
            qty = 0
        if qty <= 0:
            self._say("Quantity must be a whole number above 0.", T.RED)
            return
        name = self.medicines.get(sku)["name"]
        for item in self.items:
            if item["sku"] == sku:                    # same medicine twice: add the quantities
                item["qty"] += qty
                break
        else:
            self.items.append({"sku": sku, "name": name, "qty": qty})
        self._say(f"Added {name} x {qty}.", T.GREEN)
        self.render_items()

    # ---------- prescription list ----------
    def render_items(self):
        stock = db.stock_by_sku()
        T.fill(self.item_tree, [
            (i, (i + 1, it["name"], it["qty"], stock.get(it["sku"], 0)), None)
            for i, it in enumerate(self.items)
        ])

    def remove_item(self):
        sel = self.item_tree.selection()
        if not sel:
            messagebox.showinfo("Select a medicine", "Click a medicine in the list first.")
            return
        del self.items[int(sel[0])]
        self.render_items()

    # ---------- resident ----------
    def on_scan(self, code):
        resident = self.residents.get(code) or self.residents.get(code.upper())   # Hash Table lookup
        if resident is None:
            self.resident = None
            self.resident_label.config(text=f"Resident not found: {code}", fg=T.RED)
            return
        self.set_resident(resident)

    def on_pick(self):
        resident = self.res_labels.get(self.res_combo.get())
        if resident:
            self.set_resident(resident)

    def set_resident(self, resident):
        self.resident = resident
        rate = subsidy.subsidy_rate(resident["category"]) * 100
        self.resident_label.config(
            text=(f"{resident['full_name']}\n{resident['scanned_id']}  •  {resident['category']} "
                  f"({rate:.0f}% subsidy)"),
            fg=T.GREEN)

    # ---------- save and print ----------
    def save(self):
        if not self.resident:
            self._say("Choose a resident first.", T.RED)
            return
        if not self.items:
            self._say("Click at least one medicine.", T.RED)
            return
        code = db.add_prescription(self.resident["id"], [(i["sku"], i["qty"]) for i in self.items],
                                   auth.current_user()["id"])
        rx = db.get_prescription(code)
        self.items = []
        self.resident = None
        self.resident_label.config(text="No resident selected.", fg=T.MUTED)
        self.res_combo.set("")
        self.render_items()
        self.render_recent()
        self._say(f"Prescription {code} saved.", T.GREEN)
        self.slip(rx)

    def slip(self, rx):
        """Make the slip picture with the QR code and offer to print it."""
        try:
            path, has_qr = prescription.save_slip(rx)
        except Exception as err:
            messagebox.showwarning(
                "Saved, but no slip",
                f"Prescription {rx['code']} was saved, but the slip could not be made:\n{err}\n\n"
                "Try 'Reprint' from Recent slips.")
            return
        note = "" if has_qr else ("\n\nThe QR code could not be drawn. Run:  uv add qrcode\n"
                                  "The code is written on the slip, so the pharmacy can type it.")
        if messagebox.askyesno("Prescription saved",
                               f"Code: {rx['code']}\nSlip: {path}{note}\n\nPrint it now?"):
            receipt.print_receipt(path)

    # ---------- recent slips (opens in its own window) ----------
    def open_recent(self):
        dlg = tk.Toplevel(self)
        dlg.title("Recent slips")
        dlg.configure(bg=T.BG)
        dlg.geometry("620x380")
        top = tk.Frame(dlg, bg=T.BG)
        top.pack(fill="x", padx=18, pady=(16, 8))
        T.label(top, "Recent prescriptions", 12, True).pack(side="left")
        T.button(top, "Reprint", self.reprint, "ghost").pack(side="right")
        T.button(top, "Cancel selected", self.cancel_rx, "danger").pack(side="right", padx=8)
        frame, self.recent_tree = T.table(dlg, [
            ("code", "Code", 90), ("resident", "Resident", 170), ("items", "Items", 50),
            ("status", "Status", 90), ("time", "Created", 130),
        ], height=10)
        frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        dlg.bind("<Destroy>", lambda e: setattr(self, "recent_tree", None) if e.widget is dlg else None)
        self.render_recent()

    def render_recent(self):
        if self.recent_tree is None:
            return
        self.recent = db.get_prescriptions()
        try:
            T.fill(self.recent_tree, [
                (i, (p["code"], p["resident_name"], p["item_count"], p["status"], p["created_at"]), None)
                for i, p in enumerate(self.recent)
            ])
        except tk.TclError:
            self.recent_tree = None

    def _selected_recent(self):
        sel = self.recent_tree.selection() if self.recent_tree else ()
        if not sel:
            messagebox.showinfo("Select a prescription", "Click a prescription in the list first.")
            return None
        return self.recent[int(sel[0])]

    def reprint(self):
        picked = self._selected_recent()
        if picked:
            self.slip(db.get_prescription(picked["code"]))

    def cancel_rx(self):
        picked = self._selected_recent()
        if not picked:
            return
        if picked["status"] != "Open":
            messagebox.showinfo("Cannot cancel", f"{picked['code']} is already {picked['status']}.")
            return
        if messagebox.askyesno("Cancel prescription", f"Cancel {picked['code']}? Its QR will stop working."):
            db.cancel_prescription(picked["id"])
            self.render_recent()