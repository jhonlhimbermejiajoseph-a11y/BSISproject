"""
qr_scanner.py  -  put this file inside your  src/  folder.

Install once:
    pip install opencv-python pillow pyzbar

Opens a live camera window. When a QR code is shown to the camera it is
read automatically and checked with YOUR lookup function:

    found     ->  big green check mark  +  medicine name
    not found ->  red cross

Usage inside pharmacy_app.py:
    from src.qr_scanner import open_scanner

    def lookup_medicine(code):
        # return the medicine name (or any text) if the code is valid,
        # return None if it is NOT in your database
        ...

    open_scanner(self, lookup_medicine)
"""

import sys
import time
import tkinter as tk
from tkinter import messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk

# pyzbar reads QR codes AND barcodes. If it is not installed we fall back to
# OpenCV's built-in reader (QR codes only).
try:
    from pyzbar.pyzbar import decode as _zbar_decode
except Exception:
    _zbar_decode = None

_qr_detector = cv2.QRCodeDetector()

COOLDOWN_SECONDS = 2.5   # ignore the same code for this long after a scan
VIDEO_WIDTH = 480        # width of the preview in pixels


def _read_codes(frame):
    """Return a list of (text, corner_points) found in a camera frame."""
    found = []
    if _zbar_decode is not None:
        for c in _zbar_decode(frame):
            text = c.data.decode("utf-8", errors="ignore")
            pts = [(p.x, p.y) for p in c.polygon]
            found.append((text, pts))
    else:
        text, pts, _ = _qr_detector.detectAndDecode(frame)
        if text:
            corners = [tuple(int(v) for v in p) for p in pts[0]] if pts is not None else []
            found.append((text, corners))
    return found


def _beep(ok: bool):
    """Small sound on Windows (does nothing on other systems)."""
    try:
        import winsound
        winsound.Beep(1200 if ok else 400, 150)
    except Exception:
        pass


class QRScannerWindow:
    def __init__(self, parent, lookup, on_success=None, camera_index=0):
        """
        lookup(code)            -> return info (e.g. medicine name) or None
        on_success(code, info)  -> optional, called when a valid code is scanned
        """
        self.lookup = lookup
        self.on_success = on_success
        self.running = False
        self.last_code = None
        self.last_time = 0.0

        # Open the camera (CAP_DSHOW opens much faster on Windows)
        if sys.platform.startswith("win"):
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(camera_index)

        if not self.cap.isOpened():
            messagebox.showerror("Camera", "Could not open the camera.\n"
                                           "Close other apps using it and try again.")
            return

        self.win = tk.Toplevel(parent)
        self.win.title("Scan QR Code")
        self.win.configure(bg="#111")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self.video = tk.Label(self.win, bg="black")
        self.video.pack(padx=16, pady=(16, 8))

        self.status = tk.Label(self.win, text="Scanning...", bg="#111", fg="#aaa",
                               font=("Segoe UI Emoji", 30))
        self.status.pack()
        self.detail = tk.Label(self.win, text="Show the QR code to the camera",
                               bg="#111", fg="#888", font=("Segoe UI", 11),
                               wraplength=VIDEO_WIDTH)
        self.detail.pack(pady=(0, 8))

        tk.Button(self.win, text="Close", width=14, command=self.close).pack(pady=(0, 16))

        self.running = True
        self._update()

    # ---------- main loop ----------
    def _update(self):
        if not self.running:
            return

        ok, frame = self.cap.read()
        if ok:
            now = time.time()
            for text, pts in _read_codes(frame):
                if pts:  # draw a green box around the detected code
                    cv2.polylines(frame, [np.array(pts, np.int32)], True, (0, 255, 0), 3)
                is_new = text != self.last_code or (now - self.last_time) > COOLDOWN_SECONDS
                if text and is_new:
                    self.last_code, self.last_time = text, now
                    self._handle(text)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            h = int(img.height * VIDEO_WIDTH / img.width)
            photo = ImageTk.PhotoImage(img.resize((VIDEO_WIDTH, h)))
            self.video.configure(image=photo)
            self.video.image = photo  # keep a reference

        self.win.after(30, self._update)

    # ---------- what happens after a scan ----------
    def _handle(self, code):
        try:
            info = self.lookup(code)
        except Exception as e:
            info = None
            print("Lookup error:", e)

        if info:
            self.status.configure(text="\u2705", fg="#2ecc71")           # check mark
            self.detail.configure(text=f"{info}", fg="#2ecc71")
            _beep(True)
            if self.on_success:
                self.on_success(code, info)
        else:
            self.status.configure(text="\u274C", fg="#e74c3c")           # red cross
            self.detail.configure(text=f"Not found: {code}", fg="#e74c3c")
            _beep(False)

        self.win.after(2500, self._reset_status)

    def _reset_status(self):
        if self.running:
            self.status.configure(text="Scanning...", fg="#aaa", font=("Segoe UI Emoji", 30))
            self.detail.configure(text="Show the QR code to the camera", fg="#888")

    def close(self):
        self.running = False
        try:
            self.cap.release()
        finally:
            if hasattr(self, "win"):
                self.win.destroy()


def open_scanner(parent, lookup, on_success=None, camera_index=0):
    """Open the live QR scanner window."""
    return QRScannerWindow(parent, lookup, on_success, camera_index)