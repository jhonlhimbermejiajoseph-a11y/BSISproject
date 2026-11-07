"""SQLite database layer: schema, sample data, and every query.

All screens go through this file, so no SQL lives in the UI code.
The database file (barangay_medicine.db) is created automatically on first run.
"""
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta

from src.utils.auth import hash_password

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "barangay_medicine.db")

EXPIRY_WARNING_DAYS = 90

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS {name} (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('BHW', 'Check-up', 'Admin'))
);
"""

SCHEMA = USERS_TABLE.format(name="users") + """
CREATE TABLE IF NOT EXISTS residents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    scanned_id TEXT NOT NULL UNIQUE,
    full_name  TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT 'Regular',
    address    TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS medicines (
    sku             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    unit_price      REAL NOT NULL DEFAULT 0,
    low_stock_level INTEGER NOT NULL DEFAULT 20
);
CREATE TABLE IF NOT EXISTS batches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sku           TEXT NOT NULL REFERENCES medicines(sku) ON DELETE CASCADE,
    batch_no      TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    delivered_qty INTEGER NOT NULL,
    expiry_date   TEXT NOT NULL,
    received_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL REFERENCES residents(id),
    sku         TEXT NOT NULL REFERENCES medicines(sku),
    quantity    INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Queued',   -- Queued, Pending, Completed, Cancelled
    created_at  TEXT NOT NULL,
    staff_id    INTEGER
);
CREATE TABLE IF NOT EXISTS transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id     INTEGER NOT NULL REFERENCES requests(id),
    resident_id    INTEGER NOT NULL,
    sku            TEXT NOT NULL,
    quantity       INTEGER NOT NULL,
    batch_info     TEXT NOT NULL,
    gross_amount   REAL NOT NULL,
    subsidy_rate   REAL NOT NULL,
    subsidy_amount REAL NOT NULL,
    total_amount   REAL NOT NULL,
    staff_id       INTEGER,
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prescriptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,                 -- what the QR code holds, e.g. RX-00007
    resident_id  INTEGER NOT NULL REFERENCES residents(id),
    status       TEXT NOT NULL DEFAULT 'Open',         -- Open, Dispensed, Cancelled
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    staff_id     INTEGER,
    dispensed_at TEXT,
    dispensed_by INTEGER
);
CREATE TABLE IF NOT EXISTS prescription_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id INTEGER NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    sku             TEXT NOT NULL REFERENCES medicines(sku),
    quantity        INTEGER NOT NULL
);
"""


# ---------- connection helpers ----------
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=()):
    """Run a SELECT and return a list of dicts."""
    conn = connect()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE and return the new row id."""
    conn = connect()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ---------- small helpers ----------
def today():
    return date.today().isoformat()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def expiry_status(expiry_date):
    """'Expired', 'Expiring soon' (within 90 days) or 'OK'."""
    exp = date.fromisoformat(expiry_date)
    t = date.today()
    if exp < t:
        return "Expired"
    if exp <= t + timedelta(days=EXPIRY_WARNING_DAYS):
        return "Expiring soon"
    return "OK"


# ---------- setup ----------
def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    _migrate_roles()
    _seed()


def _migrate_roles():
    """Older databases use the role 'Inventory Officer'. Rebuild the users table so it
    allows 'Check-up' instead, and turn the old demo login officer into checkup."""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone()
        if not row or "Check-up" in row["sql"]:
            return
        conn.executescript(
            "DROP TABLE IF EXISTS users_new;"
            + USERS_TABLE.format(name="users_new")
            + "INSERT INTO users_new (id, username, full_name, password_hash, role) "
              "SELECT id, username, full_name, password_hash, "
              "CASE role WHEN 'Inventory Officer' THEN 'Check-up' ELSE role END FROM users;"
              "DROP TABLE users;"
              "ALTER TABLE users_new RENAME TO users;"
        )
        old = conn.execute(
            "SELECT id FROM users WHERE username = 'officer' AND role = 'Check-up'").fetchone()
        taken = conn.execute("SELECT 1 FROM users WHERE username = 'checkup'").fetchone()
        if old and not taken:
            conn.execute(
                "UPDATE users SET username = 'checkup', full_name = 'Check-up Doctor', "
                "password_hash = ? WHERE id = ?", (hash_password("checkup123"), old["id"]))
        conn.commit()
    finally:
        conn.close()


def _seed():
    """Sample data for the demo. Runs only on the very first start."""
    if query("SELECT 1 FROM users LIMIT 1"):
        return
    for username, name, password, role in [
        ("admin", "System Administrator", "admin123", "Admin"),
        ("bhw", "Barangay Health Worker", "bhw123", "BHW"),
        ("checkup", "Check-up Doctor", "checkup123", "Check-up"),
    ]:
        add_user(username, name, password, role)

    for sku, name, price, low in [
        ("PARA500", "Paracetamol 500mg", 2.00, 50),
        ("AMOX500", "Amoxicillin 500mg", 8.50, 30),
        ("LOSA50", "Losartan 50mg", 6.00, 30),
        ("METF500", "Metformin 500mg", 4.50, 30),
        ("CETI10", "Cetirizine 10mg", 3.00, 20),
        ("ORS", "Oral Rehydration Salts", 12.00, 15),   # no stock: good for the Pending demo
    ]:
        add_medicine(sku, name, price, low)

    t = date.today()
    for sku, batch_no, qty, days in [
        ("PARA500", "B2601A", 100, 40),
        ("PARA500", "B2602A", 200, 300),
        ("AMOX500", "B2603A", 25, 120),
        ("LOSA50", "B2604A", 60, 200),
        ("METF500", "B2605A", 15, 60),
        ("CETI10", "B2501X", 10, -15),     # already expired
        ("CETI10", "B2607A", 80, 400),
    ]:
        add_batch(sku, batch_no, qty, (t + timedelta(days=days)).isoformat())

    for name, category, address in [
        ("Juan Dela Cruz", "Senior Citizen", "Purok 1"),
        ("Maria Santos", "PWD", "Purok 2"),
        ("Pedro Reyes", "Low-income", "Purok 3"),
        ("Ana Lopez", "Regular", "Purok 4"),
    ]:
        add_resident(name, category, address)


# ---------- users ----------
def get_user_by_username(username):
    rows = query("SELECT * FROM users WHERE username = ?", (username,))
    return rows[0] if rows else None


def get_users():
    return query("SELECT id, username, full_name, role FROM users ORDER BY id")


def add_user(username, full_name, password, role):
    return execute(
        "INSERT INTO users (username, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
        (username, full_name, hash_password(password), role),
    )


def delete_user(user_id):
    execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------- residents ----------
def get_residents():
    return query("SELECT * FROM residents ORDER BY id")


def add_resident(full_name, category, address=""):
    """Register a resident and return the generated ID, e.g. 'BRGY-0005'."""
    n = query("SELECT COALESCE(MAX(id), 0) + 1 AS n FROM residents")[0]["n"]
    code = f"BRGY-{n:04d}"
    execute(
        "INSERT INTO residents (scanned_id, full_name, category, address) VALUES (?, ?, ?, ?)",
        (code, full_name, category, address),
    )
    return code


def delete_resident(resident_id):
    execute("DELETE FROM residents WHERE id = ?", (resident_id,))


# ---------- medicines ----------
def get_medicines():
    return query("SELECT * FROM medicines ORDER BY name")


def add_medicine(sku, name, unit_price, low_stock_level=20):
    execute(
        "INSERT INTO medicines (sku, name, unit_price, low_stock_level) VALUES (?, ?, ?, ?)",
        (sku, name, unit_price, low_stock_level),
    )


def get_medicine(sku):
    rows = query("SELECT * FROM medicines WHERE sku = ?", (sku,))
    return rows[0] if rows else None


def update_medicine(sku, name, unit_price, low_stock_level):
    execute("UPDATE medicines SET name = ?, unit_price = ?, low_stock_level = ? WHERE sku = ?",
            (name, unit_price, low_stock_level, sku))


def delete_medicine(sku):
    execute("DELETE FROM medicines WHERE sku = ?", (sku,))


def stock_by_sku():
    """{sku: units that can still be dispensed (not expired)}"""
    rows = query(
        "SELECT sku, SUM(quantity) AS total FROM batches "
        "WHERE quantity > 0 AND expiry_date >= ? GROUP BY sku",
        (today(),),
    )
    return {r["sku"]: r["total"] for r in rows}


def available_stock(sku):
    return stock_by_sku().get(sku, 0)


# ---------- batches ----------
def get_batches(sku=None, in_stock_only=False):
    sql = (
        "SELECT b.*, m.name AS medicine_name, m.low_stock_level "
        "FROM batches b JOIN medicines m ON m.sku = b.sku"
    )
    where, params = [], []
    if sku:
        where.append("b.sku = ?")
        params.append(sku)
    if in_stock_only:
        where.append("b.quantity > 0")
    if where:
        sql += " WHERE " + " AND ".join(where)
    return query(sql + " ORDER BY b.id", params)


def add_batch(sku, batch_no, quantity, expiry_date):
    return execute(
        "INSERT INTO batches (sku, batch_no, quantity, delivered_qty, expiry_date, received_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (sku, batch_no, quantity, quantity, expiry_date, now()),
    )


def get_batch(batch_id):
    rows = query("SELECT * FROM batches WHERE id = ?", (batch_id,))
    return rows[0] if rows else None


def update_batch(batch_id, batch_no, quantity, expiry_date):
    execute("UPDATE batches SET batch_no = ?, quantity = ?, expiry_date = ?, "
            "delivered_qty = MAX(delivered_qty, ?) WHERE id = ?",
            (batch_no, quantity, expiry_date, quantity, batch_id))


def delete_batch(batch_id):
    execute("DELETE FROM batches WHERE id = ?", (batch_id,))


# ---------- requests ----------
_REQUEST_SQL = """
    SELECT r.id, r.resident_id, r.sku, r.quantity, r.status, r.created_at,
           res.scanned_id, res.full_name AS resident_name, res.category,
           m.name AS medicine_name, m.unit_price
    FROM requests r
    JOIN residents res ON res.id = r.resident_id
    JOIN medicines m ON m.sku = r.sku
"""


def add_request(resident_id, sku, quantity, status, staff_id):
    return execute(
        "INSERT INTO requests (resident_id, sku, quantity, status, created_at, staff_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (resident_id, sku, quantity, status, now(), staff_id),
    )


def get_requests(status=None):
    """Oldest first, so the result is already in arrival (FIFO) order."""
    if status:
        return query(_REQUEST_SQL + " WHERE r.status = ? ORDER BY r.id", (status,))
    return query(_REQUEST_SQL + " ORDER BY r.id")


def get_request(request_id):
    rows = query(_REQUEST_SQL + " WHERE r.id = ?", (request_id,))
    return rows[0] if rows else None


def set_request_status(request_id, status):
    execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))


# ---------- dispensing ----------
def dispense(request, allocations, calc, batch_info, staff_id):
    """Take stock from the chosen batches, save the transaction, complete the request.

    allocations: list of (batch_id, quantity). Everything succeeds or nothing does.
    Returns the new transaction id.
    """
    conn = connect()
    try:
        for batch_id, qty in allocations:
            cur = conn.execute(
                "UPDATE batches SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
                (qty, batch_id, qty),
            )
            if cur.rowcount == 0:
                raise ValueError("Stock changed while processing. Please try again.")
        cur = conn.execute(
            "INSERT INTO transactions (request_id, resident_id, sku, quantity, batch_info, "
            "gross_amount, subsidy_rate, subsidy_amount, total_amount, staff_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (request["id"], request["resident_id"], request["sku"], request["quantity"],
             batch_info, calc["gross"], calc["rate"], calc["subsidy"], calc["total"],
             staff_id, now()),
        )
        transaction_id = cur.lastrowid
        conn.execute("UPDATE requests SET status = 'Completed' WHERE id = ?", (request["id"],))
        conn.commit()
        return transaction_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- transactions ----------
_TRANSACTION_SQL = """
    SELECT t.*, res.scanned_id, res.full_name AS resident_name, res.category,
           m.name AS medicine_name, u.full_name AS staff_name
    FROM transactions t
    JOIN residents res ON res.id = t.resident_id
    JOIN medicines m ON m.sku = t.sku
    LEFT JOIN users u ON u.id = t.staff_id
"""


def get_transaction(transaction_id):
    rows = query(_TRANSACTION_SQL + " WHERE t.id = ?", (transaction_id,))
    return rows[0] if rows else None


def get_transactions():
    return query(_TRANSACTION_SQL + " ORDER BY t.id")


# ---------- prescriptions (Check-up writes them, Pharmacy dispenses them) ----------
_RX_SQL = """
    SELECT p.*, res.scanned_id, res.full_name AS resident_name, res.category, res.address,
           u.full_name AS staff_name
    FROM prescriptions p
    JOIN residents res ON res.id = p.resident_id
    LEFT JOIN users u ON u.id = p.staff_id
"""


def add_prescription(resident_id, items, staff_id, notes=""):
    """items: list of (sku, quantity). Saves everything together and returns the code
    (e.g. 'RX-00007'), which is what the QR code on the slip holds."""
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO prescriptions (code, resident_id, status, notes, created_at, staff_id) "
            "VALUES (?, ?, 'Open', ?, ?, ?)",
            (f"TMP-{uuid.uuid4().hex}", resident_id, notes, now(), staff_id))
        rx_id = cur.lastrowid
        code = f"RX-{rx_id:05d}"
        conn.execute("UPDATE prescriptions SET code = ? WHERE id = ?", (code, rx_id))
        conn.executemany(
            "INSERT INTO prescription_items (prescription_id, sku, quantity) VALUES (?, ?, ?)",
            [(rx_id, sku, qty) for sku, qty in items])
        conn.commit()
        return code
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_prescription_items(rx_id):
    return query(
        "SELECT i.id, i.sku, i.quantity, m.name AS medicine_name, m.unit_price "
        "FROM prescription_items i JOIN medicines m ON m.sku = i.sku "
        "WHERE i.prescription_id = ? ORDER BY i.id", (rx_id,))


def get_prescription(code):
    """One prescription (with its 'items' list) by code, or None. Not case sensitive."""
    rows = query(_RX_SQL + " WHERE UPPER(p.code) = UPPER(?)", ((code or "").strip(),))
    if not rows:
        return None
    rx = rows[0]
    rx["items"] = get_prescription_items(rx["id"])
    return rx


def get_prescriptions(limit=30):
    """Newest first, for the 'Recent prescriptions' list."""
    return query(
        "SELECT p.id, p.code, p.status, p.created_at, res.full_name AS resident_name, "
        "(SELECT COUNT(*) FROM prescription_items i WHERE i.prescription_id = p.id) AS item_count "
        "FROM prescriptions p JOIN residents res ON res.id = p.resident_id "
        "ORDER BY p.id DESC LIMIT ?", (limit,))


def cancel_prescription(rx_id):
    """Only an Open prescription can be cancelled."""
    execute("UPDATE prescriptions SET status = 'Cancelled' WHERE id = ? AND status = 'Open'",
            (rx_id,))


def dispense_prescription(rx, lines, staff_id):
    """Dispense a whole prescription in one go. Everything succeeds or nothing does.

    lines: one dict per medicine with keys sku, quantity, allocations [(batch_id, qty)],
    calc (from subsidy.calculate) and batch_info. Returns the list of transaction ids.
    The prescription is marked Dispensed first, so the same QR can never be used twice.
    """
    conn = connect()
    try:
        cur = conn.execute(
            "UPDATE prescriptions SET status = 'Dispensed', dispensed_at = ?, dispensed_by = ? "
            "WHERE id = ? AND status = 'Open'", (now(), staff_id, rx["id"]))
        if cur.rowcount == 0:
            raise ValueError("This prescription was already used or cancelled.")
        transaction_ids = []
        for line in lines:
            for batch_id, qty in line["allocations"]:
                cur = conn.execute(
                    "UPDATE batches SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
                    (qty, batch_id, qty))
                if cur.rowcount == 0:
                    raise ValueError("Stock changed while processing. Please try again.")
            cur = conn.execute(
                "INSERT INTO requests (resident_id, sku, quantity, status, created_at, staff_id) "
                "VALUES (?, ?, ?, 'Completed', ?, ?)",
                (rx["resident_id"], line["sku"], line["quantity"], now(), staff_id))
            request_id = cur.lastrowid
            calc = line["calc"]
            cur = conn.execute(
                "INSERT INTO transactions (request_id, resident_id, sku, quantity, batch_info, "
                "gross_amount, subsidy_rate, subsidy_amount, total_amount, staff_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (request_id, rx["resident_id"], line["sku"], line["quantity"], line["batch_info"],
                 calc["gross"], calc["rate"], calc["subsidy"], calc["total"], staff_id, now()))
            transaction_ids.append(cur.lastrowid)
        conn.commit()
        return transaction_ids
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()