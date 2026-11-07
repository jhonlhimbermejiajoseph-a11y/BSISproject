# Barangay Medicine Request & Inventory System

*"Healthy Barangay, Healthy Community"*

A desktop application that helps a barangay pharmacy manage medicine requests, stock, deliveries and resident records digitally, built with Python as a BSIS **Data Structures and Algorithms** semestral project (Second Year, A.Y. 2025–2026).

## About the Project

Many barangay pharmacies still record requests on paper. This causes slow service, unfair queues, medicines that expire unnoticed, and no record when a medicine is out of stock.

This system replaces the paper process:

- Residents are identified by **scanning their ID card (QR code)**.
- Requests are served in **first come, first served** order.
- Stock is used by **FEFO** (First Expired, First Out), so the earliest-expiry batch is used first and less medicine is wasted.
- A request for a medicine that has no stock is kept in a **pending / backorder list** and can be re-checked when new stock arrives.
- A doctor can record a **check-up** and print a prescription slip with a **QR code**. The pharmacy scans it once to see the medicines, the discount and the total.

### Prototype Description

The **Barangay Medicine Request & Inventory System** is a desktop application prototype designed to demonstrate how technology can improve medicine distribution, inventory management, and healthcare services at the barangay level.

This prototype provides a digital solution for common problems encountered in traditional paper-based barangay pharmacies. It demonstrates essential pharmacy operations, including resident identification through QR code scanning, medicine requests, queue management, inventory monitoring, batch tracking using the FEFO method, medicine deliveries, doctor check-ups, prescription generation, and medicine dispensing.

The system is developed using Python and incorporates custom Data Structures and Algorithms to demonstrate their practical applications in a real-world scenario.

**Project Purpose:** To develop and demonstrate a functional prototype that improves the organization, accessibility, and efficiency of barangay pharmacy operations.

**Development Status:** Academic prototype – currently under development and intended for educational, testing, and demonstration purposes. It is not yet intended for actual medical or production use.

## Features

| Feature             | Description                                                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Medicine requests   | Scan the resident ID, add a request, and serve the queue in arrival order                                                 |
| Pending / backorder | Requests with no stock are saved and can be re-checked later                                                              |
| Inventory           | Medicines and batches sorted by earliest expiry, with low-stock, expiring and expired alerts                              |
| Deliveries          | Record new stock by batch                                                                                                 |
| Residents           | Resident records and printable ID cards with a QR code                                                                    |
| Check-up            | The doctor picks a resident, selects medicines, and prints a prescription slip                                            |
| Pharmacy (dispense) | Scan the slip code (for example `RX-00001`) to see the resident, medicines, discount by category and total, then dispense |
| Reports             | Inventory and other reports sorted by date, quantity or status                                                            |
| Users               | Account and role management                                                                                               |
| Receipts            | Printable receipt for each transaction                                                                                    |
| Sidebar menu        | A ☰ button hides or shows the side menu                                                                                   |

## User Roles

| Role                         | Demo login               | Main screens                             |
| ---------------------------- | ------------------------ | ---------------------------------------- |
| Admin                        | `admin` / `admin123`     | All screens, including Users             |
| Barangay Health Worker (BHW) | `bhw` / `bhw123`         | Requests, Residents, Inventory, Pharmacy |
| Inventory Officer            | `officer` / `officer123` | Inventory, Deliveries, Reports           |
| Check-up doctor              | `checkup` / `checkup123` | Check-up                                 |

> These are demo accounts for testing only. Change them before real use.

## Data Structures and Algorithms

| Data structure / algorithm | File                    | Where it is used                                          | Complexity                     |
| -------------------------- | ----------------------- | --------------------------------------------------------- | ------------------------------ |
| Queue                      | `src/dsa/queue.py`      | Service queue, first come first served                    | enqueue / dequeue: O(1)        |
| Min heap                   | `src/dsa/min_heap.py`   | FEFO: the batch with the earliest expiry is used first    | insert / extract-min: O(log n) |
| Hash table                 | `src/dsa/hash_table.py` | Fast resident lookup by ID after a scan                   | lookup: O(1) average           |
| Merge sort                 | `src/dsa/merge_sort.py` | Sorting inventory and reports by date, quantity or status | O(n log n)                     |

## Technologies Used

- Python 3
- Tkinter desktop interface
- SQLite database (`barangay_medicine.db`)
- QR codes for resident IDs and prescription slips
- [uv](https://docs.astral.sh/uv/) for dependency management

## Project Structure

```text
BSISproject/
├── assets/                  # Logo, images and other resources
├── src/
│   ├── dsa/                 # Data structures and algorithms (custom code)
│   │   ├── hash_table.py
│   │   ├── merge_sort.py
│   │   ├── min_heap.py
│   │   └── queue.py
│   ├── ui/                  # Screens
│   │   ├── login_view.py
│   │   ├── requests_view.py
│   │   ├── residents_view.py
│   │   ├── inventory_view.py
│   │   ├── deliveries_view.py
│   │   ├── reports_view.py
│   │   ├── users_view.py
│   │   ├── checkup_view.py
│   │   ├── dispense_view.py
│   │   ├── catalog_view.py
│   │   ├── scan_dialog.py
│   │   └── theme.py
│   ├── utils/               # Helpers
│   │   ├── auth.py          # Login and roles
│   │   ├── database.py      # SQLite access
│   │   ├── id_card.py       # Resident ID card
│   │   ├── prescription.py  # Check-up slip with QR code
│   │   ├── receipt.py       # Receipts
│   │   ├── scanner.py       # QR scanning
│   │   └── subsidy.py       # Discount by resident category
│   └── app.py               # Main window and navigation
├── barangay_medicine.db     # SQLite database
├── main.py                  # Starts the application
├── pyproject.toml           # Project configuration
├── uv.lock                  # Dependency lock file
└── .gitignore               # Git ignore configuration
```

## Installation and Usage

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. Clone or download this repository (extract it if it is a ZIP).
3. Open the project folder in your code editor.
4. Install the dependencies:

```bash
uv sync
```

5. Run the application:

```bash
uv run main.py
```

6. Sign in with one of the demo accounts above.

### Quick test of the check-up and pharmacy flow

1. Sign in as `checkup` / `checkup123`, open **Check-up**, pick a resident, select medicines, and save and print the slip.
2. Sign in as `bhw` / `bhw123` (or `admin`), open **Pharmacy**, type the code on the slip (for example `RX-00001`) and press Enter.
3. Check the medicines, discount and total, then press **Dispense**.

## Developers

BSIS Second Year students

- Jhon lhimber mejia
- jeffrey idanan
- fitz manurac

## Project Status

Under development. This project is made for academic purposes.

Still to do:

- Unit tests for the heap, queue, hash table and merge sort
- Sample dataset with at least 500 records for testing and demonstration
- Time and space complexity analysis in the technical documentation
- User manual and demo video
