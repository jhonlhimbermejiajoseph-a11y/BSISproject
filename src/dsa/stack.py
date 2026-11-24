class Stack:
    """LIFO stack: the last item pushed is the first one popped (like a pile of plates).

    Used by the Check-up screen so Undo takes back the most recent action first.
    """

    def __init__(self):
        self._items = []

    def push(self, item):
        """Put an item on top. O(1)."""
        self._items.append(item)

    def pop(self):
        """Remove and return the top item, or None when the stack is empty. O(1)."""
        return self._items.pop() if self._items else None

    def peek(self):
        """Look at the top item without removing it."""
        return self._items[-1] if self._items else None

    def is_empty(self):
        return not self._items

    def clear(self):
        self._items.clear()

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        """Top to bottom (newest first)."""
        return iter(reversed(self._items))