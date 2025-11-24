#!/usr/bin/env python3
"""
Enhanced Audio Synchronization with Global FPS Control
Handles audio input/output synchronization with master clock timing
"""

import numpy as np
import threading
import time
import queue
from typing import Optional, Callable, Dict, Any
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtMultimedia import QAudioFormat, QAudioSource, QAudioSink, QMediaDevices

# Import FPS controller for global timing
try:
    from fps_controller import get_fps_controller
    FPS_CONTROLLER_AVAILABLE = True
except ImportError:
    FPS_CONTROLLER_AVAILABLE = False
    print("FPS Controller not available for audio sync")

class AudioResampler:
    """High-quality audio resampler for synchronization"""
    
    def __init__(self, input_rate: int, output_rate: int, channels: int = 2):
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.channels = channels
        self.ratio = output_rate / input_rate
        
        # Simple linear interpolation buffer
        self.last_sample = np.zeros(channels, dtype=np.float32)
        self.fractional_delay = 0.0
        
    def resample(self, input_data: np.ndarray) -> np.ndarray:
        """Resample audio data to target rate"""
        if self.input_rate == self.output_rate:
            return input_data
        
        try:
            # Simple linear interpolation resampling
            input_length = len(input_data)
            output_length = int(input_length * self.ratio)
            
            # Create output array
            output_data = np.zeros((output_length, self.channels), dtype=np.float32)
            
            for i in range(output_length):
                # Calculate source position
                src_pos = i / self.ratio
                src_idx = int(src_pos)
                src_frac = src_pos - src_idx
                
                if src_idx < input_length - 1:
                    # Linear interpolation
                    sample1 = input_data[src_idx]
                    sample2 = input_data[src_idx + 1]
                    output_data[i] = sample1 + src_frac * (sample2 - sample1)
                elif src_idx < input_length:
                    output_data[i] = input_data[src_idx]
                else:
                    output_data[i] = self.last_sample
            
            # Update last sample
            if input_length > 0:
                self.last_sample = input_data[-1]
            
            return output_data
            
        except Exception as e:
            print(f"Resampling error: {e}")
            return input_data

class EnhancedAudioSync(QObject):
    """Enhanced audio synchronization with master clock"""
    
    # Signals
    audio_ready = pyqtSignal(np.ndarray)  # Synchronized audio data
    sync_stats = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, sample_rate: int = 48000, channels: int = 2):
        super().__init__()
        
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_size = 1024  # Samples per frame
        
        # FPS controller integration
        self.fps_controller = None
        self.master_clock_time = 0.0
        if FPS_CONTROLLER_AVAILABLE:
            self.fps_controller = get_fps_controller()
            self.fps_controller.fps_changed.connect(self._on_fps_changed)
        
        # Audio format
        self.audio_format = QAudioFormat()
        self.audio_format.setSampleRate(sample_rate)
        self.audio_format.setChannelCount(channels)
        self.audio_format.setSampleFormat(QAudioFormat.SampleFormat.Float)
        
        # Audio devices
        self.audio_source: Optional[QAudioSource] = None
        self.audio_sink: Optional[QAudioSink] = None
        
        # Synchronization
        self.audio_buffer = queue.Queue(maxsize=100)
        self.resampler = AudioResampler(sample_rate, sample_rate, channels)
        
        # Timing control
        self.target_fps = 60
        self.samples_per_frame = sample_rate // self.target_fps
        self.audio_time_offset = 0.0
        
        # Statistics
        self.stats = {
            'buffer_size': 0,
            'drift_ms': 0.0,
            'resampling_ratio': 1.0,
            'frames_processed': 0,
            'underruns': 0,
            'overruns': 0
        }
        
        # Processing thread
        self.processing_thread: Optional[threading.Thread] = None
        self.should_stop = False
        self.is_running = False
        
        # Stats timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(1000)  # Update every second
    
    def start_sync(self) -> bool:
        """Start audio synchronization"""
        if self.is_running:
            return True
        
        try:
            # Initialize audio devices
            if not self._init_audio_devices():
                return False
            
            # Start processing thread
            self.should_stop = False
            self.processing_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.processing_thread.start()
            
            self.is_running = True
            print(f"Audio sync started: {self.sample_rate}Hz, {self.channels}ch")
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Audio sync start error: {e}")
            return False
    
    def stop_sync(self):
        """Stop audio synchronization"""
        if not self.is_running:
            return
        
        self.should_stop = True
        
        # Wait for processing thread
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        
        # Clean up audio devices
        if self.audio_source:
            self.audio_source.stop()
            self.audio_source = None
        
        if self.audio_sink:
            self.audio_sink.stop()
            self.audio_sink = None
        
        self.is_running = False
        print("Audio sync stopped")
    
    def _init_audio_devices(self) -> bool:
        """Initialize audio input/output devices"""
        try:
            # Get default audio devices
            input_device = QMediaDevices.defaultAudioInput()
            output_device = QMediaDevices.defaultAudioOutput()
            
            if not input_device.isNull():
                self.audio_source = QAudioSource(input_device, self.audio_format)
                self.audio_source.setBufferSize(self.frame_size * 4)  # 4 frames buffer
            
            if not output_device.isNull():
                self.audio_sink = QAudioSink(output_device, self.audio_format)
                self.audio_sink.setBufferSize(self.frame_size * 4)
            
            return True
            
        except Exception as e:
            print(f"Audio device initialization error: {e}")
            return False
    
    def _sync_loop(self):
        """Main audio synchronization loop"""
        frame_duration = self.samples_per_frame / self.sample_rate
        next_frame_time = time.monotonic()
        
        while not self.should_stop:
            try:
                current_time = time.monotonic()
                
                # Get master clock time if available
                if self.fps_controller:
                    self.master_clock_time = self.fps_controller.get_current_time()
                else:
                    self.master_clock_time = current_time
                
                # Wait for next frame time
                if current_time < next_frame_time:
                    sleep_time = next_frame_time - current_time
                    if sleep_time > 0.001:
                        time.sleep(sleep_time)
                
                # Process audio frame
                self._process_audio_frame()
                
                # Update timing
                next_frame_time += frame_duration
                
                # Prevent timing drift
                if next_frame_time < current_time - frame_duration:
                    next_frame_time = current_time
                
            except Exception as e:
                if not self.should_stop:
                    print(f"Audio sync loop error: {e}")
                break
    
    def _process_audio_frame(self):
        """Process a single audio frame with synchronization"""
        try:
            # Generate or capture audio data
            audio_data = self._generate_audio_frame()
            
            if audio_data is not None:
                # Apply synchronization
                synced_data = self._apply_sync(audio_data)
                
                # Emit synchronized audio
                self.audio_ready.emit(synced_data)
                self.stats['frames_processed'] += 1
            
        except Exception as e:
            print(f"Audio frame processing error: {e}")
    
    def _generate_audio_frame(self) -> Optional[np.ndarray]:
        """Generate or capture audio frame"""
        try:
            # For now, generate silence (can be replaced with actual capture)
            audio_frame = np.zeros((self.samples_per_frame, self.channels), dtype=np.float32)
            return audio_frame
            
        except Exception as e:
            print(f"Audio generation error: {e}")
            return None
    
    def _apply_sync(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply synchronization to audio data"""
        try:
            # Calculate timing drift
            expected_time = self.stats['frames_processed'] * (self.samples_per_frame / self.sample_rate)
            actual_time = self.master_clock_time
            drift = actual_time - expected_time
            
            # Update statistics
            self.stats['drift_ms'] = drift * 1000.0
            
            # Apply drift correction if significant
            if abs(drift) > 0.01:  # 10ms threshold
                # Adjust resampling ratio to correct drift
                correction_factor = 1.0 + (drift * 0.1)  # Gentle correction
                target_rate = int(self.sample_rate * correction_factor)
                
                # Update resampler
                self.resampler = AudioResampler(self.sample_rate, target_rate, self.channels)
                self.stats['resampling_ratio'] = correction_factor
                
                # Resample audio
                audio_data = self.resampler.resample(audio_data)
            
            return audio_data
            
        except Exception as e:
            print(f"Audio sync error: {e}")
            return audio_data
    
    def _on_fps_changed(self, new_fps: int):
        """Handle FPS change from global controller"""
        self.target_fps = new_fps
        self.samples_per_frame = self.sample_rate // new_fps
        
        print(f"Audio sync updated to {new_fps} FPS ({self.samples_per_frame} samples/frame)")
    
    def _update_stats(self):
        """Update synchronization statistics"""
        self.stats['buffer_size'] = self.audio_buffer.qsize()
        self.sync_stats.emit(self.stats.copy())
    
    def add_audio_data(self, data: np.ndarray):
        """Add audio data to processing queue"""
        try:
            if not self.audio_buffer.full():
                self.audio_buffer.put_nowait(data)
            else:
                # Buffer full, drop oldest data
                try:
                    self.audio_buffer.get_nowait()
                    self.audio_buffer.put_nowait(data)
                    self.stats['overruns'] += 1
                except queue.Empty:
                    pass
        except queue.Full:
            self.stats['overruns'] += 1
    
    def get_audio_data(self) -> Optional[np.ndarray]:
        """Get synchronized audio data"""
        try:
            return self.audio_buffer.get_nowait()
        except queue.Empty:
            self.stats['underruns'] += 1
            return None

class AudioSyncManager(QObject):
    """Manager for audio synchronization across multiple inputs/outputs"""
    
    # Signals
    sync_started = pyqtSignal()
    sync_stopped = pyqtSignal()
    stats_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
        # Audio sync instances
        self.audio_syncs: Dict[str, EnhancedAudioSync] = {}
        
        # Global statistics
        self.global_stats = {
            'active_syncs': 0,
            'total_drift_ms': 0.0,
            'avg_drift_ms': 0.0
        }
        
        # FPS controller integration
        self.fps_controller = None
        if FPS_CONTROLLER_AVAILABLE:
            self.fps_controller = get_fps_controller()
            self.fps_controller.fps_changed.connect(self._on_global_fps_changed)
    
    def add_audio_sync(self, sync_id: str, sample_rate: int = 48000, channels: int = 2) -> bool:
        """Add an audio sync instance"""
        try:
            if sync_id not in self.audio_syncs:
                audio_sync = EnhancedAudioSync(sample_rate, channels)
                audio_sync.sync_stats.connect(self._on_sync_stats)
                
                self.audio_syncs[sync_id] = audio_sync
                self.global_stats['active_syncs'] = len(self.audio_syncs)
                
                print(f"Audio sync added: {sync_id}")
                return True
            return True
            
        except Exception as e:
            print(f"Failed to add audio sync {sync_id}: {e}")
            return False
    
    def remove_audio_sync(self, sync_id: str):
        """Remove an audio sync instance"""
        if sync_id in self.audio_syncs:
            audio_sync = self.audio_syncs[sync_id]
            audio_sync.stop_sync()
            del self.audio_syncs[sync_id]
            
            self.global_stats['active_syncs'] = len(self.audio_syncs)
            print(f"Audio sync removed: {sync_id}")
    
    def start_all_syncs(self):
        """Start all audio sync instances"""
        for audio_sync in self.audio_syncs.values():
            audio_sync.start_sync()
        
        if self.audio_syncs:
            self.sync_started.emit()
    
    def stop_all_syncs(self):
        """Stop all audio sync instances"""
        for audio_sync in self.audio_syncs.values():
            audio_sync.stop_sync()
        
        if self.audio_syncs:
            self.sync_stopped.emit()
    
    def _on_sync_stats(self, stats: dict):
        """Handle statistics from individual sync instances"""
        # Calculate global statistics
        total_drift = sum(
            sync.stats.get('drift_ms', 0.0) 
            for sync in self.audio_syncs.values()
        )
        
        self.global_stats['total_drift_ms'] = total_drift
        self.global_stats['avg_drift_ms'] = (
            total_drift / len(self.audio_syncs) if self.audio_syncs else 0.0
        )
        
        self.stats_updated.emit(self.global_stats.copy())
    
    def _on_global_fps_changed(self, new_fps: int):
        """Handle global FPS change"""
        print(f"Audio sync manager updating to {new_fps} FPS")
        # Individual sync instances will be updated automatically

# Global audio sync manager
audio_sync_manager = AudioSyncManager()

def get_audio_sync_manager() -> AudioSyncManager:
    """Get the global audio sync manager"""
    return audio_sync_manager
