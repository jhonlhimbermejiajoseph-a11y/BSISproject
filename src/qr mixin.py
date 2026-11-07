"""
qr_mixin.py  -  put this file inside your  src/  folder.

Adds two actions to your PharmacyApp:
    self.view_selected_qr()   -> popup with the QR of the selected medicine
    self.scan_qr()            -> camera scanner, shows a check mark if valid

HOW TO USE (3 steps) in src/pharmacy_app.py
------------------------------------------------------------------
1) At the top:
       from src.qr_mixin import QRMixin

2) Add QRMixin to your class (put it FIRST):
       class PharmacyApp(QRMixin, tk.Tk):        # or ctk.CTk, whatever you use

3) Add two buttons where your other buttons are:
       tk.Button(frame, text="View QR", command=self.view_selected_qr).pack()
       tk.Button(frame, text="Scan QR", command=self.scan_qr).pack()

Then edit the 2 places marked  >>> EDIT <<<  below.
"""

from tkinter import messagebox

from src.qr_viewer import show_qr_window
from src.qr_scanner import open_scanner


class QRMixin:

    # >>> EDIT 1 <<<  How to get the selected medicine from YOUR table.
    # Returns (medicine_id, medicine_name).
    # This version works if your table is a ttk.Treeview called self.table
    # and the first column is the ID and the second column is the name.
    def get_selected_medicine(self):
        selected = self.table.selection()
        if not selected:
            return None, None
        values = self.table.item(selected[0])["values"]
        return str(values[0]), str(values[1])

    # >>> EDIT 2 <<<  How to check a scanned code in YOUR database.
    # Return the medicine name if the code exists, or None if it does NOT.
    # Example for sqlite3 (change the table and column names):
    #
    #     import sqlite3
    #     conn = sqlite3.connect("pharmacy.db")
    #     row = conn.execute("SELECT name FROM medicines WHERE id = ?", (code,)).fetchone()
    #     conn.close()
    #     return row[0] if row else None
    def find_medicine(self, code):
        raise NotImplementedError("Edit find_medicine() in qr_mixin.py to search your database.")

    # ---- these two need no changes ----
    def view_selected_qr(self):
        med_id, med_name = self.get_selected_medicine()
        if not med_id:
            messagebox.showwarning("Select", "Select a medicine first.")
            return
        show_qr_window(self, med_id, med_name)

    def scan_qr(self):
        open_scanner(self, self.find_medicine)