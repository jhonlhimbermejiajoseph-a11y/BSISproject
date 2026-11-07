import os
import tkinter as tk

from src.ui import theme as T
from src.utils import auth

# Put your photo in the assets folder with one of these names.
BG_FILES = ("login_bg.png", "login_bg.jpg", "login_bg.jpeg")


def _find_background():
    for name in BG_FILES:
        path = os.path.join(T.ASSETS_DIR, name)
        if os.path.exists(path):
            return path
    return None


class LoginView(tk.Frame):
    def __init__(self, parent, on_success):
        super().__init__(parent, bg=T.BG)
        self.on_success = on_success
        self.logo = T.load_logo(270)                      # assets/logo.png (optional)
        self.bg_photo = None
        self.last_size = None

        # ---------- background photo (needs Pillow; plain dark background without it) ----------
        self.status = tk.Label(self, text="", bg=T.BG, fg=T.YELLOW, font=("Segoe UI", 9),
                               wraplength=1000, justify="center")
        problems = []
        self.bg_source, problem = self._load_background()
        if self.bg_source is not None:
            self.bg_label = tk.Label(self, bg=T.BG, bd=0)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.bind("<Configure>", self._resize_background)
        elif problem:
            problems.append(problem)
        if self.logo is None:
            problems.append(self._logo_problem())
        self._show_problem("\n".join(problems))

        # ---------- sign-in card (drawn after the photo, so it sits on top) ----------
        box = T.card(self)
        box.place(relx=0.5, rely=0.5, anchor="center")
        form = tk.Frame(box, bg=T.CARD)
        form.pack(padx=44, pady=34)

        if self.logo:                                      # the logo already shows the name
            tk.Label(form, image=self.logo, bg=T.CARD).pack(pady=(0, 4))
            T.label(form, T.SYSTEM_NAME, 9, color=T.MUTED, wraplength=340,
                    justify="center").pack(pady=(0, 20))
        else:
            T.label(form, T.BARANGAY_NAME, 20, True, T.GREEN, wraplength=340,
                    justify="center").pack()
            T.label(form, "Health Center", 11).pack(pady=(0, 2))
            T.label(form, T.SYSTEM_NAME, 9, color=T.MUTED, wraplength=340,
                    justify="center").pack(pady=(0, 20))

        row, self.username = T.labeled_entry(form, "Username", 34)
        row.pack(fill="x")
        row, self.password = T.labeled_entry(form, "Password", 34, show="*")
        row.pack(fill="x", pady=(12, 0))

        self.show_var = tk.BooleanVar(value=False)
        T.checkbox(form, "Show password", self.show_var).pack(anchor="w", pady=(6, 0))
        self.show_var.trace_add("write", lambda *a: self.password.config(
            show="" if self.show_var.get() else "*"))

        self.error = T.label(form, "", 9, color=T.RED)
        self.error.pack(anchor="w", pady=(8, 0))
        T.button(form, "Sign in", self.sign_in).pack(fill="x", pady=(8, 0), ipady=4)
        T.label(form, "Demo: admin/admin123  \u00b7  bhw/bhw123  \u00b7  checkup/checkup123", 8,
                color=T.MUTED).pack(pady=(16, 0))

        self.username.bind("<Return>", lambda e: self.password.focus_set())
        self.password.bind("<Return>", lambda e: self.sign_in())
        self.username.focus_set()

    # ---------- background helpers ----------
    @staticmethod
    def _load_background():
        """Load the photo once and darken it. Returns (image, problem_text)."""
        path = _find_background()
        if path is None:
            folder = T.ASSETS_DIR
            found = ", ".join(os.listdir(folder)) or "(empty)" if os.path.isdir(folder) else "(folder does not exist)"
            return None, f"Background photo not found. Save it as login_bg.png in:\n{folder}\nFiles found there: {found}"
        try:
            from PIL import Image
            img = Image.open(path).convert("RGB")
            shade = Image.new("RGB", img.size, (15, 21, 25))
            return Image.blend(img, shade, 0.45), ""       # 0 = original, 1 = fully dark
        except ImportError:
            return None, "Pillow is not installed. In the PyCharm Terminal run: uv add pillow"
        except Exception as err:
            return None, f"Could not read the background photo ({path}): {err}"

    @staticmethod
    def _logo_problem():
        path = T.logo_path()
        if path is not None:
            return f"Could not load the logo file: {path}"
        folder = T.ASSETS_DIR
        found = ", ".join(os.listdir(folder)) or "(empty)" if os.path.isdir(folder) else "(folder does not exist)"
        return f"Logo not found. Save it as logo.png in:\n{folder}\nFiles found there: {found}"

    def _show_problem(self, text):
        """Show why the photo is missing, at the bottom of the window."""
        if text:
            self.status.config(text=text)
            self.status.place(relx=0.5, rely=0.99, anchor="s")

    def _resize_background(self, event):
        """Scale the photo to cover the whole window (cropping the edges if needed)."""
        w, h = event.width, event.height
        if w < 20 or h < 20 or (w, h) == self.last_size:
            return
        self.last_size = (w, h)
        try:
            from PIL import Image, ImageTk
            resample = getattr(Image, "Resampling", Image).BILINEAR
            src = self.bg_source
            scale = max(w / src.width, h / src.height)
            resized = src.resize((int(src.width * scale) + 1, int(src.height * scale) + 1), resample)
            left, top = (resized.width - w) // 2, (resized.height - h) // 2
            self.bg_photo = ImageTk.PhotoImage(resized.crop((left, top, left + w, top + h)))
            self.bg_label.config(image=self.bg_photo)
        except Exception as err:
            self._show_problem(f"Background photo error: {err}")

    # ---------- sign in ----------
    def sign_in(self):
        user = auth.authenticate(self.username.get(), self.password.get())
        if user is None:
            self.error.config(text="Wrong username or password.")
            self.password.delete(0, "end")
            return
        auth.set_user(user)
        self.on_success()