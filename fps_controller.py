#!/usr/bin/env python3
"""
Global FPS Controller for GoLive Studio
Provides centralized timing control for all subsystems
"""

import time
import threading
from typing import Optional, Callable, Dict, Any
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, QElapsedTimer
from dataclasses import dataclass
from enum import Enum
import queue
import numpy as np
import statistics

class FPSMode(Enum):
    FPS_30 = 30
    FPS_60 = 60

@dataclass
class FrameTimestamp:
    """Frame with precise timing information"""
    frame_data: Any
    capture_time: float
    target_time: float
    frame_id: int
    source_id: str

class MasterClock:
    """High-precision master clock for all timing operations"""
    
    def __init__(self):
        self._start_time = time.monotonic()
        self._qt_timer = QElapsedTimer()
        self._qt_timer.start()
        
    def get_time(self) -> float:
        """Get current time in seconds since clock start"""
        return time.monotonic() - self._start_time
    
    def get_time_ms(self) -> int:
        """Get current time in milliseconds"""
        return int(self.get_time() * 1000)
    
    def reset(self):
        """Reset the master clock"""
        self._start_time = time.monotonic()
        self._qt_timer.restart()

class FrameRateConverter:
    """Converts input frames to target FPS using frame dropping/duplication with stability improvements"""
    
    def __init__(self, source_id: str, target_fps: int):
        self.source_id = source_id
        self.target_fps = target_fps
        self.target_interval = 1.0 / target_fps
        self.last_output_time = 0.0
        self.frame_buffer = queue.Queue(maxsize=10)
        self.last_frame = None
        self.frame_counter = 0
        
        # FPS stability tracking
        self.frame_times = []
        self.max_frame_time_samples = 30
        self.adaptive_threshold = 0.002  # 2ms tolerance for frame timing
        
    def add_input_frame(self, frame_data: Any, capture_time: float) -> Optional[FrameTimestamp]:
        """Add input frame and return output frame if needed with improved stability"""
        current_time = capture_time
        
        # Store the frame
        self.last_frame = frame_data
        
        # Track frame timing for stability
        if self.last_output_time > 0:
            frame_interval = current_time - self.last_output_time
            self.frame_times.append(frame_interval)
            if len(self.frame_times) > self.max_frame_time_samples:
                self.frame_times.pop(0)
        
        # Adaptive frame timing with stability improvements
        expected_next_time = self.last_output_time + self.target_interval
        
        # Use adaptive threshold based on recent frame timing variance
        threshold = self.target_interval * 0.1  # 10% tolerance
        if len(self.frame_times) > 5:
            variance = statistics.variance(self.frame_times[-10:])
            threshold = max(self.adaptive_threshold, variance * 2)
        
        # Check if we need to output a frame with improved timing
        if current_time >= expected_next_time - threshold:
            # Use more precise target time calculation
            target_time = expected_next_time
            self.last_output_time = target_time
            
            # Create timestamped frame
            timestamped_frame = FrameTimestamp(
                frame_data=frame_data,
                capture_time=capture_time,
                target_time=target_time,
                frame_id=self.frame_counter,
                source_id=self.source_id
            )
            self.frame_counter += 1
            return timestamped_frame
        
        return None
    
    def get_fps_stability(self) -> float:
        """Calculate FPS stability (lower is better)"""
        if len(self.frame_times) < 5:
            return 0.0
        
        # Calculate variance in frame timing
        try:
            variance = statistics.variance(self.frame_times[-10:])
            return variance * 1000  # Convert to milliseconds
        except:
            return 0.0
    
    def get_duplicate_frame(self, target_time: float) -> Optional[FrameTimestamp]:
        """Get a duplicate of the last frame for frame rate conversion"""
        if self.last_frame is not None:
            timestamped_frame = FrameTimestamp(
                frame_data=self.last_frame,
                capture_time=target_time,
                target_time=target_time,
                frame_id=self.frame_counter,
                source_id=self.source_id
            )
            self.frame_counter += 1
            return timestamped_frame
        return None
    
    def set_target_fps(self, fps: int):
        """Update target FPS"""
        self.target_fps = fps
        self.target_interval = 1.0 / fps

class GlobalFPSController(QObject):
    """Global FPS controller managing all timing in the application"""
    
    # Signals
    fps_changed = pyqtSignal(int)
    frame_ready = pyqtSignal(object)  # FrameTimestamp
    timing_stats = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
        # Global FPS settings
        self.target_fps = 60
        self.frame_interval = 1.0 / self.target_fps
        
        # Master clock
        self.master_clock = MasterClock()
        
        # Frame rate converters for each input source
        self.converters: Dict[str, FrameRateConverter] = {}
        
        # Timing control
        self.master_timer = QTimer()
        self.master_timer.timeout.connect(self._master_tick)
        
        # Statistics with stability tracking
        self.stats = {
            'frames_processed': 0,
            'frames_dropped': 0,
            'frames_duplicated': 0,
            'timing_drift': 0.0,
            'last_frame_time': 0.0,
            'fps_stability': 0.0,
            'average_fps': 0.0
        }
        
        # FPS stability monitoring
        self.fps_samples = []
        self.max_fps_samples = 60  # Track 1 second of FPS at 60fps
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Active state
        self.is_running = False
        
    def set_target_fps(self, fps: int):
        """Set global target FPS and update all subsystems"""
        with self.lock:
            old_fps = self.target_fps
            self.target_fps = fps
            self.frame_interval = 1.0 / fps
            
            # Update all converters
            for converter in self.converters.values():
                converter.set_target_fps(fps)
            
            # Restart master timer with new interval
            if self.is_running:
                self.master_timer.stop()
                self.master_timer.start(int(self.frame_interval * 1000))
            
            print(f"Global FPS changed: {old_fps} -> {fps}")
            self.fps_changed.emit(fps)
    
    def start(self):
        """Start the global FPS controller"""
        with self.lock:
            if not self.is_running:
                self.master_clock.reset()
                self.master_timer.start(int(self.frame_interval * 1000))
                self.is_running = True
                print(f"Global FPS Controller started at {self.target_fps} FPS")
    
    def stop(self):
        """Stop the global FPS controller"""
        with self.lock:
            if self.is_running:
                self.master_timer.stop()
                self.is_running = False
                print("Global FPS Controller stopped")
    
    def register_input_source(self, source_id: str) -> FrameRateConverter:
        """Register a new input source and return its converter"""
        with self.lock:
            if source_id not in self.converters:
                self.converters[source_id] = FrameRateConverter(source_id, self.target_fps)
                print(f"Registered input source: {source_id}")
            return self.converters[source_id]
    
    def unregister_input_source(self, source_id: str):
        """Unregister an input source"""
        with self.lock:
            if source_id in self.converters:
                del self.converters[source_id]
                print(f"Unregistered input source: {source_id}")
    
    def process_input_frame(self, source_id: str, frame_data: Any) -> Optional[FrameTimestamp]:
        """Process an input frame and return timestamped frame if needed"""
        current_time = self.master_clock.get_time()
        
        with self.lock:
            if source_id not in self.converters:
                self.register_input_source(source_id)
            
            converter = self.converters[source_id]
            timestamped_frame = converter.add_input_frame(frame_data, current_time)
            
            if timestamped_frame:
                self.stats['frames_processed'] += 1
                self.stats['last_frame_time'] = current_time
                self.frame_ready.emit(timestamped_frame)
            
            return timestamped_frame
    
    def _master_tick(self):
        """Master timer tick - ensures consistent frame output"""
        current_time = self.master_clock.get_time()
        target_frame_time = current_time
        
        # Check if any sources need frame duplication
        with self.lock:
            for source_id, converter in self.converters.items():
                # If no recent frames, duplicate the last one
                if (current_time - converter.last_output_time) > (self.frame_interval * 1.5):
                    duplicate_frame = converter.get_duplicate_frame(target_frame_time)
                    if duplicate_frame:
                        self.stats['frames_duplicated'] += 1
                        self.frame_ready.emit(duplicate_frame)
        
        # Update timing statistics
        self.stats['timing_drift'] = abs(current_time - self.stats['last_frame_time'])
        self.timing_stats.emit(self.stats.copy())
    
    def get_current_time(self) -> float:
        """Get current master clock time"""
        return self.master_clock.get_time()
    
    def get_frame_interval(self) -> float:
        """Get current frame interval"""
        return self.frame_interval
    
    def get_target_fps(self) -> int:
        """Get current target FPS"""
        return self.target_fps
    
    def get_stats(self) -> dict:
        """Get timing statistics"""
        with self.lock:
            return self.stats.copy()

# Global instance
global_fps_controller = GlobalFPSController()

def get_fps_controller() -> GlobalFPSController:
    """Get the global FPS controller instance"""
    return global_fps_controller

def set_global_fps(fps: int):
    """Convenience function to set global FPS"""
    global_fps_controller.set_target_fps(fps)

def get_global_fps() -> int:
    """Convenience function to get global FPS"""
    return global_fps_controller.get_target_fps()

def get_master_time() -> float:
    """Convenience function to get master clock time"""
    return global_fps_controller.get_current_time()
