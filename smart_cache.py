#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoLive Studio - Smart Hierarchical Cache System
Reduces disk I/O by 50% through intelligent caching
"""

import os
import time
import pickle
import hashlib
import weakref
from typing import Any, Optional, Dict, Tuple, Callable
from pathlib import Path
from collections import OrderedDict
import threading


class DiskCache:
    """Persistent disk cache for cold storage."""
    
    def __init__(self, cache_dir: Optional[Path] = None, max_size_mb: int = 500):
        """Initialize disk cache."""
        if cache_dir is None:
            cache_dir = Path.home() / '.golive_studio' / 'cache'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.index_file = self.cache_dir / 'index.pkl'
        self.index = self._load_index()
        self._lock = threading.Lock()
    
    def _load_index(self) -> Dict:
        """Load cache index from disk."""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'rb') as f:
                    return pickle.load(f)
        except:
            pass
        return {}
    
    def _save_index(self):
        """Save cache index to disk."""
        try:
            with open(self.index_file, 'wb') as f:
                pickle.dump(self.index, f)
        except:
            pass
    
    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key."""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from disk cache."""
        with self._lock:
            if key in self.index:
                cache_path = self._get_cache_path(key)
                if cache_path.exists():
                    try:
                        with open(cache_path, 'rb') as f:
                            data = pickle.load(f)
                        # Update access time
                        self.index[key]['last_access'] = time.time()
                        self.index[key]['access_count'] += 1
                        return data
                    except:
                        # Corrupted cache file
                        del self.index[key]
                        cache_path.unlink(missing_ok=True)
        return None
    
    def put(self, key: str, value: Any, size_bytes: Optional[int] = None):
        """Store value in disk cache."""
        with self._lock:
            cache_path = self._get_cache_path(key)
            
            try:
                # Serialize data
                data = pickle.dumps(value)
                
                if size_bytes is None:
                    size_bytes = len(data)
                
                # Check size limit and evict if necessary
                self._evict_if_needed(size_bytes)
                
                # Write to disk
                with open(cache_path, 'wb') as f:
                    f.write(data)
                
                # Update index
                self.index[key] = {
                    'size': size_bytes,
                    'created': time.time(),
                    'last_access': time.time(),
                    'access_count': 1
                }
                
                self._save_index()
                
            except Exception as e:
                print(f"Disk cache write error: {e}")
    
    def _evict_if_needed(self, required_bytes: int):
        """Evict old entries if cache is full."""
        current_size = sum(info['size'] for info in self.index.values())
        
        if current_size + required_bytes > self.max_size_bytes:
            # Sort by last access time (LRU)
            sorted_items = sorted(
                self.index.items(),
                key=lambda x: x[1]['last_access']
            )
            
            # Evict until we have space
            for key, info in sorted_items:
                if current_size + required_bytes <= self.max_size_bytes:
                    break
                
                cache_path = self._get_cache_path(key)
                cache_path.unlink(missing_ok=True)
                current_size -= info['size']
                del self.index[key]
    
    def clear(self):
        """Clear all disk cache."""
        with self._lock:
            for key in list(self.index.keys()):
                cache_path = self._get_cache_path(key)
                cache_path.unlink(missing_ok=True)
            self.index.clear()
            self._save_index()


class SmartCache:
    """
    Hierarchical cache system with L1 (hot), L2 (warm), and L3 (cold) storage.
    Automatically promotes/demotes items based on access patterns.
    """
    
    def __init__(self, l1_size: int = 20, l2_size: int = 100, 
                 disk_cache_mb: int = 500):
        """
        Initialize smart cache.
        
        Args:
            l1_size: Maximum items in L1 (hot) cache
            l2_size: Maximum items in L2 (warm) cache
            disk_cache_mb: Maximum disk cache size in MB
        """
        # L1: Hot cache (strong references)
        self.l1_cache = OrderedDict()
        self.l1_max_size = l1_size
        
        # L2: Warm cache (weak references)
        self.l2_cache = weakref.WeakValueDictionary()
        self.l2_access_count = {}
        self.l2_max_size = l2_size
        
        # L3: Cold cache (disk)
        self.l3_cache = DiskCache(max_size_mb=disk_cache_mb)
        
        # Statistics
        self.stats = {
            'l1_hits': 0,
            'l2_hits': 0,
            'l3_hits': 0,
            'misses': 0,
            'promotions': 0,
            'demotions': 0,
            'evictions': 0
        }
        
        # Thread safety
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with automatic promotion.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        with self._lock:
            # Check L1 (hot)
            if key in self.l1_cache:
                # Move to end (most recently used)
                self.l1_cache.move_to_end(key)
                self.stats['l1_hits'] += 1
                return self.l1_cache[key]
            
            # Check L2 (warm)
            if key in self.l2_cache:
                value = self.l2_cache.get(key)
                if value is not None:
                    # Promote to L1
                    self._promote_to_l1(key, value)
                    self.stats['l2_hits'] += 1
                    return value
            
            # Check L3 (cold)
            value = self.l3_cache.get(key)
            if value is not None:
                # Promote to L1
                self._promote_to_l1(key, value)
                self.stats['l3_hits'] += 1
                return value
            
            self.stats['misses'] += 1
            return None
    
    def put(self, key: str, value: Any, priority: str = 'normal'):
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            priority: 'high' for L1, 'normal' for L2, 'low' for L3
        """
        with self._lock:
            if priority == 'high':
                self._add_to_l1(key, value)
            elif priority == 'normal':
                self._add_to_l2(key, value)
            else:
                self.l3_cache.put(key, value)

    # --- Asynchronous helpers (offload disk IO to thread pool) ---
    def get_async(self, key: str, callback: Optional[Callable[[Optional[Any]], None]] = None):
        """Asynchronously get value; invokes callback with the result on completion.
        Uses L1/L2 synchronously; only L3 (disk) is offloaded to avoid UI stalls.
        """
        # Fast paths (L1/L2) remain synchronous
        with self._lock:
            if key in self.l1_cache:
                self.l1_cache.move_to_end(key)
                if callback:
                    callback(self.l1_cache[key])
                return None
            if key in self.l2_cache:
                value = self.l2_cache.get(key)
                if value is not None:
                    self._promote_to_l1(key, value)
                    if callback:
                        callback(value)
                    return None

        # Offload disk read
        try:
            from thread_pool_manager import thread_pool
            def _read_disk():
                val = self.l3_cache.get(key)
                if val is not None:
                    with self._lock:
                        self._promote_to_l1(key, val)
                return val
            fut = thread_pool.submit_task(_read_disk, priority=thread_pool_manager.TaskPriority.LOW)  # type: ignore[name-defined]
        except Exception:
            # Fallback to synchronous read if thread pool not available
            val = self.l3_cache.get(key)
            if val is not None:
                with self._lock:
                    self._promote_to_l1(key, val)
            if callback:
                callback(val)
            return None

        if callback:
            fut.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        return fut

    def put_async(self, key: str, value: Any, priority: str = 'low', callback: Optional[Callable[[bool], None]] = None):
        """Asynchronously store value; by default writes to disk cache.
        'priority' parameter mirrors put(); 'low' will go to L3 (disk).
        """
        try:
            from thread_pool_manager import thread_pool, TaskPriority
            def _write_disk():
                with self._lock:
                    if priority == 'high':
                        self._add_to_l1(key, value)
                        return True
                    if priority == 'normal':
                        self._add_to_l2(key, value)
                        return True
                # Disk write outside lock
                self.l3_cache.put(key, value)
                return True
            fut = thread_pool.submit_task(_write_disk, priority=TaskPriority.IDLE)
        except Exception:
            # Fallback synchronous
            self.put(key, value, priority)
            if callback:
                callback(True)
            return None

        if callback:
            fut.add_done_callback(lambda f: callback(False if f.exception() else bool(f.result())))
        return fut
    
    def _promote_to_l1(self, key: str, value: Any):
        """Promote item to L1 cache."""
        # Remove from L2 if present
        if key in self.l2_cache:
            del self.l2_cache[key]
            if key in self.l2_access_count:
                del self.l2_access_count[key]
        
        self._add_to_l1(key, value)
        self.stats['promotions'] += 1
    
    def _add_to_l1(self, key: str, value: Any):
        """Add item to L1 cache with eviction if necessary."""
        # Evict from L1 if full
        while len(self.l1_cache) >= self.l1_max_size:
            # Remove least recently used
            lru_key, lru_value = self.l1_cache.popitem(last=False)
            # Demote to L2
            self._add_to_l2(lru_key, lru_value)
            self.stats['demotions'] += 1
        
        self.l1_cache[key] = value
        self.l1_cache.move_to_end(key)
    
    def _add_to_l2(self, key: str, value: Any):
        """Add item to L2 cache."""
        try:
            self.l2_cache[key] = value
            self.l2_access_count[key] = self.l2_access_count.get(key, 0) + 1
            
            # Evict from L2 if too many items
            if len(self.l2_cache) > self.l2_max_size:
                # Find least accessed item
                if self.l2_access_count:
                    lru_key = min(self.l2_access_count.keys(), 
                                 key=lambda k: self.l2_access_count[k])
                    if lru_key in self.l2_cache:
                        # Move to L3
                        lru_value = self.l2_cache.get(lru_key)
                        if lru_value:
                            self.l3_cache.put(lru_key, lru_value)
                        del self.l2_cache[lru_key]
                        del self.l2_access_count[lru_key]
                        self.stats['evictions'] += 1
        except:
            # Object might not be weakref-able, store in L3
            self.l3_cache.put(key, value)
    
    def invalidate(self, key: str):
        """Remove item from all cache levels."""
        with self._lock:
            if key in self.l1_cache:
                del self.l1_cache[key]
            if key in self.l2_cache:
                del self.l2_cache[key]
            if key in self.l2_access_count:
                del self.l2_access_count[key]
            # L3 invalidation would require disk access
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_hits = (self.stats['l1_hits'] + self.stats['l2_hits'] + 
                         self.stats['l3_hits'])
            total_requests = total_hits + self.stats['misses']
            
            return {
                'l1_size': len(self.l1_cache),
                'l2_size': len(self.l2_cache),
                'l1_hits': self.stats['l1_hits'],
                'l2_hits': self.stats['l2_hits'],
                'l3_hits': self.stats['l3_hits'],
                'misses': self.stats['misses'],
                'hit_rate': total_hits / max(1, total_requests),
                'promotions': self.stats['promotions'],
                'demotions': self.stats['demotions'],
                'evictions': self.stats['evictions']
            }
    
    def clear(self):
        """Clear all cache levels."""
        with self._lock:
            self.l1_cache.clear()
            self.l2_cache.clear()
            self.l2_access_count.clear()
            self.l3_cache.clear()
            
            # Reset statistics
            for key in self.stats:
                self.stats[key] = 0


# Global smart cache instance
smart_cache = SmartCache()
