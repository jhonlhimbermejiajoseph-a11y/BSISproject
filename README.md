# Barangay Medicine Request & Inventory System

*"Healthy Barangay, Healthy Community"*

A desktop application that helps a barangay pharmacy manage medicine requests, stock, deliveries and resident records digitally, built with Python as a BSIS Data Structures and Algorithms semestral project (Second Year, A.Y. 2025–2026).

## About the Project

Many barangay pharmacies still record requests on paper. This causes slow service, unfair queues, medicines that expire unnoticed, and no record when a medicine is out of stock.

This system replaces the paper process:

- Residents are identified by scanning their ID card (QR code).
- A resident can order **several medicines at once** (cart) and gets one receipt.
- Requests are served in first come, first served order.
- Stock is used by **FEFO** (First Expired, First Out), so the earliest-expiry batch is used first and less medicine is wasted.
- A request for a medicine that has no stock is kept as *Pending*. When a delivery arrives, it moves to the service queue automatically.
- A doctor writes a prescription and prints a slip with a QR code. The BHW scans it once to see the medicines, the discount and the total. If a medicine is short, the available part is still dispensed.
- The Admin only monitors and manages: stock, deliveries, reports, residents and staff accounts.

## Prototype Description

The Barangay Medicine Request & Inventory System is a desktop application prototype designed to demonstrate how technology can improve medicine distribution, inventory management, and healthcare services at the barangay level.

It demonstrates essential pharmacy operations: resident identification through QR code scanning, medicine requests with a cart, queue management, inventory monitoring, batch tracking using FEFO, medicine deliveries, doctor check-ups, prescriptions, dispensing with receipts, and Admin reports with charts.

The system uses custom Data Structures and Algorithms to show their practical use in a real-world scenario.

**Project Purpose:** To develop and demonstrate a functional prototype that improves the organization, accessibility, and efficiency of barangay pharmacy operations.

**Development Status:** Academic prototype, intended for educational, testing, and demonstration purposes. It is not intended for actual medical or production use.

## Features

| Feature | Description |
|---------|-------------|
| Medicines (cart) | Pick several medicines, set quantities, check out for a resident or walk-in customer, and get a receipt. A new resident can be registered at checkout. |
| Requests | The BHW serves the queue in arrival order. A whole order is served at once with one receipt. |
| Pending / backorder | Requests with no stock are saved and move to the queue when a delivery arrives. |
| Prescriptions | Scan the slip code (for example RX-00001) to see the resident, medicines, discount and total, then dispense. Short stock is handled with a partial release. |
| Check-up | The doctor picks a resident, selects medicines, and prints a prescription slip with a QR code. |
| Inventory | Medicines and batches sorted by earliest expiry, with low-stock, expiring and expired alerts. Only the Admin can edit. |
| Deliveries | The Admin records new stock by batch with an expiry date. |
| Residents | Resident records, discount categories, and printable **ID cards with the resident's photo** taken from the camera. |
| Reports | Admin dashboard: sales today, discounts, low stock, expiring batches, charts, stock and sales tables, sorting and CSV export. |
| Users | Account and role management. |
| Receipts | Printable receipt for each transaction. |
| Safety | Expiry status on every batch, and a warning if the computer clock was turned back. |
| Sidebar menu | A ☰ button hides or shows the side menu. |

## User Roles

| Role | Demo login | Main screens |
|------|------------|--------------|
| Admin | admin / admin123 | Reports, Inventory, Deliveries, Residents, Users (monitor and manage only; does not serve customers) |
| Barangay Health Worker (BHW) | bhw / bhw123 | Medicines, Requests, Prescriptions, Residents, Inventory (view) |
| Check-up doctor | checkup / checkup123 | Check-up, Medicines, Inventory (view). Cannot edit inventory. |

These are demo accounts for testing only. Change them before real use.

## Data Structures and Algorithms

All are written by the team in `src/dsa/`. SQLite is used only for storage; sorting, FEFO and queueing are done by this code, not by SQL.

| Data structure / algorithm | File | Where it is used | Complexity |
|----------------------------|------|------------------|------------|
| Queue (linked list) | `src/dsa/queue.py` | Service queue, first come first served | enqueue / dequeue: O(1) |
| Min heap | `src/dsa/min_heap.py` | FEFO: the batch with the earliest expiry is used first | insert / extract-min: O(log n) |
| Hash table | `src/dsa/hash_table.py` | Fast resident lookup by ID after a scan | lookup: O(1) average |
| Merge sort | `src/dsa/merge_sort.py` | Sorting inventory, deliveries and reports by date, quantity or status | O(n log n) |
| Stack | `src/dsa/stack.py` | Undo the last inventory action | push / pop: O(1) |
| Binary search tree | `src/dsa/bst.py` | Medicine search in Check-up | search: O(log n) average |

## Technologies Used

- Python 3.12
- Tkinter desktop interface
- SQLite database (`barangay_medicine.db`)
- Pillow (images and ID cards), `qrcode` (QR codes), OpenCV (camera)
- uv for dependency management

## Project Structure

```
BSIsproject/
├── assets/                  # Logo, images and other resources
├── src/
│   ├── dsa/                 # Data structures and algorithms (custom code)
│   │   ├── bst.py
│   │   ├── hash_table.py
│   │   ├── merge_sort.py
│   │   ├── min_heap.py
│   │   ├── queue.py
│   │   └── stack.py
│   ├── ui/                  # Screens
│   │   ├── login_view.py
│   │   ├── catalog_view.py        # Medicines (cart and checkout)
│   │   ├── requests_view.py
│   │   ├── dispense_view.py       # Prescriptions
│   │   ├── checkup_view.py
│   │   ├── residents_view.py
│   │   ├── id_card_dialog.py      # Camera photo and ID card
│   │   ├── inventory_view.py
│   │   ├── deliveries_view.py
│   │   ├── reports_view.py
│   │   ├── users_view.py
│   │   ├── scan_dialog.py
│   │   └── theme.py
│   ├── utils/               # Helpers
│   │   ├── auth.py          # Login and roles
│   │   ├── clock.py         # Dates, validation, clock-rollback warning
│   │   ├── database.py      # SQLite access
│   │   ├── id_card_design.py  # Draws the ID card with photo
│   │   ├── prescription.py  # Check-up slip with QR code
│   │   ├── receipt.py       # Receipts
│   │   ├── scanner.py       # QR scanning
│   │   └── subsidy.py       # Discount by resident category
│   └── app.py               # Main window and navigation
├── tests/test_dsa.py        # Unit tests
├── barangay_medicine.db     # SQLite database (created on first run)
├── main.py                  # Starts the application
├── pyproject.toml           # Project configuration
├── uv.lock                  # Dependency lock file
└── .gitignore               # Git ignore configuration
```

## Installation and Usage

1. Install uv.
2. Clone or download this repository (extract it if it is a ZIP).
3. Open the project folder in your code editor.
4. Install the dependencies:
   ```
   uv sync
   uv add opencv-python pillow qrcode
   ```
   (The second line is only needed if they are not installed yet. Without a camera you can choose a photo from a file instead.)
5. Run the application:
   ```
   uv run main.py
   ```
6. Sign in with one of the demo accounts above.

### Run the tests

```
python -m unittest discover -s tests -v
```

### Quick test of the check-up and prescription flow

1. Sign in as `checkup` / `checkup123`, open **Check-up**, pick a resident, select medicines, and save and print the slip.
2. Sign in as `bhw` / `bhw123`, open **Prescriptions**, type the code on the slip (for example RX-00001) and press Enter.
3. Check the medicines, discount and total, then press **Dispense**.

### Quick test of the cart

1. Sign in as `bhw`, open **Medicines**, add two or three medicines to the cart and press **Checkout**.
2. Choose a resident (or register a new one), confirm, and view the receipt.
3. Open **Requests** and serve the order.

## Developers

BSIS Second Year students

- Jhon Lhimber Mejia
- Jeffrey Idanan
- Fitz Manurac

## Project Status

Under development. This project is made for academic purposes.

Done: unit tests for the data structures, sample dataset, and technical documentation with complexity analysis.

Still to do:

- User manual
- Demo video
