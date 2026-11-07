import tkinter as tk
from tkinter import messagebox

from src.dsa.hash_table import HashTable
from src.dsa.min_heap import MinHeap
from src.dsa.queue import RequestQueue
from src.ui import theme as T
from src.utils import auth, database as db, receipt, subsidy
from src.utils.scanner import bind_scanner


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
    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        self.residents = HashTable()     # scanned ID -> resident
        self.medicines = HashTable()     # SKU -> medicine
        self.queue = RequestQueue()      # FIFO queue of requests waiting to be served
        self.resident = None
        self.med_labels = {}
        self._build()
        self.refresh()

    # ---------- layout ----------
    def _build(self):
        T.header(self, "Medicine Requests",
                 "Scan the resident ID, add the request, then serve the queue in arrival order.").pack(
            fill="x", padx=28, pady=(22, 12))
        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 22))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=T.BG, width=340)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        left.pack_propagate(False)
        right = tk.Frame(body, bg=T.BG)
        right.grid(row=0, column=1, sticky="nsew")

        # step 1: scan
        c1 = T.card(left)
        c1.pack(fill="x")
        T.label(c1, "1. Scan resident ID", 11, True).pack(anchor="w", padx=16, pady=(14, 2))
        T.label(c1, "Scan the ID card, or type the ID and press Enter.", 9, color=T.MUTED).pack(anchor="w", padx=16)
        row = tk.Frame(c1, bg=T.CARD)
        row.pack(fill="x", padx=16, pady=10)
        self.scan_entry = T.entry(row, 20)
        self.scan_entry.pack(side="left", fill="x", expand=True, ipady=6)
        handle = bind_scanner(self.scan_entry, self.on_scan)
        T.button(row, "Find", handle).pack(side="left", padx=(8, 0))
        self.resident_label = T.label(c1, "No resident selected.", 10, color=T.MUTED,
                                      justify="left", wraplength=290)
        self.resident_label.pack(anchor="w", padx=16, pady=(0, 14))

        # step 2: request
        c2 = T.card(left)
        c2.pack(fill="x", pady=(14, 0))
        T.label(c2, "2. Medicine request", 11, True).pack(anchor="w", padx=16, pady=(14, 8))
        box, self.med_combo = T.labeled_combo(c2, "Medicine", 30)
        box.pack(fill="x", padx=16)
        self.med_combo.bind("<<ComboboxSelected>>", lambda e: self.show_stock())
        self.stock_label = T.label(c2, "", 9, color=T.MUTED, wraplength=290, justify="left")
        self.stock_label.pack(anchor="w", padx=16, pady=(4, 0))
        box, self.qty_entry = T.labeled_entry(c2, "Quantity", 10)
        box.pack(fill="x", padx=16, pady=(10, 0))
        self.qty_entry.insert(0, "1")
        T.button(c2, "Add request", self.add_request).pack(fill="x", padx=16, pady=(14, 8))
        self.msg_label = T.label(c2, "", 9, color=T.MUTED, wraplength=290, justify="left")
        self.msg_label.pack(anchor="w", padx=16, pady=(0, 14))

        # right: queue
        top = tk.Frame(right, bg=T.BG)
        top.pack(fill="x")
        T.label(top, "Service queue (first come, first served)", 11, True).pack(side="left")
        T.button(top, "Serve next", self.serve_next).pack(side="right")
        T.button(top, "Cancel selected", lambda: self.cancel_selected(True), "danger").pack(side="right", padx=8)
        frame, self.queue_tree = T.table(right, [
            ("pos", "#", 36), ("id", "Req", 50), ("resident", "Resident", 150),
            ("medicine", "Medicine", 160), ("qty", "Qty", 50), ("time", "Requested", 120),
        ], height=7)
        frame.pack(fill="both", expand=True, pady=(8, 14))

        # right: pending
        top = tk.Frame(right, bg=T.BG)
        top.pack(fill="x")
        T.label(top, "Pending / backorder (no stock at the time)", 11, True).pack(side="left")
        T.button(top, "Re-check stock", self.recheck_pending, "ghost").pack(side="right")
        T.button(top, "Cancel selected", lambda: self.cancel_selected(False), "danger").pack(side="right", padx=8)
        frame, self.pending_tree = T.table(right, [
            ("id", "Req", 50), ("resident", "Resident", 160), ("medicine", "Medicine", 170),
            ("qty", "Qty", 50), ("time", "Requested", 130),
        ], height=5)
        frame.pack(fill="both", expand=True, pady=(8, 0))

    # ---------- data ----------
    def refresh(self):
        meds = db.get_medicines()
        self.residents.clear()
        self.residents.load(db.get_residents(), "scanned_id")
        self.medicines.clear()
        self.medicines.load(meds, "sku")
        self.med_labels = {f"{m['sku']} - {m['name']}": m["sku"] for m in meds}
        self.med_combo["values"] = list(self.med_labels)
        self.queue.clear()
        self.queue.load(db.get_requests("Queued"))        # oldest first
        self.render()

    def render(self):
        T.fill(self.queue_tree, [
            (r["id"], (pos, r["id"], r["resident_name"], r["medicine_name"], r["quantity"], r["created_at"]), None)
            for pos, r in enumerate(self.queue, start=1)
        ])
        T.fill(self.pending_tree, [
            (r["id"], (r["id"], r["resident_name"], r["medicine_name"], r["quantity"], r["created_at"]), "warn")
            for r in db.get_requests("Pending")
        ])

    def _say(self, text, color=T.MUTED):
        self.msg_label.config(text=text, fg=color)

    # ---------- step 1 ----------
    def on_scan(self, code):
        resident = self.residents.get(code)               # Hash Table lookup, O(1)
        if resident is None:
            self.resident = None
            self.resident_label.config(
                text=f"Resident not found: {code}\nRegister them in the Residents screen.", fg=T.RED)
            return
        self.resident = resident
        rate = subsidy.subsidy_rate(resident["category"]) * 100
        self.resident_label.config(
            text=(f"{resident['full_name']}\n{resident['scanned_id']}  •  {resident['category']} "
                  f"({rate:.0f}% subsidy)\n{resident['address'] or 'No address'}"),
            fg=T.GREEN)

    # ---------- step 2 ----------
    def show_stock(self):
        sku = self.med_labels.get(self.med_combo.get())
        if not sku:
            return
        med = self.medicines.get(sku)
        stock = db.available_stock(sku)
        if stock > 0:
            self.stock_label.config(text=f"In stock: {stock}  •  PHP {med['unit_price']:,.2f} each", fg=T.GREEN)
        else:
            self.stock_label.config(text="Out of stock. The request will be recorded as Pending.", fg=T.YELLOW)

    def add_request(self):
        if not self.resident:
            self._say("Scan a resident ID first.", T.RED)
            return
        sku = self.med_labels.get(self.med_combo.get())
        if not sku:
            self._say("Choose a medicine.", T.RED)
            return
        try:
            qty = int(self.qty_entry.get().strip())
        except ValueError:
            qty = 0
        if qty <= 0:
            self._say("Quantity must be a whole number above 0.", T.RED)
            return

        staff_id = auth.current_user()["id"]
        stock = db.available_stock(sku)
        if stock >= qty:
            rid = db.add_request(self.resident["id"], sku, qty, "Queued", staff_id)
            self.queue.enqueue(db.get_request(rid))       # joins the back of the line
            self._say(f"Request #{rid} added. Place in line: {len(self.queue)}.", T.GREEN)
        else:
            rid = db.add_request(self.resident["id"], sku, qty, "Pending", staff_id)
            self._say(f"Only {stock} in stock. Request #{rid} recorded as Pending (backorder).", T.YELLOW)
        self.render()
        self.show_stock()
        self.scan_entry.focus_set()

    # ---------- queue actions ----------
    def serve_next(self):
        request = self.queue.peek()
        if request is None:
            messagebox.showinfo("Queue is empty", "No requests are waiting.")
            return
        ProcessDialog(self, request, self.after_served)

    def after_served(self):
        self.queue.dequeue()                              # the head of the line is done
        self.render()
        self.show_stock()
        self.scan_entry.focus_set()

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
    """Verify, compute subsidy, pick FEFO batches, dispense, print receipt."""

    def __init__(self, parent, request, on_done):
        super().__init__(parent)
        self.request = request
        self.on_done = on_done
        self.title(f"Process request #{request['id']}")
        self.configure(bg=T.BG)
        self.resizable(False, False)

        calc = subsidy.calculate(request["unit_price"], request["quantity"], request["category"])
        allocations, shortfall = allocate_fefo(request["sku"], request["quantity"])

        body = T.card(self)
        body.pack(padx=20, pady=20)
        pad = {"anchor": "w", "padx": 22}
        T.label(body, f"Request #{request['id']}", 14, True).pack(pady=(18, 2), **pad)
        T.label(body, f"{request['resident_name']}  ({request['scanned_id']})", 10).pack(**pad)
        T.label(body, f"{request['category']}  •  {calc['rate'] * 100:.0f}% subsidy", 9,
                color=T.MUTED).pack(**pad)
        T.label(body, f"{request['medicine_name']}  x {request['quantity']}", 11, True).pack(pady=(12, 0), **pad)

        if shortfall > 0:
            T.label(body, "Stock is no longer enough. Confirming will move this request to Pending.",
                    9, color=T.RED, wraplength=380, justify="left").pack(pady=(4, 0), **pad)
        else:
            text = ", ".join(f"{b['batch_no']} x{n} (exp {b['expiry_date']})" for b, n in allocations)
            T.label(body, f"FEFO batches: {text}", 9, color=T.MUTED, wraplength=380,
                    justify="left").pack(pady=(4, 0), **pad)

        T.label(body, f"Gross: PHP {calc['gross']:,.2f}", 10).pack(pady=(12, 0), **pad)
        T.label(body, f"Subsidy: - PHP {calc['subsidy']:,.2f}", 10, color=T.GREEN).pack(**pad)
        T.label(body, f"Resident pays: PHP {calc['total']:,.2f}", 12, True).pack(pady=(2, 0), **pad)

        self.rx_var = tk.BooleanVar()
        self.id_var = tk.BooleanVar()
        T.checkbox(body, "Prescription verified", self.rx_var).pack(pady=(14, 0), **pad)
        T.checkbox(body, "Eligibility / ID verified", self.id_var).pack(**pad)

        row = tk.Frame(body, bg=T.CARD)
        row.pack(fill="x", padx=22, pady=18)
        T.button(row, "Dispense & receipt", self.confirm).pack(side="left")
        T.button(row, "Close", self.destroy, "ghost").pack(side="left", padx=8)

        self.transient(parent.winfo_toplevel())
        self.wait_visibility()
        self.grab_set()

    def confirm(self):
        if not (self.rx_var.get() and self.id_var.get()):
            messagebox.showwarning("Verification needed",
                                   "Tick both checks before dispensing.", parent=self)
            return
        req = self.request
        allocations, shortfall = allocate_fefo(req["sku"], req["quantity"])
        if shortfall > 0:
            db.set_request_status(req["id"], "Pending")
            messagebox.showinfo("Out of stock", "Not enough stock. The request was moved to Pending.",
                                parent=self)
            self.destroy()
            self.on_done()
            return

        calc = subsidy.calculate(req["unit_price"], req["quantity"], req["category"])
        batch_info = ", ".join(f"{b['batch_no']} x{n}" for b, n in allocations)
        try:
            tid = db.dispense(req, [(b["id"], n) for b, n in allocations], calc, batch_info,
                              auth.current_user()["id"])
        except ValueError as err:
            messagebox.showerror("Could not dispense", str(err), parent=self)
            return

        path = receipt.save_receipt(db.get_transaction(tid))
        self.destroy()
        self.on_done()
        if messagebox.askyesno("Receipt ready", f"Receipt saved:\n{path}\n\nPrint it now?"):
            receipt.print_receipt(path)