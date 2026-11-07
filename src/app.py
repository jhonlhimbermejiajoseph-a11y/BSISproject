import time
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
SLIDE_TIME = 0.22        # seconds the slide takes
SLIDE_TICK = 8           # milliseconds between frames


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
        self.slide_began = 0.0
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

        # The sidebar floats on top of the window (place), so sliding it never
        # makes the screen next to it redraw. That is what keeps the slide smooth.
        sidebar = tk.Frame(self, bg=T.SIDEBAR)
        sidebar.place(x=0, y=0, width=SIDEBAR_W, relheight=1)
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
        self.right.pack(fill="both", expand=True, padx=(SIDEBAR_W, 0))
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
        self.sidebar.lift()                                # keep the sidebar above the screen
        self.show_screen(screens[0])

    # ---------- burger: slide the sidebar left and back ----------
    def toggle_sidebar(self):
        if self.sliding:
            return
        self.sliding = True
        if self.sidebar_open:
            start, target = 0, -SIDEBAR_W
        else:
            start, target = -SIDEBAR_W, 0
            self.sidebar.place_configure(x=start)
            self.right.pack_configure(padx=(SIDEBAR_W, 0))  # make room first (one redraw)
            self.update_idletasks()
        self.slide_began = time.perf_counter()
        self.slide(start, target)

    def slide(self, start, target):
        """Timed ease-out slide. Only the sidebar moves, so nothing else is redrawn."""
        t = min(1.0, (time.perf_counter() - self.slide_began) / SLIDE_TIME)
        eased = 1 - (1 - t) ** 3
        self.sidebar.place_configure(x=int(round(start + (target - start) * eased)))
        if t >= 1.0:
            self.sidebar_open = target == 0
            if not self.sidebar_open:
                self.right.pack_configure(padx=0)           # screen takes the full width (one redraw)
            self.sliding = False
            return
        self.after(SLIDE_TICK, lambda: self.slide(start, target))

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