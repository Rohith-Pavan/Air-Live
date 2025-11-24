"""
GoLive Studio - Qt Audio Manager
Cross-platform audio management using PyQt6 multimedia
"""

from typing import List, Optional
from PyQt6.QtCore import QTimer
from PyQt6.QtMultimedia import QMediaDevices, QAudioDevice, QAudioFormat, QAudioSource, QAudioSink

from .base_audio import BaseAudioManager, AudioDevice, AudioSettings, AudioDeviceType, AudioFormat as CustomAudioFormat


class QtAudioManager(BaseAudioManager):
    """
    Qt-based audio manager using PyQt6 multimedia
    Cross-platform fallback implementation
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Qt audio objects
        self._audio_sources: dict = {}
        self._audio_sinks: dict = {}
        
        # Level monitoring
        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._update_levels)
        
    def initialize(self) -> bool:
        """Initialize Qt audio system"""
        try:
            # Refresh device lists
            if not self.refresh_devices():
                return False
            
            # Start level monitoring
            self._level_timer.start(50)  # 20 FPS level updates
            
            self._initialized = True
            return True
            
        except Exception as e:
            self._emit_error(f"Qt audio initialization failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up Qt audio resources"""
        self._level_timer.stop()
        
        # Stop all audio streams
        for device_id in list(self._active_inputs.keys()):
            self.stop_input_monitoring(device_id)
        
        for device_id in list(self._active_outputs.keys()):
            self.stop_output_playback(device_id)
        
        self._audio_sources.clear()
        self._audio_sinks.clear()
        
        self._initialized = False
    
    def refresh_devices(self) -> bool:
        """Refresh Qt audio device lists"""
        try:
            self._input_devices.clear()
            self._output_devices.clear()
            
            # Get Qt audio devices
            qt_inputs = QMediaDevices.audioInputs()
            qt_outputs = QMediaDevices.audioOutputs()
            
            default_input = QMediaDevices.defaultAudioInput()
            default_output = QMediaDevices.defaultAudioOutput()
            
            # Convert Qt input devices
            for qt_device in qt_inputs:
                device = self._convert_qt_device(qt_device, AudioDeviceType.INPUT)
                device.is_default = (qt_device == default_input)
                self._input_devices.append(device)
            
            # Convert Qt output devices
            for qt_device in qt_outputs:
                device = self._convert_qt_device(qt_device, AudioDeviceType.OUTPUT)
                device.is_default = (qt_device == default_output)
                self._output_devices.append(device)
            
            self.device_list_changed.emit()
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to refresh Qt audio devices: {e}")
            return False
    
    def get_input_devices(self) -> List[AudioDevice]:
        """Get Qt input devices"""
        return self._input_devices.copy()
    
    def get_output_devices(self) -> List[AudioDevice]:
        """Get Qt output devices"""
        return self._output_devices.copy()
    
    def get_default_input_device(self) -> Optional[AudioDevice]:
        """Get default Qt input device"""
        for device in self._input_devices:
            if device.is_default:
                return device
        return self._input_devices[0] if self._input_devices else None
    
    def get_default_output_device(self) -> Optional[AudioDevice]:
        """Get default Qt output device"""
        for device in self._output_devices:
            if device.is_default:
                return device
        return self._output_devices[0] if self._output_devices else None
    
    def start_input_monitoring(self, device_id: str) -> bool:
        """Start Qt input monitoring"""
        try:
            if device_id in self._active_inputs:
                return True
            
            device = self.get_device_by_id(device_id)
            if not device:
                return False
            
            # Find Qt device
            qt_device = self._find_qt_device(device_id, AudioDeviceType.INPUT)
            if not qt_device:
                return False
            
            # Create audio format
            audio_format = self._create_qt_format()
            
            # Create audio source
            audio_source = QAudioSource(qt_device, audio_format)
            
            # Store reference
            self._audio_sources[device_id] = audio_source
            self._active_inputs[device_id] = {
                'device': device,
                'qt_device': qt_device,
                'source': audio_source,
                'volume': 1.0
            }
            
            self._monitoring_active = True
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to start Qt input monitoring: {e}")
            return False
    
    def stop_input_monitoring(self, device_id: str):
        """Stop Qt input monitoring"""
        try:
            if device_id not in self._active_inputs:
                return
            
            input_info = self._active_inputs[device_id]
            audio_source = input_info['source']
            
            if audio_source:
                audio_source.stop()
            
            del self._active_inputs[device_id]
            self._audio_sources.pop(device_id, None)
            
            if not self._active_inputs:
                self._monitoring_active = False
                
        except Exception as e:
            self._emit_error(f"Failed to stop Qt input monitoring: {e}")
    
    def start_output_playback(self, device_id: str) -> bool:
        """Start Qt output playback"""
        try:
            if device_id in self._active_outputs:
                return True
            
            device = self.get_device_by_id(device_id)
            if not device:
                return False
            
            # Find Qt device
            qt_device = self._find_qt_device(device_id, AudioDeviceType.OUTPUT)
            if not qt_device:
                return False
            
            # Create audio format
            audio_format = self._create_qt_format()
            
            # Create audio sink
            audio_sink = QAudioSink(qt_device, audio_format)
            
            # Store reference
            self._audio_sinks[device_id] = audio_sink
            self._active_outputs[device_id] = {
                'device': device,
                'qt_device': qt_device,
                'sink': audio_sink,
                'volume': 1.0
            }
            
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to start Qt output playback: {e}")
            return False
    
    def stop_output_playback(self, device_id: str):
        """Stop Qt output playback"""
        try:
            if device_id not in self._active_outputs:
                return
            
            output_info = self._active_outputs[device_id]
            audio_sink = output_info['sink']
            
            if audio_sink:
                audio_sink.stop()
            
            del self._active_outputs[device_id]
            self._audio_sinks.pop(device_id, None)
            
        except Exception as e:
            self._emit_error(f"Failed to stop Qt output playback: {e}")
    
    def set_input_volume(self, device_id: str, volume: float):
        """Set Qt input volume"""
        if device_id in self._active_inputs:
            self._active_inputs[device_id]['volume'] = max(0.0, min(1.0, volume))
            
            # Qt doesn't provide direct input volume control
            # Volume would need to be applied during audio processing
    
    def set_output_volume(self, device_id: str, volume: float):
        """Set Qt output volume"""
        if device_id in self._active_outputs:
            volume = max(0.0, min(1.0, volume))
            self._active_outputs[device_id]['volume'] = volume
            
            audio_sink = self._active_outputs[device_id]['sink']
            if audio_sink:
                audio_sink.setVolume(volume)
    
    def get_input_level(self, device_id: str) -> float:
        """Get Qt input level"""
        if device_id not in self._active_inputs:
            return 0.0
        
        # Qt doesn't provide direct level monitoring
        # This would need to be implemented with audio data analysis
        return 0.0
    
    def get_output_level(self, device_id: str) -> float:
        """Get Qt output level"""
        if device_id not in self._active_outputs:
            return 0.0
        
        # Qt doesn't provide direct level monitoring
        # This would need to be implemented with audio data analysis
        return 0.0
    
    def _convert_qt_device(self, qt_device: QAudioDevice, device_type: AudioDeviceType) -> AudioDevice:
        """Convert Qt audio device to our format"""
        return AudioDevice(
            id=qt_device.id().data().decode() if qt_device.id() else str(hash(qt_device.description())),
            name=qt_device.description(),
            device_type=device_type,
            sample_rates=[44100, 48000],  # Common rates
            channels=[1, 2],  # Mono and stereo
            formats=[CustomAudioFormat.PCM_16, CustomAudioFormat.FLOAT_32]
        )
    
    def _find_qt_device(self, device_id: str, device_type: AudioDeviceType) -> Optional[QAudioDevice]:
        """Find Qt device by ID"""
        if device_type == AudioDeviceType.INPUT:
            qt_devices = QMediaDevices.audioInputs()
        else:
            qt_devices = QMediaDevices.audioOutputs()
        
        for qt_device in qt_devices:
            qt_id = qt_device.id().data().decode() if qt_device.id() else str(hash(qt_device.description()))
            if qt_id == device_id:
                return qt_device
        
        return None
    
    def _create_qt_format(self) -> QAudioFormat:
        """Create Qt audio format from settings"""
        format = QAudioFormat()
        format.setSampleRate(self._settings.sample_rate)
        format.setChannelCount(self._settings.channels)
        
        # Map our format to Qt format
        if self._settings.format == CustomAudioFormat.PCM_16:
            format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        elif self._settings.format == CustomAudioFormat.FLOAT_32:
            format.setSampleFormat(QAudioFormat.SampleFormat.Float)
        else:
            format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        
        return format
    
    def _update_levels(self):
        """Update audio levels (timer callback)"""
        # Update input levels
        for device_id in self._active_inputs:
            level = self.get_input_level(device_id)
            self._emit_level_update(device_id, level)
        
        # Update output levels
        for device_id in self._active_outputs:
            level = self.get_output_level(device_id)
            self._emit_level_update(device_id, level)
