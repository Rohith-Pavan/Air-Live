"""
GoLive Studio - NVENC Hardware Encoder
NVIDIA hardware H.264 encoding
"""

import subprocess
import sys
from typing import Optional
from PyQt6.QtGui import QImage

from .base_encoder import BaseEncoder, EncoderSettings, EncoderCapabilities, EncoderType


class NVENCEncoder(BaseEncoder):
    """
    NVIDIA NVENC hardware encoder
    Provides GPU-accelerated H.264 encoding on NVIDIA GPUs
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._gpu_available = self._check_nvenc_support()
        
    def _check_nvenc_support(self) -> bool:
        """Check if NVENC is available on the system"""
        try:
            # Try to run ffmpeg with nvenc to check availability
            result = subprocess.run([
                'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                '-c:v', 'h264_nvenc', '-f', 'null', '-'
            ], capture_output=True, timeout=10)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def get_capabilities(self) -> EncoderCapabilities:
        """Get NVENC encoder capabilities"""
        return EncoderCapabilities(
            name="h264_nvenc",
            encoder_type=EncoderType.HARDWARE,
            supported_formats=["h264", "mp4", "flv"],
            max_resolution=(7680, 4320),  # Depends on GPU generation
            max_fps=240,  # High FPS support
            supports_crf=False,  # NVENC doesn't support CRF
            supports_cbr=True,
            supports_vbr=True,
            hardware_acceleration=True,
            encoding_speed="fast",
            quality_rating="good"
        )
    
    def initialize(self, settings: EncoderSettings) -> bool:
        """Initialize NVENC encoder"""
        try:
            if not self._gpu_available:
                self._emit_error("NVENC not available on this system")
                return False
            
            if not self._validate_settings(settings):
                self._emit_error("Invalid NVENC settings")
                return False
            
            self._settings = settings
            self._capabilities = self.get_capabilities()
            self._initialized = True
            
            return True
            
        except Exception as e:
            self._emit_error(f"NVENC initialization failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up NVENC encoder"""
        self.stop_encoding()
        self._initialized = False
    
    def start_encoding(self) -> bool:
        """Start NVENC encoding session"""
        if not self._initialized:
            self._emit_error("NVENC encoder not initialized")
            return False
        
        if self._encoding:
            return True
        
        try:
            self._encoding = True
            self.reset_stats()
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to start NVENC encoding: {e}")
            self._encoding = False
            return False
    
    def stop_encoding(self):
        """Stop NVENC encoding session"""
        self._encoding = False
    
    def encode_frame(self, frame: QImage) -> bool:
        """Encode frame using NVENC"""
        if not self._encoding or not frame or frame.isNull():
            return False
        
        try:
            # NVENC frame encoding would be handled by FFmpeg process
            # This is a placeholder for the actual implementation
            
            # Update stats
            self._stats['frames_encoded'] += 1
            self._update_stats(frames_encoded=self._stats['frames_encoded'])
            
            return True
            
        except Exception as e:
            self._emit_error(f"NVENC frame encoding failed: {e}")
            return False
    
    def flush(self):
        """Flush remaining frames"""
        pass
    
    def get_ffmpeg_args(self) -> list:
        """Get FFmpeg arguments for NVENC encoding"""
        args = []
        
        # Video codec
        args.extend(['-c:v', 'h264_nvenc'])
        
        # Hardware preset (NVENC-specific)
        nvenc_preset = self._get_nvenc_preset()
        args.extend(['-preset', nvenc_preset])
        
        # Rate control mode
        args.extend(['-rc', 'cbr'])  # Constant bitrate
        
        # Bitrate
        args.extend(['-b:v', f'{self._settings.bitrate_kbps}k'])
        args.extend(['-maxrate', f'{self._settings.bitrate_kbps}k'])
        args.extend(['-bufsize', f'{self._settings.bitrate_kbps * 2}k'])
        
        # GOP settings
        args.extend(['-g', str(self._settings.keyframe_interval)])
        
        # Profile
        args.extend(['-profile:v', self._settings.profile.value])
        
        # Pixel format
        args.extend(['-pix_fmt', 'yuv420p'])
        
        # Low latency options
        if self._settings.low_latency:
            args.extend(['-zerolatency', '1'])
            args.extend(['-delay', '0'])
        
        # B-frames (NVENC supports limited B-frames)
        b_frames = min(self._settings.b_frames, 2)
        args.extend(['-bf', str(b_frames)])
        
        return args
    
    def _get_nvenc_preset(self) -> str:
        """Map software preset to NVENC preset"""
        preset_map = {
            'ultrafast': 'p1',
            'superfast': 'p2', 
            'veryfast': 'p3',
            'faster': 'p4',
            'fast': 'p5',
            'medium': 'p6',
            'slow': 'p7',
            'slower': 'p7',
            'veryslow': 'p7'
        }
        
        return preset_map.get(self._settings.preset.value, 'p4')
    
    def get_nvenc_presets(self) -> dict:
        """Get NVENC-specific presets"""
        return {
            'streaming_low_latency': {
                'preset': 'p1',  # Fastest
                'rc_mode': 'cbr',
                'low_latency': True
            },
            'streaming_quality': {
                'preset': 'p6',  # Balanced
                'rc_mode': 'vbr',
                'low_latency': False
            },
            'recording_quality': {
                'preset': 'p7',  # Best quality
                'rc_mode': 'vbr',
                'low_latency': False
            }
        }
    
    @staticmethod
    def is_available() -> bool:
        """Check if NVENC is available on the system"""
        try:
            result = subprocess.run([
                'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                '-c:v', 'h264_nvenc', '-f', 'null', '-'
            ], capture_output=True, timeout=10)
            
            return result.returncode == 0
            
        except Exception:
            return False
