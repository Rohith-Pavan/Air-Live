"""
GoLive Studio - Base Audio Abstract Interface
Defines the abstract interface for cross-platform audio management
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal


class AudioDeviceType(Enum):
    """Audio device types"""
    INPUT = "input"
    OUTPUT = "output"


class AudioFormat(Enum):
    """Audio format types"""
    PCM_16 = "pcm_s16le"
    PCM_24 = "pcm_s24le"
    PCM_32 = "pcm_s32le"
    FLOAT_32 = "pcm_f32le"


@dataclass
class AudioDevice:
    """Audio device information"""
    id: str
    name: str
    device_type: AudioDeviceType
    is_default: bool = False
    sample_rates: List[int] = None
    channels: List[int] = None
    formats: List[AudioFormat] = None
    
    def __post_init__(self):
        if self.sample_rates is None:
            self.sample_rates = [44100, 48000]
        if self.channels is None:
            self.channels = [1, 2]
        if self.formats is None:
            self.formats = [AudioFormat.PCM_16, AudioFormat.FLOAT_32]
    
    def __str__(self) -> str:
        default_str = " (Default)" if self.is_default else ""
        return f"{self.name}{default_str}"


@dataclass
class AudioSettings:
    """Audio configuration settings"""
    sample_rate: int = 48000
    channels: int = 2
    format: AudioFormat = AudioFormat.FLOAT_32
    buffer_size: int = 1024
    
    # Device settings
    input_device_id: Optional[str] = None
    output_device_id: Optional[str] = None
    
    # Monitoring settings
    monitor_enabled: bool = True
    monitor_volume: float = 1.0
    
    # Processing settings
    noise_gate_enabled: bool = False
    noise_gate_threshold: float = -40.0
    compressor_enabled: bool = False
    compressor_ratio: float = 3.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'format': self.format.value,
            'buffer_size': self.buffer_size,
            'input_device_id': self.input_device_id,
            'output_device_id': self.output_device_id,
            'monitor_enabled': self.monitor_enabled,
            'monitor_volume': self.monitor_volume,
            'noise_gate_enabled': self.noise_gate_enabled,
            'noise_gate_threshold': self.noise_gate_threshold,
            'compressor_enabled': self.compressor_enabled,
            'compressor_ratio': self.compressor_ratio
        }


class BaseAudioManager(QObject, ABC):
    """
    Abstract base class for audio management
    
    Provides interface for:
    - Device enumeration and selection
    - Audio capture and playback
    - Level monitoring
    - Audio processing effects
    """
    
    # Signals
    device_list_changed = pyqtSignal()
    level_updated = pyqtSignal(str, float)  # device_id, level
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._settings = AudioSettings()
        self._initialized = False
        self._monitoring_active = False
        
        # Device lists
        self._input_devices: List[AudioDevice] = []
        self._output_devices: List[AudioDevice] = []
        
        # Active streams
        self._active_inputs: Dict[str, Any] = {}
        self._active_outputs: Dict[str, Any] = {}
        
        # Callbacks
        self._level_callbacks: Dict[str, Callable[[float], None]] = {}
        self._audio_callbacks: Dict[str, Callable[[bytes], None]] = {}
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize audio system"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up audio resources"""
        pass
    
    @abstractmethod
    def refresh_devices(self) -> bool:
        """Refresh device lists"""
        pass
    
    @abstractmethod
    def get_input_devices(self) -> List[AudioDevice]:
        """Get available input devices"""
        pass
    
    @abstractmethod
    def get_output_devices(self) -> List[AudioDevice]:
        """Get available output devices"""
        pass
    
    @abstractmethod
    def get_default_input_device(self) -> Optional[AudioDevice]:
        """Get default input device"""
        pass
    
    @abstractmethod
    def get_default_output_device(self) -> Optional[AudioDevice]:
        """Get default output device"""
        pass
    
    @abstractmethod
    def start_input_monitoring(self, device_id: str) -> bool:
        """Start monitoring input device"""
        pass
    
    @abstractmethod
    def stop_input_monitoring(self, device_id: str):
        """Stop monitoring input device"""
        pass
    
    @abstractmethod
    def start_output_playback(self, device_id: str) -> bool:
        """Start output playback"""
        pass
    
    @abstractmethod
    def stop_output_playback(self, device_id: str):
        """Stop output playback"""
        pass
    
    @abstractmethod
    def set_input_volume(self, device_id: str, volume: float):
        """Set input volume (0.0 to 1.0)"""
        pass
    
    @abstractmethod
    def set_output_volume(self, device_id: str, volume: float):
        """Set output volume (0.0 to 1.0)"""
        pass
    
    @abstractmethod
    def get_input_level(self, device_id: str) -> float:
        """Get current input level"""
        pass
    
    @abstractmethod
    def get_output_level(self, device_id: str) -> float:
        """Get current output level"""
        pass
    
    # Common interface methods
    
    def set_settings(self, settings: AudioSettings):
        """Update audio settings"""
        self._settings = settings
    
    def get_settings(self) -> AudioSettings:
        """Get current audio settings"""
        return self._settings
    
    def set_level_callback(self, device_id: str, callback: Callable[[float], None]):
        """Set level monitoring callback"""
        self._level_callbacks[device_id] = callback
    
    def set_audio_callback(self, device_id: str, callback: Callable[[bytes], None]):
        """Set audio data callback"""
        self._audio_callbacks[device_id] = callback
    
    def remove_callbacks(self, device_id: str):
        """Remove callbacks for device"""
        self._level_callbacks.pop(device_id, None)
        self._audio_callbacks.pop(device_id, None)
    
    def is_initialized(self) -> bool:
        """Check if audio system is initialized"""
        return self._initialized
    
    def is_monitoring_active(self) -> bool:
        """Check if monitoring is active"""
        return self._monitoring_active
    
    def get_device_by_id(self, device_id: str) -> Optional[AudioDevice]:
        """Get device by ID"""
        for device in self._input_devices + self._output_devices:
            if device.id == device_id:
                return device
        return None
    
    def get_device_by_name(self, name: str, device_type: AudioDeviceType) -> Optional[AudioDevice]:
        """Get device by name and type"""
        devices = self._input_devices if device_type == AudioDeviceType.INPUT else self._output_devices
        for device in devices:
            if device.name == name:
                return device
        return None
    
    def get_audio_info(self) -> Dict[str, Any]:
        """Get comprehensive audio system information"""
        return {
            'initialized': self._initialized,
            'monitoring_active': self._monitoring_active,
            'settings': self._settings.to_dict(),
            'input_devices': len(self._input_devices),
            'output_devices': len(self._output_devices),
            'active_inputs': list(self._active_inputs.keys()),
            'active_outputs': list(self._active_outputs.keys())
        }
    
    # Protected helper methods
    
    def _emit_level_update(self, device_id: str, level: float):
        """Emit level update"""
        if device_id in self._level_callbacks:
            self._level_callbacks[device_id](level)
        self.level_updated.emit(device_id, level)
    
    def _emit_audio_data(self, device_id: str, data: bytes):
        """Emit audio data"""
        if device_id in self._audio_callbacks:
            self._audio_callbacks[device_id](data)
    
    def _emit_error(self, message: str):
        """Emit error message"""
        self.error_occurred.emit(message)
    
    def _validate_device(self, device: AudioDevice) -> bool:
        """Validate device configuration"""
        if not device.id or not device.name:
            return False
        
        if not device.sample_rates or not device.channels:
            return False
        
        return True
