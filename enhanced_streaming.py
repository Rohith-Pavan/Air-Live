#!/usr/bin/env python3
"""
Enhanced Streaming Module with Global FPS Control
Integrates with fps_controller for precise timing
"""

import subprocess
import threading
import time
import queue
import numpy as np
from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal
from fps_controller import get_fps_controller, FrameTimestamp
import cv2

class TimedFFmpegEncoder(QObject):
    """FFmpeg encoder with precise PTS timing control"""
    
    # Signals
    encoding_started = pyqtSignal()
    encoding_stopped = pyqtSignal()
    frame_encoded = pyqtSignal(int)  # frame number
    error_occurred = pyqtSignal(str)
    
    def __init__(self, output_url: str, width: int = 1920, height: int = 1080):
        super().__init__()
        
        self.output_url = output_url
        self.width = width
        self.height = height
        
        # FPS controller integration
        self.fps_controller = get_fps_controller()
        self.target_fps = self.fps_controller.get_target_fps()
        
        # FFmpeg process
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.encoding_thread: Optional[threading.Thread] = None
        
        # Frame queue with timing
        self.frame_queue = queue.Queue(maxsize=30)
        
        # Timing control
        self.pts_counter = 0
        self.time_base = 1.0 / self.target_fps
        self.start_time = 0.0
        
        # State
        self.is_encoding = False
        self.should_stop = False
        
        # Connect to FPS controller
        self.fps_controller.fps_changed.connect(self._on_fps_changed)
        self.fps_controller.frame_ready.connect(self._on_frame_ready)
    
    def _build_ffmpeg_command(self) -> list:
        """Build FFmpeg command with precise timing parameters"""
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{self.width}x{self.height}',
            '-r', str(self.target_fps),  # Input frame rate
            '-i', '-',  # Input from stdin
            
            # Video encoding settings
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', '23',
            '-maxrate', '6000k',
            '-bufsize', '12000k',
            '-g', str(self.target_fps * 2),  # GOP size
            '-keyint_min', str(self.target_fps),
            '-sc_threshold', '0',
            
            # Timing control
            '-vsync', 'cfr',  # Constant frame rate
            '-time_base', f'1/{self.target_fps}',
            '-fflags', '+genpts',
            
            # Output format
            '-f', 'flv' if 'rtmp' in self.output_url else 'mp4',
            self.output_url
        ]
        
        return cmd
    
    def start_encoding(self):
        """Start the FFmpeg encoding process"""
        if self.is_encoding:
            return
        
        try:
            # Reset timing
            self.pts_counter = 0
            self.start_time = self.fps_controller.get_current_time()
            self.should_stop = False
            
            # Build command
            cmd = self._build_ffmpeg_command()
            print(f"Starting FFmpeg encoder: {' '.join(cmd[:10])}...")
            
            # Start FFmpeg process
            self.ffmpeg_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Start encoding thread
            self.encoding_thread = threading.Thread(target=self._encoding_loop, daemon=True)
            self.encoding_thread.start()
            
            self.is_encoding = True
            self.encoding_started.emit()
            print(f"FFmpeg encoder started at {self.target_fps} FPS")
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to start encoding: {e}")
    
    def stop_encoding(self):
        """Stop the FFmpeg encoding process"""
        if not self.is_encoding:
            return
        
        self.should_stop = True
        
        # Close FFmpeg stdin
        if self.ffmpeg_process and self.ffmpeg_process.stdin:
            try:
                self.ffmpeg_process.stdin.close()
            except:
                pass
        
        # Wait for encoding thread
        if self.encoding_thread:
            self.encoding_thread.join(timeout=5.0)
        
        # Terminate FFmpeg process
        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait(timeout=5.0)
            except:
                try:
                    self.ffmpeg_process.kill()
                except:
                    pass
            self.ffmpeg_process = None
        
        self.is_encoding = False
        self.encoding_stopped.emit()
        print("FFmpeg encoder stopped")
    
    def _encoding_loop(self):
        """Main encoding loop with precise timing"""
        frame_interval = 1.0 / self.target_fps
        next_frame_time = self.start_time
        
        while not self.should_stop and self.ffmpeg_process:
            try:
                current_time = self.fps_controller.get_current_time()
                
                # Wait for next frame time
                if current_time < next_frame_time:
                    sleep_time = next_frame_time - current_time
                    if sleep_time > 0.001:  # Only sleep if significant
                        time.sleep(sleep_time)
                
                # Get frame from queue or use last frame
                frame_data = None
                try:
                    # Try to get the most recent frame
                    while not self.frame_queue.empty():
                        frame_data = self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
                
                if frame_data is not None:
                    # Encode frame with precise PTS
                    self._encode_frame(frame_data)
                    self.frame_encoded.emit(self.pts_counter)
                
                # Update timing
                next_frame_time += frame_interval
                self.pts_counter += 1
                
                # Prevent timing drift
                if next_frame_time < current_time - frame_interval:
                    next_frame_time = current_time
                
            except Exception as e:
                if not self.should_stop:
                    self.error_occurred.emit(f"Encoding error: {e}")
                break
    
    def _encode_frame(self, frame_data: np.ndarray):
        """Encode a single frame with proper timing"""
        if not self.ffmpeg_process or not self.ffmpeg_process.stdin:
            return
        
        try:
            # Ensure frame is correct size and format
            if frame_data.shape[:2] != (self.height, self.width):
                frame_data = cv2.resize(frame_data, (self.width, self.height))
            
            # Write frame to FFmpeg stdin
            self.ffmpeg_process.stdin.write(frame_data.tobytes())
            self.ffmpeg_process.stdin.flush()
            
        except Exception as e:
            if not self.should_stop:
                print(f"Frame encoding error: {e}")
    
    def add_frame(self, frame: np.ndarray):
        """Add frame to encoding queue"""
        if not self.is_encoding:
            return
        
        try:
            # Add to queue, dropping old frames if full
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()  # Drop oldest frame
                except queue.Empty:
                    pass
            
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            pass  # Queue full, drop frame
    
    def _on_fps_changed(self, new_fps: int):
        """Handle FPS change from controller"""
        if self.target_fps != new_fps:
            print(f"Encoder FPS changing: {self.target_fps} -> {new_fps}")
            
            was_encoding = self.is_encoding
            
            # Stop current encoding
            if was_encoding:
                self.stop_encoding()
            
            # Update settings
            self.target_fps = new_fps
            self.time_base = 1.0 / new_fps
            
            # Restart encoding if it was running
            if was_encoding:
                self.start_encoding()
    
    def _on_frame_ready(self, timestamped_frame: FrameTimestamp):
        """Handle frame ready from FPS controller"""
        if self.is_encoding and hasattr(timestamped_frame, 'frame_data'):
            self.add_frame(timestamped_frame.frame_data)

class EnhancedStreamingManager(QObject):
    """Enhanced streaming manager with global FPS control"""
    
    # Signals
    stream_started = pyqtSignal(str)  # stream URL
    stream_stopped = pyqtSignal()
    stream_error = pyqtSignal(str)
    stats_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
        # FPS controller
        self.fps_controller = get_fps_controller()
        
        # Encoders
        self.encoders: Dict[str, TimedFFmpegEncoder] = {}
        
        # Statistics
        self.stats = {
            'active_streams': 0,
            'total_frames_encoded': 0,
            'encoding_fps': 0.0,
            'last_frame_time': 0.0
        }
        
        # Connect to FPS controller
        self.fps_controller.timing_stats.connect(self._update_stats)
    
    def start_stream(self, stream_url: str, width: int = 1920, height: int = 1080) -> bool:
        """Start streaming to URL"""
        try:
            if stream_url in self.encoders:
                print(f"Stream already active: {stream_url}")
                return True
            
            # Create encoder
            encoder = TimedFFmpegEncoder(stream_url, width, height)
            encoder.encoding_started.connect(lambda: self.stream_started.emit(stream_url))
            encoder.encoding_stopped.connect(self.stream_stopped.emit)
            encoder.error_occurred.connect(self.stream_error.emit)
            
            # Start encoding
            encoder.start_encoding()
            
            self.encoders[stream_url] = encoder
            self.stats['active_streams'] = len(self.encoders)
            
            print(f"Started stream: {stream_url}")
            return True
            
        except Exception as e:
            self.stream_error.emit(f"Failed to start stream: {e}")
            return False
    
    def stop_stream(self, stream_url: str):
        """Stop streaming to URL"""
        if stream_url in self.encoders:
            encoder = self.encoders[stream_url]
            encoder.stop_encoding()
            del self.encoders[stream_url]
            
            self.stats['active_streams'] = len(self.encoders)
            print(f"Stopped stream: {stream_url}")
    
    def stop_all_streams(self):
        """Stop all active streams"""
        for stream_url in list(self.encoders.keys()):
            self.stop_stream(stream_url)
    
    def add_frame_to_all_streams(self, frame: np.ndarray):
        """Add frame to all active streams"""
        for encoder in self.encoders.values():
            encoder.add_frame(frame)
    
    def _update_stats(self, timing_stats: dict):
        """Update streaming statistics"""
        self.stats.update({
            'encoding_fps': self.fps_controller.get_target_fps(),
            'last_frame_time': timing_stats.get('last_frame_time', 0.0)
        })
        
        # Count total encoded frames
        total_frames = sum(
            encoder.pts_counter for encoder in self.encoders.values()
        )
        self.stats['total_frames_encoded'] = total_frames
        
        self.stats_updated.emit(self.stats.copy())
    
    def get_active_streams(self) -> list:
        """Get list of active stream URLs"""
        return list(self.encoders.keys())
    
    def is_streaming(self) -> bool:
        """Check if any streams are active"""
        return len(self.encoders) > 0

# Global streaming manager instance
enhanced_streaming_manager = EnhancedStreamingManager()

def get_streaming_manager() -> EnhancedStreamingManager:
    """Get the global streaming manager"""
    return enhanced_streaming_manager
