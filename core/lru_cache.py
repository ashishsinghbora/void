"""
core/lru_cache.py - Bounded LRU Cache using Doubly-Linked List + Hash Map.

Engineered with __slots__ optimization and thread safety for ultra-low memory
edge architectures. Provides O(1) time complexity for get and put operations.
"""

import threading
from typing import Any, Optional, Dict


class _LRUNode:
    """Doubly-linked list node optimized with __slots__ for zero dict allocation."""
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: Any, value: Any):
        self.key = key
        self.value = value
        self.prev: Optional["_LRUNode"] = None
        self.next: Optional["_LRUNode"] = None


class BoundedLRUCache:
    """
    Thread-safe, bounded Least Recently Used (LRU) cache.
    Eliminates linear scanning overhead and prevents unbounded memory growth.
    """
    __slots__ = ("_capacity", "_cache", "_head", "_tail", "_lock", "_hits", "_misses", "_evictions")

    def __init__(self, capacity: int = 256):
        if capacity <= 0:
            raise ValueError("LRU Cache capacity must be greater than zero.")
        self._capacity = capacity
        self._cache: Dict[Any, _LRUNode] = {}
        
        # Sentinel dummy head and tail nodes to simplify boundary operations
        self._head = _LRUNode(None, None)
        self._tail = _LRUNode(None, None)
        self._head.next = self._tail
        self._tail.prev = self._head

        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _remove_node(self, node: _LRUNode) -> None:
        """Unlink node from its current position."""
        prev_node = node.prev
        next_node = node.next
        if prev_node:
            prev_node.next = next_node
        if next_node:
            next_node.prev = prev_node

    def _add_to_head(self, node: _LRUNode) -> None:
        """Insert node immediately after dummy head (most recently used position)."""
        node.prev = self._head
        node.next = self._head.next
        if self._head.next:
            self._head.next.prev = node
        self._head.next = node

    def _move_to_head(self, node: _LRUNode) -> None:
        """Move existing node to head (mark as most recently used)."""
        self._remove_node(node)
        self._add_to_head(node)

    def _pop_tail(self) -> _LRUNode:
        """Evict the least recently used node before the dummy tail."""
        res = self._tail.prev
        if res and res != self._head:
            self._remove_node(res)
            return res
        raise RuntimeError("Attempted to pop from empty LRU cache.")

    def get(self, key: Any, default: Any = None) -> Any:
        """
        O(1) lookup. Moves accessed item to head of LRU queue.
        Returns default if key does not exist.
        """
        with self._lock:
            node = self._cache.get(key)
            if node is None:
                self._misses += 1
                return default
            self._move_to_head(node)
            self._hits += 1
            return node.value

    def put(self, key: Any, value: Any) -> None:
        """
        O(1) insertion or update. Evicts LRU entry when capacity is exceeded.
        """
        with self._lock:
            node = self._cache.get(key)
            if node is not None:
                node.value = value
                self._move_to_head(node)
            else:
                new_node = _LRUNode(key, value)
                self._cache[key] = new_node
                self._add_to_head(new_node)

                if len(self._cache) > self._capacity:
                    tail = self._pop_tail()
                    self._cache.pop(tail.key, None)
                    self._evictions += 1

    def clear(self) -> None:
        """Clears all cached nodes to immediately release memory."""
        with self._lock:
            self._cache.clear()
            self._head.next = self._tail
            self._tail.prev = self._head
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._cache

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def capacity(self) -> int:
        return self._capacity

    def stats(self) -> Dict[str, Any]:
        """Provides telemetry metrics for performance and memory profiling."""
        with self._lock:
            total = self._hits + self._misses
            hit_ratio = (self._hits / total) if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "capacity": self._capacity,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_ratio": round(hit_ratio, 4),
            }
