"""Min-Heap, written from scratch for the project.

Used for FEFO (First-Expiring, First-Out) inventory handling: the batch that
expires earliest is always at the top of the heap.

Time: push = O(log n), pop = O(log n), peek = O(1).

Priority is usually the expiry date string "YYYY-MM-DD". These strings compare
correctly in date order, so no conversion is needed.
"""


class MinHeap:
    def __init__(self):
        self._data = []        # list of (priority, counter, item)
        self._counter = 0      # tie-breaker so equal priorities stay in insert order

    # ---------- helpers ----------
    def _swap(self, i, j):
        self._data[i], self._data[j] = self._data[j], self._data[i]

    def _sift_up(self, i):
        while i > 0:
            parent = (i - 1) // 2
            if self._data[i][:2] < self._data[parent][:2]:
                self._swap(i, parent)
                i = parent
            else:
                break

    def _sift_down(self, i):
        n = len(self._data)
        while True:
            smallest = i
            left, right = 2 * i + 1, 2 * i + 2
            if left < n and self._data[left][:2] < self._data[smallest][:2]:
                smallest = left
            if right < n and self._data[right][:2] < self._data[smallest][:2]:
                smallest = right
            if smallest == i:
                break
            self._swap(i, smallest)
            i = smallest

    # ---------- core operations ----------
    def push(self, priority, item):
        """Add an item. Lower priority (earlier expiry) comes out first."""
        self._data.append((priority, self._counter, item))
        self._counter += 1
        self._sift_up(len(self._data) - 1)

    def pop(self):
        """Remove and return the item with the smallest priority."""
        if not self._data:
            raise IndexError("pop from empty heap")
        self._swap(0, len(self._data) - 1)
        _, _, item = self._data.pop()
        if self._data:
            self._sift_down(0)
        return item

    def peek(self):
        """Return the smallest item without removing it, or None if empty."""
        return self._data[0][2] if self._data else None

    def peek_priority(self):
        return self._data[0][0] if self._data else None

    def is_empty(self):
        return not self._data

    def clear(self):
        self._data = []
        self._counter = 0

    # ---------- bulk loading ----------
    def load(self, rows, priority_field="expiry_date"):
        """Fill the heap from a list of dict rows (e.g. batches from the database)."""
        for row in rows:
            self.push(row[priority_field], row)

    # ---------- FEFO helper ----------
    def drop_while(self, should_drop):
        """Pop items from the top while should_drop(item) is True.

        Example: remove empty or expired batches from the top:
            heap.drop_while(lambda b: b["quantity"] <= 0 or b["expiry_date"] < today)
        """
        while self._data and should_drop(self._data[0][2]):
            self.pop()

    def to_sorted_list(self):
        """Return all items in expiry order WITHOUT changing the heap."""
        return [entry[2] for entry in sorted(self._data, key=lambda e: e[:2])]

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"MinHeap(size={len(self._data)}, next={self.peek_priority()})"


if __name__ == "__main__":
    # quick self-test: run `python min_heap.py`
    batches = MinHeap()
    batches.push("2026-12-01", {"batch_no": "B3", "quantity": 40})
    batches.push("2026-03-15", {"batch_no": "B1", "quantity": 10})
    batches.push("2026-08-20", {"batch_no": "B2", "quantity": 25})
    print(batches.peek())      # B1 expires first
    print(batches.pop())       # B1
    print(batches.pop())       # B2
    print(len(batches), "batch left")