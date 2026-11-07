import tkinter as tk
from tkinter import ttk

from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.ui.inventory_view import load_medicine_photo
from src.utils import database as db, subsidy

CARD_W, CARD_H = 214, 310
STATUS_COLOR = {"Available": T.GREEN, "Low stock": T.YELLOW, "Out of stock": T.RED}
SHORT_NAME = {"Senior Citizen": "Senior"}
FILTERS = ["All", "Available", "Low stock", "Out of stock"]


def stock_status(stock, low_level):
    """What the customer sees: Available, Low stock or Out of stock."""
    if stock <= 0:
        return "Out of stock"
    if stock <= low_level:
        return "Low stock"
    return "Available"


def discount_lines(price):
    """What each discounted group pays per unit, e.g. 'Senior / PWD: PHP 1.00'."""
    groups = {}
    for category in subsidy.CATEGORIES:
        rate = subsidy.subsidy_rate(category)
        if rate > 0:
            groups.setdefault(rate, []).append(SHORT_NAME.get(category, category))
    return [f"{' / '.join(names)}: PHP {price * (1 - rate):,.2f}" for rate, names in groups.items()]


class CatalogView(tk.Frame):
    """Medicines with pictures, prices and availability, to show to residents."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.meds = []
        self.stock = {}
        self.cards = []
        self.photos = {}            # keeps the pictures alive (Tk drops unreferenced images)
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
        T.header(self, "Available Medicines",
                 "Check which medicines are in stock and what each group pays.").pack(
            fill="x", padx=28, pady=(22, 12))

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=28, pady=(0, 12))
        T.label(bar, "Search", 9, color=T.MUTED).pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.render())
        search = T.entry(bar, 30)
        search.config(textvariable=self.search_var)
        search.pack(side="left", ipady=5)
        self.filter_combo = T.combo(bar, 14, FILTERS)
        self.filter_combo.pack(side="left", padx=(10, 0))
        self.filter_combo.current(0)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self.render())
        T.button(bar, "Refresh", self.refresh, "ghost").pack(side="right")
        self.summary = T.label(bar, "", 10, color=T.MUTED)
        self.summary.pack(side="right", padx=14)

        wrap = tk.Frame(self, bg=T.BG)
        wrap.pack(fill="both", expand=True, padx=28, pady=(0, 18))
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
        cols = max(1, event.width // (CARD_W + 14))
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
            card.grid(row=i // cols, column=i % cols, padx=(0, 14), pady=(0, 14), sticky="n")

    # ---------- data ----------
    def refresh(self):
        self.meds = db.get_medicines()
        self.stock = db.stock_by_sku()
        self.photos.clear()
        self.render()

    def visible_medicines(self):
        text = self.search_var.get().strip().lower()
        wanted = self.filter_combo.get() or "All"
        shown = []
        for m in self.meds:
            status = stock_status(self.stock.get(m["sku"], 0), m["low_stock_level"])
            if wanted != "All" and status != wanted:
                continue
            if text and text not in f"{m['sku']} {m['name']}".lower():
                continue
            shown.append(m)
        return merge_sort(shown, key=lambda m: m["name"].lower())          # Merge Sort by name

    def render(self):
        for card in self.cards:
            card.destroy()
        self.cards = []
        shown = self.visible_medicines()
        in_stock = sum(1 for m in self.meds if self.stock.get(m["sku"], 0) > 0)
        self.summary.config(text=f"{len(self.meds)} medicines  \u2022  {in_stock} in stock")

        if not shown:
            note = ("No medicines yet. Add them in the Inventory screen." if not self.meds
                    else "No medicines match your search.")
            empty = T.label(self.grid_frame, note, 11, color=T.MUTED)
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

        pic = tk.Frame(card, bg=T.FIELD, width=CARD_W - 24, height=130)
        pic.pack(padx=12, pady=(12, 8))
        pic.pack_propagate(False)
        if m["sku"] not in self.photos:
            self.photos[m["sku"]] = load_medicine_photo(m["sku"], (CARD_W - 24, 130))
        photo = self.photos[m["sku"]]
        if photo:
            tk.Label(pic, image=photo, bg=T.FIELD).place(relx=0.5, rely=0.5, anchor="center")
        else:
            tk.Label(pic, text="No picture", bg=T.FIELD, fg=T.MUTED, font=T.FONT).place(
                relx=0.5, rely=0.5, anchor="center")

        T.label(card, m["name"], 11, True, wraplength=CARD_W - 28, justify="left").pack(anchor="w", padx=14)
        T.label(card, f"PHP {m['unit_price']:,.2f} each", 10).pack(anchor="w", padx=14, pady=(2, 0))
        text = {"Available": f"Available  \u2022  {stock} in stock",
                "Low stock": f"Low stock  \u2022  {stock} left",
                "Out of stock": "Out of stock"}[status]
        T.label(card, text, 10, True, STATUS_COLOR[status]).pack(anchor="w", padx=14, pady=(6, 4))
        for line in discount_lines(m["unit_price"]):
            T.label(card, line, 8, color=T.MUTED).pack(anchor="w", padx=14)
        return card