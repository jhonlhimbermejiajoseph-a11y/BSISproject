import os
import re
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.utils import auth, database as db

STATUS_TAG = {"OK": "ok", "Low stock": "warn", "Expiring soon": "warn",
              "Expired": "bad", "Out of stock": "bad"}

IMAGE_DIR = os.path.join(T.ASSETS_DIR, "medicines")      # one picture per medicine code
PICTURE_TYPES = [("Pictures", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"), ("All files", "*.*")]
PILLOW_HINT = "Pictures need Pillow. Open the PyCharm Terminal and run:\n    uv add pillow"
ADD_HINT = "Record stock for a new medicine in the Deliveries screen."


# ---------- medicine pictures: assets/medicines/<CODE>.png ----------
def _image_path(sku):
    return os.path.join(IMAGE_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", sku) + ".png")


def save_medicine_image(sku, source_path):
    """Copy any picture into assets/medicines/<CODE>.png (shrunk to 600 px)."""
    from PIL import Image
    os.makedirs(IMAGE_DIR, exist_ok=True)
    img = Image.open(source_path).convert("RGBA")
    img.thumbnail((600, 600))
    img.save(_image_path(sku), "PNG")


def remove_medicine_image(sku):
    try:
        os.remove(_image_path(sku))
    except OSError:
        pass


def load_medicine_photo(sku, box=(238, 170)):
    """Return a Tk image that fits inside box, or None if the medicine has no picture."""
    path = _image_path(sku)
    if not os.path.exists(path):
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(path).convert("RGBA")
        img.thumbnail(box)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


class InventoryView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.can_edit = auth.can_manage_inventory()    # BHWs can only view
        self.rows = []
        self.by_iid = {}
        self.meds = {}
        self.stock = {}
        self.new_image = None
        self.photo = None
        self._build()
        self.refresh()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Medicine Inventory",
                 "Sorted by FEFO: the earliest expiry is listed first.").pack(fill="x", padx=28, pady=(22, 12))

        stats = tk.Frame(self, bg=T.BG)
        stats.pack(fill="x", padx=28)
        self.stat = {}
        for i, (key, text, color) in enumerate([
            ("total", "Total medicines", T.TEXT), ("low", "Low stock", T.YELLOW),
            ("soon", "Expiring in 90 days", T.YELLOW), ("expired", "Expired", T.RED),
        ]):
            stats.columnconfigure(i, weight=1, uniform="stat")
            box, value = T.stat_card(stats, text, color)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            self.stat[key] = value

        if self.can_edit:
            form = T.card(self)
            form.pack(fill="x", padx=28, pady=(14, 0))
            T.label(form, "Add new medicine", 11, True).pack(anchor="w", padx=16, pady=(14, 6))
            row = tk.Frame(form, bg=T.CARD)
            row.pack(fill="x", padx=16, pady=(0, 6))
            box, self.sku_entry = T.labeled_entry(row, "Med code (SKU)", 12)
            box.pack(side="left", padx=(0, 10))
            box, self.name_entry = T.labeled_entry(row, "Medicine name", 22)
            box.pack(side="left", padx=(0, 10))
            box, self.price_entry = T.labeled_entry(row, "Unit price (PHP)", 11)
            box.pack(side="left", padx=(0, 10))
            box, self.low_entry = T.labeled_entry(row, "Low-stock level", 11)
            box.pack(side="left", padx=(0, 10))
            self.low_entry.insert(0, "20")
            T.button(row, "Choose picture", self.choose_new_image, "ghost").pack(
                side="left", anchor="s", padx=(0, 10))
            T.button(row, "Add medicine", self.add_medicine).pack(side="left", anchor="s")
            self.form_hint = T.label(form, ADD_HINT, 9, color=T.MUTED)
            self.form_hint.pack(anchor="w", padx=16, pady=(0, 12))

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=28, pady=(14, 6))
        T.label(bar, "Search", 9, color=T.MUTED).pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.render())
        search = T.entry(bar, 36)
        search.config(textvariable=self.search_var)
        search.pack(side="left", ipady=5)
        if self.can_edit:
            T.button(bar, "Delete selected", self.delete_selected, "danger").pack(side="right")
            T.button(bar, "Edit selected", self.edit_selected).pack(side="right", padx=(0, 8))

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 22))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        frame, self.tree = T.table(body, [
            ("sku", "Med code", 90), ("name", "Medicine name", 200), ("batch", "Batch", 90),
            ("qty", "Stock", 60), ("expiry", "Expiry date", 100), ("status", "Status", 100),
        ], height=10)
        frame.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        if self.can_edit:
            self.tree.bind("<Double-1>", lambda e: self.edit_selected())

        # details panel: picture + info for the selected medicine
        self.preview = T.card(body, width=272)
        self.preview.grid(row=0, column=1, sticky="ns", padx=(14, 0))
        self.preview.pack_propagate(False)
        T.label(self.preview, "Details", 11, True).pack(anchor="w", padx=16, pady=(14, 8))
        pic = tk.Frame(self.preview, bg=T.FIELD, width=238, height=170)
        pic.pack(padx=16)
        pic.pack_propagate(False)
        self.photo_label = tk.Label(pic, bg=T.FIELD, fg=T.MUTED, font=T.FONT, text="No picture")
        self.photo_label.place(relx=0.5, rely=0.5, anchor="center")
        self.p_name = T.label(self.preview, "Select a medicine", 12, True, wraplength=236, justify="left")
        self.p_name.pack(anchor="w", padx=16, pady=(12, 4))
        self.p_info = T.label(self.preview, "", 10, color=T.MUTED, wraplength=236, justify="left")
        self.p_info.pack(anchor="w", padx=16)

    # ---------- data ----------
    def refresh(self):
        meds = db.get_medicines()
        self.meds = {m["sku"]: m for m in meds}
        self.stock = db.stock_by_sku()
        batches = db.get_batches(in_stock_only=True)
        low_skus = {m["sku"] for m in meds if self.stock.get(m["sku"], 0) <= m["low_stock_level"]}

        rows = []
        for b in batches:
            status = db.expiry_status(b["expiry_date"])
            if status == "OK" and b["sku"] in low_skus:
                status = "Low stock"
            rows.append({"iid": f"b{b['id']}", "sku": b["sku"], "name": b["medicine_name"],
                         "batch": b["batch_no"], "qty": b["quantity"],
                         "expiry": b["expiry_date"], "status": status})
        have = {b["sku"] for b in batches}
        for m in meds:
            if m["sku"] not in have:
                rows.append({"iid": f"m{m['sku']}", "sku": m["sku"], "name": m["name"],
                             "batch": "-", "qty": 0, "expiry": "-", "status": "Out of stock"})

        # Merge Sort by expiry date (FEFO order); rows without a batch go last
        self.rows = merge_sort(rows, key=lambda r: (r["expiry"] == "-", r["expiry"]))
        self.by_iid = {r["iid"]: r for r in self.rows}

        self.stat["total"].config(text=str(len(meds)))
        self.stat["low"].config(text=str(len(low_skus)))
        self.stat["soon"].config(text=str(sum(r["status"] == "Expiring soon" for r in rows)))
        self.stat["expired"].config(text=str(sum(r["status"] == "Expired" for r in rows)))
        self.render()

    def render(self):
        sel = self.tree.selection()
        keep = sel[0] if sel else None
        text = self.search_var.get().strip().lower()
        shown = [r for r in self.rows if text in f"{r['sku']} {r['name']} {r['batch']}".lower()]
        T.fill(self.tree, [
            (r["iid"], (r["sku"], r["name"], r["batch"], r["qty"], r["expiry"], r["status"]),
             STATUS_TAG[r["status"]])
            for r in shown
        ])
        if keep and keep in self.by_iid and any(r["iid"] == keep for r in shown):
            self.tree.selection_set(keep)
            self.show_preview(keep)
        else:
            self.show_preview(None)

    # ---------- details panel ----------
    def on_select(self):
        sel = self.tree.selection()
        self.show_preview(sel[0] if sel else None)

    def show_preview(self, iid):
        row = self.by_iid.get(iid) if iid else None
        if row is None:
            self.photo = None
            self.photo_label.config(image="", text="No picture")
            self.p_name.config(text="Select a medicine")
            self.p_info.config(text="")
            return
        sku = row["sku"]
        med = self.meds[sku]
        self.photo = load_medicine_photo(sku)
        if self.photo:
            self.photo_label.config(image=self.photo, text="")
        else:
            self.photo_label.config(image="", text="No picture")
        nxt = next((r for r in self.rows
                    if r["sku"] == sku and r["qty"] > 0 and r["status"] != "Expired"), None)
        lines = [f"Code: {sku}",
                 f"PHP {med['unit_price']:,.2f} each",
                 f"In stock: {self.stock.get(sku, 0)}",
                 f"Low-stock level: {med['low_stock_level']}",
                 f"Next to use: {nxt['batch']} (exp {nxt['expiry']})" if nxt else "Next to use: none"]
        self.p_name.config(text=med["name"])
        self.p_info.config(text="\n".join(lines))

    # ---------- actions (officer / admin only) ----------
    def choose_new_image(self):
        path = filedialog.askopenfilename(title="Choose a picture of the medicine",
                                          filetypes=PICTURE_TYPES)
        if path:
            self.new_image = path
            self.form_hint.config(text=f"Picture selected: {os.path.basename(path)}.  {ADD_HINT}")

    def add_medicine(self):
        sku = self.sku_entry.get().strip().upper()
        name = self.name_entry.get().strip()
        try:
            price = float(self.price_entry.get())
            low = int(self.low_entry.get())
        except ValueError:
            messagebox.showwarning("Check the numbers", "Price and low-stock level must be numbers.")
            return
        if not sku or not name or price < 0 or low < 0:
            messagebox.showwarning("Missing details", "Fill in the code and name, with valid numbers.")
            return
        try:
            db.add_medicine(sku, name, price, low)
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate code", f"A medicine with code {sku} already exists.")
            return
        if self.new_image:
            try:
                save_medicine_image(sku, self.new_image)
            except ImportError:
                messagebox.showinfo("Pillow needed", PILLOW_HINT)
            except Exception as err:
                messagebox.showerror("Picture problem", f"The medicine was added, but its picture failed:\n{err}")
            self.new_image = None
            self.form_hint.config(text=ADD_HINT)
        for e in (self.sku_entry, self.name_entry, self.price_entry):
            e.delete(0, "end")
        self.refresh()

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Click a medicine in the table first.")
            return
        EditDialog(self, self.by_iid[sel[0]], self.refresh)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Click a row in the table first.")
            return
        iid = sel[0]
        if iid.startswith("b"):
            if messagebox.askyesno("Delete batch", "Delete this batch from the inventory?"):
                db.delete_batch(int(iid[1:]))
        else:
            sku = iid[1:]
            if messagebox.askyesno("Delete medicine", f"Delete medicine {sku}?"):
                try:
                    db.delete_medicine(sku)
                    remove_medicine_image(sku)
                except sqlite3.IntegrityError:
                    messagebox.showerror("Cannot delete", "This medicine already has request history.")
        self.refresh()


class EditDialog(tk.Toplevel):
    """Edit a medicine's details, its batch (if a batch row was selected) and its picture."""

    def __init__(self, parent, row, on_saved):
        super().__init__(parent)
        self.on_saved = on_saved
        self.sku = row["sku"]
        self.med = db.get_medicine(self.sku)
        self.batch = db.get_batch(int(row["iid"][1:])) if row["iid"].startswith("b") else None
        self.new_image = None
        self.remove_image = False
        self.title(f"Edit {self.sku}")
        self.configure(bg=T.BG)
        self.resizable(False, False)

        body = T.card(self)
        body.pack(padx=20, pady=20)
        pad = {"padx": 24}
        T.label(body, f"Edit medicine  \u2022  {self.sku}", 13, True).pack(anchor="w", pady=(20, 10), **pad)

        box, self.name_e = T.labeled_entry(body, "Medicine name", 42)
        box.pack(fill="x", **pad)
        self.name_e.insert(0, self.med["name"])
        line = tk.Frame(body, bg=T.CARD)
        line.pack(fill="x", pady=(10, 0), **pad)
        box, self.price_e = T.labeled_entry(line, "Unit price (PHP)", 14)
        box.pack(side="left", padx=(0, 10))
        self.price_e.insert(0, f"{self.med['unit_price']:g}")
        box, self.low_e = T.labeled_entry(line, "Low-stock level", 14)
        box.pack(side="left")
        self.low_e.insert(0, str(self.med["low_stock_level"]))

        if self.batch:
            T.label(body, "This batch", 11, True).pack(anchor="w", pady=(16, 6), **pad)
            line = tk.Frame(body, bg=T.CARD)
            line.pack(fill="x", **pad)
            box, self.batch_e = T.labeled_entry(line, "Batch no.", 14)
            box.pack(side="left", padx=(0, 10))
            self.batch_e.insert(0, self.batch["batch_no"])
            box, self.qty_e = T.labeled_entry(line, "Quantity", 9)
            box.pack(side="left", padx=(0, 10))
            self.qty_e.insert(0, str(self.batch["quantity"]))
            box, self.exp_e = T.labeled_entry(line, "Expiry (YYYY-MM-DD)", 16)
            box.pack(side="left")
            self.exp_e.insert(0, self.batch["expiry_date"])

        T.label(body, "Picture", 11, True).pack(anchor="w", pady=(16, 6), **pad)
        line = tk.Frame(body, bg=T.CARD)
        line.pack(fill="x", **pad)
        T.button(line, "Choose picture", self.choose_image, "ghost").pack(side="left")
        T.button(line, "Remove picture", self.mark_remove, "danger").pack(side="left", padx=8)
        has = os.path.exists(_image_path(self.sku))
        self.pic_status = T.label(body, "Current picture will be kept." if has else "No picture yet.",
                                  9, color=T.MUTED)
        self.pic_status.pack(anchor="w", pady=(6, 0), **pad)

        row_btn = tk.Frame(body, bg=T.CARD)
        row_btn.pack(fill="x", pady=22, **pad)
        T.button(row_btn, "Save changes", self.save).pack(side="left")
        T.button(row_btn, "Cancel", self.destroy, "ghost").pack(side="left", padx=8)

        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()

    def choose_image(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a picture of the medicine",
                                          filetypes=PICTURE_TYPES)
        if path:
            self.new_image, self.remove_image = path, False
            self.pic_status.config(text=f"New picture: {os.path.basename(path)}")

    def mark_remove(self):
        self.new_image, self.remove_image = None, True
        self.pic_status.config(text="The picture will be removed when you save.")

    def save(self):
        name = self.name_e.get().strip()
        try:
            price = float(self.price_e.get())
            low = int(self.low_e.get())
        except ValueError:
            messagebox.showwarning("Check the numbers", "Price and low-stock level must be numbers.", parent=self)
            return
        if not name or price < 0 or low < 0:
            messagebox.showwarning("Missing details", "Enter a name and valid numbers.", parent=self)
            return

        batch_args = None
        if self.batch:
            batch_no = self.batch_e.get().strip()
            try:
                qty = int(self.qty_e.get())
                expiry = datetime.strptime(self.exp_e.get().strip(), "%Y-%m-%d").date()
            except ValueError:
                messagebox.showwarning("Check the batch", "Quantity must be a whole number and the "
                                       "expiry date must look like 2027-06-30.", parent=self)
                return
            if not batch_no or qty < 0:
                messagebox.showwarning("Check the batch", "Enter a batch number and a quantity of 0 or more.",
                                       parent=self)
                return
            batch_args = (self.batch["id"], batch_no, qty, expiry.isoformat())

        try:
            if self.remove_image:
                remove_medicine_image(self.sku)
            elif self.new_image:
                save_medicine_image(self.sku, self.new_image)
        except ImportError:
            messagebox.showinfo("Pillow needed", PILLOW_HINT, parent=self)
            return
        except Exception as err:
            messagebox.showerror("Picture problem", str(err), parent=self)
            return

        db.update_medicine(self.sku, name, price, low)
        if batch_args:
            db.update_batch(*batch_args)
        self.destroy()
        self.on_saved()