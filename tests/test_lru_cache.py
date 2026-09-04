"""
tests/test_lru_cache.py - Bounded LRU Cache Verification.
"""

import threading
from core.lru_cache import BoundedLRUCache


def test_lru_cache_basic_ops():
    cache = BoundedLRUCache(capacity=3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert len(cache) == 3


def test_lru_eviction():
    cache = BoundedLRUCache(capacity=3)
    cache.put("k1", 10)
    cache.put("k2", 20)
    cache.put("k3", 30)

    # Access k1 to make it most recently used (order now: k2 (oldest), k3, k1)
    assert cache.get("k1") == 10

    # Insert k4, should evict k2
    cache.put("k4", 40)

    assert cache.get("k2") is None
    assert cache.get("k1") == 10
    assert cache.get("k3") == 30
    assert cache.get("k4") == 40
    assert len(cache) == 3

    stats = cache.stats()
    assert stats["evictions"] == 1
    assert stats["hits"] >= 3


def test_lru_cache_thread_safety():
    cache = BoundedLRUCache(capacity=50)

    def worker(worker_id: int):
        for i in range(100):
            cache.put(f"key_{worker_id}_{i}", i)
            cache.get(f"key_{worker_id}_{i}")

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(cache) <= 50
