import math
import tkinter as tk
from tkinter import messagebox

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
from src.utils import auth, clock, database as db, receipt

SCREENS = {
    "Requests": RequestsView,
    "Residents": ResidentsView,
    "Check-up": CheckupView,
    "Prescriptions": DispenseView,
    "Inventory": InventoryView,
    "Medicines": CatalogView,
    "Deliveries": DeliveriesView,
    "Reports": ReportsView,
    "Users": UsersView,
}

SIDEBAR_W = 230
TOPBAR_H = 56
HOVER_BG = "#172229"
ACTIVE_BG = "#16262d"
ROLE_COLOR = {"BHW": T.GREEN, "Check-up": "#3aa0ff", "Admin": "#ff9f1a"}


class Burger(tk.Canvas):
    """A thin, rounded menu button (three lines) that lights up when the mouse is over it."""
    SIZE = 36

    def __init__(self, parent, command):
        super().__init__(parent, width=self.SIZE, height=self.SIZE, bg=T.BG, highlightthickness=0,
                         cursor="hand2")
        self.command = command
        self.hover = False
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.draw()

    def _set_hover(self, on):
        self.hover = on
        self.draw()

    def draw(self):
        self.delete("all")
        c = self.SIZE / 2
        if self.hover:                                       # soft rounded highlight
            self._round_rect(2, 2, self.SIZE - 2, self.SIZE - 2, 10, T.CARD)
        color = T.GREEN if self.hover else T.TEXT
        for dy, half in ((-6, 9), (0, 9), (6, 6)):           # the last line is shorter: a modern touch
            self.create_line(c - 9, c + dy, c - 9 + 2 * half, c + dy, fill=color, width=2, capstyle="round")

    def _round_rect(self, x1, y1, x2, y2, r, fill):
        self.create_polygon(x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
                            x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1, smooth=True, fill=fill,
                            outline="")


def avatar(parent, letter, color, size=34, bg=T.SIDEBAR):
    """A round badge with the user's first letter."""
    c = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0)
    c.create_oval(1, 1, size - 1, size - 1, fill=color, outline="")
    c.create_text(size / 2, size / 2, text=letter.upper(), fill="#001a0d", font=("Segoe UI", 11, "bold"))
    return c


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{T.BARANGAY_NAME} Medicine System")
        self.geometry("1280x800")
        self.minsize(1050, 700)
        self.configure(bg=T.BG)
        T.setup_styles(self)
        db.init_db()
        receipt.HEADER = f"{T.BARANGAY_NAME.upper()} HEALTH CENTER"
        self.nav = {}                  # screen name -> (row, accent bar, button)
        self.content = None
        self.sidebar = None
        self.right = None
        self.crumb = None
        self.sidebar_open = True
        self.logo = None
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
        user = auth.current_user()
        color = ROLE_COLOR.get(user["role"], T.GREEN)

        # left: the menu (always there, like most apps; the burger can hide it)
        sidebar = tk.Frame(self, bg=T.SIDEBAR, width=SIDEBAR_W)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebar = sidebar
        tk.Frame(sidebar, bg=T.BORDER, width=1).pack(side="right", fill="y")     # thin edge line

        head = tk.Frame(sidebar, bg=T.SIDEBAR)
        head.pack(fill="x", padx=18, pady=(20, 6))
        self.logo = T.load_logo(34)
        if self.logo:
            tk.Label(head, image=self.logo, bg=T.SIDEBAR).pack(side="left", padx=(0, 10))
        names = tk.Frame(head, bg=T.SIDEBAR)
        names.pack(side="left", fill="x")
        T.label(names, T.BARANGAY_NAME, 12, True, T.GREEN, wraplength=150, justify="left").pack(anchor="w")
        T.label(names, "Medicine system", 9, color=T.MUTED).pack(anchor="w")
        tk.Frame(sidebar, bg=T.BORDER, height=1).pack(fill="x", padx=18, pady=(14, 10))
        T.label(sidebar, "MENU", 8, True, T.MUTED).pack(anchor="w", padx=22, pady=(0, 6))

        self.nav = {}
        screens = auth.screens_for_role(user["role"])      # each role sees only its screens
        for name in screens:
            row = tk.Frame(sidebar, bg=T.SIDEBAR, cursor="hand2")
            row.pack(fill="x", padx=(10, 12), pady=1)
            accent = tk.Frame(row, bg=T.SIDEBAR, width=3)
            accent.pack(side="left", fill="y")
            btn = tk.Button(row, text=name, anchor="w", relief="flat", bd=0, font=T.FONT_BOLD, padx=14,
                            pady=9, cursor="hand2", highlightthickness=0, bg=T.SIDEBAR, fg=T.TEXT,
                            activebackground=ACTIVE_BG, activeforeground=T.GREEN,
                            command=lambda n=name: self.show_screen(n))
            btn.pack(side="left", fill="x", expand=True)
            btn.bind("<Enter>", lambda e, n=name: self._hover(n, True))
            btn.bind("<Leave>", lambda e, n=name: self._hover(n, False))
            self.nav[name] = (row, accent, btn)

        bottom = tk.Frame(sidebar, bg=T.SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=16, pady=16)
        who = tk.Frame(bottom, bg=T.SIDEBAR)
        who.pack(fill="x", pady=(0, 12))
        avatar(who, user["full_name"][:1] or "?", color).pack(side="left")
        info = tk.Frame(who, bg=T.SIDEBAR)
        info.pack(side="left", padx=10)
        T.label(info, user["full_name"], 10, True, wraplength=125, justify="left").pack(anchor="w")
        T.label(info, user["role"], 9, color=color).pack(anchor="w")
        T.button(bottom, "Log out", self.logout, "ghost").pack(fill="x")

        # right: a top bar (burger, where you are, who is logged in), then the screen
        self.right = tk.Frame(self, bg=T.BG)
        self.right.pack(side="left", fill="both", expand=True)
        bar = tk.Frame(self.right, bg=T.BG, height=TOPBAR_H)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        Burger(bar, self.toggle_sidebar).pack(side="left", padx=(14, 4), pady=10)
        self.crumb = tk.Frame(bar, bg=T.BG)
        self.crumb.pack(side="left", padx=6)
        self.crumb_page = T.label(self.crumb, "", 11, True)
        T.label(self.crumb, T.BARANGAY_NAME + "   \u203a   ", 10, color=T.MUTED).pack(side="left")
        self.crumb_page.pack(side="left")
        chip = tk.Frame(bar, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER)
        chip.pack(side="right", padx=22, pady=11)
        self.clock_label = T.label(bar, "", 10, color=T.MUTED)
        self.clock_label.pack(side="right", padx=(0, 6))
        self._tick_clock()
        tk.Label(chip, text="\u25cf", bg=T.CARD, fg=color, font=("Segoe UI", 8)).pack(side="left", padx=(10, 4))
        T.label(chip, f"{user['full_name']}  \u2022  {user['role']}", 9, color=T.MUTED, bg=T.CARD).pack(
            side="left", padx=(0, 12), pady=3)
        tk.Frame(self.right, bg=T.BORDER, height=1).pack(fill="x")

        self.content = tk.Frame(self.right, bg=T.BG)
        self.content.pack(fill="both", expand=True)
        self.show_screen(screens[0])
        warning = clock.check_clock()                       # warn if the PC clock was turned back
        if warning:
            self.after(300, lambda: messagebox.showwarning("Check the date", warning))

    def _tick_clock(self):
        if self.clock_label.winfo_exists():
            self.clock_label.config(text=clock.now().strftime("%a, %b %d %Y  %I:%M %p"))
            self.after(30000, self._tick_clock)             # refresh every 30 seconds

    # ---------- menu ----------
    def toggle_sidebar(self):
        """Hide or show the menu. The screen is laid out once, so nothing flickers."""
        if self.sidebar_open:
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(side="left", fill="y", before=self.right)
        self.sidebar_open = not self.sidebar_open

    def _hover(self, name, inside):
        row, accent, btn = self.nav[name]
        if getattr(self, "current", None) == name:
            return
        btn.config(bg=HOVER_BG if inside else T.SIDEBAR)

    def show_screen(self, name):
        if not auth.can_access(name):
            return
        self.current = name
        for widget in self.content.winfo_children():
            widget.destroy()
        for n, (row, accent, btn) in self.nav.items():
            active = n == name
            btn.config(bg=ACTIVE_BG if active else T.SIDEBAR, fg=T.GREEN if active else T.TEXT)
            accent.config(bg=T.GREEN if active else T.SIDEBAR)
        self.crumb_page.config(text=name)
        SCREENS[name](self.content).pack(fill="both", expand=True)   # fresh data every time