import sqlite3
import tkinter as tk
from tkinter import messagebox

from src.dsa.hash_table import HashTable
from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.ui.scan_dialog import open_scanner
from src.utils import auth, database as db, id_card, receipt, subsidy
from src.utils.scanner import bind_scanner


class ResidentsView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.by_id = HashTable()      # scanned ID -> resident record (O(1) lookup)
        self.rows = []
        self._build()
        self.refresh()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Residents", "Register residents and look them up by scanned ID.").pack(
            fill="x", padx=28, pady=(22, 12))

        # search / scan
        find = T.card(self)
        find.pack(fill="x", padx=28)
        T.label(find, "Scan or type a resident ID (or part of a name)", 10, True).pack(
            anchor="w", padx=16, pady=(14, 6))
        row = tk.Frame(find, bg=T.CARD)
        row.pack(fill="x", padx=16)
        self.scan_entry = T.entry(row, 30)
        self.scan_entry.pack(side="left", ipady=6)
        handle = bind_scanner(self.scan_entry, self.find)
        T.button(row, "Find", handle).pack(side="left", padx=8)
        T.button(row, "Show all", self.show_all, "ghost").pack(side="left")
        T.button(row, "Scan with camera", lambda: open_scanner(self, self.find), "ghost").pack(
            side="left", padx=8)
        self.find_label = T.label(find, "", 10, color=T.MUTED, justify="left")
        self.find_label.pack(anchor="w", padx=16, pady=(8, 14))

        # register
        reg = T.card(self)
        reg.pack(fill="x", padx=28, pady=(12, 0))
        T.label(reg, "Register new resident", 11, True).pack(anchor="w", padx=16, pady=(14, 6))
        row = tk.Frame(reg, bg=T.CARD)
        row.pack(fill="x", padx=16, pady=(0, 14))
        box, self.name_entry = T.labeled_entry(row, "Full name", 26)
        box.pack(side="left", padx=(0, 10))
        box, self.cat_combo = T.labeled_combo(row, "Category", 16, subsidy.CATEGORIES)
        box.pack(side="left", padx=(0, 10))
        self.cat_combo.current(0)
        box, self.addr_entry = T.labeled_entry(row, "Address", 26)
        box.pack(side="left", padx=(0, 10))
        T.button(row, "Register", self.register).pack(side="left", anchor="s")
        # press Enter in the name or address box = Register
        self.name_entry.bind("<Return>", lambda e: self.register())
        self.addr_entry.bind("<Return>", lambda e: self.register())
        self.name_entry.focus_set()

        # table
        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=28, pady=(12, 6))
        T.button(bar, "Create ID card", self.make_card).pack(side="left")
        if auth.is_admin():
            T.button(bar, "Delete selected", self.delete_selected, "danger").pack(side="right")
        frame, self.tree = T.table(self, [
            ("scanned_id", "Resident ID", 110), ("full_name", "Full name", 210),
            ("category", "Category", 130), ("rate", "Subsidy", 70), ("address", "Address", 220),
        ], height=10)
        frame.pack(fill="both", expand=True, padx=28, pady=(0, 22))

    # ---------- data ----------
    def refresh(self):
        self.rows = db.get_residents()
        self.by_id.clear()
        self.by_id.load(self.rows, "scanned_id")
        self.render(self.rows)

    def render(self, rows):
        ordered = merge_sort(rows, key=lambda r: r["full_name"].lower())   # Merge Sort by name
        T.fill(self.tree, [
            (r["scanned_id"],
             (r["scanned_id"], r["full_name"], r["category"],
              f"{subsidy.subsidy_rate(r['category']) * 100:.0f}%", r["address"]), None)
            for r in ordered
        ])

    # ---------- actions ----------
    def find(self, code):
        resident = self.by_id.get(code)                       # Hash Table lookup
        if resident:
            self.render(self.rows)
            self.tree.selection_set(resident["scanned_id"])
            self.tree.see(resident["scanned_id"])
            self.find_label.config(
                text=f"{resident['full_name']}  •  {resident['category']}  •  {resident['address'] or 'No address'}",
                fg=T.GREEN)
            return
        matches = [r for r in self.rows if code.lower() in r["full_name"].lower()]
        if matches:
            self.render(matches)
            self.find_label.config(text=f"No ID match. Showing {len(matches)} name match(es).", fg=T.YELLOW)
        else:
            self.find_label.config(text=f"Resident not found: {code}", fg=T.RED)

    def show_all(self):
        self.render(self.rows)
        self.find_label.config(text="")

    def register(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Enter the resident's full name.")
            return
        code = db.add_resident(name, self.cat_combo.get(), self.addr_entry.get().strip())
        self.name_entry.delete(0, "end")
        self.addr_entry.delete(0, "end")
        self.name_entry.focus_set()
        self.refresh()
        self.find_label.config(text=f"Registered {name}. Resident ID: {code}", fg=T.GREEN)
        RegisteredDialog(self, self.by_id.get(code))

    def make_card(self, resident=None):
        """Create a printable ID card with a QR code for the selected resident."""
        if resident is None:
            sel = self.tree.selection()
            if not sel:
                messagebox.showinfo("Select a resident", "Click a resident in the table first.")
                return
            resident = self.by_id.get(sel[0])
        try:
            path = id_card.make_id_card(resident, T.BARANGAY_NAME, T.logo_path())
        except ImportError:
            messagebox.showinfo("Install ID card support",
                                "Open the PyCharm terminal and run:\n    uv add opencv-python pillow\n\n"
                                "Then restart the app.")
            return
        if messagebox.askyesno("ID card ready", f"Saved:\n{path}\n\nOpen it now to print?"):
            id_card.open_file(path)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a resident", "Click a resident in the table first.")
            return
        resident = self.by_id.get(sel[0])
        if not messagebox.askyesno("Delete resident", f"Delete {resident['full_name']}?"):
            return
        try:
            db.delete_resident(resident["id"])
        except sqlite3.IntegrityError:
            messagebox.showerror("Cannot delete", "This resident already has medicine requests.")
            return
        self.refresh()


class RegisteredDialog(tk.Toplevel):
    """Shown right after registering: the generated ID, plus receipt and ID card buttons."""

    def __init__(self, parent, resident):
        super().__init__(parent)
        self.parent = parent
        self.resident = resident
        self.title("Resident registered")
        self.configure(bg=T.BG)
        self.resizable(False, False)

        body = T.card(self)
        body.pack(padx=20, pady=20)
        pad = {"anchor": "w", "padx": 30}
        rate = subsidy.subsidy_rate(resident["category"]) * 100
        T.label(body, "Resident registered", 14, True, T.GREEN).pack(pady=(22, 2), **pad)
        T.label(body, resident["full_name"], 12).pack(**pad)
        T.label(body, "Resident ID", 9, color=T.MUTED).pack(pady=(16, 0), **pad)
        T.label(body, resident["scanned_id"], 30, True).pack(**pad)
        T.label(body, f"{resident['category']}  \u2022  {rate:.0f}% subsidy", 9,
                color=T.MUTED).pack(pady=(2, 0), **pad)

        row = tk.Frame(body, bg=T.CARD)
        row.pack(fill="x", padx=30, pady=24)
        T.button(row, "Print receipt", self.print_receipt).pack(side="left")
        T.button(row, "Create ID card", lambda: parent.make_card(resident), "ghost").pack(side="left", padx=8)
        T.button(row, "Done", self.destroy, "ghost").pack(side="left")
        self.transient(parent.winfo_toplevel())

    def print_receipt(self):
        path = receipt.save_registration(self.resident, auth.current_user()["full_name"])
        receipt.print_receipt(path)