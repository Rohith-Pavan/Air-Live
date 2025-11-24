"""
GoLive Studio - macOS Audio Manager
macOS-specific audio management using Core Audio
"""

import subprocess
from typing import List, Optional
from .base_audio import BaseAudioManager, AudioDevice, AudioDeviceType, AudioFormat


class MacOSAudioManager(BaseAudioManager):
    """
    macOS-specific audio manager using Core Audio
    Provides enhanced audio device control on macOS
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def initialize(self) -> bool:
        """Initialize macOS audio system"""
        try:
            if not self.refresh_devices():
                return False
            
            self._initialized = True
            return True
            
        except Exception as e:
            self._emit_error(f"macOS audio initialization failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up macOS audio resources"""
        # Stop all monitoring
        for device_id in list(self._active_inputs.keys()):
            self.stop_input_monitoring(device_id)
        
        self._initialized = False
    
    def refresh_devices(self) -> bool:
        """Refresh macOS audio devices using system_profiler"""
        try:
            self._input_devices.clear()
            self._output_devices.clear()
            
            # Use system_profiler to get audio devices
            result = subprocess.run([
                'system_profiler', 'SPAudioDataType', '-json'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                self._parse_system_profiler_audio(data)
            
            # Fallback to basic device enumeration
            if not self._input_devices and not self._output_devices:
                self._enumerate_basic_devices()
            
            self.device_list_changed.emit()
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to refresh macOS audio devices: {e}")
            # Try fallback enumeration
            try:
                self._enumerate_basic_devices()
                return True
            except:
                return False
    
    def get_input_devices(self) -> List[AudioDevice]:
        """Get macOS input devices"""
        return self._input_devices.copy()
    
    def get_output_devices(self) -> List[AudioDevice]:
        """Get macOS output devices"""
        return self._output_devices.copy()
    
    def get_default_input_device(self) -> Optional[AudioDevice]:
        """Get default macOS input device"""
        for device in self._input_devices:
            if device.is_default:
                return device
        return self._input_devices[0] if self._input_devices else None
    
    def get_default_output_device(self) -> Optional[AudioDevice]:
        """Get default macOS output device"""
        for device in self._output_devices:
            if device.is_default:
                return device
        return self._output_devices[0] if self._output_devices else None
    
    def start_input_monitoring(self, device_id: str) -> bool:
        """Start macOS input monitoring"""
        try:
            if device_id in self._active_inputs:
                return True
            
            device = self.get_device_by_id(device_id)
            if not device:
                return False
            
            # Store active input
            self._active_inputs[device_id] = {
                'device': device,
                'volume': 1.0,
                'monitoring': True
            }
            
            self._monitoring_active = True
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to start macOS input monitoring: {e}")
            return False
    
    def stop_input_monitoring(self, device_id: str):
        """Stop macOS input monitoring"""
        try:
            if device_id in self._active_inputs:
                del self._active_inputs[device_id]
            
            if not self._active_inputs:
                self._monitoring_active = False
                
        except Exception as e:
            self._emit_error(f"Failed to stop macOS input monitoring: {e}")
    
    def start_output_playback(self, device_id: str) -> bool:
        """Start macOS output playback"""
        try:
            if device_id in self._active_outputs:
                return True
            
            device = self.get_device_by_id(device_id)
            if not device:
                return False
            
            self._active_outputs[device_id] = {
                'device': device,
                'volume': 1.0
            }
            
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to start macOS output playback: {e}")
            return False
    
    def stop_output_playback(self, device_id: str):
        """Stop macOS output playback"""
        if device_id in self._active_outputs:
            del self._active_outputs[device_id]
    
    def set_input_volume(self, device_id: str, volume: float):
        """Set macOS input volume"""
        if device_id in self._active_inputs:
            self._active_inputs[device_id]['volume'] = max(0.0, min(1.0, volume))
    
    def set_output_volume(self, device_id: str, volume: float):
        """Set macOS output volume"""
        if device_id in self._active_outputs:
            self._active_outputs[device_id]['volume'] = max(0.0, min(1.0, volume))
    
    def get_input_level(self, device_id: str) -> float:
        """Get macOS input level"""
        # Placeholder - would need Core Audio implementation
        return 0.0
    
    def get_output_level(self, device_id: str) -> float:
        """Get macOS output level"""
        # Placeholder - would need Core Audio implementation
        return 0.0
    
    def _parse_system_profiler_audio(self, data: dict):
        """Parse system_profiler audio data"""
        try:
            audio_data = data.get('SPAudioDataType', [])
            
            for item in audio_data:
                if 'coreaudio_device_input' in item:
                    # Input device
                    for input_item in item['coreaudio_device_input']:
                        device = self._create_device_from_profiler(input_item, AudioDeviceType.INPUT)
                        if device:
                            self._input_devices.append(device)
                
                if 'coreaudio_device_output' in item:
                    # Output device
                    for output_item in item['coreaudio_device_output']:
                        device = self._create_device_from_profiler(output_item, AudioDeviceType.OUTPUT)
                        if device:
                            self._output_devices.append(device)
                            
        except Exception as e:
            print(f"Error parsing system profiler data: {e}")
    
    def _create_device_from_profiler(self, item: dict, device_type: AudioDeviceType) -> Optional[AudioDevice]:
        """Create AudioDevice from system_profiler item"""
        try:
            name = item.get('_name', 'Unknown Device')
            
            # Generate ID from name
            device_id = f"macos_{device_type.value}_{hash(name) & 0x7FFFFFFF}"
            
            return AudioDevice(
                id=device_id,
                name=name,
                device_type=device_type,
                sample_rates=[44100, 48000, 96000],
                channels=[1, 2] if device_type == AudioDeviceType.INPUT else [1, 2, 6, 8],
                formats=[AudioFormat.PCM_16, AudioFormat.PCM_24, AudioFormat.FLOAT_32]
            )
            
        except Exception:
            return None
    
    def _enumerate_basic_devices(self):
        """Basic device enumeration fallback"""
        # Add basic built-in devices
        self._input_devices.append(AudioDevice(
            id="macos_input_builtin",
            name="Built-in Microphone",
            device_type=AudioDeviceType.INPUT,
            is_default=True
        ))
        
        self._output_devices.append(AudioDevice(
            id="macos_output_builtin",
            name="Built-in Output",
            device_type=AudioDeviceType.OUTPUT,
            is_default=True
        ))
    
    def get_avfoundation_device_index(self, device_name: str) -> Optional[str]:
        """Get AVFoundation device index for FFmpeg"""
        try:
            # List AVFoundation devices
            result = subprocess.run([
                'ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', ''
            ], capture_output=True, text=True, timeout=10)
            
            lines = result.stderr.split('\n')
            for line in lines:
                if 'AVFoundation audio devices:' in line:
                    continue
                if f'] {device_name}' in line:
                    # Extract device index
                    start = line.find('[') + 1
                    end = line.find(']')
                    if start > 0 and end > start:
                        return line[start:end]
            
            return None
            
        except Exception:
            return None
