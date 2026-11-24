import os
import re
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from src.dsa.bst import BST
from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.utils import auth, database as db

STATUS_TAG = {"OK": "ok", "Low stock": "warn", "Expiring soon": "warn",
              "Expired": "bad", "Out of stock": "bad"}
STATUS_COLOR = {"OK": T.GREEN, "Low stock": T.YELLOW, "Expiring soon": T.YELLOW,
                "Expired": T.RED, "Out of stock": T.RED}
# (button text, status it shows). None means show everything.
FILTERS = [("All", None), ("Low stock", "Low stock"), ("Expiring", "Expiring soon"),
           ("Expired", "Expired"), ("Out of stock", "Out of stock")]

IMAGE_DIR = os.path.join(T.ASSETS_DIR, "medicines")      # one picture per medicine code
PICTURE_TYPES = [("Pictures", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"), ("All files", "*.*")]
PILLOW_HINT = "Pictures need Pillow. Open the PyCharm Terminal and run:\n    uv add pillow"
ADD_HINT = "Record stock for a new medicine in the Deliveries screen."
PANEL_W, PIC_W, PIC_H = 290, 258, 170
CARD_W, CARD_H = 198, 322                      # medicine cards (Cards view)


# ---------- medicine pictures: assets/medicines/<CODE>.png ----------
def _image_path(sku):
    return os.path.join(IMAGE_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", sku) + ".png")


def save_medicine_image(sku, source_path):
    """Copy any picture into assets/medicines/<CODE>.png (shrunk to 600 px)."""
    from PIL import Image
    os.makedirs(IMAGE_DIR, exist_ok=True)
    img = Image.open(source_path).convert("RGBA")
    img.thumbnail((600, 600))
    img.save(_image_path(sku), "PNG")


def remove_medicine_image(sku):
    try:
        os.remove(_image_path(sku))
    except OSError:
        pass


def load_medicine_photo(sku, box=(238, 170)):
    """Return a Tk image that fits inside box, or None if the medicine has no picture."""
    path = _image_path(sku)
    if not os.path.exists(path):
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(path).convert("RGBA")
        img.thumbnail(box)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def stat_tile(parent, text, accent):
    """A counter with a colored stripe on top. Returns (container, value_label)."""
    box = T.card(parent, cursor="hand2")
    tk.Frame(box, bg=accent, height=3).pack(fill="x")
    value = tk.Label(box, text="0", bg=T.CARD, fg=accent, font=T.FONT_STAT)
    value.pack(anchor="w", padx=16, pady=(10, 0))
    T.label(box, text, 9, color=T.MUTED).pack(anchor="w", padx=16, pady=(0, 12))
    return box, value


def bind_click(widget, command):
    widget.bind("<Button-1>", lambda e: command())
    for child in widget.winfo_children():
        bind_click(child, command)


class InventoryView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.can_edit = auth.can_manage_inventory()    # BHWs can only view
        self.rows = []
        self.by_iid = {}
        self.meds = {}
        self.stock = {}
        self.photo = None
        self.filter_value = None
        self.low_skus = set()
        self.chips = {}
        self.view_mode = "cards"                       # "cards" (one card per medicine) or "table" (one row per batch)
        self.view_buttons = {}
        self.selected = None                           # iid of the selected row / card
        self.info = {}                                 # per-medicine numbers shown on the cards
        self.name_tree = None
        self.cards = []
        self.card_photos = {}
        self.cols = 3
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
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=28, pady=(22, 12))
        T.header(top, "Medicine Inventory",
                 "Sorted by FEFO: the earliest expiry is listed first.").pack(side="left")
        if self.can_edit:
            T.button(top, "+  Add medicine", self.open_add).pack(side="right", anchor="s")
        for text, mode in (("Table", "table"), ("Cards", "cards")):          # how to show the medicines
            btn = tk.Button(top, text=text, relief="flat", bd=0, font=T.FONT, padx=12, pady=5,
                            cursor="hand2", highlightthickness=0, command=lambda m=mode: self.set_view(m))
            btn.pack(side="right", padx=(6, 0) if mode == "cards" else (6, 0), anchor="s",
                     pady=(0, 2))
            self.view_buttons[mode] = btn

        stats = tk.Frame(self, bg=T.BG)
        stats.pack(fill="x", padx=28)
        self.stat = {}
        for i, (key, text, accent, show) in enumerate([
            ("total", "Total medicines", T.GREEN, None),
            ("low", "Low stock", T.YELLOW, "Low stock"),
            ("soon", "Expiring in 90 days", "#ff9f1a", "Expiring soon"),
            ("expired", "Expired", T.RED, "Expired"),
        ]):
            stats.columnconfigure(i, weight=1, uniform="stat")
            box, value = stat_tile(stats, text, accent)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            bind_click(box, lambda s=show: self.set_filter(s))      # click a counter to filter
            self.stat[key] = value

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=28, pady=(16, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.render())
        search = T.entry(bar, 22)
        search.config(textvariable=self.search_var)
        search.pack(side="left", ipady=6)
        T.label(bar, "Code, name or batch", 9, color=T.MUTED).pack(side="left", padx=(8, 14))
        for text, value in FILTERS:
            chip = tk.Button(bar, text=text, relief="flat", bd=0, font=T.FONT, padx=10, pady=5,
                             cursor="hand2", highlightthickness=0, command=lambda v=value: self.set_filter(v))
            chip.pack(side="left", padx=(0, 6))
            self.chips[value] = chip

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 22))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        frame, self.tree = T.table(body, [
            ("sku", "Code", 80), ("name", "Medicine", 160), ("batch", "Batch", 80),
            ("qty", "Stock", 55), ("expiry", "Expiry", 95), ("status", "Status", 105),
        ], height=10)
        for column in ("sku", "name", "batch", "qty", "expiry", "status"):
            self.tree.column(column, minwidth=45)          # columns may shrink in a narrow window
        frame.grid(row=0, column=0, sticky="nsew")
        self.table_frame = frame

        # cards view: every medicine as a picture card
        self.cards_wrap = tk.Frame(body, bg=T.BG)
        self.cards_wrap.grid(row=0, column=0, sticky="nsew")
        self.canvas = tk.Canvas(self.cards_wrap, bg=T.BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.cards_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.grid_frame = tk.Frame(self.canvas, bg=T.BG)
        self.window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.bind("<Configure>", self.on_resize)
        self.grid_frame.bind("<Configure>",
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        style = ttk.Style(self)                      # roomier rows, only for this table
        style.configure("Inv.Treeview", background=T.CARD, fieldbackground=T.CARD, foreground=T.TEXT,
                        rowheight=36, borderwidth=0, font=T.FONT)
        style.configure("Inv.Treeview.Heading", background=T.SIDEBAR, foreground=T.MUTED,
                        relief="flat", font=T.FONT_BOLD, padding=(10, 9))
        style.map("Inv.Treeview", background=[("selected", "#1f3a30")], foreground=[("selected", T.GREEN)])
        style.map("Inv.Treeview.Heading", background=[("active", T.SIDEBAR)])
        self.tree.configure(style="Inv.Treeview")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        if self.can_edit:
            self.tree.bind("<Double-1>", lambda e: self.edit_selected())

        # details panel: picture, status, stock bar and the Edit / Delete buttons
        self.preview = T.card(body, width=PANEL_W)
        self.preview.grid(row=0, column=1, sticky="ns", padx=(14, 0))
        self.preview.pack_propagate(False)
        if self.can_edit:
            btns = tk.Frame(self.preview, bg=T.CARD)
            btns.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
            T.button(btns, "Edit", self.edit_selected).pack(side="left", fill="x", expand=True)
            T.button(btns, "Delete", self.delete_selected, "danger").pack(side="left", padx=(8, 0))
        pic = tk.Frame(self.preview, bg=T.FIELD, width=PIC_W, height=PIC_H)
        pic.pack(padx=16, pady=(16, 0))
        pic.pack_propagate(False)
        self.photo_label = tk.Label(pic, bg=T.FIELD, fg=T.MUTED, font=T.FONT, text="No picture")
        self.photo_label.place(relx=0.5, rely=0.5, anchor="center")
        self.p_name = T.label(self.preview, "Select a medicine", 13, True, wraplength=PIC_W, justify="left")
        self.p_name.pack(anchor="w", padx=16, pady=(14, 0))
        self.p_sub = T.label(self.preview, "Click a medicine to see its details.", 10, color=T.MUTED,
                             wraplength=PIC_W, justify="left")
        self.p_sub.pack(anchor="w", padx=16, pady=(2, 0))
        self.p_pill = tk.Label(self.preview, text="", bg=T.CARD, fg=T.MUTED, font=("Segoe UI", 9, "bold"))
        self.p_pill.pack(anchor="w", padx=16, pady=(10, 0))
        self.p_bar = tk.Canvas(self.preview, width=PIC_W, height=8, bg=T.FIELD, highlightthickness=0)
        self.p_bar.pack(padx=16, pady=(10, 0))
        self.p_stock = T.label(self.preview, "", 10, True)
        self.p_stock.pack(anchor="w", padx=16, pady=(6, 0))
        self.p_info = T.label(self.preview, "", 10, color=T.MUTED, wraplength=PIC_W, justify="left")
        self.p_info.pack(anchor="w", padx=16, pady=(8, 0))
        self.set_view(self.view_mode)

    # ---------- Cards / Table ----------
    def set_view(self, mode):
        self.view_mode = mode
        if mode == "cards":
            self.table_frame.grid_remove()
            self.cards_wrap.grid()
        else:
            self.cards_wrap.grid_remove()
            self.table_frame.grid()
        for m, btn in self.view_buttons.items():
            on = m == mode
            btn.config(bg=T.GREEN if on else T.FIELD, fg="#001a0d" if on else T.TEXT,
                       activebackground=T.GREEN if on else T.FIELD,
                       activeforeground="#001a0d" if on else T.TEXT)
        if self.rows:
            self.select(self.selected)

    def on_resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        cols = max(1, event.width // (CARD_W + 14))
        if cols != self.cols:
            self.cols = cols
            self.layout_cards()

    def on_wheel(self, event):
        if self.view_mode != "cards":
            return
        try:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except tk.TclError:
            pass

    def layout_cards(self):
        for i, card in enumerate(self.cards):
            card.grid(row=i // self.cols, column=i % self.cols, padx=(0, 14), pady=(0, 14), sticky="n")

    def primary_iid(self, sku):
        """The row that stands for a medicine: its next batch to use (FEFO), else any row of it."""
        info = self.info.get(sku)
        if info and info["next"]:
            return info["next"]["iid"]
        mine = [r for r in self.rows if r["sku"] == sku]
        return mine[0]["iid"] if mine else None

    def visible_meds(self, text):
        """Medicines to show as cards: filter chip + search, in name order (Binary Search Tree)."""
        shown = []
        for m in self.name_tree.in_order():
            info = self.info[m["sku"]]
            if not self.med_matches_filter(m["sku"], info):
                continue
            batches = " ".join(r["batch"] for r in self.rows if r["sku"] == m["sku"])
            if text and text not in f"{m['sku']} {m['name']} {batches}".lower():
                continue
            shown.append(m)
        return shown

    def med_matches_filter(self, sku, info):
        if self.filter_value is None:
            return True
        if self.filter_value == "Low stock":
            return sku in self.low_skus
        if self.filter_value == "Expiring soon":
            return info["soon"]
        if self.filter_value == "Expired":
            return info["expired"] > 0
        return info["stock"] <= 0                                    # Out of stock

    def render_cards(self, meds):
        for card in self.cards:
            card.destroy()
        self.cards = []
        if not meds:
            note = "No medicines yet." if not self.info else "No medicines match."
            empty = T.label(self.grid_frame, note, 11, color=T.MUTED)
            empty.grid(row=0, column=0, pady=30, sticky="w")
            self.cards.append(empty)
            return
        for m in meds:
            self.cards.append(self.make_card(m))
        self.layout_cards()

    def make_card(self, m):
        sku = m["sku"]
        info = self.info[sku]
        color = STATUS_COLOR[info["status"]]
        card = T.card(self.grid_frame, width=CARD_W, height=CARD_H)
        card.pack_propagate(False)
        card.sku = sku

        pic = tk.Frame(card, bg=T.FIELD, width=CARD_W - 24, height=122)
        pic.pack(padx=12, pady=(12, 8))
        pic.pack_propagate(False)
        if sku not in self.card_photos:
            self.card_photos[sku] = load_medicine_photo(sku, (CARD_W - 24, 122))
        photo = self.card_photos[sku]
        if photo:
            tk.Label(pic, image=photo, bg=T.FIELD).place(relx=0.5, rely=0.5, anchor="center")
        else:
            tk.Label(pic, text="No picture", bg=T.FIELD, fg=T.MUTED, font=T.FONT).place(
                relx=0.5, rely=0.5, anchor="center")

        T.label(card, m["name"], 11, True, wraplength=CARD_W - 28, justify="left").pack(anchor="w", padx=14)
        T.label(card, f"{sku}  \u2022  PHP {m['unit_price']:,.2f}", 9, color=T.MUTED).pack(
            anchor="w", padx=14, pady=(2, 0))
        T.label(card, f"\u25cf  {info['status']}", 10, True, color).pack(anchor="w", padx=14, pady=(8, 0))

        low = m["low_stock_level"]
        bar = tk.Canvas(card, width=CARD_W - 28, height=6, bg=T.FIELD, highlightthickness=0)
        bar.pack(padx=14, pady=(6, 0))
        ratio = min(1.0, info["stock"] / max(low * 2, 1))
        if ratio > 0:
            bar.create_rectangle(0, 0, (CARD_W - 28) * ratio, 6, width=0,
                                 fill=T.YELLOW if info["stock"] <= low else T.GREEN)
        T.label(card, f"{info['stock']} in stock", 10, True).pack(anchor="w", padx=14, pady=(4, 0))
        nxt = info["next"]
        T.label(card, f"Next: {nxt['batch']} \u2022 {nxt['expiry']}" if nxt else "No batch to use",
                8, color=T.MUTED).pack(anchor="w", padx=14, pady=(2, 0))
        if info["expired"]:
            T.label(card, f"{info['expired']} expired batch" + ("es" if info["expired"] > 1 else ""),
                    8, True, T.RED).pack(anchor="w", padx=14)

        def click(event=None, sku=sku):
            self.select(self.primary_iid(sku))

        def bind_all_children(widget):                       # click anywhere on the card
            widget.bind("<Button-1>", click)
            if self.can_edit:
                widget.bind("<Double-1>", lambda e: self.edit_selected())
            widget.configure(cursor="hand2")
            for child in widget.winfo_children():
                bind_all_children(child)
        bind_all_children(card)
        return card

    def select(self, iid):
        """Select one row (table) or card, and show its details on the right."""
        self.selected = iid if iid in self.by_iid else None
        if self.selected and self.tree.exists(self.selected):
            self.tree.selection_set(self.selected)
        else:
            self.tree.selection_remove(self.tree.selection())
        want = self.by_iid[self.selected]["sku"] if self.selected else None
        for card in self.cards:
            on = getattr(card, "sku", None) == want and want is not None
            card.config(highlightbackground=T.GREEN if on else T.BORDER, highlightthickness=2 if on else 1)
        self.show_preview(self.selected)

    # ---------- filter chips ----------
    def set_filter(self, value):
        self.filter_value = value
        for v, chip in self.chips.items():
            on = v == value
            chip.config(bg=T.GREEN if on else T.FIELD, fg="#001a0d" if on else T.TEXT,
                        activebackground=T.GREEN if on else T.FIELD,
                        activeforeground="#001a0d" if on else T.TEXT)
        self.render()

    # ---------- data ----------
    def refresh(self):
        meds = db.get_medicines()
        self.meds = {m["sku"]: m for m in meds}
        self.stock = db.stock_by_sku()
        batches = db.get_batches(in_stock_only=True)
        low_skus = {m["sku"] for m in meds if self.stock.get(m["sku"], 0) <= m["low_stock_level"]}
        self.low_skus = low_skus

        rows = []
        for b in batches:
            status = db.expiry_status(b["expiry_date"])
            if status == "OK" and b["sku"] in low_skus:
                status = "Low stock"
            rows.append({"iid": f"b{b['id']}", "sku": b["sku"], "name": b["medicine_name"],
                         "batch": b["batch_no"], "qty": b["quantity"],
                         "expiry": b["expiry_date"], "status": status})
        have = {b["sku"] for b in batches}
        for m in meds:
            if m["sku"] not in have:
                rows.append({"iid": f"m{m['sku']}", "sku": m["sku"], "name": m["name"],
                             "batch": "-", "qty": 0, "expiry": "-", "status": "Out of stock"})

        # Merge Sort by expiry date (FEFO order); rows without a batch go last
        self.rows = merge_sort(rows, key=lambda r: (r["expiry"] == "-", r["expiry"]))
        self.by_iid = {r["iid"]: r for r in self.rows}

        self.name_tree = BST.build(meds, key=lambda m: m["name"].lower())     # Binary Search Tree
        self.card_photos.clear()
        self.info = {}
        for m in meds:
            sku = m["sku"]
            mine = [r for r in self.rows if r["sku"] == sku and r["qty"] > 0]   # already in FEFO order
            stock = self.stock.get(sku, 0)
            soon = any(r["status"] == "Expiring soon" for r in mine)
            if stock <= 0:
                status = "Out of stock"
            elif sku in low_skus:
                status = "Low stock"
            elif soon:
                status = "Expiring soon"
            else:
                status = "OK"
            self.info[sku] = {"stock": stock, "status": status, "soon": soon,
                              "expired": sum(r["status"] == "Expired" for r in mine),
                              "next": next((r for r in mine if r["status"] != "Expired"), None)}

        self.stat["total"].config(text=str(len(meds)))
        self.stat["low"].config(text=str(len(low_skus)))
        self.stat["soon"].config(text=str(sum(r["status"] == "Expiring soon" for r in rows)))
        self.stat["expired"].config(text=str(sum(r["status"] == "Expired" for r in rows)))
        self.set_filter(self.filter_value)

    def matches_filter(self, row):
        if self.filter_value is None:
            return True
        if self.filter_value == "Low stock":              # same rule as the Low stock counter
            return row["sku"] in self.low_skus
        return row["status"] == self.filter_value

    def render(self):
        text = self.search_var.get().strip().lower()
        shown = [r for r in self.rows
                 if self.matches_filter(r) and text in f"{r['sku']} {r['name']} {r['batch']}".lower()]
        T.fill(self.tree, [
            (r["iid"], (r["sku"], r["name"], r["batch"], r["qty"], r["expiry"], f"\u25cf  {r['status']}"),
             STATUS_TAG[r["status"]])
            for r in shown
        ])
        meds = self.visible_meds(text)
        self.render_cards(meds)

        keep = self.selected if self.selected in self.by_iid else None
        if keep:
            if self.view_mode == "table":
                still_there = any(r["iid"] == keep for r in shown)
            else:
                still_there = self.by_iid[keep]["sku"] in {m["sku"] for m in meds}
            if not still_there:
                keep = None
        self.select(keep)

    # ---------- details panel ----------
    def on_select(self):
        sel = self.tree.selection()
        if sel and sel[0] != self.selected:
            self.select(sel[0])

    def show_preview(self, iid):
        row = self.by_iid.get(iid) if iid else None
        self.p_bar.delete("all")
        if row is None:
            self.photo = None
            self.photo_label.config(image="", text="No picture")
            self.p_name.config(text="Select a medicine")
            self.p_sub.config(text="Click a medicine to see its details.")
            self.p_pill.config(text="", bg=T.CARD, padx=0)
            self.p_stock.config(text="")
            self.p_info.config(text="")
            return
        sku = row["sku"]
        med = self.meds[sku]
        self.photo = load_medicine_photo(sku, (PIC_W, PIC_H))
        if self.photo:
            self.photo_label.config(image=self.photo, text="")
        else:
            self.photo_label.config(image="", text="No picture")

        stock, low = self.stock.get(sku, 0), med["low_stock_level"]
        color = STATUS_COLOR[row["status"]]
        self.p_name.config(text=med["name"])
        self.p_sub.config(text=f"{sku}   •   PHP {med['unit_price']:,.2f} each")
        self.p_pill.config(text=row["status"], fg=color, bg=T.FIELD, padx=10, pady=2)

        ratio = min(1.0, stock / max(low * 2, 1))              # a full bar = twice the low-stock level
        bar_color = T.RED if stock <= 0 else T.YELLOW if stock <= low else T.GREEN
        if ratio > 0:
            self.p_bar.create_rectangle(0, 0, PIC_W * ratio, 8, fill=bar_color, width=0)
        self.p_stock.config(text=f"{stock} in stock")

        nxt = next((r for r in self.rows
                    if r["sku"] == sku and r["qty"] > 0 and r["status"] != "Expired"), None)
        self.p_info.config(text=(f"Low-stock level: {low}\n"
                                 + (f"Next to use: {nxt['batch']} (exp {nxt['expiry']})"
                                    if nxt else "Next to use: none")))

    # ---------- actions (Check-up / Admin only) ----------
    def open_add(self):
        AddDialog(self, self.refresh)

    def edit_selected(self):
        if not self.selected:
            messagebox.showinfo("Select a medicine", "Click a medicine first.")
            return
        EditDialog(self, self.by_iid[self.selected], self.refresh)

    def delete_selected(self):
        if not self.selected:
            messagebox.showinfo("Select a medicine", "Click a medicine first.")
            return
        iid = self.selected
        if self.view_mode == "table" and iid.startswith("b"):
            if messagebox.askyesno("Delete batch", "Delete this batch from the inventory?"):
                db.delete_batch(int(iid[1:]))
        else:
            sku = self.by_iid[iid]["sku"]
            name = self.meds[sku]["name"]
            if messagebox.askyesno("Delete medicine", f"Delete {name} ({sku}) and all its batches?"):
                try:
                    db.delete_medicine(sku)
                    remove_medicine_image(sku)
                except sqlite3.IntegrityError:
                    messagebox.showerror("Cannot delete", "This medicine already has request history.")
        self.selected = None
        self.refresh()


class AddDialog(tk.Toplevel):
    """Add a new medicine (code, name, price, low-stock level and an optional picture)."""

    def __init__(self, parent, on_added):
        super().__init__(parent)
        self.on_added = on_added
        self.new_image = None
        self.title("Add medicine")
        self.configure(bg=T.BG)
        self.resizable(False, False)

        body = T.card(self)
        body.pack(padx=20, pady=20)
        pad = {"padx": 24}
        T.label(body, "Add new medicine", 13, True).pack(anchor="w", pady=(20, 10), **pad)
        line = tk.Frame(body, bg=T.CARD)
        line.pack(fill="x", **pad)
        box, self.sku_e = T.labeled_entry(line, "Med code (SKU)", 14)
        box.pack(side="left", padx=(0, 10))
        box, self.name_e = T.labeled_entry(line, "Medicine name", 28)
        box.pack(side="left")
        line = tk.Frame(body, bg=T.CARD)
        line.pack(fill="x", pady=(10, 0), **pad)
        box, self.price_e = T.labeled_entry(line, "Unit price (PHP)", 14)
        box.pack(side="left", padx=(0, 10))
        box, self.low_e = T.labeled_entry(line, "Low-stock level", 14)
        box.pack(side="left")
        self.low_e.insert(0, "20")

        T.label(body, "Picture", 11, True).pack(anchor="w", pady=(16, 6), **pad)
        T.button(body, "Choose picture", self.choose_image, "ghost").pack(anchor="w", **pad)
        self.hint = T.label(body, "No picture chosen. " + ADD_HINT, 9, color=T.MUTED,
                            wraplength=380, justify="left")
        self.hint.pack(anchor="w", pady=(6, 0), **pad)

        row = tk.Frame(body, bg=T.CARD)
        row.pack(fill="x", pady=22, **pad)
        T.button(row, "Add medicine", self.add).pack(side="left")
        T.button(row, "Cancel", self.destroy, "ghost").pack(side="left", padx=8)

        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()
        self.sku_e.focus_set()

    def choose_image(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a picture of the medicine",
                                          filetypes=PICTURE_TYPES)
        if path:
            self.new_image = path
            self.hint.config(text=f"Picture selected: {os.path.basename(path)}.  {ADD_HINT}")

    def add(self):
        sku = self.sku_e.get().strip().upper()
        name = self.name_e.get().strip()
        try:
            price = float(self.price_e.get())
            low = int(self.low_e.get())
        except ValueError:
            messagebox.showwarning("Check the numbers", "Price and low-stock level must be numbers.", parent=self)
            return
        if not sku or not name or price < 0 or low < 0:
            messagebox.showwarning("Missing details", "Fill in the code and name, with valid numbers.",
                                   parent=self)
            return
        try:
            db.add_medicine(sku, name, price, low)
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate code", f"A medicine with code {sku} already exists.", parent=self)
            return
        if self.new_image:
            try:
                save_medicine_image(sku, self.new_image)
            except ImportError:
                messagebox.showinfo("Pillow needed", PILLOW_HINT, parent=self)
            except Exception as err:
                messagebox.showerror("Picture problem",
                                     f"The medicine was added, but its picture failed:\n{err}", parent=self)
        self.destroy()
        self.on_added()


class EditDialog(tk.Toplevel):
    """Edit a medicine's details, its batch (if a batch row was selected) and its picture."""

    def __init__(self, parent, row, on_saved):
        super().__init__(parent)
        self.on_saved = on_saved
        self.sku = row["sku"]
        self.med = db.get_medicine(self.sku)
        self.batch = db.get_batch(int(row["iid"][1:])) if row["iid"].startswith("b") else None
        self.new_image = None
        self.remove_image = False
        self.title(f"Edit {self.sku}")
        self.configure(bg=T.BG)
        self.resizable(False, False)

        body = T.card(self)
        body.pack(padx=20, pady=20)
        pad = {"padx": 24}
        T.label(body, f"Edit medicine  •  {self.sku}", 13, True).pack(anchor="w", pady=(20, 10), **pad)

        box, self.name_e = T.labeled_entry(body, "Medicine name", 42)
        box.pack(fill="x", **pad)
        self.name_e.insert(0, self.med["name"])
        line = tk.Frame(body, bg=T.CARD)
        line.pack(fill="x", pady=(10, 0), **pad)
        box, self.price_e = T.labeled_entry(line, "Unit price (PHP)", 14)
        box.pack(side="left", padx=(0, 10))
        self.price_e.insert(0, f"{self.med['unit_price']:g}")
        box, self.low_e = T.labeled_entry(line, "Low-stock level", 14)
        box.pack(side="left")
        self.low_e.insert(0, str(self.med["low_stock_level"]))

        if self.batch:
            T.label(body, "This batch", 11, True).pack(anchor="w", pady=(16, 6), **pad)
            line = tk.Frame(body, bg=T.CARD)
            line.pack(fill="x", **pad)
            box, self.batch_e = T.labeled_entry(line, "Batch no.", 14)
            box.pack(side="left", padx=(0, 10))
            self.batch_e.insert(0, self.batch["batch_no"])
            box, self.qty_e = T.labeled_entry(line, "Quantity", 9)
            box.pack(side="left", padx=(0, 10))
            self.qty_e.insert(0, str(self.batch["quantity"]))
            box, self.exp_e = T.labeled_entry(line, "Expiry (YYYY-MM-DD)", 16)
            box.pack(side="left")
            self.exp_e.insert(0, self.batch["expiry_date"])

        T.label(body, "Picture", 11, True).pack(anchor="w", pady=(16, 6), **pad)
        line = tk.Frame(body, bg=T.CARD)
        line.pack(fill="x", **pad)
        T.button(line, "Choose picture", self.choose_image, "ghost").pack(side="left")
        T.button(line, "Remove picture", self.mark_remove, "danger").pack(side="left", padx=8)
        has = os.path.exists(_image_path(self.sku))
        self.pic_status = T.label(body, "Current picture will be kept." if has else "No picture yet.",
                                  9, color=T.MUTED)
        self.pic_status.pack(anchor="w", pady=(6, 0), **pad)

        row_btn = tk.Frame(body, bg=T.CARD)
        row_btn.pack(fill="x", pady=22, **pad)
        T.button(row_btn, "Save changes", self.save).pack(side="left")
        T.button(row_btn, "Cancel", self.destroy, "ghost").pack(side="left", padx=8)

        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()

    def choose_image(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a picture of the medicine",
                                          filetypes=PICTURE_TYPES)
        if path:
            self.new_image, self.remove_image = path, False
            self.pic_status.config(text=f"New picture: {os.path.basename(path)}")

    def mark_remove(self):
        self.new_image, self.remove_image = None, True
        self.pic_status.config(text="The picture will be removed when you save.")

    def save(self):
        name = self.name_e.get().strip()
        try:
            price = float(self.price_e.get())
            low = int(self.low_e.get())
        except ValueError:
            messagebox.showwarning("Check the numbers", "Price and low-stock level must be numbers.", parent=self)
            return
        if not name or price < 0 or low < 0:
            messagebox.showwarning("Missing details", "Enter a name and valid numbers.", parent=self)
            return

        batch_args = None
        if self.batch:
            batch_no = self.batch_e.get().strip()
            try:
                qty = int(self.qty_e.get())
                expiry = datetime.strptime(self.exp_e.get().strip(), "%Y-%m-%d").date()
            except ValueError:
                messagebox.showwarning("Check the batch", "Quantity must be a whole number and the "
                                       "expiry date must look like 2027-06-30.", parent=self)
                return
            if not batch_no or qty < 0:
                messagebox.showwarning("Check the batch", "Enter a batch number and a quantity of 0 or more.",
                                       parent=self)
                return
            batch_args = (self.batch["id"], batch_no, qty, expiry.isoformat())

        try:
            if self.remove_image:
                remove_medicine_image(self.sku)
            elif self.new_image:
                save_medicine_image(self.sku, self.new_image)
        except ImportError:
            messagebox.showinfo("Pillow needed", PILLOW_HINT, parent=self)
            return
        except Exception as err:
            messagebox.showerror("Picture problem", str(err), parent=self)
            return

        db.update_medicine(self.sku, name, price, low)
        if batch_args:
            db.update_batch(*batch_args)
        self.destroy()
        self.on_saved()