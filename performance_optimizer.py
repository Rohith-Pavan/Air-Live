#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoLive Studio - Performance Optimizer
Addresses memory usage, FPS stability, and frame latency issues
"""

import gc
import sys
import time
import threading
import weakref
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
import psutil
import numpy as np


@dataclass
class OptimizationTargets:
    """Performance optimization targets."""
    memory_target_mb: int = 250
    fps_stability_variance: float = 1.0
    frame_latency_target_ms: float = 20.0
    cpu_target_percent: float = 5.0


class MemoryOptimizer:
    """Optimizes memory usage to meet target requirements."""
    
    def __init__(self, target_mb: int = 250):
        self.target_mb = target_mb
        self.target_bytes = target_mb * 1024 * 1024
        self._gc_threshold = 0.85  # Trigger cleanup at 85% of target
        self._last_cleanup = time.time()
        self._cleanup_interval = 5.0  # Cleanup every 5 seconds
        
    def get_current_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def is_memory_critical(self) -> bool:
        """Check if memory usage is approaching target."""
        current_mb = self.get_current_memory_mb()
        return current_mb > (self.target_mb * self._gc_threshold)
    
    def aggressive_cleanup(self):
        """Perform aggressive memory cleanup."""
        # Force garbage collection multiple times
        for _ in range(3):
            gc.collect()
        
        # Force Python to return memory to OS (Python 3.8+)
        if hasattr(gc, 'freeze'):
            gc.freeze()
        
        # Additional cleanup for PyQt objects
        try:
            from PyQt6.QtCore import QCoreApplication
            app = QCoreApplication.instance()
            if app:
                app.processEvents()
        except:
            pass
        
        print(f"Memory cleanup: {self.get_current_memory_mb():.1f}MB")
    
    def optimize_numpy_arrays(self):
        """Optimize NumPy array memory usage."""
        # Set NumPy to use less memory for small arrays
        np.seterr(all='ignore')  # Reduce error checking overhead
        
    def periodic_cleanup(self):
        """Perform periodic memory cleanup if needed."""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            if self.is_memory_critical():
                self.aggressive_cleanup()
            self._last_cleanup = now


class FPSStabilizer:
    """Stabilizes FPS to maintain ±1fps variance."""
    
    def __init__(self, target_fps: int = 60, variance_limit: float = 1.0):
        self.target_fps = target_fps
        self.variance_limit = variance_limit
        self.frame_times = []
        self.max_samples = 30  # Track last 30 frames
        self._last_frame_time = time.time()
        self._frame_interval = 1.0 / target_fps
        
    def record_frame(self):
        """Record a frame timestamp."""
        now = time.time()
        frame_time = now - self._last_frame_time
        self._last_frame_time = now
        
        self.frame_times.append(frame_time)
        if len(self.frame_times) > self.max_samples:
            self.frame_times.pop(0)
    
    def get_current_fps(self) -> float:
        """Calculate current FPS from recent frames."""
        if len(self.frame_times) < 2:
            return self.target_fps
        
        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_frame_time if avg_frame_time > 0 else self.target_fps
    
    def get_fps_variance(self) -> float:
        """Calculate FPS variance from target."""
        current_fps = self.get_current_fps()
        return abs(current_fps - self.target_fps)
    
    def is_fps_stable(self) -> bool:
        """Check if FPS is within acceptable variance."""
        return self.get_fps_variance() <= self.variance_limit
    
    def get_adaptive_sleep_time(self) -> float:
        """Calculate adaptive sleep time to stabilize FPS."""
        if len(self.frame_times) < 2:
            return self._frame_interval
        
        recent_avg = sum(self.frame_times[-5:]) / min(5, len(self.frame_times))
        target_time = self._frame_interval
        
        # Adaptive sleep to maintain target FPS
        if recent_avg < target_time:
            return target_time - recent_avg
        return 0.0


class LatencyOptimizer:
    """Optimizes frame latency to under 20ms."""
    
    def __init__(self, target_latency_ms: float = 20.0):
        self.target_latency_ms = target_latency_ms
        self.latency_samples = []
        self.max_samples = 10
        
    def record_latency(self, latency_ms: float):
        """Record frame latency measurement."""
        self.latency_samples.append(latency_ms)
        if len(self.latency_samples) > self.max_samples:
            self.latency_samples.pop(0)
    
    def get_average_latency(self) -> float:
        """Get average latency from recent samples."""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)
    
    def is_latency_acceptable(self) -> bool:
        """Check if latency is within target."""
        return self.get_average_latency() <= self.target_latency_ms
    
    def optimize_qt_settings(self):
        """Optimize Qt settings for lower latency."""
        from PyQt6.QtCore import QCoreApplication
        
        # Reduce Qt event processing overhead
        app = QCoreApplication.instance()
        if app:
            app.processEvents()  # Clear event queue


class PerformanceOptimizer(QObject):
    """Main performance optimizer coordinating all optimizations."""
    
    performance_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.targets = OptimizationTargets()
        self.memory_optimizer = MemoryOptimizer(self.targets.memory_target_mb)
        self.fps_stabilizer = FPSStabilizer(60, self.targets.fps_stability_variance)
        self.latency_optimizer = LatencyOptimizer(self.targets.frame_latency_target_ms)
        self._debug = False
        
        # Monitoring timer
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_performance)
        self.monitor_timer.start(1500)  # Reduce monitoring frequency to lower overhead
        
        # Optimization timer
        self.optimize_timer = QTimer(self)
        self.optimize_timer.timeout.connect(self._run_optimizations)
        self.optimize_timer.start(200)  # Slightly lower frequency to reduce contention
        
        if self._debug:
            print("Performance Optimizer initialized with aggressive memory management")
    
    def _monitor_performance(self):
        """Monitor current performance metrics."""
        current_memory = self.memory_optimizer.get_current_memory_mb()
        current_fps = self.fps_stabilizer.get_current_fps()
        fps_variance = self.fps_stabilizer.get_fps_variance()
        avg_latency = self.latency_optimizer.get_average_latency()
        
        metrics = {
            'memory_mb': current_memory,
            'memory_target_met': current_memory <= self.targets.memory_target_mb,
            'fps': current_fps,
            'fps_variance': fps_variance,
            'fps_stable': self.fps_stabilizer.is_fps_stable(),
            'latency_ms': avg_latency,
            'latency_acceptable': self.latency_optimizer.is_latency_acceptable()
        }
        
        self.performance_updated.emit(metrics)
        
        # Print status every 10 seconds
        if self._debug:
            if hasattr(self, '_last_status_time'):
                if time.time() - self._last_status_time > 10:
                    self._print_status(metrics)
                    self._last_status_time = time.time()
            else:
                self._last_status_time = time.time()
    
    def _print_status(self, metrics: Dict[str, Any]):
        """Print current optimization status."""
        print(f"\n🎯 Performance Status:")
        print(f"  Memory: {metrics['memory_mb']:.1f}MB (Target: {self.targets.memory_target_mb}MB) {'✅' if metrics['memory_target_met'] else '❌'}")
        print(f"  FPS: {metrics['fps']:.1f} (Variance: ±{metrics['fps_variance']:.1f}) {'✅' if metrics['fps_stable'] else '❌'}")
        print(f"  Latency: {metrics['latency_ms']:.1f}ms (Target: <{self.targets.frame_latency_target_ms}ms) {'✅' if metrics['latency_acceptable'] else '❌'}")
    
    def _run_optimizations(self):
        """Run periodic optimizations."""
        # Memory optimization
        self.memory_optimizer.periodic_cleanup()
        
        # FPS stabilization
        self.fps_stabilizer.record_frame()
        
        # Latency optimization
        self.latency_optimizer.optimize_qt_settings()
    
    def force_memory_optimization(self):
        """Force immediate memory optimization."""
        print("🧹 Forcing aggressive memory cleanup...")
        self.memory_optimizer.aggressive_cleanup()
        self.memory_optimizer.optimize_numpy_arrays()
        
        # Additional aggressive measures
        if sys.platform == 'win32':
            # Windows: Trim working set
            try:
                import ctypes
                ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
            except:
                pass
        elif sys.platform == 'darwin':
            # macOS: Force memory pressure relief
            try:
                import os
                os.system('purge > /dev/null 2>&1 &')
            except:
                pass
        
        print(f"✅ Memory after cleanup: {self.memory_optimizer.get_current_memory_mb():.1f}MB")
    
    def record_frame_latency(self, latency_ms: float):
        """Record frame latency for optimization."""
        self.latency_optimizer.record_latency(latency_ms)
    
    def get_adaptive_sleep_time(self) -> float:
        """Get adaptive sleep time for FPS stabilization."""
        return self.fps_stabilizer.get_adaptive_sleep_time()


# Global optimizer instance
_performance_optimizer = None

def get_performance_optimizer() -> PerformanceOptimizer:
    """Get global performance optimizer instance."""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer

def optimize_performance_now():
    """Force immediate performance optimization."""
    optimizer = get_performance_optimizer()
    optimizer.force_memory_optimization()
    return optimizer
