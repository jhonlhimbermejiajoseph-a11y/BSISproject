import tkinter as tk

from src.ui import theme as T
from src.ui.catalog_view import CatalogView
from src.ui.checkup_view import CheckupView
from src.ui.deliveries_view import DeliveriesView
from src.ui.dispense_view import DispenseView
from src.ui.inventory_view import InventoryView
from src.ui.login_view import LoginView
from src.ui.reports_view import ReportsView
from src.ui.requests_view import RequestsView
from src.ui.residents_view import ResidentsView
from src.ui.users_view import UsersView
from src.utils import auth, database as db, receipt

SCREENS = {
    "Requests": RequestsView,
    "Residents": ResidentsView,
    "Check-up": CheckupView,
    "Pharmacy": DispenseView,
    "Inventory": InventoryView,
    "Medicines": CatalogView,
    "Deliveries": DeliveriesView,
    "Reports": ReportsView,
    "Users": UsersView,
}

SIDEBAR_W = 210
SLIDE_STEP = 30          # pixels per animation step
SLIDE_DELAY = 10         # milliseconds between steps


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{T.BARANGAY_NAME} Medicine System")
        self.geometry("1200x780")
        self.minsize(1050, 700)
        self.configure(bg=T.BG)
        T.setup_styles(self)
        db.init_db()
        receipt.HEADER = f"{T.BARANGAY_NAME.upper()} HEALTH CENTER"
        self.nav_buttons = {}
        self.content = None
        self.sidebar = None
        self.right = None
        self.screen_title = None
        self.sidebar_open = True
        self.sliding = False
        self.show_login()

    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    # ---------- login ----------
    def show_login(self):
        self._clear()
        LoginView(self, self.show_main).pack(fill="both", expand=True)

    def logout(self):
        auth.logout()
        self.show_login()

    # ---------- main window ----------
    def show_main(self):
        self._clear()
        self.sidebar_open = True
        self.sliding = False
        user = auth.current_user()

        sidebar = tk.Frame(self, bg=T.SIDEBAR, width=SIDEBAR_W)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebar = sidebar
        head = tk.Frame(sidebar, bg=T.SIDEBAR)
        head.pack(fill="x", padx=18, pady=(22, 18))
        T.label(head, T.BARANGAY_NAME, 12, True, T.GREEN, wraplength=170, justify="left").pack(anchor="w")
        T.label(head, "Medicine system", 9, color=T.MUTED).pack(anchor="w")

        self.nav_buttons = {}
        screens = auth.screens_for_role(user["role"])      # each role sees only its screens
        for name in screens:
            btn = tk.Button(sidebar, text=name, anchor="w", relief="flat", bd=0, font=T.FONT_BOLD,
                            padx=16, pady=7, cursor="hand2", command=lambda n=name: self.show_screen(n))
            btn.pack(fill="x", padx=12, pady=1)
            self.nav_buttons[name] = btn

        bottom = tk.Frame(sidebar, bg=T.SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=16, pady=16)
        T.label(bottom, user["full_name"], 10, True).pack(anchor="w")
        T.label(bottom, user["role"], 9, color=T.MUTED).pack(anchor="w")
        T.button(bottom, "Log out", self.logout, "ghost").pack(fill="x", pady=(10, 0))

        # right side: a thin bar with the burger button, then the screen
        self.right = tk.Frame(self, bg=T.BG)
        self.right.pack(side="left", fill="both", expand=True)
        bar = tk.Frame(self.right, bg=T.BG, height=36)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        burger = tk.Button(bar, text="☰", relief="flat", bd=0, font=("Segoe UI", 15),
                           bg=T.BG, fg=T.TEXT, activebackground=T.CARD, activeforeground=T.GREEN,
                           cursor="hand2", padx=12, command=self.toggle_sidebar)
        burger.pack(side="left", padx=(8, 0), pady=3)
        burger.bind("<Enter>", lambda e: burger.config(bg=T.CARD))
        burger.bind("<Leave>", lambda e: burger.config(bg=T.BG))
        self.screen_title = tk.Label(bar, text="", bg=T.BG, fg=T.MUTED, font=T.FONT)
        self.screen_title.pack(side="left", padx=10)

        self.content = tk.Frame(self.right, bg=T.BG)
        self.content.pack(fill="both", expand=True)
        self.show_screen(screens[0])

    # ---------- burger: slide the sidebar left and back ----------
    def toggle_sidebar(self):
        if self.sliding:
            return
        self.sliding = True
        if self.sidebar_open:
            self.slide(SIDEBAR_W, 0)
        else:
            self.sidebar.config(width=1)
            self.sidebar.pack(side="left", fill="y", before=self.right)
            self.slide(1, SIDEBAR_W)

    def slide(self, width, target):
        if target < width:
            width = max(target, width - SLIDE_STEP)
        else:
            width = min(target, width + SLIDE_STEP)
        self.sidebar.config(width=max(width, 1))
        if width == target:
            self.sidebar_open = target > 0
            if not self.sidebar_open:
                self.sidebar.pack_forget()
            self.sliding = False
            return
        self.after(SLIDE_DELAY, lambda: self.slide(width, target))

    def show_screen(self, name):
        if not auth.can_access(name):
            return
        for widget in self.content.winfo_children():
            widget.destroy()
        for n, btn in self.nav_buttons.items():
            active = n == name
            btn.config(bg=T.CARD if active else T.SIDEBAR, fg=T.GREEN if active else T.TEXT,
                       activebackground=T.CARD, activeforeground=T.GREEN)
        self.screen_title.config(text=name)
        SCREENS[name](self.content).pack(fill="both", expand=True)   # fresh data every time