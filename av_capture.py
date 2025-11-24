#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-FPS AVFoundation capture using PyAV for macOS.
Designed to support very high frame rates (e.g., up to 4K240) when the device and bus permit.

This module exposes AVFVideoCapture which:
- Opens an AVFoundation video device by name or index
- Decodes frames on a background thread
- Emits frames via a Qt signal as QImage
- Measures runtime FPS

Requires: av (PyAV), PyQt6
"""
from __future__ import annotations
import threading
import time
from typing import Optional, Dict, Any
import numpy as np

from PyQt6.QtCore import QObject, pyqtSignal, QSize
from PyQt6.QtGui import QImage


class AVFVideoCapture(QObject):
    """AVFoundation video capture via PyAV with high-FPS support.

    Signals:
      frameReady(input_number: int, image: QImage, measured_fps: float)
      error(str)
    """
    frameReady = pyqtSignal(int, QImage, float)
    error = pyqtSignal(str)

    def __init__(self, input_number: int, device: str | int, width: Optional[int] = None, height: Optional[int] = None,
                 fps: Optional[int] = None, pixel_format: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._input_number = int(input_number)
        self._device = device  # name or index
        self._width = int(width) if width else None
        self._height = int(height) if height else None
        self._fps = int(fps) if fps else None
        self._pix_fmt = pixel_format or 'uyvy422'  # common for capture cards
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._container = None  # type: ignore[assignment]
        self._stream = None  # type: ignore[assignment]
        self._times: list[float] = []

    def start(self) -> bool:
        try:
            # Ensure FFmpeg dylibs are discoverable when using Homebrew builds (macOS)
            import os
            try:
                candidates = [
                    "/opt/homebrew/opt/ffmpeg/lib",
                    "/usr/local/opt/ffmpeg/lib",
                ]
                dyld = os.environ.get('DYLD_LIBRARY_PATH', '')
                parts = [p for p in dyld.split(':') if p]
                for c in candidates:
                    if os.path.isdir(c) and c not in parts:
                        parts.insert(0, c)
                if parts:
                    os.environ['DYLD_LIBRARY_PATH'] = ':'.join(parts)
            except Exception:
                pass
            # Lazy import PyAV; may not be available on all systems
            import av  # type: ignore
            url = None
            if isinstance(self._device, int):
                url = f"{self._device}"
            else:
                # AVFoundation accepts device names; leave as-is
                url = f"{self._device}"

            opts: Dict[str, Any] = {}
            if self._fps and self._fps > 0:
                # Request high fps; device may clamp to nearest mode
                opts['framerate'] = str(int(self._fps))
            if self._width and self._height:
                opts['video_size'] = f"{self._width}x{self._height}"
            if self._pix_fmt:
                opts['pixel_format'] = self._pix_fmt

            # Open AVFoundation device
            self._container = av.open(url=f"avfoundation:{url}", format='avfoundation', options=opts)
            # Pick first video stream
            self._stream = next((s for s in self._container.streams if s.type == 'video'), None)
            if self._stream is None:
                raise RuntimeError('No video stream found in AVFoundation device')

            # Use low-latency
            try:
                self._stream.thread_type = 'AUTO'
            except Exception:
                pass

            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name=f"AVFVideoCapture-{self._input_number}", daemon=True)
            self._thread.start()
            return True
        except ImportError as e:
            self.error.emit(f"PyAV not available: {e}")
            return False
        except Exception as e:
            self.error.emit(f"AVF open error: {e}")
            return False

    def stop(self):
        try:
            self._stop.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.5)
        except Exception:
            pass
        try:
            if self._container is not None:
                self._container.close()
        except Exception:
            pass
        self._container = None
        self._stream = None

    def _measure_fps(self, now: float) -> float:
        self._times.append(now)
        # Keep about 2 seconds of samples
        horizon = now - 2.0
        while len(self._times) > 1 and self._times[0] < horizon:
            self._times.pop(0)
        if len(self._times) >= 2:
            dt = self._times[-1] - self._times[0]
            if dt > 0:
                return (len(self._times) - 1) / dt
        return 0.0

    def _run(self):
        try:
            import av  # type: ignore
            for frame in self._container.decode(self._stream):
                if self._stop.is_set():
                    break
                try:
                    # Convert to RGB for QImage
                    rgb = frame.to_rgb()
                    h = rgb.height
                    w = rgb.width
                    # Obtain bytes
                    img_bytes = rgb.to_ndarray()
                    # Ensure contiguous
                    if not img_bytes.flags['C_CONTIGUOUS']:
                        img_bytes = np.ascontiguousarray(img_bytes)
                    # Create QImage (Format_RGB24)
                    qimg = QImage(img_bytes.data, w, h, 3 * w, QImage.Format.Format_RGB888)
                    # Make a deep copy detached from buffer lifetime
                    qimg_copy = qimg.copy()
                    fps_measured = self._measure_fps(time.time())
                    self.frameReady.emit(self._input_number, qimg_copy, float(fps_measured))
                except Exception as e:
                    self.error.emit(f"AVF frame error: {e}")
        except ImportError as e:
            self.error.emit(f"PyAV not available in capture thread: {e}")
        except Exception as e:
            self.error.emit(f"AVF decode loop error: {e}")


def probe_device(device: str | int, sample_seconds: float = 1.0,
                 width: Optional[int] = None, height: Optional[int] = None,
                 fps_request: Optional[int] = None, pixel_format: Optional[str] = None) -> dict:
    """Probe an AVFoundation device and return measured resolution and FPS.

    Returns dict: { 'ok': bool, 'width': int, 'height': int, 'fps': float, 'error': str|None }
    """
    try:
        # Ensure FFmpeg dylibs are discoverable when using Homebrew builds (macOS)
        import os
        try:
            candidates = [
                "/opt/homebrew/opt/ffmpeg/lib",
                "/usr/local/opt/ffmpeg/lib",
            ]
            dyld = os.environ.get('DYLD_LIBRARY_PATH', '')
            parts = [p for p in dyld.split(':') if p]
            for c in candidates:
                if os.path.isdir(c) and c not in parts:
                    parts.insert(0, c)
            if parts:
                os.environ['DYLD_LIBRARY_PATH'] = ':'.join(parts)
        except Exception:
            pass
        import av  # type: ignore
        url = f"{device}"
        opts: Dict[str, Any] = {}
        if fps_request and fps_request > 0:
            opts['framerate'] = str(int(fps_request))
        if width and height:
            opts['video_size'] = f"{int(width)}x{int(height)}"
        if pixel_format:
            opts['pixel_format'] = pixel_format

        container = av.open(url=f"avfoundation:{url}", format='avfoundation', options=opts)
        stream = next((s for s in container.streams if s.type == 'video'), None)
        if stream is None:
            try:
                container.close()
            except Exception:
                pass
            return { 'ok': False, 'width': 0, 'height': 0, 'fps': 0.0, 'error': 'no video stream' }

        t_start = time.time()
        times: list[float] = []
        w = h = 0
        for frame in container.decode(stream):
            now = time.time()
            times.append(now)
            if w == 0 or h == 0:
                try:
                    w = int(frame.width)
                    h = int(frame.height)
                except Exception:
                    w = h = 0
            if now - t_start >= max(0.25, float(sample_seconds)):
                break
        try:
            container.close()
        except Exception:
            pass
        fps = 0.0
        if len(times) >= 2:
            dt = max(1e-3, times[-1] - times[0])
            fps = (len(times) - 1) / dt
        return { 'ok': True, 'width': w, 'height': h, 'fps': float(fps), 'error': None }
    except ImportError as e:
        return { 'ok': False, 'width': 0, 'height': 0, 'fps': 0.0, 'error': f'PyAV not available: {e}' }
    except Exception as e:
        return { 'ok': False, 'width': 0, 'height': 0, 'fps': 0.0, 'error': str(e) }
