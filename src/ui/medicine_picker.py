import tkinter as tk
from tkinter import ttk

from src.dsa.bst import BST
from src.ui import theme as T
from src.ui.catalog_view import STATUS_COLOR, stock_status
from src.ui.inventory_view import load_medicine_photo
from src.utils import database as db

CARD_W, CARD_H = 168, 212
PIC_W, PIC_H = CARD_W - 20, 96


class MedicinePicker(tk.Toplevel):
    """A window that shows ALL medicines as picture cards. Click one and on_pick(sku) is called."""

    def __init__(self, parent, on_pick):
        super().__init__(parent)
        self.title("Choose a medicine")
        self.configure(bg=T.BG)
        self.geometry("820x560")
        self.minsize(520, 360)
        self.transient(parent.winfo_toplevel())
        self.on_pick = on_pick
        self.meds = db.get_medicines()
        self.stock = db.stock_by_sku()
        self.tree = BST.build(self.meds, key=lambda m: m["name"].lower())     # Binary Search Tree
        self.cards = []
        self.photos = {}
        self.cols = 4
        self._build()
        self.bind_all("<MouseWheel>", self.on_wheel)
        self.bind("<Escape>", lambda e: self.destroy())
        self.render()
        self.search.focus_set()
        self.grab_set()

    def destroy(self):
        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        super().destroy()

    # ---------- layout ----------
    def _build(self):
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=18, pady=(16, 8))
        T.label(top, "All medicines", 14, True).pack(side="left")
        self.count_label = T.label(top, "", 9, color=T.MUTED)
        self.count_label.pack(side="right")

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=18, pady=(0, 10))
        T.label(bar, "Search", 9, color=T.MUTED).pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.render())
        self.search = T.entry(bar, 28)
        self.search.config(textvariable=self.search_var)
        self.search.pack(side="left", ipady=5)
        T.label(bar, "Click a medicine to choose it.", 9, color=T.MUTED).pack(side="right")

        wrap = tk.Frame(self, bg=T.BG)
        wrap.pack(fill="both", expand=True, padx=18, pady=(0, 16))
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
        for i, card in enumerate(self.cards):
            card.grid(row=i // self.cols, column=i % self.cols, padx=(0, 12), pady=(0, 12), sticky="n")

    # ---------- cards ----------
    def visible(self):
        text = self.search_var.get().strip().lower()
        if not text:
            return self.tree.in_order()                      # all medicines, sorted by name
        found = self.tree.starts_with(text)                  # BST prefix search
        if found:
            return found
        return [m for m in self.tree.in_order() if text in f"{m['sku']} {m['name']}".lower()]

    def render(self):
        for card in self.cards:
            card.destroy()
        self.cards = []
        shown = self.visible()
        self.count_label.config(text=f"{len(shown)} of {len(self.meds)} medicines")
        if not shown:
            note = "No medicines yet." if not self.meds else "No medicines match your search."
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

        def bind_click(widget):                              # the whole card is clickable
            widget.bind("<Button-1>", lambda e, sku=m["sku"]: self.choose(sku))
            for child in widget.winfo_children():
                bind_click(child)
        card.configure(cursor="hand2")
        bind_click(card)
        return card

    def choose(self, sku):
        self.destroy()
        self.on_pick(sku)


def open_medicine_picker(parent, on_pick):
    """Open the window with every medicine. on_pick(sku) runs when one is clicked."""
    return MedicinePicker(parent, on_pick)