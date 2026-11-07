"""Shared colors, fonts and small widget helpers (dark theme, green accent)."""
import math
import os
import tkinter as tk
from tkinter import ttk

# ---------- branding: change these two lines for your barangay ----------
BARANGAY_NAME = "Barangay Name"
SYSTEM_NAME = "Community Medicine Request & Inventory System"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR = os.path.join(ROOT, "assets")
LOGO_FILES = ("logo.png", "logo.gif", "logo.jpg", "logo.jpeg")

BG = "#0f1519"
SIDEBAR = "#121b20"
CARD = "#151f26"
FIELD = "#1b2830"
BORDER = "#24343d"
TEXT = "#e8eef1"
MUTED = "#8a9ba5"
GREEN = "#00d26a"
YELLOW = "#f5c400"
RED = "#e5483b"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_STAT = ("Segoe UI", 22, "bold")


def logo_path():
    """Path of assets/logo.png (or .gif/.jpg), or None if there is no logo."""
    return next((os.path.join(ASSETS_DIR, f) for f in LOGO_FILES
                 if os.path.exists(os.path.join(ASSETS_DIR, f))), None)


def load_logo(size):
    """Load assets/logo.png scaled to fit size x size pixels. Returns None if there is no logo.

    Keep a reference to the result (e.g. self.logo = ...) or Tk will discard the image.
    With Pillow installed the scaling is smooth and .jpg works; without it, PNG/GIF still
    work but are shrunk in whole-number steps.
    """
    path = logo_path()
    if path is None:
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(path).convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except ImportError:
        try:
            photo = tk.PhotoImage(file=path)
            factor = max(1, math.ceil(max(photo.width(), photo.height()) / size))
            return photo.subsample(factor) if factor > 1 else photo
        except tk.TclError:
            return None
    except Exception:
        return None


def setup_styles(root):
    """Dark styling for ttk widgets (tables, dropdowns, scrollbars)."""
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                    rowheight=28, borderwidth=0, font=FONT)
    style.configure("Treeview.Heading", background=SIDEBAR, foreground=MUTED, relief="flat",
                    font=FONT_BOLD, padding=(8, 6))
    style.map("Treeview", background=[("selected", "#1f3a30")], foreground=[("selected", GREEN)])
    style.map("Treeview.Heading", background=[("active", SIDEBAR)])
    style.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT,
                    arrowcolor=TEXT, bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD,
                    padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", FIELD)],
              foreground=[("readonly", TEXT)], selectbackground=[("readonly", FIELD)],
              selectforeground=[("readonly", TEXT)])
    style.configure("Vertical.TScrollbar", background=FIELD, troughcolor=CARD, bordercolor=CARD,
                    arrowcolor=MUTED, lightcolor=FIELD, darkcolor=FIELD)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", GREEN)
    root.option_add("*TCombobox*Listbox.selectForeground", "#001a0d")


# ---------- basic widgets ----------
def label(parent, text="", size=10, bold=False, color=TEXT, **kw):
    kw.setdefault("bg", parent["bg"])
    return tk.Label(parent, text=text, fg=color,
                    font=("Segoe UI", size, "bold" if bold else "normal"), **kw)


def card(parent, **kw):
    return tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER, **kw)


def button(parent, text, command, kind="primary"):
    """kind: 'primary' (green), 'danger' (red outline) or 'ghost' (grey)."""
    bg, fg = {"primary": (GREEN, "#001a0d"), "danger": (CARD, RED), "ghost": (FIELD, TEXT)}[kind]
    b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=bg,
                  activeforeground=fg, relief="flat", bd=0, font=FONT_BOLD, padx=14, pady=6,
                  cursor="hand2")
    if kind == "danger":
        b.config(highlightthickness=1, highlightbackground=RED)
    return b


def entry(parent, width=18, show=""):
    return tk.Entry(parent, width=width, show=show, bg=FIELD, fg=TEXT, insertbackground=TEXT,
                    relief="flat", highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=GREEN, font=FONT)


def combo(parent, width=24, values=()):
    return ttk.Combobox(parent, width=width, values=list(values), state="readonly", font=FONT)


def checkbox(parent, text, variable):
    return tk.Checkbutton(parent, text=text, variable=variable, bg=parent["bg"], fg=TEXT,
                          selectcolor=FIELD, activebackground=parent["bg"],
                          activeforeground=TEXT, font=FONT, highlightthickness=0, bd=0)


def labeled_entry(parent, text, width=18, show=""):
    """Small label above an entry. Returns (container, entry)."""
    box = tk.Frame(parent, bg=parent["bg"])
    label(box, text, 9, color=MUTED).pack(anchor="w")
    e = entry(box, width, show)
    e.pack(fill="x", ipady=5, pady=(2, 0))
    return box, e


def labeled_combo(parent, text, width=24, values=()):
    box = tk.Frame(parent, bg=parent["bg"])
    label(box, text, 9, color=MUTED).pack(anchor="w")
    c = combo(box, width, values)
    c.pack(fill="x", pady=(2, 0))
    return box, c


def header(parent, title, subtitle=""):
    box = tk.Frame(parent, bg=parent["bg"])
    label(box, title, 20, True).pack(anchor="w")
    if subtitle:
        label(box, subtitle, 10, color=MUTED).pack(anchor="w", pady=(2, 0))
    return box


def stat_card(parent, text, color=TEXT):
    """Returns (container, value_label)."""
    box = card(parent)
    value = tk.Label(box, text="0", bg=CARD, fg=color, font=FONT_STAT)
    value.pack(anchor="w", padx=16, pady=(12, 0))
    label(box, text, 9, color=MUTED).pack(anchor="w", padx=16, pady=(0, 12))
    return box, value


# ---------- tables ----------
def set_columns(tree, columns):
    """columns: list of (id, heading, width)."""
    tree["columns"] = [c[0] for c in columns]
    for cid, heading, width in columns:
        tree.heading(cid, text=heading, anchor="w")
        tree.column(cid, width=width, anchor="w", stretch=True)


def table(parent, columns, height=10):
    """Scrollable table inside a card. Returns (container, tree).

    Row tags: 'ok' (green), 'warn' (yellow), 'bad' (red).
    """
    frame = card(parent)
    tree = ttk.Treeview(frame, show="headings", height=height, selectmode="browse")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
    scroll.pack(side="right", fill="y", pady=6, padx=(0, 4))
    set_columns(tree, columns)
    tree.tag_configure("ok", foreground=GREEN)
    tree.tag_configure("warn", foreground=YELLOW)
    tree.tag_configure("bad", foreground=RED)
    return frame, tree


def fill(tree, rows):
    """rows: list of (iid, values, tag_or_None)."""
    tree.delete(*tree.get_children())
    for iid, values, tag in rows:
        tree.insert("", "end", iid=str(iid), values=values, tags=(tag,) if tag else ())