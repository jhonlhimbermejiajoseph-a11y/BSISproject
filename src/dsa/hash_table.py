"""Hash table (separate chaining), written from scratch for the project.

Used for:
  - Resident lookup by scanned ID   (e.g. "BRGY-0001")
  - Medicine lookup by SKU          (e.g. "PARA-500")

Average time: put / get / remove = O(1). Worst case O(n) if many keys collide.
Keys are normalized (stripped + uppercased) so a scanner or manual typing with
different casing or stray spaces still finds the same record.
"""


class HashTable:
    def __init__(self, capacity=16, max_load=0.75):
        self._capacity = max(4, capacity)
        self._max_load = max_load
        self._buckets = [[] for _ in range(self._capacity)]
        self._size = 0

    # ---------- helpers ----------
    @staticmethod
    def _normalize(key):
        return str(key).strip().upper()

    def _index(self, key):
        return hash(key) % self._capacity

    def _resize(self):
        old_buckets = self._buckets
        self._capacity *= 2
        self._buckets = [[] for _ in range(self._capacity)]
        for bucket in old_buckets:
            for key, value in bucket:
                self._buckets[self._index(key)].append([key, value])

    # ---------- core operations ----------
    def put(self, key, value):
        """Insert a key/value pair, or update the value if the key exists."""
        key = self._normalize(key)
        bucket = self._buckets[self._index(key)]
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value
                return
        bucket.append([key, value])
        self._size += 1
        if self._size / self._capacity > self._max_load:
            self._resize()

    def get(self, key, default=None):
        """Return the value for key, or default if not found."""
        key = self._normalize(key)
        for k, v in self._buckets[self._index(key)]:
            if k == key:
                return v
        return default

    def remove(self, key):
        """Delete a key. Returns True if it existed, else False."""
        key = self._normalize(key)
        bucket = self._buckets[self._index(key)]
        for i, pair in enumerate(bucket):
            if pair[0] == key:
                del bucket[i]
                self._size -= 1
                return True
        return False

    def contains(self, key):
        key = self._normalize(key)
        return any(k == key for k, _ in self._buckets[self._index(key)])

    def clear(self):
        self._buckets = [[] for _ in range(self._capacity)]
        self._size = 0

    # ---------- iteration ----------
    def items(self):
        for bucket in self._buckets:
            for key, value in bucket:
                yield key, value

    def keys(self):
        for key, _ in self.items():
            yield key

    def values(self):
        for _, value in self.items():
            yield value

    # ---------- bulk loading ----------
    def load(self, rows, key_field):
        """Fill the table from a list of dicts (e.g. rows from the database).

        Example:
            residents.load(db_rows, "scanned_id")
        """
        for row in rows:
            self.put(row[key_field], row)

    # ---------- python niceties ----------
    def __len__(self):
        return self._size

    def __contains__(self, key):
        return self.contains(key)

    def __getitem__(self, key):
        sentinel = object()
        value = self.get(key, sentinel)
        if value is sentinel:
            raise KeyError(key)
        return value

    def __setitem__(self, key, value):
        self.put(key, value)

    def __repr__(self):
        return f"HashTable(size={self._size}, capacity={self._capacity})"


if __name__ == "__main__":
    # quick self-test: run `python hash_table.py`
    residents = HashTable()
    residents.put("BRGY-0001", {"name": "Juan Dela Cruz", "category": "Senior"})
    residents.put("BRGY-0002", {"name": "Maria Santos", "category": "PWD"})
    print(residents.get(" brgy-0001 "))      # works with spaces / lowercase
    print(residents.get("BRGY-9999"))        # None
    print(len(residents), "residents stored")