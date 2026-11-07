import sqlite3
import tkinter as tk
from tkinter import messagebox

from src.ui import theme as T
from src.utils import auth, database as db


class UsersView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self._build()
        self.refresh()

    def _build(self):
        T.header(self, "Users", "Manage staff accounts and their roles.").pack(
            fill="x", padx=28, pady=(22, 12))

        form = T.card(self)
        form.pack(fill="x", padx=28)
        T.label(form, "Add user", 11, True).pack(anchor="w", padx=16, pady=(14, 6))
        row = tk.Frame(form, bg=T.CARD)
        row.pack(fill="x", padx=16, pady=(0, 14))
        box, self.name_entry = T.labeled_entry(row, "Full name", 22)
        box.pack(side="left", padx=(0, 10))
        box, self.user_entry = T.labeled_entry(row, "Username", 14)
        box.pack(side="left", padx=(0, 10))
        box, self.pass_entry = T.labeled_entry(row, "Password (6+ chars)", 16, show="*")
        box.pack(side="left", padx=(0, 10))
        box, self.role_combo = T.labeled_combo(row, "Role", 18, auth.ROLES)
        box.pack(side="left", padx=(0, 10))
        self.role_combo.current(0)
        T.button(row, "Add user", self.add_user).pack(side="left", anchor="s")

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=28, pady=(14, 6))
        T.button(bar, "Delete selected", self.delete_selected, "danger").pack(side="right")
        frame, self.tree = T.table(self, [
            ("id", "ID", 50), ("full_name", "Full name", 230),
            ("username", "Username", 160), ("role", "Role", 160),
        ], height=10)
        frame.pack(fill="both", expand=True, padx=28, pady=(0, 22))

    def refresh(self):
        T.fill(self.tree, [
            (u["id"], (u["id"], u["full_name"], u["username"], u["role"]), None)
            for u in db.get_users()
        ])

    def add_user(self):
        name = self.name_entry.get().strip()
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not name or not username:
            messagebox.showwarning("Missing details", "Enter the full name and username.")
            return
        if len(password) < 6:
            messagebox.showwarning("Weak password", "Use at least 6 characters.")
            return
        try:
            db.add_user(username, name, password, self.role_combo.get())
        except sqlite3.IntegrityError:
            messagebox.showerror("Username taken", f"'{username}' already exists.")
            return
        for e in (self.name_entry, self.user_entry, self.pass_entry):
            e.delete(0, "end")
        self.refresh()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a user", "Click a user in the table first.")
            return
        user_id = int(sel[0])
        if user_id == auth.current_user()["id"]:
            messagebox.showwarning("Not allowed", "You cannot delete the account you are using.")
            return
        if messagebox.askyesno("Delete user", "Delete this account?"):
            db.delete_user(user_id)
            self.refresh()