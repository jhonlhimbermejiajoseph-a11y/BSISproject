import csv
import tkinter as tk
from datetime import date, timedelta
from tkinter import filedialog, messagebox

from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.ui.inventory_view import stat_tile
from src.utils import database as db

ORANGE = "#ff9f1a"
STATUS_TAG = {"OK": "ok", "Expiring soon": "warn", "Expired": "bad"}
STATUS_ORDER = {"Expired": 0, "Expiring soon": 1, "OK": 2}
STOCK_SORTS = ["Expiry date", "Medicine", "Quantity", "Status"]
SALES_SORTS = ["Date", "Customer", "Medicine", "Amount"]
STOCK_FILTERS = ["All", "OK", "Expiring soon", "Expired"]
SALES_FILTERS = ["All time", "Today", "Last 7 days"]
CHART_H = 200


def money(value):
    return f"PHP {value:,.2f}"


class ReportsView(tk.Frame):
    """Admin dashboard: totals, charts, and two reports (stock and sales) you can sort and export."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.mode = "stock"                  # "stock" or "sales"
        self.mode_buttons = {}
        self.batches = []
        self.sales = []
        self.shown = []                      # rows currently in the table (for the CSV export)
        self._build()
        self.refresh()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Reports",
                 "Monitor stock and sales. Sort, filter and export what you see.").pack(
            fill="x", padx=28, pady=(22, 12))

        tiles = tk.Frame(self, bg=T.BG)
        tiles.pack(fill="x", padx=28)
        self.tile = {}
        for i, (key, text, accent) in enumerate([
            ("sold", "Sold today", T.GREEN), ("saved", "Discounts given today", "#3aa0ff"),
            ("low", "Low stock medicines", T.YELLOW), ("expiry", "Expiring or expired batches", T.RED),
        ]):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            box, value = stat_tile(tiles, text, accent)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            self.tile[key] = value

        charts = tk.Frame(self, bg=T.BG)
        charts.pack(fill="x", padx=28, pady=(12, 0))
        for i, weight in enumerate((5, 4, 3)):
            charts.columnconfigure(i, weight=weight, uniform="chart")
        self.stock_canvas = self._chart_card(charts, 0, "Stock by medicine (top 8)")
        self.sales_canvas = self._chart_card(charts, 1, "Sales, last 7 days (PHP)")
        self.status_canvas = self._chart_card(charts, 2, "Batch status")
        for canvas in (self.stock_canvas, self.sales_canvas, self.status_canvas):
            canvas.bind("<Configure>", lambda e: self.draw_charts())

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=28, pady=(14, 8))
        for mode, text in (("stock", "Stock report"), ("sales", "Sales records")):
            btn = tk.Button(bar, text=text, relief="flat", bd=0, font=T.FONT_BOLD, padx=14, pady=6,
                            cursor="hand2", highlightthickness=0, command=lambda m=mode: self.set_mode(m))
            btn.pack(side="left", padx=(0, 6))
            self.mode_buttons[mode] = btn
        T.button(bar, "Export CSV", self.export, "ghost").pack(side="right")
        T.button(bar, "Refresh", self.refresh, "ghost").pack(side="right", padx=8)
        self.order_combo = T.combo(bar, 11, ["Ascending", "Descending"])
        self.order_combo.pack(side="right")
        self.order_combo.current(0)
        T.label(bar, "Order", 9, color=T.MUTED).pack(side="right", padx=(12, 6))
        self.sort_combo = T.combo(bar, 13)
        self.sort_combo.pack(side="right")
        T.label(bar, "Sort by", 9, color=T.MUTED).pack(side="right", padx=(12, 6))
        self.filter_combo = T.combo(bar, 13)
        self.filter_combo.pack(side="right")
        T.label(bar, "Show", 9, color=T.MUTED).pack(side="right", padx=(12, 6))
        for combo in (self.order_combo, self.sort_combo, self.filter_combo):
            combo.bind("<<ComboboxSelected>>", lambda e: self.render_table())

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 18))
        self.table_host = body
        self.tables = {}
        frame, tree = T.table(body, [("medicine", "Medicine", 220), ("batch", "Batch", 110),
                                     ("qty", "Quantity", 90), ("expiry", "Expiry date", 120),
                                     ("status", "Status", 120)], height=8)
        self.tables["stock"] = (frame, tree)
        frame, tree = T.table(body, [("date", "Date", 130), ("customer", "Customer", 190),
                                     ("medicine", "Medicine", 190), ("qty", "Qty", 60),
                                     ("discount", "Discount", 100), ("paid", "Paid", 100)], height=8)
        self.tables["sales"] = (frame, tree)
        self.footer = T.label(body, "", 10, True)
        self.footer.pack(side="bottom", anchor="e", pady=(8, 0))
        self.set_mode("stock")

    def _chart_card(self, parent, column, title):
        card = T.card(parent)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 10, 0))
        T.label(card, title, 10, True).pack(anchor="w", padx=14, pady=(10, 0))
        canvas = tk.Canvas(card, bg=T.CARD, highlightthickness=0, height=CHART_H)
        canvas.pack(fill="x", padx=10, pady=(4, 8))
        return canvas

    def set_mode(self, mode):
        self.mode = mode
        for m, btn in self.mode_buttons.items():
            on = m == mode
            btn.config(bg=T.GREEN if on else T.FIELD, fg="#001a0d" if on else T.TEXT,
                       activebackground=T.GREEN if on else T.FIELD,
                       activeforeground="#001a0d" if on else T.TEXT)
        for m, (frame, tree) in self.tables.items():
            frame.pack_forget()
        self.tables[mode][0].pack(fill="both", expand=True)
        sorts = STOCK_SORTS if mode == "stock" else SALES_SORTS
        filters = STOCK_FILTERS if mode == "stock" else SALES_FILTERS
        self.sort_combo.config(values=sorts)
        self.sort_combo.current(0)
        self.filter_combo.config(values=filters)
        self.filter_combo.current(0)
        self.order_combo.current(1 if mode == "sales" else 0)       # newest sales first
        self.render_table()

    # ---------- data ----------
    def refresh(self):
        medicines = db.get_medicines()
        self.stock = db.stock_by_sku()
        self.med_names = {m["sku"]: m["name"] for m in medicines}
        self.batches = []
        for b in db.get_batches(in_stock_only=True):
            self.batches.append({"medicine": b["medicine_name"], "batch": b["batch_no"], "qty": b["quantity"],
                                 "expiry": b["expiry_date"], "status": db.expiry_status(b["expiry_date"])})
        self.sales = [{"date": t["created_at"], "customer": t["resident_name"], "medicine": t["medicine_name"],
                       "qty": t["quantity"], "discount": t["subsidy_amount"], "paid": t["total_amount"]}
                      for t in db.get_transactions()]

        today = date.today().isoformat()
        todays = [s for s in self.sales if s["date"][:10] == today]
        low = sum(1 for m in medicines if self.stock.get(m["sku"], 0) <= m["low_stock_level"])
        self.tile["sold"].config(text=money(sum(s["paid"] for s in todays)))
        self.tile["saved"].config(text=money(sum(s["discount"] for s in todays)))
        self.tile["low"].config(text=str(low))
        self.tile["expiry"].config(text=str(sum(1 for b in self.batches if b["status"] != "OK")))
        self.draw_charts()
        self.render_table()

    # ---------- table ----------
    def render_table(self):
        sort = self.sort_combo.get()
        descending = self.order_combo.get() == "Descending"
        if self.mode == "stock":
            wanted = self.filter_combo.get() or "All"
            rows = [b for b in self.batches if wanted == "All" or b["status"] == wanted]
            keys = {"Expiry date": lambda r: r["expiry"], "Medicine": lambda r: r["medicine"].lower(),
                    "Quantity": lambda r: r["qty"], "Status": lambda r: STATUS_ORDER[r["status"]]}
            rows = merge_sort(rows, key=keys.get(sort, keys["Expiry date"]))          # Merge Sort
            if descending:
                rows.reverse()
            T.fill(self.tables["stock"][1], [
                (i, (r["medicine"], r["batch"], r["qty"], r["expiry"], r["status"]), STATUS_TAG[r["status"]])
                for i, r in enumerate(rows)])
            units = sum(r["qty"] for r in rows)
            self.footer.config(text=f"{len(rows)} batches  •  {units} units", fg=T.MUTED)
        else:
            period = self.filter_combo.get() or "All time"
            today = date.today()
            first = {"Today": today, "Last 7 days": today - timedelta(days=6)}.get(period)
            rows = [s for s in self.sales if first is None or s["date"][:10] >= first.isoformat()]
            keys = {"Date": lambda r: r["date"], "Customer": lambda r: r["customer"].lower(),
                    "Medicine": lambda r: r["medicine"].lower(), "Amount": lambda r: r["paid"]}
            rows = merge_sort(rows, key=keys.get(sort, keys["Date"]))
            if descending:
                rows.reverse()
            T.fill(self.tables["sales"][1], [
                (i, (r["date"], r["customer"], r["medicine"], r["qty"], f"{r['discount']:,.2f}",
                     f"{r['paid']:,.2f}"), None) for i, r in enumerate(rows)])
            self.footer.config(text=f"{len(rows)} sales  •  Paid {money(sum(r['paid'] for r in rows))}"
                                    f"  •  Discounts {money(sum(r['discount'] for r in rows))}", fg=T.GREEN)
        self.shown = rows

    def export(self):
        if not self.shown:
            messagebox.showinfo("Nothing to export", "There are no rows in this report.")
            return
        name = "stock_report.csv" if self.mode == "stock" else "sales_report.csv"
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile=name,
                                            filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(self.shown[0].keys()))
            writer.writeheader()
            writer.writerows(self.shown)
        messagebox.showinfo("Exported", f"Saved {len(self.shown)} rows to:\n{path}")

    # ---------- charts (drawn by hand on a Canvas) ----------
    def draw_charts(self):
        self.draw_stock_bars()
        self.draw_sales_bars()
        self.draw_status_donut()

    def draw_stock_bars(self):
        c = self.stock_canvas
        c.delete("all")
        w = max(c.winfo_width(), 260)
        items = sorted(((self.med_names.get(s, s), n) for s, n in self.stock.items()), key=lambda x: -x[1])[:8]
        if not items:
            c.create_text(w / 2, CHART_H / 2, text="No stock yet", fill=T.MUTED, font=T.FONT)
            return
        top = max(n for _, n in items)
        row_h = (CHART_H - 8) / len(items)
        label_w, value_w = 128, 44
        for i, (name, qty) in enumerate(items):
            y = 4 + i * row_h
            c.create_text(4, y + row_h / 2, text=name if len(name) < 19 else name[:17] + "…",
                          anchor="w", fill=T.TEXT, font=("Segoe UI", 9))
            span = max(w - label_w - value_w - 10, 20)
            length = max(3, span * qty / top)
            c.create_rectangle(label_w, y + 4, label_w + length, y + row_h - 4, width=0,
                               fill=T.GREEN if qty > 20 else T.YELLOW)
            c.create_text(label_w + length + 6, y + row_h / 2, text=str(qty), anchor="w",
                          fill=T.MUTED, font=("Segoe UI", 9))

    def draw_sales_bars(self):
        c = self.sales_canvas
        c.delete("all")
        w = max(c.winfo_width(), 220)
        today = date.today()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        totals = {d.isoformat(): 0.0 for d in days}
        for s in self.sales:
            if s["date"][:10] in totals:
                totals[s["date"][:10]] += s["paid"]
        top = max(totals.values())
        base, slot = CHART_H - 22, (w - 16) / 7
        if top <= 0:
            c.create_text(w / 2, CHART_H / 2, text="No sales in the last 7 days", fill=T.MUTED, font=T.FONT)
        for i, d in enumerate(days):
            amount = totals[d.isoformat()]
            x = 8 + i * slot
            height = (base - 22) * amount / top if top > 0 else 0
            if amount > 0:
                c.create_rectangle(x + 6, base - height, x + slot - 6, base, width=0,
                                   fill=T.GREEN if d == today else "#1f8f5a")
                c.create_text(x + slot / 2, base - height - 8, text=f"{amount:,.0f}", fill=T.MUTED,
                              font=("Segoe UI", 8))
            c.create_text(x + slot / 2, CHART_H - 8, text=d.strftime("%a"), fill=T.MUTED, font=("Segoe UI", 8))
        c.create_line(8, base, w - 8, base, fill=T.BORDER)

    def draw_status_donut(self):
        c = self.status_canvas
        c.delete("all")
        w = max(c.winfo_width(), 200)
        counts = {s: sum(1 for b in self.batches if b["status"] == s) for s in ("OK", "Expiring soon", "Expired")}
        total = sum(counts.values())
        colors = {"OK": T.GREEN, "Expiring soon": ORANGE, "Expired": T.RED}
        size = CHART_H - 24
        cx, cy = 14 + size / 2, CHART_H / 2
        box = (cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2)
        if total == 0:
            c.create_text(w / 2, CHART_H / 2, text="No batches", fill=T.MUTED, font=T.FONT)
            return
        start = 90.0
        for status, n in counts.items():
            if n:
                sweep = -359.99 * n / total if n == total else -360.0 * n / total
                c.create_arc(*box, start=start, extent=sweep, style="arc", width=22, outline=colors[status])
                start += sweep
        c.create_text(cx, cy - 8, text=str(total), fill=T.TEXT, font=("Segoe UI", 20, "bold"))
        c.create_text(cx, cy + 14, text="batches", fill=T.MUTED, font=("Segoe UI", 9))
        x, y = 14 + size + 18, CHART_H / 2 - 36
        for status, n in counts.items():
            c.create_rectangle(x, y + 3, x + 10, y + 13, width=0, fill=colors[status])
            c.create_text(x + 18, y + 8, text=f"{status}", anchor="w", fill=T.TEXT, font=("Segoe UI", 9))
            c.create_text(x + 18, y + 24, text=f"{n} batch" + ("es" if n != 1 else ""), anchor="w",
                          fill=T.MUTED, font=("Segoe UI", 8))
            y += 40