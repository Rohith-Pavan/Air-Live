"""
GoLive Studio - VideoToolbox Hardware Encoder (macOS)
Apple VideoToolbox H.264 encoding
"""

import subprocess
import sys
from typing import Optional
from PyQt6.QtGui import QImage

from .base_encoder import BaseEncoder, EncoderSettings, EncoderCapabilities, EncoderType


class VideoToolboxEncoder(BaseEncoder):
    """
    Apple VideoToolbox hardware encoder
    Provides GPU-accelerated H.264 encoding on macOS
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._available = sys.platform == 'darwin' and self._check_videotoolbox_support()
        
    def _check_videotoolbox_support(self) -> bool:
        """Check if VideoToolbox is available"""
        try:
            # Try to run ffmpeg with videotoolbox to check availability
            result = subprocess.run([
                'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                '-c:v', 'h264_videotoolbox', '-f', 'null', '-'
            ], capture_output=True, timeout=10)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def get_capabilities(self) -> EncoderCapabilities:
        """Get VideoToolbox encoder capabilities"""
        return EncoderCapabilities(
            name="h264_videotoolbox",
            encoder_type=EncoderType.HARDWARE,
            supported_formats=["h264", "mp4", "mov"],
            max_resolution=(7680, 4320),  # Depends on hardware
            max_fps=120,
            supports_crf=False,  # VideoToolbox doesn't support CRF
            supports_cbr=True,
            supports_vbr=True,
            hardware_acceleration=True,
            encoding_speed="fast",
            quality_rating="excellent"
        )
    
    def initialize(self, settings: EncoderSettings) -> bool:
        """Initialize VideoToolbox encoder"""
        try:
            if not self._available:
                self._emit_error("VideoToolbox not available on this system")
                return False
            
            if not self._validate_settings(settings):
                self._emit_error("Invalid VideoToolbox settings")
                return False
            
            self._settings = settings
            self._capabilities = self.get_capabilities()
            self._initialized = True
            
            return True
            
        except Exception as e:
            self._emit_error(f"VideoToolbox initialization failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up VideoToolbox encoder"""
        self.stop_encoding()
        self._initialized = False
    
    def start_encoding(self) -> bool:
        """Start VideoToolbox encoding session"""
        if not self._initialized:
            self._emit_error("VideoToolbox encoder not initialized")
            return False
        
        if self._encoding:
            return True
        
        try:
            self._encoding = True
            self.reset_stats()
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to start VideoToolbox encoding: {e}")
            self._encoding = False
            return False
    
    def stop_encoding(self):
        """Stop VideoToolbox encoding session"""
        self._encoding = False
    
    def encode_frame(self, frame: QImage) -> bool:
        """Encode frame using VideoToolbox"""
        if not self._encoding or not frame or frame.isNull():
            return False
        
        try:
            # VideoToolbox frame encoding would be handled by FFmpeg process
            # This is a placeholder for the actual implementation
            
            # Update stats
            self._stats['frames_encoded'] += 1
            self._update_stats(frames_encoded=self._stats['frames_encoded'])
            
            return True
            
        except Exception as e:
            self._emit_error(f"VideoToolbox frame encoding failed: {e}")
            return False
    
    def flush(self):
        """Flush remaining frames"""
        pass
    
    def get_ffmpeg_args(self) -> list:
        """Get FFmpeg arguments for VideoToolbox encoding"""
        args = []
        
        # Video codec
        args.extend(['-c:v', 'h264_videotoolbox'])
        
        # Profile
        args.extend(['-profile:v', self._settings.profile.value])
        
        # Bitrate control
        args.extend(['-b:v', f'{self._settings.bitrate_kbps}k'])
        
        if self._settings.max_bitrate_kbps:
            args.extend(['-maxrate', f'{self._settings.max_bitrate_kbps}k'])
        
        if self._settings.buffer_size_kbps:
            args.extend(['-bufsize', f'{self._settings.buffer_size_kbps}k'])
        
        # GOP settings
        args.extend(['-g', str(self._settings.keyframe_interval)])
        
        # Pixel format
        args.extend(['-pix_fmt', 'yuv420p'])
        
        # VideoToolbox-specific quality settings
        quality = self._get_videotoolbox_quality()
        if quality:
            args.extend(['-q:v', str(quality)])
        
        # Real-time encoding for low latency
        if self._settings.low_latency:
            args.extend(['-realtime', '1'])
        
        return args
    
    def _get_videotoolbox_quality(self) -> Optional[int]:
        """Map preset to VideoToolbox quality value"""
        quality_map = {
            'ultrafast': 80,
            'superfast': 70,
            'veryfast': 60,
            'faster': 50,
            'fast': 40,
            'medium': 30,
            'slow': 20,
            'slower': 15,
            'veryslow': 10
        }
        
        return quality_map.get(self._settings.preset.value)
    
    def get_videotoolbox_presets(self) -> dict:
        """Get VideoToolbox-specific presets"""
        return {
            'streaming_low_latency': {
                'quality': 60,
                'realtime': True,
                'low_latency': True
            },
            'streaming_quality': {
                'quality': 40,
                'realtime': False,
                'low_latency': False
            },
            'recording_quality': {
                'quality': 20,
                'realtime': False,
                'low_latency': False
            }
        }
    
    @staticmethod
    def is_available() -> bool:
        """Check if VideoToolbox is available on the system"""
        if sys.platform != 'darwin':
            return False
        
        try:
            result = subprocess.run([
                'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                '-c:v', 'h264_videotoolbox', '-f', 'null', '-'
            ], capture_output=True, timeout=10)
            
            return result.returncode == 0
            
        except Exception:
            return False
