from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.dsa.bst import BST
from src.dsa.hash_table import HashTable
from src.ui import theme as T
from src.ui.inventory_view import load_medicine_photo
from src.ui.scan_dialog import open_scanner
from src.utils import auth, database as db, subsidy
from src.utils.scanner import bind_scanner

CARD_W, CARD_H = 214, 352
CART_W = 290
STATUS_COLOR = {"Available": T.GREEN, "Low stock": T.YELLOW, "Out of stock": T.RED}
SHORT_NAME = {"Senior Citizen": "Senior"}
CART = {"owner": None, "items": {}}   # sku -> quantity. Kept while the BHW moves between screens.
WALK_IN = "Walk-in customer"          # shared record for people who order without a resident ID
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


def can_order():
    """Only the BHW (at the counter) and the Admin place orders. The doctor prescribes in Check-up."""
    user = auth.current_user()
    return bool(user) and user["role"] in ("BHW", "Admin")


def reserved_stock(sku):
    """Stock already promised to orders that are waiting in the service queue."""
    return sum(r["quantity"] for r in db.get_requests("Queued") if r["sku"] == sku)


def free_stock(sku):
    """What a new order can still count on: stock on the shelf minus what the queue already holds."""
    return max(0, db.available_stock(sku) - reserved_stock(sku))


def walk_in_resident():
    """The shared 'Walk-in customer' (Regular price). It is created the first time it is needed."""
    for _ in range(2):
        for r in db.get_residents():
            if r["full_name"] == WALK_IN:
                return r
        db.add_resident(WALK_IN, "Regular", "No resident ID (walk-in)")
    raise RuntimeError("Could not create the walk-in record.")


def cart_items():
    """The order cart of the logged-in user. A different user starts with an empty cart."""
    user = auth.current_user()
    owner = user["id"] if user else None
    if CART["owner"] != owner:
        CART["owner"] = owner
        CART["items"] = {}
    return CART["items"]


ID_HINT = "Scan the resident ID card, or type the ID and press Enter."


CATEGORIES = getattr(subsidy, "CATEGORIES", ["Regular", "Senior Citizen", "PWD", "Low-income"])


class RegisterDialog(tk.Toplevel):
    """Register a new resident (name, category, address) without leaving the checkout."""

    def __init__(self, parent, on_done):
        super().__init__(parent)
        self.title("Register resident")
        self.configure(bg=T.BG)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.on_done = on_done
        box = tk.Frame(self, bg=T.BG)
        box.pack(padx=24, pady=20)
        T.label(box, "Register new resident", 14, True).pack(anchor="w", pady=(0, 10))
        row, self.name_e = T.labeled_entry(box, "Full name", 34)
        row.pack(fill="x")
        T.label(box, "Category", 9, color=T.MUTED).pack(anchor="w", pady=(10, 0))
        self.cat = T.combo(box, 32, CATEGORIES)
        self.cat.pack(fill="x", ipady=3, pady=(2, 0))
        self.cat.current(0)
        row, self.addr_e = T.labeled_entry(box, "Address", 34)
        row.pack(fill="x", pady=(10, 0))
        self.msg = T.label(box, "The discount applies to Senior Citizen, PWD and Low-income. "
                                "Check the ID before choosing one.", 9, color=T.MUTED, wraplength=330,
                           justify="left")
        self.msg.pack(anchor="w", pady=(10, 0))
        buttons = tk.Frame(box, bg=T.BG)
        buttons.pack(fill="x", pady=(14, 0))
        T.button(buttons, "Register", self.save).pack(side="right")
        T.button(buttons, "Cancel", self.destroy, "ghost").pack(side="right", padx=8)
        self.name_e.focus_set()
        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def save(self):
        name = self.name_e.get().strip()
        if not name:
            self.msg.config(text="Type the resident's full name.", fg=T.RED)
            return
        code = db.add_resident(name, self.cat.get() or "Regular", self.addr_e.get().strip())
        self.destroy()
        self.on_done(code)


class CheckoutDialog(tk.Toplevel):
    """Pay for everything in the cart. The customer chooses Regular price or With discount (resident ID).

    Each medicine becomes one request in the Requests screen: the service queue when there is
    enough free stock, otherwise the Pending list.
    """

    def __init__(self, parent, lines, on_done):
        super().__init__(parent)
        self.title("Checkout")
        self.configure(bg=T.BG)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.lines = lines                                   # [(medicine, quantity), ...]
        self.on_done = on_done
        self.mode = "regular"                                # "regular" or "discount"
        self.resident = None
        self.residents = HashTable()                         # Hash Table: scanned ID -> resident
        self.residents.load(db.get_residents(), "scanned_id")
        self._build()
        self.set_mode("regular")
        self.grab_set()

    def _build(self):
        box = tk.Frame(self, bg=T.BG)
        box.pack(padx=24, pady=20)
        T.label(box, "Checkout", 14, True).pack(anchor="w")
        T.label(box, f"{len(self.lines)} medicine" + ("s" if len(self.lines) != 1 else ""), 10,
                color=T.MUTED).pack(anchor="w", pady=(2, 8))

        frame, self.tree = T.table(box, [("name", "Medicine", 170), ("qty", "Qty", 44),
                                         ("price", "Price", 84), ("goes", "Goes to", 96)],
                                   height=min(max(len(self.lines), 2), 6))
        frame.pack(fill="x")

        T.label(box, "How will the customer pay?", 10, True).pack(anchor="w", pady=(14, 0))
        self.mode_row = tk.Frame(box, bg=T.BG)
        self.mode_row.pack(fill="x", pady=(6, 0))
        self.mode_buttons = {}
        for mode, text in (("regular", "Regular price"), ("discount", "With discount")):
            btn = tk.Button(self.mode_row, text=text, relief="flat", bd=0, font=T.FONT_BOLD, padx=16, pady=8,
                            cursor="hand2", highlightthickness=0, command=lambda m=mode: self.set_mode(m))
            btn.pack(side="left", fill="x", expand=True, padx=(0, 6) if mode == "regular" else 0)
            self.mode_buttons[mode] = btn
        self.mode_hint = T.label(box, "", 9, color=T.MUTED, wraplength=400, justify="left")
        self.mode_hint.pack(anchor="w", pady=(6, 0))

        # only shown when "With discount" is chosen
        self.id_box = tk.Frame(box, bg=T.BG)
        row = tk.Frame(self.id_box, bg=T.BG)
        row.pack(fill="x", pady=(8, 4))
        self.id_entry = T.entry(row, 20)
        self.id_entry.pack(side="left", fill="x", expand=True, ipady=6)
        handle = bind_scanner(self.id_entry, self.find_resident)
        self.id_entry.bind("<KeyRelease>", self.on_id_edit, add="+")
        T.button(row, "Find", handle).pack(side="left", padx=(8, 0))
        T.button(row, "Camera", lambda: open_scanner(self, self.find_resident), "ghost").pack(
            side="left", padx=(6, 0))
        self.res_label = T.label(self.id_box, ID_HINT, 10, color=T.MUTED, wraplength=400, justify="left")
        self.res_label.pack(anchor="w")
        T.button(self.id_box, "No ID yet? Register a new resident", self.register_new, "ghost").pack(
            anchor="w", pady=(6, 0))

        self.total_label = T.label(box, "", 12, True, wraplength=400, justify="left")
        self.total_label.pack(anchor="w", pady=(14, 0))
        self.note_label = T.label(box, "", 9, color=T.MUTED, wraplength=400, justify="left")
        self.note_label.pack(anchor="w", pady=(2, 0))
        self.msg_label = T.label(box, "", 9, color=T.RED, wraplength=400, justify="left")
        self.msg_label.pack(anchor="w", pady=(6, 0))

        buttons = tk.Frame(box, bg=T.BG)
        buttons.pack(fill="x", pady=(14, 0))
        T.button(buttons, "Place order", self.place_order).pack(side="right")
        T.button(buttons, "Cancel", self.destroy, "ghost").pack(side="right", padx=8)

    # ---------- the two choices ----------
    def set_mode(self, mode):
        self.mode = mode
        for key, btn in self.mode_buttons.items():
            on = key == mode
            btn.config(bg=T.GREEN if on else T.FIELD, fg="#001a0d" if on else T.TEXT,
                       activebackground=T.GREEN if on else T.FIELD,
                       activeforeground="#001a0d" if on else T.TEXT)
        self.msg_label.config(text="")
        if mode == "discount":
            self.mode_hint.config(text="Senior citizen, PWD or low-income resident. The ID gives the discount.")
            self.id_box.pack(fill="x", after=self.mode_hint)
            self.id_entry.focus_set()
        else:
            self.mode_hint.config(text="Anyone can buy at the regular price. No ID needed.")
            self.id_box.pack_forget()
            self.resident = None
            self.id_entry.delete(0, "end")
            self.res_label.config(text=ID_HINT, fg=T.MUTED)
        self.update_prices()

    def on_id_edit(self, event=None):
        """Changing the ID box forgets the resident that was found before."""
        typed = self.id_entry.get().strip().upper()
        if self.resident is not None and typed != self.resident["scanned_id"].upper():
            self.resident = None
            self.res_label.config(text=ID_HINT, fg=T.MUTED)
            self.msg_label.config(text="")
            self.update_prices()

    def find_resident(self, code):
        resident = self.residents.get(code)
        self.resident = resident
        if resident is None:
            self.res_label.config(text=f"No resident with ID '{code}'.", fg=T.RED)
        else:
            rate = subsidy.subsidy_rate(resident["category"]) * 100
            self.res_label.config(
                text=f"{resident['full_name']}  \u2022  {resident['category']}"
                     + (f"  \u2022  {rate:.0f}% discount" if rate else "  \u2022  no discount for this category"),
                fg=T.GREEN if rate else T.YELLOW)
        self.msg_label.config(text="")
        self.update_prices()

    def register_new(self):
        RegisterDialog(self, self.after_register)

    def after_register(self, code):
        """A resident was just registered: reload the hash table and use that resident for the discount."""
        self.residents.clear()
        self.residents.load(db.get_residents(), "scanned_id")
        self.id_entry.delete(0, "end")
        self.id_entry.insert(0, code)
        self.find_resident(code)

    def update_prices(self):
        discounted = self.mode == "discount" and self.resident is not None
        category = self.resident["category"] if discounted else "Regular"
        rows, total, saved, pending = [], 0.0, 0.0, 0
        for i, (m, qty) in enumerate(self.lines):
            calc = subsidy.calculate(m["unit_price"], qty, category)
            total += calc["total"]
            saved += calc["subsidy"]
            waits = free_stock(m["sku"]) < qty
            pending += waits
            rows.append((i, (m["name"], qty, f"{calc['total']:,.2f}", "Pending" if waits else "Queue"),
                         "warn" if waits else None))
        T.fill(self.tree, rows)
        self.total_label.config(text=f"Total: PHP {total:,.2f}"
                                     + (f"   (you save PHP {saved:,.2f})" if saved else ""))
        if pending:
            self.note_label.config(text=f"{pending} medicine(s) have not enough free stock. They will wait in "
                                        "the Pending list until stock arrives.", fg=T.YELLOW)
        elif self.mode == "discount" and self.resident is None:
            self.note_label.config(text="Scan the ID to see the discounted prices.", fg=T.MUTED)
        elif self.mode == "regular":
            self.note_label.config(text="Regular price, no discount.", fg=T.MUTED)
        else:
            self.note_label.config(text="")

    def place_order(self):
        if self.mode == "discount" and self.resident is None:
            self.msg_label.config(text="Scan or type a valid resident ID for the discount, "
                                       "or choose Regular price.")
            return
        user = auth.current_user()
        buyer = self.resident if self.mode == "discount" else walk_in_resident()      # regular = walk-in customer
        category = buyer["category"] if self.mode == "discount" else "Regular"
        lines, total, saved = [], 0.0, 0.0
        for m, qty in self.lines:
            status = "Queued" if free_stock(m["sku"]) >= qty else "Pending"           # checked again right now
            req_id = db.add_request(buyer["id"], m["sku"], qty, status, user["id"] if user else None)
            calc = subsidy.calculate(m["unit_price"], qty, category)
            total += calc["total"]
            saved += calc["subsidy"]
            lines.append((req_id, m["name"], qty, m["unit_price"], calc["total"], status))
        receipt = {"buyer": buyer["full_name"], "category": category, "lines": lines, "total": total,
                   "saved": saved, "staff": user["full_name"] if user and "full_name" in user.keys() else ""}
        parent = self.master
        self.destroy()
        self.on_done()                                       # empties the cart and refreshes the cards
        ReceiptDialog(parent, receipt)


def receipt_text(r):
    """The receipt as plain text (shown on screen and saved to a file)."""
    w = 44
    out = ["BARANGAY MEDICINE SYSTEM".center(w), "ORDER RECEIPT".center(w),
           datetime.now().strftime("%Y-%m-%d  %H:%M").center(w), "-" * w,
           f"Customer : {r['buyer']}", "Price     : " + ("Regular price" if r["category"] == "Regular" else f"{r['category']} discount")]
    if r["staff"]:
        out.append(f"Served by : {r['staff']}")
    out.append("-" * w)
    for req_id, name, qty, price, line_total, status in r["lines"]:
        out.append(name[:w])
        out.append(f"  {qty} x {price:,.2f}".ljust(26) + f"{line_total:>10,.2f}")
        out.append(f"  Request #{req_id}  {'in queue' if status == 'Queued' else 'waiting for stock'}")
    out.append("-" * w)
    if r["saved"]:
        out.append("Discount".ljust(26) + f"{-r['saved']:>10,.2f}")
    out.append("TOTAL (PHP)".ljust(26) + f"{r['total']:>10,.2f}")
    out += ["", "Thank you!".center(w)]
    return "\n".join(out)


class ReceiptDialog(tk.Toplevel):
    """Receipt shown after the order is placed."""

    def __init__(self, parent, receipt):
        super().__init__(parent)
        self.title("Receipt")
        self.configure(bg=T.BG)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.text = receipt_text(receipt)
        paper = tk.Frame(self, bg="#f5f5f0")
        paper.pack(padx=24, pady=(20, 10))
        tk.Label(paper, text=self.text, bg="#f5f5f0", fg="#1a1a1a", font=("Courier New", 10),
                 justify="left", padx=18, pady=16).pack()
        row = tk.Frame(self, bg=T.BG)
        row.pack(fill="x", padx=24, pady=(0, 18))
        T.button(row, "Done", self.destroy).pack(side="right")
        T.button(row, "Save receipt", self.save, "ghost").pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.focus_set()

    def save(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".txt", initialfile="receipt.txt",
                                            filetypes=[("Text file", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text)


class CatalogView(tk.Frame):
    """Medicines with pictures, prices and availability. The BHW adds medicines to an order cart."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.meds = []
        self.stock = {}
        self.cards = []
        self.card_buttons = {}      # sku -> its "Add to order" button
        self.photos = {}            # keeps the pictures alive (Tk drops unreferenced images)
        self.cols = 3
        self.cart = cart_items()
        self._build()
        self.bind_all("<MouseWheel>", self.on_wheel)
        self.refresh()
        self.render_cart()

    def destroy(self):
        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        super().destroy()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Available Medicines",
                 "Click medicines to add them to the order cart. You can buy several kinds at once."
                 if can_order() else "Check which medicines are in stock and what each group pays.").pack(
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

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 18))
        if can_order():
            self._build_cart(body)
        wrap = tk.Frame(body, bg=T.BG)
        wrap.pack(side="left", fill="both", expand=True)
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

    def _build_cart(self, parent):
        cart = tk.Frame(parent, bg=T.BG, width=CART_W)
        cart.pack(side="right", fill="y", padx=(14, 0))
        cart.pack_propagate(False)
        T.label(cart, "Order cart", 12, True).pack(anchor="w")
        T.label(cart, "Add as many medicines as the customer needs.", 9, color=T.MUTED,
                wraplength=CART_W - 10, justify="left").pack(anchor="w", pady=(0, 8))

        # bottom part first, so it always stays visible
        self.cart_msg = T.label(cart, "", 9, color=T.RED, wraplength=CART_W - 10, justify="left")
        self.cart_msg.pack(side="bottom", anchor="w", pady=(6, 0))
        buttons = tk.Frame(cart, bg=T.BG)
        buttons.pack(side="bottom", fill="x", pady=(10, 0))
        T.button(buttons, "Checkout", self.checkout).pack(side="left", fill="x", expand=True)
        T.button(buttons, "Clear", self.clear_cart, "ghost").pack(side="left", padx=(6, 0))
        self.cart_total = T.label(cart, "", 11, True)
        self.cart_total.pack(side="bottom", anchor="w", pady=(10, 0))
        edit = tk.Frame(cart, bg=T.BG)
        edit.pack(side="bottom", fill="x", pady=(8, 0))
        T.button(edit, "+1", lambda: self.change_selected(1), "ghost").pack(side="left")
        T.button(edit, "\u22121", lambda: self.change_selected(-1), "ghost").pack(side="left", padx=6)
        T.button(edit, "Remove", self.remove_selected, "ghost").pack(side="left")

        frame, self.cart_tree = T.table(cart, [("name", "Medicine", 124), ("qty", "Qty", 38),
                                               ("price", "Price", 70)], height=8)
        frame.pack(fill="both", expand=True)

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

    # ---------- the order cart ----------
    def medicine(self, sku):
        return next((m for m in self.meds if m["sku"] == sku), None)

    def add_to_cart(self, sku):
        self.cart[sku] = self.cart.get(sku, 0) + 1
        self.cart_msg.config(text="")
        self.render_cart()

    def selected_sku(self):
        sel = self.cart_tree.selection()
        return sel[0] if sel else None

    def change_selected(self, delta):
        sku = self.selected_sku()
        if sku is None:
            self.cart_msg.config(text="Click a medicine in the cart first.")
            return
        self.cart[sku] = self.cart.get(sku, 0) + delta
        if self.cart[sku] <= 0:
            del self.cart[sku]
        self.render_cart(keep=sku)

    def remove_selected(self):
        sku = self.selected_sku()
        if sku is None:
            self.cart_msg.config(text="Click a medicine in the cart first.")
            return
        self.cart.pop(sku, None)
        self.render_cart()

    def clear_cart(self):
        self.cart.clear()
        self.cart_msg.config(text="")
        self.render_cart()

    def render_cart(self, keep=None):
        """Show the cart (regular prices; the discount is chosen at checkout)."""
        for sku in [s for s in self.cart if self.medicine(s) is None]:
            del self.cart[sku]                               # a medicine that was deleted meanwhile
        rows, total = [], 0.0
        for sku, qty in self.cart.items():
            m = self.medicine(sku)
            line = m["unit_price"] * qty
            total += line
            rows.append((sku, (m["name"], qty, f"{line:,.2f}"), None))
        if hasattr(self, "cart_tree"):
            T.fill(self.cart_tree, rows)
            if keep and self.cart_tree.exists(keep):
                self.cart_tree.selection_set(keep)
            kinds = len(self.cart)
            self.cart_total.config(text=f"{kinds} kind{'s' if kinds != 1 else ''}  \u2022  PHP {total:,.2f}"
                                   if kinds else "Cart is empty")
        for sku, btn in self.card_buttons.items():
            btn.config(text=self.button_text(sku))

    def button_text(self, sku):
        m = self.medicine(sku)
        waits = self.stock.get(sku, 0) <= 0
        base = "Add (wait for stock)" if waits else "Add to order"
        qty = self.cart.get(sku, 0)
        return f"{base}  \u2022  {qty} in cart" if qty else base

    def checkout(self):
        lines = [(self.medicine(sku), qty) for sku, qty in self.cart.items() if self.medicine(sku)]
        if not lines:
            self.cart_msg.config(text="The cart is empty. Click a medicine to add it.")
            return
        CheckoutDialog(self, lines, self.after_checkout)

    def after_checkout(self):
        self.cart.clear()
        try:
            self.refresh()
            self.render_cart()
        except tk.TclError:
            pass                                             # the screen was already closed

    # ---------- data ----------
    def refresh(self):
        self.meds = db.get_medicines()
        self.name_tree = BST.build(self.meds, key=lambda m: m["name"].lower())   # Binary Search Tree
        self.stock = db.stock_by_sku()
        self.photos.clear()
        self.render()

    def visible_medicines(self):
        text = self.search_var.get().strip().lower()
        wanted = self.filter_combo.get() or "All"
        # BST prefix search first; if nothing starts with the text, look for it anywhere in name/SKU
        candidates = self.name_tree.starts_with(text) if text else []
        if not candidates:
            candidates = self.name_tree.in_order()                         # BST in-order = sorted by name
        shown = []
        for m in candidates:
            status = stock_status(self.stock.get(m["sku"], 0), m["low_stock_level"])
            if wanted != "All" and status != wanted:
                continue
            if text and text not in f"{m['sku']} {m['name']}".lower():
                continue
            shown.append(m)
        return shown

    def render(self):
        for card in self.cards:
            card.destroy()
        self.cards = []
        self.card_buttons = {}
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
        card = T.card(self.grid_frame, width=CARD_W, height=CARD_H if can_order() else CARD_H - 52)
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
        if not can_order():                                   # the doctor only looks
            return card

        def add(event=None, sku=m["sku"]):
            self.add_to_cart(sku)

        btn = T.button(card, self.button_text(m["sku"]), add,
                       "primary" if status != "Out of stock" else "ghost")
        btn.pack(side="bottom", fill="x", padx=14, pady=(0, 12))
        self.card_buttons[m["sku"]] = btn

        def bind_click(widget):                              # click the picture or anywhere on the card
            if not isinstance(widget, tk.Button):            # the button has its own command
                widget.bind("<Button-1>", add)
                widget.configure(cursor="hand2")
            for child in widget.winfo_children():
                bind_click(child)
        bind_click(card)
        return card