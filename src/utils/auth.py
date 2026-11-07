"""Password hashing, login session, and role permissions."""
import hashlib
import hmac
import os

ROLES = ("BHW", "Check-up", "Admin")

# Sidebar screens each role is allowed to open (the order here is the sidebar order).
PERMISSIONS = {
    "BHW": ["Requests", "Residents", "Pharmacy", "Inventory", "Medicines"],
    "Check-up": ["Check-up", "Inventory", "Medicines", "Deliveries", "Reports"],
    "Admin": ["Requests", "Residents", "Check-up", "Pharmacy", "Inventory", "Medicines",
              "Deliveries", "Reports", "Users"],
}

_current_user = None


# ---------- passwords ----------
def hash_password(password, salt=None):
    """Return 'salt$hash' using PBKDF2 (never store plain passwords)."""
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(password, stored):
    try:
        salt, _ = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def authenticate(username, password):
    """Return the user dict if the login is correct, otherwise None."""
    from src.utils import database as db   # imported here to avoid a circular import
    user = db.get_user_by_username(username.strip())
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


# ---------- session ----------
def set_user(user):
    global _current_user
    _current_user = user


def current_user():
    return _current_user


def logout():
    set_user(None)


# ---------- permissions ----------
def screens_for_role(role):
    return PERMISSIONS.get(role, [])


def can_access(screen):
    return bool(_current_user) and screen in screens_for_role(_current_user["role"])


def can_manage_inventory():
    """Check-up and Admin can add, edit and delete in Inventory. BHW can only look."""
    return bool(_current_user) and _current_user["role"] in ("Check-up", "Admin")


def is_admin():
    return bool(_current_user) and _current_user["role"] == "Admin"