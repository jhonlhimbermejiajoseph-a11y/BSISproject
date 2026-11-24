from src.dsa.merge_sort import merge_sort


class _Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.left = None
        self.right = None


class BST:
    """Binary Search Tree keyed by text (medicine name, lowercase).

    insert / search: O(log n) when balanced (O(n) worst case).
    in_order: O(n), gives the items already sorted.
    starts_with: O(log n + k) for k matches.
    """

    def __init__(self):
        self.root = None
        self.size = 0

    @classmethod
    def build(cls, items, key):
        """Build a balanced tree: sort first (Merge Sort), then insert the middle item first."""
        tree = cls()
        ordered = merge_sort(list(items), key=lambda x: key(x))
        tree._fill(ordered, 0, len(ordered) - 1, key)
        return tree

    def _fill(self, ordered, low, high, key):
        if low > high:
            return
        mid = (low + high) // 2
        self.insert(key(ordered[mid]), ordered[mid])
        self._fill(ordered, low, mid - 1, key)
        self._fill(ordered, mid + 1, high, key)

    def __len__(self):
        return self.size

    def insert(self, key, value):
        if self.root is None:
            self.root = _Node(key, value)
            self.size = 1
            return
        node = self.root
        while True:
            if key == node.key:
                node.value = value                  # same key: replace
                return
            side = "left" if key < node.key else "right"
            child = getattr(node, side)
            if child is None:
                setattr(node, side, _Node(key, value))
                self.size += 1
                return
            node = child

    def search(self, key):
        """Exact match. Returns the value or None."""
        node = self.root
        while node is not None:
            if key == node.key:
                return node.value
            node = node.left if key < node.key else node.right
        return None

    def in_order(self):
        """All values, sorted by key (left, node, right)."""
        result = []

        def walk(node):
            if node is None:
                return
            walk(node.left)
            result.append(node.value)
            walk(node.right)

        walk(self.root)
        return result

    def starts_with(self, prefix):
        """Values whose key starts with prefix, sorted. Skips branches that cannot match."""
        result = []

        def walk(node):
            if node is None:
                return
            if node.key >= prefix:
                walk(node.left)
            if node.key.startswith(prefix):
                result.append(node.value)
            if node.key <= prefix or node.key.startswith(prefix):
                walk(node.right)

        walk(self.root)
        return result

    def height(self):
        def h(node):
            return 0 if node is None else 1 + max(h(node.left), h(node.right))
        return h(self.root)