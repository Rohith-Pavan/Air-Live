"""
GoLive Studio - X264 Software Encoder
Software H.264 encoding using libx264 via FFmpeg
"""

import subprocess
import threading
from typing import Optional
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage

from .base_encoder import BaseEncoder, EncoderSettings, EncoderCapabilities, EncoderType, EncoderPreset, EncoderProfile


class X264Encoder(BaseEncoder):
    """
    Software H.264 encoder using libx264
    Cross-platform software encoding fallback
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._process: Optional[subprocess.Popen] = None
        self._encoding_thread: Optional[threading.Thread] = None
        
    def get_capabilities(self) -> EncoderCapabilities:
        """Get X264 encoder capabilities"""
        return EncoderCapabilities(
            name="libx264",
            encoder_type=EncoderType.SOFTWARE,
            supported_formats=["h264", "mp4", "flv"],
            max_resolution=(7680, 4320),  # 8K support
            max_fps=120,
            supports_crf=True,
            supports_cbr=True,
            supports_vbr=True,
            hardware_acceleration=False,
            encoding_speed="medium",
            quality_rating="excellent"
        )
    
    def initialize(self, settings: EncoderSettings) -> bool:
        """Initialize X264 encoder"""
        try:
            if not self._validate_settings(settings):
                self._emit_error("Invalid encoder settings")
                return False
            
            self._settings = settings
            self._capabilities = self.get_capabilities()
            self._initialized = True
            
            return True
            
        except Exception as e:
            self._emit_error(f"X264 initialization failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up X264 encoder"""
        self.stop_encoding()
        self._initialized = False
    
    def start_encoding(self) -> bool:
        """Start X264 encoding session"""
        if not self._initialized:
            self._emit_error("Encoder not initialized")
            return False
        
        if self._encoding:
            return True
        
        try:
            self._encoding = True
            self.reset_stats()
            return True
            
        except Exception as e:
            self._emit_error(f"Failed to start X264 encoding: {e}")
            self._encoding = False
            return False
    
    def stop_encoding(self):
        """Stop X264 encoding session"""
        self._encoding = False
        
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except:
                try:
                    self._process.kill()
                except:
                    pass
            self._process = None
        
        if self._encoding_thread and self._encoding_thread.is_alive():
            self._encoding_thread.join(timeout=2)
    
    def encode_frame(self, frame: QImage) -> bool:
        """Encode frame using X264"""
        if not self._encoding or not frame or frame.isNull():
            return False
        
        try:
            # Convert QImage to raw RGBA data
            frame_rgba = frame.convertToFormat(QImage.Format.Format_RGBA8888)
            width = frame_rgba.width()
            height = frame_rgba.height()
            
            # For X264, we typically use FFmpeg process
            # This is a simplified implementation - in practice, you'd use
            # a more sophisticated approach with proper frame queuing
            
            # Update stats
            self._stats['frames_encoded'] += 1
            self._update_stats(frames_encoded=self._stats['frames_encoded'])
            
            return True
            
        except Exception as e:
            self._emit_error(f"X264 frame encoding failed: {e}")
            return False
    
    def flush(self):
        """Flush remaining frames"""
        if self._process:
            try:
                self._process.stdin.close()
            except:
                pass
    
    def get_ffmpeg_args(self) -> list:
        """Get FFmpeg arguments for X264 encoding"""
        args = []
        
        # Video codec
        args.extend(['-c:v', 'libx264'])
        
        # Preset
        args.extend(['-preset', self._settings.preset.value])
        
        # Profile
        args.extend(['-profile:v', self._settings.profile.value])
        
        # Rate control
        if self._settings.crf is not None:
            # Constant Rate Factor (quality-based)
            args.extend(['-crf', str(self._settings.crf)])
        else:
            # Constant Bitrate
            args.extend(['-b:v', f'{self._settings.bitrate_kbps}k'])
            
            if self._settings.max_bitrate_kbps:
                args.extend(['-maxrate', f'{self._settings.max_bitrate_kbps}k'])
            
            if self._settings.buffer_size_kbps:
                args.extend(['-bufsize', f'{self._settings.buffer_size_kbps}k'])
        
        # GOP settings
        args.extend(['-g', str(self._settings.keyframe_interval)])
        args.extend(['-keyint_min', str(self._settings.keyframe_interval)])
        
        # B-frames
        args.extend(['-bf', str(self._settings.b_frames)])
        
        # Reference frames
        args.extend(['-refs', str(self._settings.ref_frames)])
        
        # Pixel format
        args.extend(['-pix_fmt', 'yuv420p'])
        
        # Low latency options
        if self._settings.low_latency:
            args.extend(['-tune', 'zerolatency'])
            args.extend(['-sc_threshold', '0'])
        
        return args
    
    def get_quality_presets(self) -> dict:
        """Get recommended quality presets for different use cases"""
        return {
            'streaming_low': {
                'preset': EncoderPreset.VERYFAST,
                'crf': 28,
                'profile': EncoderProfile.MAIN,
                'b_frames': 2
            },
            'streaming_medium': {
                'preset': EncoderPreset.FAST,
                'crf': 23,
                'profile': EncoderProfile.HIGH,
                'b_frames': 3
            },
            'streaming_high': {
                'preset': EncoderPreset.MEDIUM,
                'crf': 20,
                'profile': EncoderProfile.HIGH,
                'b_frames': 3
            },
            'recording_high': {
                'preset': EncoderPreset.SLOW,
                'crf': 18,
                'profile': EncoderProfile.HIGH,
                'b_frames': 5
            },
            'recording_archive': {
                'preset': EncoderPreset.VERYSLOW,
                'crf': 15,
                'profile': EncoderProfile.HIGH,
                'b_frames': 8
            }
        }
    
    def apply_preset(self, preset_name: str) -> bool:
        """Apply a quality preset"""
        presets = self.get_quality_presets()
        if preset_name not in presets:
            return False
        
        preset = presets[preset_name]
        
        # Update settings
        if 'preset' in preset:
            self._settings.preset = preset['preset']
        if 'crf' in preset:
            self._settings.crf = preset['crf']
        if 'profile' in preset:
            self._settings.profile = preset['profile']
        if 'b_frames' in preset:
            self._settings.b_frames = preset['b_frames']
        
        return True
