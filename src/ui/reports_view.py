import tkinter as tk

from src.dsa.merge_sort import merge_sort
from src.ui import theme as T
from src.utils import database as db


# ---------- report data ----------
def _inventory_rows():
    return [{"sku": b["sku"], "medicine": b["medicine_name"], "batch_no": b["batch_no"],
             "quantity": b["quantity"], "expiry_date": b["expiry_date"],
             "status": db.expiry_status(b["expiry_date"])}
            for b in db.get_batches(in_stock_only=True)]


def _request_rows():
    return [{"id": r["id"], "created_at": r["created_at"], "resident": r["resident_name"],
             "medicine": r["medicine_name"], "quantity": r["quantity"], "status": r["status"]}
            for r in db.get_requests()]


def _subsidy_rows():
    return [{"id": t["id"], "created_at": t["created_at"], "resident": t["resident_name"],
             "category": t["category"], "gross": t["gross_amount"],
             "subsidy": t["subsidy_amount"], "total": t["total_amount"]}
            for t in db.get_transactions()]


def _inventory_summary(rows):
    return f"{len(rows)} batch(es) with stock."


def _request_summary(rows):
    done = sum(r["status"] == "Completed" for r in rows)
    pending = sum(r["status"] == "Pending" for r in rows)
    return f"{len(rows)} request(s): {done} completed, {pending} pending."


def _subsidy_summary(rows):
    return (f"{len(rows)} transaction(s)  •  total subsidy PHP {sum(r['subsidy'] for r in rows):,.2f}"
            f"  •  collected from residents PHP {sum(r['total'] for r in rows):,.2f}")


REPORTS = {
    "Inventory report": {
        "rows": _inventory_rows, "summary": _inventory_summary,
        "columns": [("sku", "Med code", 90), ("medicine", "Medicine", 200), ("batch_no", "Batch", 100),
                    ("quantity", "Quantity", 80), ("expiry_date", "Expiry date", 110), ("status", "Status", 110)],
        "sorts": {"Expiry date": "expiry_date", "Quantity": "quantity", "Status": "status", "Medicine": "medicine"},
    },
    "Request report": {
        "rows": _request_rows, "summary": _request_summary,
        "columns": [("id", "Req", 50), ("created_at", "Date", 130), ("resident", "Resident", 170),
                    ("medicine", "Medicine", 190), ("quantity", "Quantity", 80), ("status", "Status", 100)],
        "sorts": {"Date": "created_at", "Quantity": "quantity", "Status": "status", "Resident": "resident"},
    },
    "Subsidy summary": {
        "rows": _subsidy_rows, "summary": _subsidy_summary,
        "columns": [("id", "Receipt", 70), ("created_at", "Date", 130), ("resident", "Resident", 170),
                    ("category", "Category", 120), ("gross", "Gross (PHP)", 100),
                    ("subsidy", "Subsidy (PHP)", 110), ("total", "Paid (PHP)", 100)],
        "sorts": {"Date": "created_at", "Subsidy amount": "subsidy", "Category": "category", "Resident": "resident"},
    },
}


def _fmt(value):
    return f"{value:,.2f}" if isinstance(value, float) else value


class ReportsView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self._build()
        self.change_report()

    def _build(self):
        T.header(self, "Reports", "Sorted with Merge Sort by date, quantity, or status.").pack(
            fill="x", padx=28, pady=(22, 12))

        bar = T.card(self)
        bar.pack(fill="x", padx=28)
        row = tk.Frame(bar, bg=T.CARD)
        row.pack(fill="x", padx=16, pady=14)
        box, self.report_combo = T.labeled_combo(row, "Report", 24, list(REPORTS))
        box.pack(side="left", padx=(0, 10))
        self.report_combo.current(0)
        self.report_combo.bind("<<ComboboxSelected>>", lambda e: self.change_report())
        box, self.sort_combo = T.labeled_combo(row, "Sort by", 18)
        box.pack(side="left", padx=(0, 10))
        self.sort_combo.bind("<<ComboboxSelected>>", lambda e: self.render())
        box, self.order_combo = T.labeled_combo(row, "Order", 14, ["Ascending", "Descending"])
        box.pack(side="left", padx=(0, 10))
        self.order_combo.current(0)
        self.order_combo.bind("<<ComboboxSelected>>", lambda e: self.render())
        T.button(row, "Refresh", self.render, "ghost").pack(side="left", anchor="s")

        self.summary = T.label(self, "", 10, color=T.MUTED)
        self.summary.pack(anchor="w", padx=28, pady=(12, 6))
        frame, self.tree = T.table(self, REPORTS["Inventory report"]["columns"], height=14)
        frame.pack(fill="both", expand=True, padx=28, pady=(0, 22))

    def change_report(self):
        report = REPORTS[self.report_combo.get()]
        self.sort_combo["values"] = list(report["sorts"])
        self.sort_combo.current(0)
        T.set_columns(self.tree, report["columns"])
        self.render()

    def render(self):
        report = REPORTS[self.report_combo.get()]
        field = report["sorts"][self.sort_combo.get()]
        rows = merge_sort(report["rows"](), key=lambda r: r[field],
                          reverse=self.order_combo.get() == "Descending")
        ids = [c[0] for c in report["columns"]]
        T.fill(self.tree, [(i, tuple(_fmt(r[c]) for c in ids), None) for i, r in enumerate(rows)])
        self.summary.config(text=report["summary"](rows))