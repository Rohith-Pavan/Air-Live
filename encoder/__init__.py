"""
GoLive Studio - Encoder Module
Cross-platform hardware and software encoding abstraction
"""

from .base_encoder import BaseEncoder, EncoderSettings, EncoderCapabilities
from .x264_encoder import X264Encoder

# Platform-specific encoder imports
import sys

try:
    from .nvenc_encoder import NVENCEncoder
    _HAS_NVENC = True
except ImportError:
    _HAS_NVENC = False
    NVENCEncoder = None

if sys.platform == 'darwin':
    try:
        from .vt_encoder import VideoToolboxEncoder
        _HAS_VT = True
    except ImportError:
        _HAS_VT = False
        VideoToolboxEncoder = None
else:
    _HAS_VT = False
    VideoToolboxEncoder = None


def get_available_encoders() -> list:
    """Get list of available encoders on current platform"""
    encoders = []
    
    # Software encoder (always available)
    encoders.append({
        'name': 'x264',
        'type': 'software',
        'class': X264Encoder,
        'description': 'Software H.264 encoder (libx264)'
    })
    
    # Hardware encoders
    if _HAS_NVENC:
        encoders.append({
            'name': 'nvenc',
            'type': 'hardware',
            'class': NVENCEncoder,
            'description': 'NVIDIA Hardware H.264 encoder'
        })
    
    if _HAS_VT:
        encoders.append({
            'name': 'videotoolbox',
            'type': 'hardware', 
            'class': VideoToolboxEncoder,
            'description': 'Apple VideoToolbox H.264 encoder'
        })
    
    return encoders


def create_encoder(encoder_type='auto', **kwargs) -> BaseEncoder:
    """
    Factory function to create appropriate encoder
    
    Args:
        encoder_type: 'auto', 'x264', 'nvenc', 'videotoolbox'
        **kwargs: Additional encoder arguments
    
    Returns:
        BaseEncoder: Configured encoder instance
    """
    if encoder_type == 'auto':
        # Auto-select best available encoder
        if _HAS_NVENC:
            encoder_type = 'nvenc'
        elif _HAS_VT:
            encoder_type = 'videotoolbox'
        else:
            encoder_type = 'x264'
    
    if encoder_type == 'x264':
        return X264Encoder(**kwargs)
    elif encoder_type == 'nvenc' and _HAS_NVENC:
        return NVENCEncoder(**kwargs)
    elif encoder_type == 'videotoolbox' and _HAS_VT:
        return VideoToolboxEncoder(**kwargs)
    else:
        # Fallback to software encoder
        return X264Encoder(**kwargs)


def check_encoder_support() -> dict:
    """Check encoder support on current platform"""
    return {
        'x264': True,  # Always available via FFmpeg
        'nvenc': _HAS_NVENC,
        'videotoolbox': _HAS_VT,
        'available_encoders': get_available_encoders()
    }


__all__ = [
    'BaseEncoder', 'EncoderSettings', 'EncoderCapabilities',
    'X264Encoder', 'NVENCEncoder', 'VideoToolboxEncoder',
    'create_encoder', 'get_available_encoders', 'check_encoder_support'
]
