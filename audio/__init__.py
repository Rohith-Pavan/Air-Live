"""
GoLive Studio - Audio Module
Cross-platform audio capture, output, and monitoring abstraction
"""

import sys
from .base_audio import BaseAudioManager, AudioDevice, AudioFormat

# Platform-specific audio imports
if sys.platform == 'win32':
    try:
        from .windows_audio import WindowsAudioManager
        _HAS_WINDOWS_AUDIO = True
    except ImportError:
        _HAS_WINDOWS_AUDIO = False
        WindowsAudioManager = None
else:
    _HAS_WINDOWS_AUDIO = False
    WindowsAudioManager = None

if sys.platform == 'darwin':
    try:
        from .macos_audio import MacOSAudioManager
        _HAS_MACOS_AUDIO = True
    except ImportError:
        _HAS_MACOS_AUDIO = False
        MacOSAudioManager = None
else:
    _HAS_MACOS_AUDIO = False
    MacOSAudioManager = None

if sys.platform.startswith('linux'):
    try:
        from .linux_audio import LinuxAudioManager
        _HAS_LINUX_AUDIO = True
    except ImportError:
        _HAS_LINUX_AUDIO = False
        LinuxAudioManager = None
else:
    _HAS_LINUX_AUDIO = False
    LinuxAudioManager = None


def create_audio_manager(**kwargs) -> BaseAudioManager:
    """
    Factory function to create platform-appropriate audio manager
    
    Returns:
        BaseAudioManager: Platform-specific audio manager
    """
    if sys.platform == 'win32' and _HAS_WINDOWS_AUDIO:
        return WindowsAudioManager(**kwargs)
    elif sys.platform == 'darwin' and _HAS_MACOS_AUDIO:
        return MacOSAudioManager(**kwargs)
    elif sys.platform.startswith('linux') and _HAS_LINUX_AUDIO:
        return LinuxAudioManager(**kwargs)
    else:
        # Fallback to Qt-based audio manager
        from .qt_audio import QtAudioManager
        return QtAudioManager(**kwargs)


def get_platform_audio_info() -> dict:
    """Get platform audio support information"""
    return {
        'platform': sys.platform,
        'windows_audio': _HAS_WINDOWS_AUDIO,
        'macos_audio': _HAS_MACOS_AUDIO,
        'linux_audio': _HAS_LINUX_AUDIO,
        'qt_fallback': True
    }


__all__ = [
    'BaseAudioManager', 'AudioDevice', 'AudioFormat',
    'WindowsAudioManager', 'MacOSAudioManager', 'LinuxAudioManager',
    'create_audio_manager', 'get_platform_audio_info'
]
