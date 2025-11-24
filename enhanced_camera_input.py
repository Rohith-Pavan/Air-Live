#!/usr/bin/env python3
"""
Enhanced Camera Input with Global FPS Control
Handles camera input with frame rate conversion and timing synchronization
"""

import cv2
import threading
import time
import queue
import numpy as np
from typing import Optional, Callable, Dict, Any
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QImage

# Import FPS controller for global timing
try:
    from fps_controller import get_fps_controller, FrameTimestamp
    FPS_CONTROLLER_AVAILABLE = True
except ImportError:
    FPS_CONTROLLER_AVAILABLE = False
    print("FPS Controller not available for camera input")

class EnhancedCameraInput(QObject):
    """Enhanced camera input with FPS controller integration"""
    
    # Signals
    frame_ready = pyqtSignal(QImage)  # Processed frame ready for display
    camera_started = pyqtSignal(int)  # Camera index
    camera_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)
    stats_updated = pyqtSignal(dict)
    
    def __init__(self, camera_index: int = 0):
        super().__init__()
        
        self.camera_index = camera_index
        self.source_id = f"camera_{camera_index}"
        
        # FPS controller integration
        self.fps_controller = None
        if FPS_CONTROLLER_AVAILABLE:
            self.fps_controller = get_fps_controller()
            self.fps_controller.register_input_source(self.source_id)
            self.fps_controller.frame_ready.connect(self._on_frame_processed)
        
        # Camera capture
        self.cap: Optional[cv2.VideoCapture] = None
        self.capture_thread: Optional[threading.Thread] = None
        
        # State
        self.is_capturing = False
        self.should_stop = False
        
        # Camera settings
        self.native_fps = 30.0
        self.native_width = 640
        self.native_height = 480
        
        # Statistics
        self.stats = {
            'frames_captured': 0,
            'frames_processed': 0,
            'frames_dropped': 0,
            'capture_fps': 0.0,
            'processing_fps': 0.0,
            'last_capture_time': 0.0
        }
        
        # Timing for statistics
        self.last_stats_time = time.monotonic()
        self.last_frame_count = 0
        
        # Stats timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(1000)  # Update stats every second
    
    def start_capture(self, width: int = 1920, height: int = 1080, fps: float = 60.0) -> bool:
        """Start camera capture with specified settings"""
        if self.is_capturing:
            return True
        
        try:
            # Initialize camera
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.error_occurred.emit(f"Failed to open camera {self.camera_index}")
                return False
            
            # Configure camera settings
            self._configure_camera(width, height, fps)
            
            # Start capture thread
            self.should_stop = False
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            self.is_capturing = True
            self.camera_started.emit(self.camera_index)
            
            print(f"Camera {self.camera_index} started: {self.native_width}x{self.native_height} @ {self.native_fps}fps")
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Camera start error: {e}")
            return False
    
    def stop_capture(self):
        """Stop camera capture"""
        if not self.is_capturing:
            return
        
        self.should_stop = True
        
        # Wait for capture thread
        if self.capture_thread:
            self.capture_thread.join(timeout=5.0)
        
        # Release camera
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.is_capturing = False
        self.camera_stopped.emit()
        
        print(f"Camera {self.camera_index} stopped")
    
    def _configure_camera(self, width: int, height: int, fps: float):
        """Configure camera with optimal settings"""
        if not self.cap:
            return
        
        try:
            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # Set FPS
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            
            # Set buffer size to minimize latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Set format for better performance
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
            
            # Read actual settings
            self.native_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.native_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.native_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            print(f"Camera configured: {self.native_width}x{self.native_height} @ {self.native_fps}fps")
            
        except Exception as e:
            print(f"Camera configuration error: {e}")
    
    def _capture_loop(self):
        """Main capture loop with precise timing"""
        frame_interval = 1.0 / max(self.native_fps, 30.0)  # Minimum 30fps
        next_capture_time = time.monotonic()
        
        while not self.should_stop and self.cap:
            try:
                current_time = time.monotonic()
                
                # Wait for next capture time to maintain consistent timing
                if current_time < next_capture_time:
                    sleep_time = next_capture_time - current_time
                    if sleep_time > 0.001:  # Only sleep if significant
                        time.sleep(sleep_time)
                
                # Capture frame
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to capture frame")
                    continue
                
                capture_time = time.monotonic()
                self.stats['frames_captured'] += 1
                self.stats['last_capture_time'] = capture_time
                
                # Process frame through FPS controller
                if self.fps_controller:
                    # Convert BGR to RGB for processing
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.fps_controller.process_input_frame(self.source_id, frame_rgb)
                else:
                    # Fallback: direct processing
                    self._process_frame_direct(frame, capture_time)
                
                # Update timing for next frame
                next_capture_time += frame_interval
                
                # Prevent timing drift
                if next_capture_time < current_time - frame_interval:
                    next_capture_time = current_time
                
            except Exception as e:
                if not self.should_stop:
                    print(f"Capture loop error: {e}")
                break
    
    def _process_frame_direct(self, frame: np.ndarray, capture_time: float):
        """Direct frame processing without FPS controller"""
        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to QImage
            height, width, channel = frame_rgb.shape
            bytes_per_line = 3 * width
            qimage = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Emit frame
            self.frame_ready.emit(qimage)
            self.stats['frames_processed'] += 1
            
        except Exception as e:
            print(f"Direct frame processing error: {e}")
    
    def _on_frame_processed(self, timestamped_frame: FrameTimestamp):
        """Handle frame processed by FPS controller"""
        if timestamped_frame.source_id != self.source_id:
            return
        
        try:
            # Convert numpy array to QImage
            frame_data = timestamped_frame.frame_data
            if isinstance(frame_data, np.ndarray) and len(frame_data.shape) == 3:
                height, width, channel = frame_data.shape
                bytes_per_line = 3 * width
                qimage = QImage(frame_data.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                
                # Emit processed frame
                self.frame_ready.emit(qimage)
                self.stats['frames_processed'] += 1
            
        except Exception as e:
            print(f"Frame processing error: {e}")
    
    def _update_stats(self):
        """Update capture statistics"""
        current_time = time.monotonic()
        time_delta = current_time - self.last_stats_time
        
        if time_delta > 0:
            # Calculate FPS
            frame_delta = self.stats['frames_captured'] - self.last_frame_count
            self.stats['capture_fps'] = frame_delta / time_delta
            
            # Update for next calculation
            self.last_stats_time = current_time
            self.last_frame_count = self.stats['frames_captured']
            
            # Emit stats
            self.stats_updated.emit(self.stats.copy())
    
    def get_native_settings(self) -> Dict[str, Any]:
        """Get camera's native settings"""
        return {
            'width': self.native_width,
            'height': self.native_height,
            'fps': self.native_fps,
            'camera_index': self.camera_index
        }
    
    def is_camera_available(self) -> bool:
        """Check if camera is available"""
        try:
            test_cap = cv2.VideoCapture(self.camera_index)
            available = test_cap.isOpened()
            test_cap.release()
            return available
        except:
            return False

class CameraManager(QObject):
    """Manager for multiple camera inputs with FPS synchronization"""
    
    # Signals
    camera_added = pyqtSignal(int)  # camera index
    camera_removed = pyqtSignal(int)
    frame_ready = pyqtSignal(int, QImage)  # camera index, frame
    
    def __init__(self):
        super().__init__()
        
        self.cameras: Dict[int, EnhancedCameraInput] = {}
        
        # FPS controller integration
        self.fps_controller = None
        if FPS_CONTROLLER_AVAILABLE:
            self.fps_controller = get_fps_controller()
            self.fps_controller.fps_changed.connect(self._on_global_fps_changed)
    
    def add_camera(self, camera_index: int) -> bool:
        """Add a camera input"""
        if camera_index in self.cameras:
            return True
        
        try:
            camera = EnhancedCameraInput(camera_index)
            
            # Check if camera is available
            if not camera.is_camera_available():
                return False
            
            # Connect signals
            camera.frame_ready.connect(lambda frame: self.frame_ready.emit(camera_index, frame))
            
            self.cameras[camera_index] = camera
            self.camera_added.emit(camera_index)
            
            print(f"Camera {camera_index} added to manager")
            return True
            
        except Exception as e:
            print(f"Failed to add camera {camera_index}: {e}")
            return False
    
    def remove_camera(self, camera_index: int):
        """Remove a camera input"""
        if camera_index in self.cameras:
            camera = self.cameras[camera_index]
            camera.stop_capture()
            del self.cameras[camera_index]
            self.camera_removed.emit(camera_index)
            print(f"Camera {camera_index} removed from manager")
    
    def start_camera(self, camera_index: int, width: int = 1920, height: int = 1080) -> bool:
        """Start a specific camera"""
        if camera_index in self.cameras:
            target_fps = 60
            if self.fps_controller:
                target_fps = self.fps_controller.get_target_fps()
            
            return self.cameras[camera_index].start_capture(width, height, target_fps)
        return False
    
    def stop_camera(self, camera_index: int):
        """Stop a specific camera"""
        if camera_index in self.cameras:
            self.cameras[camera_index].stop_capture()
    
    def stop_all_cameras(self):
        """Stop all cameras"""
        for camera in self.cameras.values():
            camera.stop_capture()
    
    def _on_global_fps_changed(self, new_fps: int):
        """Handle global FPS change"""
        print(f"Camera manager updating to {new_fps} FPS")
        # Note: Individual cameras will be updated through the FPS controller
        # No need to restart cameras as they adapt automatically
    
    def get_available_cameras(self) -> list:
        """Get list of available camera indices"""
        available = []
        for i in range(10):  # Check first 10 camera indices
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    available.append(i)
                cap.release()
            except:
                continue
        return available
    
    def get_camera_stats(self, camera_index: int) -> Optional[dict]:
        """Get statistics for a specific camera"""
        if camera_index in self.cameras:
            return self.cameras[camera_index].stats.copy()
        return None

# Global camera manager instance
camera_manager = CameraManager()

def get_camera_manager() -> CameraManager:
    """Get the global camera manager"""
    return camera_manager
