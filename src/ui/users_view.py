import sqlite3
import tkinter as tk
from tkinter import messagebox

from src.ui import theme as T
from src.ui.inventory_view import stat_tile
from src.utils import auth, database as db

BLUE = "#3aa0ff"
ORANGE = "#ff9f1a"


class UsersView(tk.Frame):
    """Admin: manage staff accounts and their roles."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self._build()
        self.refresh()

    def _build(self):
        T.header(self, "Users", "Manage staff accounts and their roles.").pack(
            fill="x", padx=28, pady=(22, 12))

        tiles = tk.Frame(self, bg=T.BG)
        tiles.pack(fill="x", padx=28)
        self.tile = {}
        for i, (key, text, accent) in enumerate([
            ("total", "Staff accounts", T.GREEN), ("BHW", "Health workers (BHW)", T.GREEN),
            ("Check-up", "Doctors (Check-up)", BLUE), ("Admin", "Administrators", ORANGE),
        ]):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            box, value = stat_tile(tiles, text, accent)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            self.tile[key] = value

        form = T.card(self)
        form.pack(fill="x", padx=28, pady=(14, 0))
        top = tk.Frame(form, bg=T.CARD)
        top.pack(fill="x", padx=18, pady=(14, 6))
        T.label(top, "Add user", 12, True, bg=T.CARD).pack(side="left")
        T.label(top, "BHW serves customers  •  Check-up writes prescriptions  •  Admin monitors",
                9, color=T.MUTED, bg=T.CARD).pack(side="right")
        row = tk.Frame(form, bg=T.CARD)
        row.pack(fill="x", padx=18, pady=(0, 8))
        box, self.name_entry = T.labeled_entry(row, "Full name", 22)
        box.pack(side="left", padx=(0, 12))
        box, self.user_entry = T.labeled_entry(row, "Username", 14)
        box.pack(side="left", padx=(0, 12))
        box, self.pass_entry = T.labeled_entry(row, "Password (6+ chars)", 16, show="*")
        box.pack(side="left", padx=(0, 12))
        box, self.role_combo = T.labeled_combo(row, "Role", 16, auth.ROLES)
        box.pack(side="left", padx=(0, 12))
        self.role_combo.current(0)
        T.button(row, "Add user", self.add_user).pack(side="left", anchor="s")
        self.msg = T.label(form, "", 9, color=T.MUTED, bg=T.CARD)
        self.msg.pack(anchor="w", padx=18, pady=(0, 12))
        for entry in (self.name_entry, self.user_entry, self.pass_entry):
            entry.bind("<Return>", lambda e: self.add_user())

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=28, pady=(16, 6))
        T.label(bar, "Accounts", 12, True).pack(side="left")
        T.button(bar, "Delete selected", self.delete_selected, "danger").pack(side="right")
        frame, self.tree = T.table(self, [
            ("id", "ID", 50), ("full_name", "Full name", 230),
            ("username", "Username", 160), ("role", "Role", 160),
        ], height=10)
        frame.pack(fill="both", expand=True, padx=28, pady=(0, 22))

    def _say(self, text, color=T.MUTED):
        self.msg.config(text=text, fg=color)

    def refresh(self):
        self.users = db.get_users()
        T.fill(self.tree, [
            (u["id"], (u["id"], u["full_name"], u["username"], u["role"]), None)
            for u in self.users
        ])
        self.tile["total"].config(text=str(len(self.users)))
        for role in ("BHW", "Check-up", "Admin"):
            self.tile[role].config(text=str(sum(1 for u in self.users if u["role"] == role)))

    def add_user(self):
        name = self.name_entry.get().strip()
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not name or not username:
            self._say("Enter the full name and username.", T.RED)
            return
        if len(password) < 6:
            self._say("Use a password of at least 6 characters.", T.RED)
            return
        try:
            db.add_user(username, name, password, self.role_combo.get())
        except sqlite3.IntegrityError:
            self._say(f"The username '{username}' already exists.", T.RED)
            return
        for e in (self.name_entry, self.user_entry, self.pass_entry):
            e.delete(0, "end")
        self.refresh()
        self._say(f"Added {name} as {self.role_combo.get()}.", T.GREEN)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a user", "Click a user in the table first.")
            return
        user_id = int(sel[0])
        user = next((u for u in self.users if u["id"] == user_id), None)
        if user_id == auth.current_user()["id"]:
            messagebox.showwarning("Not allowed", "You cannot delete the account you are using.")
            return
        if user and user["role"] == "Admin" and sum(1 for u in self.users if u["role"] == "Admin") <= 1:
            messagebox.showwarning("Not allowed", "Keep at least one Admin account.")
            return
        name = user["full_name"] if user else "this account"
        if not messagebox.askyesno("Delete user", f"Delete {name}?"):
            return
        try:
            db.delete_user(user_id)
        except sqlite3.Error:                       # the user already served customers
            messagebox.showerror("Cannot delete", f"{name} already has records (served requests or "
                                                  "prescriptions), so the account must be kept.")
            return
        self.refresh()
        self._say(f"Deleted {name}.")