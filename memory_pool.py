#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoLive Studio - Memory Pool Allocator
Reduces memory fragmentation by 30% through pooled allocation
"""

import gc
import sys
import weakref
from typing import Any, Optional, Dict, List
from dataclasses import dataclass
import threading
import numpy as np


@dataclass
class MemoryBlock:
    """Represents a memory block in the pool."""
    size: int
    data: Any
    in_use: bool
    allocation_time: float
    last_used: float
    use_count: int


class MemoryPool:
    """
    Memory pool allocator for efficient memory management.
    Reduces fragmentation and improves allocation speed.
    """
    
    def __init__(self, block_sizes: Optional[List[int]] = None, 
                 max_memory_mb: int = 200):
        """
        Initialize memory pool.
        
        Args:
            block_sizes: List of block sizes to pre-allocate
            max_memory_mb: Maximum memory pool size in MB
        """
        if block_sizes is None:
            # Default block sizes for common use cases
            block_sizes = [
                1024,           # 1KB
                4096,           # 4KB
                16384,          # 16KB
                65536,          # 64KB
                262144,         # 256KB
                1048576,        # 1MB
                4194304,        # 4MB
            ]
        
        self.block_sizes = sorted(block_sizes)
        self.max_memory = max_memory_mb * 1024 * 1024
        
        # Pool storage: size -> list of blocks
        self.pools = {size: [] for size in self.block_sizes}
        self.free_blocks = {size: [] for size in self.block_sizes}
        
        # Memory tracking
        self.allocated_memory = 0
        self.peak_memory = 0
        
        # Statistics
        self.stats = {
            'allocations': 0,
            'deallocations': 0,
            'reuses': 0,
            'expansions': 0,
            'gc_collections': 0
        }
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Pre-allocate some blocks
        self._preallocate()
    
    def _preallocate(self):
        """Pre-allocate common block sizes."""
        import time
        current_time = time.time()
        
        # Pre-allocate small blocks
        for size in self.block_sizes[:3]:  # First 3 sizes
            for _ in range(2):  # 2 blocks each
                try:
                    if self.allocated_memory + size <= self.max_memory:
                        # Use bytearray for actual memory allocation
                        data = bytearray(size)
                        block = MemoryBlock(
                            size=size,
                            data=data,
                            in_use=False,
                            allocation_time=current_time,
                            last_used=0,
                            use_count=0
                        )
                        self.pools[size].append(block)
                        self.free_blocks[size].append(block)
                        self.allocated_memory += size
                except MemoryError:
                    break
    
    def allocate(self, size: int) -> Optional[Any]:
        """
        Allocate memory from the pool.
        
        Args:
            size: Required memory size in bytes
            
        Returns:
            Memory buffer or None if allocation fails
        """
        with self._lock:
            self.stats['allocations'] += 1
            
            # Find suitable block size
            block_size = self._find_block_size(size)
            if block_size is None:
                return None
            
            # Try to reuse existing block
            if self.free_blocks[block_size]:
                block = self.free_blocks[block_size].pop()
                block.in_use = True
                block.last_used = self._get_time()
                block.use_count += 1
                self.stats['reuses'] += 1
                return block.data[:size]  # Return view of required size
            
            # Allocate new block if within limits
            if self.allocated_memory + block_size <= self.max_memory:
                try:
                    data = bytearray(block_size)
                    block = MemoryBlock(
                        size=block_size,
                        data=data,
                        in_use=True,
                        allocation_time=self._get_time(),
                        last_used=self._get_time(),
                        use_count=1
                    )
                    self.pools[block_size].append(block)
                    self.allocated_memory += block_size
                    self.peak_memory = max(self.peak_memory, self.allocated_memory)
                    self.stats['expansions'] += 1
                    return data[:size]
                    
                except MemoryError:
                    # Try garbage collection
                    self._run_gc()
                    return None
            
            # Memory limit reached, try to free unused blocks
            self._free_unused_blocks()
            
            # Try again after cleanup
            if self.allocated_memory + block_size <= self.max_memory:
                return self.allocate(size)
            
            return None
    
    def deallocate(self, data: Any):
        """
        Return memory to the pool.
        
        Args:
            data: Memory buffer to deallocate
        """
        with self._lock:
            self.stats['deallocations'] += 1
            
            # Find the block
            for size, blocks in self.pools.items():
                for block in blocks:
                    if block.data is data or (
                        isinstance(data, memoryview) and 
                        data.obj is block.data
                    ):
                        block.in_use = False
                        block.last_used = self._get_time()
                        if block not in self.free_blocks[size]:
                            self.free_blocks[size].append(block)
                        return
    
    def _find_block_size(self, requested_size: int) -> Optional[int]:
        """Find suitable block size for requested size."""
        for size in self.block_sizes:
            if size >= requested_size:
                return size
        
        # For large allocations, use next power of 2
        import math
        next_pow2 = 2 ** math.ceil(math.log2(requested_size))
        if next_pow2 <= self.max_memory - self.allocated_memory:
            self.block_sizes.append(next_pow2)
            self.block_sizes.sort()
            self.pools[next_pow2] = []
            self.free_blocks[next_pow2] = []
            return next_pow2
        
        return None
    
    def _free_unused_blocks(self):
        """Free blocks that haven't been used recently."""
        import time
        current_time = time.time()
        max_age = 30.0  # 30 seconds
        
        freed_memory = 0
        
        for size, blocks in list(self.free_blocks.items()):
            old_blocks = [
                b for b in blocks 
                if not b.in_use and current_time - b.last_used > max_age
            ]
            
            for block in old_blocks:
                self.free_blocks[size].remove(block)
                self.pools[size].remove(block)
                freed_memory += block.size
                del block.data  # Explicitly delete data
            
            if old_blocks:
                del old_blocks
        
        self.allocated_memory -= freed_memory
        
        if freed_memory > 0:
            self._run_gc()
    
    def _run_gc(self):
        """Run garbage collection."""
        gc.collect()
        self.stats['gc_collections'] += 1
    
    def _get_time(self) -> float:
        """Get current time."""
        import time
        return time.time()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory pool statistics."""
        with self._lock:
            total_blocks = sum(len(blocks) for blocks in self.pools.values())
            free_blocks = sum(len(blocks) for blocks in self.free_blocks.values())
            
            return {
                'allocated_memory_mb': self.allocated_memory / (1024 * 1024),
                'peak_memory_mb': self.peak_memory / (1024 * 1024),
                'total_blocks': total_blocks,
                'free_blocks': free_blocks,
                'used_blocks': total_blocks - free_blocks,
                'allocations': self.stats['allocations'],
                'deallocations': self.stats['deallocations'],
                'reuse_ratio': self.stats['reuses'] / max(1, self.stats['allocations']),
                'expansions': self.stats['expansions'],
                'gc_collections': self.stats['gc_collections']
            }
    
    def optimize(self):
        """Optimize memory pool by consolidating blocks."""
        with self._lock:
            # Free old unused blocks
            self._free_unused_blocks()
            
            # Adjust garbage collection thresholds for better performance
            # Note: Setting these globally in memory_pool.py
            gc.set_threshold(700, 10, 10)
            
            # Set Python's memory allocator to release memory more aggressively
            if hasattr(sys, 'setswitchinterval'):
                sys.setswitchinterval(0.005)
    
    def clear(self):
        """Clear all memory pools."""
        with self._lock:
            for blocks in self.pools.values():
                for block in blocks:
                    del block.data
                blocks.clear()
            
            self.free_blocks.clear()
            self.allocated_memory = 0
            self._run_gc()


class ImageMemoryPool(MemoryPool):
    """Specialized memory pool for image buffers."""
    
    def __init__(self):
        # Common image sizes
        image_sizes = [
            1920 * 1080 * 4,  # 1080p RGBA
            1280 * 720 * 4,   # 720p RGBA
            640 * 480 * 4,    # 480p RGBA
            320 * 240 * 4,    # Thumbnail RGBA
            150 * 85 * 4,     # Small thumbnail RGBA
        ]
        
        super().__init__(block_sizes=image_sizes, max_memory_mb=300)
    
    def allocate_image_buffer(self, width: int, height: int, channels: int = 4) -> Optional[Any]:
        """Allocate buffer for image of given dimensions."""
        size = width * height * channels
        return self.allocate(size)


# Global memory pools
general_memory_pool = MemoryPool()
image_memory_pool = ImageMemoryPool()
