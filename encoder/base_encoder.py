"""
GoLive Studio - Base Encoder Abstract Interface
Defines the abstract interface for video encoders
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QSize
from PyQt6.QtGui import QImage


class EncoderType(Enum):
    """Encoder types"""
    SOFTWARE = "software"
    HARDWARE = "hardware"


class EncoderPreset(Enum):
    """Encoding presets (speed vs quality)"""
    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST = "veryfast"
    FASTER = "faster"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    SLOWER = "slower"
    VERYSLOW = "veryslow"


class EncoderProfile(Enum):
    """H.264 profiles"""
    BASELINE = "baseline"
    MAIN = "main"
    HIGH = "high"
    HIGH10 = "high10"


@dataclass
class EncoderSettings:
    """Encoder configuration settings"""
    # Video settings
    width: int = 1920
    height: int = 1080
    fps: int = 30
    bitrate_kbps: int = 6000
    keyframe_interval: int = 60  # GOP size
    
    # Quality settings
    preset: EncoderPreset = EncoderPreset.VERYFAST
    profile: EncoderProfile = EncoderProfile.HIGH
    crf: Optional[int] = None  # Constant Rate Factor (quality-based encoding)
    
    # Rate control
    max_bitrate_kbps: Optional[int] = None
    buffer_size_kbps: Optional[int] = None
    
    # Advanced settings
    b_frames: int = 3
    ref_frames: int = 3
    
    # Hardware-specific settings
    hardware_preset: Optional[str] = None
    low_latency: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for FFmpeg parameters"""
        return {
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'bitrate_kbps': self.bitrate_kbps,
            'keyframe_interval': self.keyframe_interval,
            'preset': self.preset.value,
            'profile': self.profile.value,
            'crf': self.crf,
            'max_bitrate_kbps': self.max_bitrate_kbps,
            'buffer_size_kbps': self.buffer_size_kbps,
            'b_frames': self.b_frames,
            'ref_frames': self.ref_frames,
            'hardware_preset': self.hardware_preset,
            'low_latency': self.low_latency
        }


@dataclass
class EncoderCapabilities:
    """Encoder capability information"""
    name: str
    encoder_type: EncoderType
    supported_formats: list
    max_resolution: tuple  # (width, height)
    max_fps: int
    supports_crf: bool = True
    supports_cbr: bool = True
    supports_vbr: bool = True
    hardware_acceleration: bool = False
    
    # Performance characteristics
    encoding_speed: str = "medium"  # slow, medium, fast
    quality_rating: str = "good"    # poor, good, excellent
    
    def __str__(self) -> str:
        return f"{self.name} ({self.encoder_type.value})"


class BaseEncoder(QObject, ABC):
    """
    Abstract base class for video encoders
    
    Provides interface for:
    - Encoder initialization and configuration
    - Frame encoding
    - Output stream management
    - Performance monitoring
    """
    
    # Signals
    frame_encoded = pyqtSignal(bytes)  # Encoded frame data
    error_occurred = pyqtSignal(str)   # Error message
    stats_updated = pyqtSignal(dict)   # Encoding statistics
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._settings = EncoderSettings()
        self._capabilities: Optional[EncoderCapabilities] = None
        self._initialized = False
        self._encoding = False
        
        # Statistics
        self._stats = {
            'frames_encoded': 0,
            'bytes_encoded': 0,
            'encoding_fps': 0.0,
            'average_bitrate': 0.0,
            'dropped_frames': 0
        }
        
        # Callbacks
        self._frame_callback: Optional[Callable[[bytes], None]] = None
        self._error_callback: Optional[Callable[[str], None]] = None
    
    @abstractmethod
    def get_capabilities(self) -> EncoderCapabilities:
        """Get encoder capabilities"""
        pass
    
    @abstractmethod
    def initialize(self, settings: EncoderSettings) -> bool:
        """Initialize encoder with settings"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up encoder resources"""
        pass
    
    @abstractmethod
    def start_encoding(self) -> bool:
        """Start encoding session"""
        pass
    
    @abstractmethod
    def stop_encoding(self):
        """Stop encoding session"""
        pass
    
    @abstractmethod
    def encode_frame(self, frame: QImage) -> bool:
        """
        Encode a single frame
        
        Args:
            frame: Input frame as QImage
            
        Returns:
            bool: Success status
        """
        pass
    
    @abstractmethod
    def flush(self):
        """Flush any remaining frames"""
        pass
    
    @abstractmethod
    def get_ffmpeg_args(self) -> list:
        """Get FFmpeg command line arguments for this encoder"""
        pass
    
    # Common interface methods
    
    def set_settings(self, settings: EncoderSettings):
        """Update encoder settings"""
        self._settings = settings
    
    def get_settings(self) -> EncoderSettings:
        """Get current encoder settings"""
        return self._settings
    
    def set_frame_callback(self, callback: Callable[[bytes], None]):
        """Set callback for encoded frame data"""
        self._frame_callback = callback
    
    def set_error_callback(self, callback: Callable[[str], None]):
        """Set callback for error messages"""
        self._error_callback = callback
    
    def get_stats(self) -> Dict[str, Any]:
        """Get encoding statistics"""
        return self._stats.copy()
    
    def reset_stats(self):
        """Reset encoding statistics"""
        self._stats = {
            'frames_encoded': 0,
            'bytes_encoded': 0,
            'encoding_fps': 0.0,
            'average_bitrate': 0.0,
            'dropped_frames': 0
        }
    
    def is_initialized(self) -> bool:
        """Check if encoder is initialized"""
        return self._initialized
    
    def is_encoding(self) -> bool:
        """Check if encoder is actively encoding"""
        return self._encoding
    
    def is_hardware_accelerated(self) -> bool:
        """Check if encoder uses hardware acceleration"""
        caps = self.get_capabilities()
        return caps.hardware_acceleration if caps else False
    
    def get_encoder_info(self) -> Dict[str, Any]:
        """Get comprehensive encoder information"""
        caps = self.get_capabilities()
        return {
            'name': caps.name if caps else 'Unknown',
            'type': caps.encoder_type.value if caps else 'unknown',
            'hardware_accelerated': self.is_hardware_accelerated(),
            'initialized': self._initialized,
            'encoding': self._encoding,
            'settings': self._settings.to_dict(),
            'stats': self._stats.copy(),
            'capabilities': caps.__dict__ if caps else {}
        }
    
    # Protected helper methods
    
    def _emit_frame(self, data: bytes):
        """Emit encoded frame data"""
        if self._frame_callback:
            self._frame_callback(data)
        self.frame_encoded.emit(data)
    
    def _emit_error(self, message: str):
        """Emit error message"""
        if self._error_callback:
            self._error_callback(message)
        self.error_occurred.emit(message)
    
    def _update_stats(self, **kwargs):
        """Update encoding statistics"""
        self._stats.update(kwargs)
        self.stats_updated.emit(self._stats.copy())
    
    def _validate_settings(self, settings: EncoderSettings) -> bool:
        """Validate encoder settings against capabilities"""
        caps = self.get_capabilities()
        if not caps:
            return True  # No validation possible
        
        # Check resolution
        max_w, max_h = caps.max_resolution
        if settings.width > max_w or settings.height > max_h:
            return False
        
        # Check FPS
        if settings.fps > caps.max_fps:
            return False
        
        return True
