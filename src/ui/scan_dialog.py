"""Scan a resident's QR code with the computer's camera (no USB scanner needed).

Needs:  uv add opencv-python pillow
"""
import sys
import tkinter as tk
from tkinter import messagebox

from src.ui import theme as T

INSTALL_HINT = ("Camera scanning needs two extra packages.\n\n"
                "Open the PyCharm terminal and run:\n    uv add opencv-python pillow\n\n"
                "Then restart the app.")


def open_scanner(parent, on_code):
    """Open the camera window. on_code(text) is called when a QR code is read."""
    try:
        import cv2          # noqa: F401
        from PIL import ImageTk   # noqa: F401
    except ImportError:
        messagebox.showinfo("Install camera support", INSTALL_HINT)
        return
    ScanDialog(parent, on_code)


class ScanDialog(tk.Toplevel):
    def __init__(self, parent, on_code):
        super().__init__(parent)
        import cv2
        from PIL import Image, ImageTk
        self.cv2, self.Image, self.ImageTk = cv2, Image, ImageTk
        self.on_code = on_code
        self.title("Scan resident ID")
        self.configure(bg=T.BG)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close)

        body = T.card(self)
        body.pack(padx=18, pady=18)
        T.label(body, "Scan resident ID", 14, True).pack(anchor="w", padx=18, pady=(16, 2))
        T.label(body, "Hold the QR code of the ID card in front of the camera.", 9,
                color=T.MUTED).pack(anchor="w", padx=18)
        self.video = tk.Label(body, bg="black")
        self.video.pack(padx=18, pady=12)
        self.status = T.label(body, "Starting camera...", 9, color=T.MUTED)
        self.status.pack()
        T.button(body, "Cancel", self.close, "ghost").pack(pady=(8, 16))

        self.cap = self._open_camera(cv2)
        self.detector = cv2.QRCodeDetector()
        self.photo = None
        self.running = True
        self.after_id = None
        if self.cap is None:
            self.close()
            messagebox.showerror(
                "No camera found",
                "Could not open a camera.\n\n"
                "- Make sure a webcam is connected (most desktop PCs have none).\n"
                "- Close other programs using the camera (Zoom, Teams, browser).\n"
                "- Windows: Settings > Privacy & security > Camera > allow desktop apps.\n\n"
                "You can still type the Resident ID and press Enter.")
            return
        self.tick()

    @staticmethod
    def _open_camera(cv2):
        """Try several camera numbers and backends. Returns an open camera, or None."""
        try:
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)   # hide OpenCV warnings
        except Exception:
            pass
        backends = ([cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if sys.platform.startswith("win")
                    else [cv2.CAP_ANY])
        for index in (0, 1, 2):
            for backend in backends:
                cap = cv2.VideoCapture(index, backend)
                if cap.isOpened():
                    ok, _ = cap.read()
                    if ok:
                        return cap
                cap.release()
        return None

    def tick(self):
        if not self.running:
            return
        ok, frame = self.cap.read()
        if ok:
            text, _, _ = self.detector.detectAndDecode(frame)
            if text:
                code = text.strip()
                self.close()
                self.on_code(code)
                return
            rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
            image = self.Image.fromarray(rgb)
            image.thumbnail((520, 390))
            self.photo = self.ImageTk.PhotoImage(image)
            self.video.config(image=self.photo)
            self.status.config(text="Looking for a QR code...")
        self.after_id = self.after(30, self.tick)

    def close(self):
        self.running = False
        try:
            if self.after_id:
                self.after_cancel(self.after_id)
            self.cap.release()
        except Exception:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass