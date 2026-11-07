"""Merge sort, written from scratch for the project.

Used for sorting inventory reports, request records, and subsidy summaries
by date, quantity, or status.

Time: O(n log n) in all cases. Stable: equal items keep their original order,
which is handy when sorting by one column after another.
"""


def merge_sort(items, key=None, reverse=False):
    """Return a NEW sorted list. The original list is not changed.

    key     -- function that returns the value to sort by (like sorted()).
               Example: key=lambda row: row["expiry_date"]
    reverse -- True for descending order.
    """
    if key is None:
        key = lambda x: x

    result = _sort(list(items), key)
    if reverse:
        result = _reverse_stable(result, key)
    return result


def _sort(items, key):
    if len(items) <= 1:
        return items
    mid = len(items) // 2
    left = _sort(items[:mid], key)
    right = _sort(items[mid:], key)
    return _merge(left, right, key)


def _merge(left, right, key):
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        # <= keeps the sort stable (left item wins on ties)
        if key(left[i]) <= key(right[j]):
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def _reverse_stable(sorted_items, key):
    """Descending order that still keeps ties in their original order."""
    result = []
    i = len(sorted_items)
    while i > 0:
        # find the start of the group of equal keys that ends at i
        j = i - 1
        while j > 0 and key(sorted_items[j - 1]) == key(sorted_items[i - 1]):
            j -= 1
        result.extend(sorted_items[j:i])
        i = j
    return result


# ---------- convenience helpers for the reports screen ----------
def sort_by_field(rows, field, reverse=False):
    """Sort a list of dict rows by one column name."""
    return merge_sort(rows, key=lambda r: r[field], reverse=reverse)


if __name__ == "__main__":
    # quick self-test: run `python merge_sort.py`
    data = [
        {"med": "Paracetamol", "qty": 50, "status": "OK"},
        {"med": "Amoxicillin", "qty": 5, "status": "Low"},
        {"med": "Losartan", "qty": 20, "status": "OK"},
    ]
    print([r["med"] for r in sort_by_field(data, "qty")])                 # lowest first
    print([r["med"] for r in sort_by_field(data, "qty", reverse=True)])   # highest first