from __future__ import annotations
from typing import Optional, Callable
from PyQt6.QtCore import QObject, QTimer, QSize, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QWidget, QLabel

class _ProgramOutputWindow(QWidget):
    def __init__(self, screen_geometry, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background-color: black;")
        self.setStyleSheet("background-color: black;")
        # Position and size on the target screen
        self.setGeometry(screen_geometry)
        self._label.setGeometry(0, 0, screen_geometry.width(), screen_geometry.height())
        self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._label:
            self._label.setGeometry(0, 0, self.width(), self.height())

    def set_frame(self, img: QImage):
        if img is None or img.isNull():
            return
        # Aim for native pixel presentation (HiDPI-aware)
        dpr = 1.0
        try:
            dpr = float(self.devicePixelRatioF())
        except Exception:
            pass
        # Native framebuffer size in pixels
        native_w = int(max(1, round(self.width() * dpr)))
        native_h = int(max(1, round(self.height() * dpr)))
        native_size = QSize(native_w, native_h)
        # If provider delivered native-sized image, attach 1:1
        if img.size() == native_size:
            pix = QPixmap.fromImage(img)
            try:
                pix.setDevicePixelRatio(dpr)
            except Exception:
                pass
            self._label.setPixmap(pix)
            return
        # Otherwise, scale to native pixels first to preserve sharpness
        scaled_img = img.scaled(native_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pix = QPixmap.fromImage(scaled_img)
        try:
            pix.setDevicePixelRatio(dpr)
        except Exception:
            pass
        self._label.setPixmap(pix)

    def native_pixel_size(self) -> QSize:
        """Return the native framebuffer size in pixels (HiDPI-aware)."""
        dpr = 1.0
        try:
            dpr = float(self.devicePixelRatioF())
        except Exception:
            pass
        return QSize(int(max(1, round(self.width() * dpr))), int(max(1, round(self.height() * dpr))))

class DisplayMirrorController(QObject):
    """Mirrors the composed program output to an external display (full screen window).

    Usage:
      - set_frame_provider(callable returning QImage)
        Provider may accept either (QSize) or (QSize, direct_passthrough: bool).
      - start(settings: {screen_index, width, height, fps, maximize, direct_passthrough})
      - stop()
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._fps = 60
        self._size = QSize(1920, 1080)
        # Provider may accept (QSize) or (QSize, bool)
        self._frame_provider: Optional[Callable[..., QImage]] = None
        self._window: Optional[_ProgramOutputWindow] = None
        self._running = False
        self._screen_index: int = 0
        self._direct_passthrough: bool = False

    def set_frame_provider(self, provider: Callable[..., QImage]):
        """Set the frame provider.

        The callable may have one of the following signatures:
        - provider(size: QSize) -> QImage
        - provider(size: QSize, direct_passthrough: bool) -> QImage
        """
        self._frame_provider = provider

    def is_running(self) -> bool:
        return self._running

    def start(self, settings: dict):
        if self._running:
            return
        try:
            from PyQt6.QtGui import QGuiApplication
            from PyQt6.QtCore import QRect
            
            self._screen_index = int(settings.get('screen_index', 0))
            # Respect requested fps and size from settings (may be overridden by maximize)
            self._fps = int(settings.get('fps', 60))
            req_w = int(settings.get('width', 1920))
            req_h = int(settings.get('height', 1080))
            self._size = QSize(req_w, req_h)
            maximize = bool(settings.get('max_quality', False) or settings.get('maximize', False))
            self._direct_passthrough = bool(settings.get('direct_passthrough', False))
            
            # Check if we have NSScreen rect data from the dialog
            nsscreen_rects = settings.get('nsscreen_rects', [])
            if nsscreen_rects and 0 <= self._screen_index < len(nsscreen_rects):
                # Use NSScreen positioning data
                x, y, w, h = nsscreen_rects[self._screen_index]
                # Convert from NSScreen coordinates (bottom-left origin) to Qt coordinates (top-left origin)
                try:
                    from AppKit import NSScreen
                    main_screen = NSScreen.mainScreen()
                    main_height = int(main_screen.frame().size.height)
                    qt_y = main_height - y - h  # Flip Y coordinate
                    geo = QRect(x, qt_y, w, h)
                    print(f"Using NSScreen positioning: {w}x{h} @({x},{qt_y})")
                except Exception:
                    geo = QRect(x, y, w, h)  # Fallback without coordinate conversion
                    print(f"Using NSScreen positioning (no conversion): {w}x{h} @({x},{y})")
            else:
                # Use Qt screen positioning
                screens = QGuiApplication.screens()
                if not screens:
                    raise RuntimeError("No displays detected")
                if self._screen_index < 0 or self._screen_index >= len(screens):
                    self._screen_index = 0
                geo = screens[self._screen_index].geometry()
                print(f"Using Qt screen positioning: {geo.width()}x{geo.height()} @({geo.x()},{geo.y()})")
            
            # Create the window on the target screen
            self._window = _ProgramOutputWindow(geo)
            self._window.show()
            # If maximize requested, update target render size to the full native window size (HiDPI)
            if maximize and self._window is not None:
                try:
                    self._size = self._window.native_pixel_size()
                except Exception:
                    self._size = QSize(self._window.width(), self._window.height())
            interval = max(1, int(1000 / max(1, self._fps)))
            self._timer.start(interval)
            self._running = True
            print(f"Display mirror started in {'DIRECT PASSTHROUGH' if self._direct_passthrough else 'NORMAL'} mode")
        except Exception as e:
            self.stop()
            raise e

    def stop(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            if self._window:
                self._window.close()
        finally:
            self._window = None
            self._running = False

    def _tick(self):
        if not self._running or not self._window or not self._frame_provider:
            return
        try:
            # Keep target render size in sync with the fullscreen window native pixel size
            try:
                native = self._window.native_pixel_size()
            except Exception:
                ws = self._window.size()
                native = QSize(ws.width(), ws.height())
            # Quantize to even pixels to avoid oscillation due to fractional DPR rounding
            if native.isValid():
                nw = max(1, int(native.width()))
                nh = max(1, int(native.height()))
                # round to nearest even to stabilize
                if nw % 2 != 0:
                    nw += 1
                if nh % 2 != 0:
                    nh += 1
                native = QSize(nw, nh)
            if native.isValid() and (native.width() != self._size.width() or native.height() != self._size.height()):
                self._size = native
                print(f"[Mirror] Adjusted render size to native: {self._size.width()}x{self._size.height()}")
            # Try calling provider with (size, direct_passthrough); fall back to (size)
            try:
                img = self._frame_provider(self._size, self._direct_passthrough)
            except TypeError:
                img = self._frame_provider(self._size)
            if img is None or img.isNull():
                return
            self._window.set_frame(img)
        except Exception as e:
            print(f"Error in display mirror tick: {e}")
            import traceback
            traceback.print_exc()

    # --- Live update of mirror parameters ---
    def update(self, settings: dict):
        """Update mirror output parameters (resolution, framerate) while running.
        If not running, this is a no-op.
        """
        if not self._running:
            return
        try:
            # Respect requested width/height unless maximize flag is passed
            maximize = bool(settings.get('max_quality', False) or settings.get('maximize', False))
            if maximize and self._window is not None:
                new_w = self._window.width()
                new_h = self._window.height()
            else:
                new_w = int(settings.get('width', self._size.width()))
                new_h = int(settings.get('height', self._size.height()))
            new_fps = int(settings.get('fps', self._fps))
            self._size = QSize(max(1, new_w), max(1, new_h))
            if new_fps != self._fps:
                self._fps = max(1, new_fps)
                interval = max(1, int(1000 / max(1, self._fps)))
                self._timer.setInterval(interval)
        except Exception:
            pass
