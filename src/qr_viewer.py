"""
qr_viewer.py  -  put this file inside your  src/  folder (next to qr_generator.py).

Shows a popup window with the QR code of a medicine, plus buttons to
Save a copy, Open the QR folder, or Close.

Usage inside pharmacy_app.py:
    from src.qr_viewer import show_qr_window

    # in a button command:
    show_qr_window(self, medicine_id, medicine_name)
"""

import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

from src.qr_generator import generate_qr, open_qr_folder

QR_DISPLAY_SIZE = 320  # pixels shown in the window


def show_qr_window(parent, data: str, label: str = "") -> None:
    """
    Open a popup showing the QR code for `data`.
    The QR image is created (or refreshed) and saved in the qrcodes/ folder.
    """
    if not data:
        messagebox.showwarning("No code", "Select a medicine first.")
        return

    try:
        path = generate_qr(data, label)
    except Exception as e:
        messagebox.showerror("QR error", f"Could not create QR code:\n{e}")
        return

    win = tk.Toplevel(parent)
    win.title(f"QR Code - {label or data}")
    win.configure(bg="white")
    win.resizable(False, False)
    win.transient(parent)

    # ---- QR image ----
    img = Image.open(path)
    img.thumbnail((QR_DISPLAY_SIZE, QR_DISPLAY_SIZE + 50))
    photo = ImageTk.PhotoImage(img)
    img_label = tk.Label(win, image=photo, bg="white")
    img_label.image = photo  # keep a reference so it doesn't disappear
    img_label.pack(padx=20, pady=(20, 8))

    tk.Label(win, text=f"Code: {data}", bg="white", fg="#555",
             font=("Segoe UI", 10)).pack()
    tk.Label(win, text=path, bg="white", fg="#999",
             font=("Segoe UI", 8), wraplength=340).pack(pady=(2, 10))

    # ---- Buttons ----
    def save_copy():
        dest = filedialog.asksaveasfilename(
            parent=win,
            defaultextension=".png",
            initialfile=path.replace("\\", "/").split("/")[-1],
            filetypes=[("PNG image", "*.png")],
        )
        if dest:
            shutil.copy(path, dest)
            messagebox.showinfo("Saved", f"Saved to:\n{dest}", parent=win)

    row = tk.Frame(win, bg="white")
    row.pack(pady=(0, 18))
    tk.Button(row, text="Save As...", width=12, command=save_copy).grid(row=0, column=0, padx=4)
    tk.Button(row, text="Open Folder", width=12, command=open_qr_folder).grid(row=0, column=1, padx=4)
    tk.Button(row, text="Close", width=12, command=win.destroy).grid(row=0, column=2, padx=4)