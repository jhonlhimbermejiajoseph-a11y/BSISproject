from datetime import datetime
import tkinter as tk
from tkinter import messagebox

from src.dsa.min_heap import MinHeap
from src.dsa.queue import RequestQueue
from src.ui import theme as T
from src.ui.inventory_view import stat_tile
from src.utils import auth, database as db, prescription, receipt, subsidy


def allocate_fefo(sku, quantity):
    """Pick batches earliest-expiry first, using the Min-Heap (FEFO).

    Returns (allocations, shortfall). allocations is a list of (batch, units_taken).
    """
    heap = MinHeap()
    heap.load(db.get_batches(sku, in_stock_only=True), "expiry_date")
    heap.drop_while(lambda b: b["expiry_date"] < db.today())      # skip expired batches
    allocations, need = [], quantity
    while need > 0 and not heap.is_empty():
        batch = heap.pop()
        take = min(batch["quantity"], need)
        allocations.append((batch, take))
        need -= take
    return allocations, need


class RequestsView(tk.Frame):
    """Orders placed on the Medicines screen wait here until the BHW serves them."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.queue = RequestQueue()      # FIFO queue of requests waiting to be served
        self._build()
        self.refresh()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Medicine Requests",
                 "Orders from the Medicines screen wait here. Serve the queue in arrival order.").pack(
            fill="x", padx=28, pady=(22, 12))
        tiles = tk.Frame(self, bg=T.BG)
        tiles.pack(fill="x", padx=28, pady=(0, 14))
        self.tile = {}
        for i, (key, text, accent) in enumerate([
            ("queue", "Waiting in the queue", T.GREEN), ("pending", "Pending (waiting for stock)", T.YELLOW),
            ("served", "Served today", "#3aa0ff"),
        ]):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            box, value = stat_tile(tiles, text, accent)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            self.tile[key] = value

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 22))

        # service queue
        top = tk.Frame(body, bg=T.BG)
        top.pack(fill="x")
        T.label(top, "Service queue (first come, first served)", 11, True).pack(side="left")
        T.button(top, "Serve next", self.serve_next).pack(side="right")
        T.button(top, "Cancel selected", lambda: self.cancel_selected(True), "danger").pack(side="right", padx=8)
        frame, self.queue_tree = T.table(body, [
            ("pos", "#", 40), ("id", "Req", 60), ("resident", "Customer", 200),
            ("medicine", "Medicine", 220), ("qty", "Qty", 60), ("time", "Requested", 150),
        ], height=5)
        frame.pack(fill="both", expand=True, pady=(8, 14))

        # pending
        top = tk.Frame(body, bg=T.BG)
        top.pack(fill="x")
        T.label(top, "Pending / backorder (no stock at the time)", 11, True).pack(side="left")
        T.button(top, "Re-check stock", self.recheck_pending, "ghost").pack(side="right")
        T.button(top, "Cancel selected", lambda: self.cancel_selected(False), "danger").pack(side="right", padx=8)
        frame, self.pending_tree = T.table(body, [
            ("id", "Req", 60), ("resident", "Customer", 200), ("medicine", "Medicine", 220),
            ("qty", "Qty", 60), ("time", "Requested", 150),
        ], height=4)
        frame.pack(fill="both", expand=True, pady=(8, 0))

        self.msg_label = T.label(body, "", 9, color=T.MUTED)
        self.msg_label.pack(anchor="w", pady=(8, 0))

    # ---------- data ----------
    def refresh(self):
        self.queue.clear()
        self.queue.load(db.get_requests("Queued"))        # oldest first
        self.render()

    def render(self):
        pending = db.get_requests("Pending")
        self.tile["queue"].config(text=str(len(self.queue.to_list())))
        self.tile["pending"].config(text=str(len(pending)))
        today = datetime.now().strftime("%Y-%m-%d")
        self.tile["served"].config(text=str(len({t["request_id"] for t in db.get_transactions()
                                                 if str(t["created_at"])[:10] == today})))
        T.fill(self.queue_tree, [
            (r["id"], (pos, r["id"], r["resident_name"], r["medicine_name"], r["quantity"], r["created_at"]), None)
            for pos, r in enumerate(self.queue, start=1)
        ])
        T.fill(self.pending_tree, [
            (r["id"], (r["id"], r["resident_name"], r["medicine_name"], r["quantity"], r["created_at"]), "warn")
            for r in pending
        ])

    def _say(self, text, color=T.MUTED):
        self.msg_label.config(text=text, fg=color)

    # ---------- queue actions ----------
    def serve_next(self):
        """Serve the customer at the head of the line. Their whole order (all medicines placed
        together, same customer and same minute) is served in one go."""
        waiting = self.queue.to_list()
        if not waiting:
            messagebox.showinfo("Queue is empty", "No requests are waiting.")
            return
        head = waiting[0]
        group = []
        for r in waiting:
            if r["resident_id"] == head["resident_id"] and r["created_at"] == head["created_at"]:
                group.append(r)
            else:
                break
        ProcessDialog(self, group, self.after_served)

    def after_served(self):
        self.refresh()                                    # the served requests are no longer Queued

    def cancel_selected(self, from_queue):
        tree = self.queue_tree if from_queue else self.pending_tree
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select a request", "Click a request in the table first.")
            return
        rid = int(sel[0])
        if not messagebox.askyesno("Cancel request", f"Cancel request #{rid}?"):
            return
        if from_queue:
            self.queue.remove_where(lambda r: r["id"] == rid)
        db.set_request_status(rid, "Cancelled")
        self.render()

    def recheck_pending(self):
        moved = 0
        for r in db.get_requests("Pending"):
            if db.available_stock(r["sku"]) >= r["quantity"]:
                db.set_request_status(r["id"], "Queued")
                moved += 1
        self.queue.clear()
        self.queue.load(db.get_requests("Queued"))        # back in original arrival order
        self.render()
        self._say(f"{moved} pending request(s) moved to the queue." if moved
                  else "Still no stock for the pending requests.", T.GREEN if moved else T.YELLOW)


class ProcessDialog(tk.Toplevel):
    """Serve one customer's order: discount, FEFO batches, dispense every medicine, one receipt."""

    def __init__(self, parent, requests, on_done):
        super().__init__(parent)
        self.requests = requests
        self.on_done = on_done
        first = requests[0]
        self.title("Serve order" if len(requests) > 1 else f"Process request #{first['id']}")
        self.configure(bg=T.BG)
        self.resizable(False, False)

        rate = subsidy.subsidy_rate(first["category"])
        self.has_discount = rate > 0

        body = T.card(self)
        body.pack(padx=20, pady=20)
        pad = {"anchor": "w", "padx": 22}
        ids = ", ".join(f"#{r['id']}" for r in requests)
        T.label(body, f"Order {ids}", 14, True).pack(pady=(18, 2), **pad)
        T.label(body, f"{first['resident_name']}  ({first['scanned_id']})", 10).pack(**pad)
        T.label(body, f"{first['category']}  \u2022  {rate * 100:.0f}% discount", 9,
                color=T.MUTED).pack(**pad)

        rows, gross, saved, total, short = [], 0.0, 0.0, 0.0, 0
        for i, r in enumerate(requests):
            calc = subsidy.calculate(r["unit_price"], r["quantity"], r["category"])
            allocations, shortfall = allocate_fefo(r["sku"], r["quantity"])
            gross += calc["gross"]
            saved += calc["subsidy"]
            total += calc["total"]
            short += shortfall > 0
            batches = ", ".join(f"{b['batch_no']} x{n}" for b, n in allocations)
            rows.append((i, (r["medicine_name"], r["quantity"], f"{calc['total']:,.2f}",
                             "Not enough stock" if shortfall > 0 else batches),
                         "warn" if shortfall > 0 else None))
        frame, tree = T.table(body, [("name", "Medicine", 170), ("qty", "Qty", 44),
                                     ("pay", "You pay", 80), ("fefo", "FEFO batches", 190)],
                              height=min(max(len(requests), 2), 6))
        frame.pack(fill="x", padx=22, pady=(12, 0))
        T.fill(tree, rows)
        if short:
            T.label(body, f"{short} medicine(s) are no longer in stock. They will move to Pending; "
                          "the rest is dispensed.", 9, color=T.YELLOW, wraplength=440,
                    justify="left").pack(pady=(6, 0), **pad)

        T.label(body, f"Gross: PHP {gross:,.2f}", 10).pack(pady=(12, 0), **pad)
        T.label(body, f"Discount: - PHP {saved:,.2f}", 10, color=T.GREEN).pack(**pad)
        T.label(body, f"Customer pays: PHP {total:,.2f}", 12, True).pack(pady=(2, 0), **pad)

        # the ID check only matters when a discount is given
        self.id_var = tk.BooleanVar()
        if self.has_discount:
            T.checkbox(body, "Resident ID / eligibility verified", self.id_var).pack(pady=(14, 0), **pad)

        row = tk.Frame(body, bg=T.CARD)
        row.pack(fill="x", padx=22, pady=18)
        T.button(row, "Dispense & receipt", self.confirm).pack(side="left")
        T.button(row, "Close", self.destroy, "ghost").pack(side="left", padx=8)

        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()

    def confirm(self):
        if self.has_discount and not self.id_var.get():
            messagebox.showwarning("Verification needed",
                                   "Tick the ID check before dispensing with a discount.", parent=self)
            return
        staff = auth.current_user()["id"]
        done, moved = [], 0
        for req in self.requests:
            allocations, shortfall = allocate_fefo(req["sku"], req["quantity"])    # stock checked right now
            if shortfall > 0:
                db.set_request_status(req["id"], "Pending")
                moved += 1
                continue
            calc = subsidy.calculate(req["unit_price"], req["quantity"], req["category"])
            batch_info = ", ".join(f"{b['batch_no']} x{n}" for b, n in allocations)
            try:
                done.append(db.dispense(req, [(b["id"], n) for b, n in allocations], calc, batch_info, staff))
            except ValueError as err:
                messagebox.showerror("Could not dispense", str(err), parent=self)
                return

        if not done:
            messagebox.showinfo("Out of stock", "Not enough stock. The request(s) were moved to Pending.",
                                parent=self)
            self.destroy()
            self.on_done()
            return

        transactions = [db.get_transaction(t) for t in done]
        if len(transactions) == 1:
            path = receipt.save_receipt(transactions[0])
        else:                                            # one receipt for the whole order
            path = prescription.save_release({"code": f"ORDER-{self.requests[0]['id']}"}, transactions)
        self.destroy()
        self.on_done()
        extra = f"\n\n{moved} medicine(s) moved to Pending (no stock)." if moved else ""
        if messagebox.askyesno("Receipt ready", f"Receipt saved:\n{path}{extra}\n\nPrint it now?"):
            receipt.print_receipt(path)