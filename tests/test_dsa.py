"""Run from the project root:  python -m unittest discover -s tests -v"""
import unittest

from src.dsa.bst import BST
from src.dsa.hash_table import HashTable
from src.dsa.merge_sort import merge_sort
from src.dsa.min_heap import MinHeap
from src.dsa.queue import RequestQueue
from src.dsa.stack import Stack

NAMES = ["paracetamol", "amoxicillin", "losartan", "ibuprofen", "cetirizine", "amlodipine", "metformin"]


class StackTests(unittest.TestCase):
    def test_lifo_order(self):
        s = Stack()
        for x in (1, 2, 3):
            s.push(x)
        self.assertEqual([s.pop(), s.pop(), s.pop()], [3, 2, 1])

    def test_empty(self):
        s = Stack()
        self.assertIsNone(s.pop())
        self.assertTrue(s.is_empty())

    def test_peek_does_not_remove(self):
        s = Stack()
        s.push("a")
        self.assertEqual(s.peek(), "a")
        self.assertEqual(len(s), 1)


class HashTableTests(unittest.TestCase):
    def test_load_and_get(self):
        h = HashTable()
        h.load([{"sku": "A1", "n": 1}, {"sku": "B2", "n": 2}], "sku")
        self.assertEqual(h.get("B2")["n"], 2)
        self.assertIsNone(h.get("ZZ"))

    def test_clear(self):
        h = HashTable()
        h.load([{"sku": "A1"}], "sku")
        h.clear()
        self.assertIsNone(h.get("A1"))


class MergeSortTests(unittest.TestCase):
    def test_sorts_by_key(self):
        self.assertEqual(merge_sort([3, 1, 2], key=lambda x: x), [1, 2, 3])

    def test_stable_and_empty(self):
        self.assertEqual(merge_sort([], key=lambda x: x), [])
        data = [("b", 1), ("a", 1), ("c", 0)]
        self.assertEqual(merge_sort(data, key=lambda x: x[1]), [("c", 0), ("b", 1), ("a", 1)])


class RequestQueueTests(unittest.TestCase):
    def setUp(self):
        self.q = RequestQueue()
        self.q.load([{"id": 1, "resident": "Juan"}, {"id": 2, "resident": "Maria"},
                     {"id": 3, "resident": "Pedro"}])

    def test_fifo_order(self):
        self.assertEqual([self.q.dequeue()["id"] for _ in range(3)], [1, 2, 3])

    def test_peek_does_not_remove(self):
        self.assertEqual(self.q.peek()["resident"], "Juan")
        self.assertEqual(len(self.q), 3)

    def test_dequeue_empty_raises(self):
        with self.assertRaises(IndexError):
            RequestQueue().dequeue()

    def test_enqueue_after_emptying(self):
        for _ in range(3):
            self.q.dequeue()
        self.assertTrue(self.q.is_empty())
        self.q.enqueue({"id": 4})
        self.assertEqual(self.q.dequeue()["id"], 4)

    def test_cancel_a_request(self):
        removed = self.q.remove_where(lambda r: r["id"] == 2)
        self.assertEqual(removed["resident"], "Maria")
        self.assertEqual([r["id"] for r in self.q.to_list()], [1, 3])
        self.assertIsNone(self.q.remove_where(lambda r: r["id"] == 99))

    def test_cancel_last_keeps_queue_working(self):
        self.q.remove_where(lambda r: r["id"] == 3)
        self.q.enqueue({"id": 5})
        self.assertEqual([r["id"] for r in self.q.to_list()], [1, 2, 5])

    def test_position_in_line(self):
        self.assertEqual(self.q.position_of(lambda r: r["id"] == 3), 3)
        self.assertIsNone(self.q.position_of(lambda r: r["id"] == 99))


class MinHeapTests(unittest.TestCase):
    def setUp(self):
        self.heap = MinHeap()
        self.heap.push("2026-12-01", {"batch_no": "B3", "quantity": 40})
        self.heap.push("2026-03-15", {"batch_no": "B1", "quantity": 10})
        self.heap.push("2026-08-20", {"batch_no": "B2", "quantity": 25})

    def test_earliest_expiry_comes_out_first(self):
        self.assertEqual([self.heap.pop()["batch_no"] for _ in range(3)], ["B1", "B2", "B3"])

    def test_peek_does_not_remove(self):
        self.assertEqual(self.heap.peek()["batch_no"], "B1")
        self.assertEqual(len(self.heap), 3)

    def test_pop_empty_raises(self):
        with self.assertRaises(IndexError):
            MinHeap().pop()

    def test_equal_priority_keeps_insert_order(self):
        h = MinHeap()
        for name in ("first", "second", "third"):
            h.push("2026-01-01", name)
        self.assertEqual([h.pop(), h.pop(), h.pop()], ["first", "second", "third"])

    def test_load_and_drop_empty_batches(self):
        h = MinHeap()
        h.load([{"expiry_date": "2026-01-01", "quantity": 0},
                {"expiry_date": "2026-02-01", "quantity": 5}])
        h.drop_while(lambda b: b["quantity"] <= 0)
        self.assertEqual(h.peek()["expiry_date"], "2026-02-01")

    def test_sorted_list_does_not_change_heap(self):
        order = [b["batch_no"] for b in self.heap.to_sorted_list()]
        self.assertEqual(order, ["B1", "B2", "B3"])
        self.assertEqual(len(self.heap), 3)


class BSTTests(unittest.TestCase):
    def setUp(self):
        self.tree = BST.build([{"name": n} for n in NAMES], key=lambda m: m["name"])

    def test_in_order_is_sorted(self):
        self.assertEqual([m["name"] for m in self.tree.in_order()], sorted(NAMES))

    def test_search_exact(self):
        self.assertEqual(self.tree.search("losartan")["name"], "losartan")
        self.assertIsNone(self.tree.search("aspirin"))

    def test_prefix_search(self):
        self.assertEqual([m["name"] for m in self.tree.starts_with("am")], ["amlodipine", "amoxicillin"])
        self.assertEqual(self.tree.starts_with("zzz"), [])

    def test_balanced_even_with_sorted_input(self):
        tree = BST.build([{"n": f"{i:04d}"} for i in range(1000)], key=lambda m: m["n"])
        self.assertEqual(len(tree), 1000)
        self.assertLessEqual(tree.height(), 11)      # log2(1000) ~ 10

    def test_duplicate_key_replaces(self):
        tree = BST()
        tree.insert("a", 1)
        tree.insert("a", 2)
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree.search("a"), 2)


if __name__ == "__main__":
    unittest.main()