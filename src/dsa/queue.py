"""FIFO Queue, written from scratch (linked list) for the project.

Used to organize medicine requests by residents' arrival order:
first in the line is the first to be served.

Time: enqueue = O(1), dequeue = O(1), peek = O(1).

NOTE: this file is named queue.py, which is also the name of a Python standard
library module. Always import it through the package:
    from src.dsa.queue import RequestQueue
If you ever get strange import errors, rename this file to request_queue.py.
"""


class _Node:
    __slots__ = ("value", "next")

    def __init__(self, value):
        self.value = value
        self.next = None


class RequestQueue:
    def __init__(self):
        self._head = None   # front of the line (next to be served)
        self._tail = None   # back of the line (newest arrival)
        self._size = 0

    # ---------- core operations ----------
    def enqueue(self, item):
        """Add a request to the back of the line."""
        node = _Node(item)
        if self._tail is None:
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def dequeue(self):
        """Remove and return the request at the front of the line."""
        if self._head is None:
            raise IndexError("dequeue from empty queue")
        node = self._head
        self._head = node.next
        if self._head is None:
            self._tail = None
        self._size -= 1
        return node.value

    def peek(self):
        """Return the front request without removing it, or None if empty."""
        return self._head.value if self._head else None

    def is_empty(self):
        return self._size == 0

    def clear(self):
        self._head = self._tail = None
        self._size = 0

    # ---------- extras for the requests screen ----------
    def remove_where(self, condition):
        """Remove the first request where condition(item) is True (e.g. a cancel).

        Example: queue.remove_where(lambda r: r["id"] == 12)
        Returns the removed item, or None if nothing matched.
        """
        prev, cur = None, self._head
        while cur:
            if condition(cur.value):
                if prev:
                    prev.next = cur.next
                else:
                    self._head = cur.next
                if cur is self._tail:
                    self._tail = prev
                self._size -= 1
                return cur.value
            prev, cur = cur, cur.next
        return None

    def position_of(self, condition):
        """Return the 1-based place in line of the first match, or None."""
        cur, pos = self._head, 1
        while cur:
            if condition(cur.value):
                return pos
            cur, pos = cur.next, pos + 1
        return None

    def load(self, rows):
        """Fill the queue from a list (e.g. pending requests, oldest first)."""
        for row in rows:
            self.enqueue(row)

    def to_list(self):
        """Return all requests front-to-back without changing the queue."""
        return list(self)

    # ---------- python niceties ----------
    def __iter__(self):
        cur = self._head
        while cur:
            yield cur.value
            cur = cur.next

    def __len__(self):
        return self._size

    def __repr__(self):
        return f"RequestQueue(size={self._size})"


if __name__ == "__main__":
    # quick self-test: run `python queue.py`
    q = RequestQueue()
    q.enqueue({"id": 1, "resident": "Juan"})
    q.enqueue({"id": 2, "resident": "Maria"})
    q.enqueue({"id": 3, "resident": "Pedro"})
    print(q.dequeue())   # Juan goes first
    print(q.peek())      # Maria is next
    print(len(q), "waiting")