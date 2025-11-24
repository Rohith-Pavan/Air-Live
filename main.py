#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoLive Studio - Main Application
A cross-platform PyQt6 application for live streaming and recording
"""

import sys
import os
import time

# Auto-restart with Python 3.12 if running with Python 3.13
if sys.version_info.major == 3 and sys.version_info.minor == 13:
    import subprocess
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, "venv_py312", "bin", "python")
    if os.path.exists(venv_python):
        print("Detected Python 3.13. Restarting with Python 3.12...")
        subprocess.run([venv_python] + sys.argv)
        sys.exit(0)
from PyQt6.QtWidgets import QApplication, QMainWindow, QFrame, QWidget, QSplitter, QMessageBox
from PyQt6.QtCore import Qt, QSize, qInstallMessageHandler, QtMsgType, QUrl, QTimer, QObject, QEvent
from PyQt6.QtGui import QIcon, QPixmap, QImage, QFont
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioSource, QAudioSink, QMediaDevices, QVideoSink, QCamera, QMediaCaptureSession
# Defer PyAV import to runtime; some systems may not have FFmpeg headers/libs available.
_HAS_AVF_PYAV = False
from PyQt6 import uic
from transitions import TransitionManager, TRANSITIONS_CATALOG
from overlay_manager import EffectManager
from premiere_effects_panel_final import FinalEffectsPanel as PremiereEffectsPanel

# Import FPS controller for global timing control
try:
    from fps_controller import get_fps_controller, set_global_fps, get_global_fps
    from enhanced_streaming import get_streaming_manager
    FPS_CONTROLLER_AVAILABLE = True
except ImportError:
    FPS_CONTROLLER_AVAILABLE = False
    print("FPS Controller not available, using legacy timing")
from fps_stabilizer import fps_manager
from unified_timer import timer_manager
from event_coalescer import event_coalescer, ui_coalescer
from gl_context_manager import gl_context_manager
from texture_pool import texture_pool
from smart_cache import smart_cache
from thread_pool_manager import thread_pool, TaskPriority
from adaptive_quality import quality_manager
from memory_pool import general_memory_pool, image_memory_pool
from performance_monitor import performance_monitor
# Import performance optimizer for memory and FPS optimization
try:
    from performance_optimizer import get_performance_optimizer, optimize_performance_now
    PERFORMANCE_OPTIMIZER_AVAILABLE = True
except ImportError:
    PERFORMANCE_OPTIMIZER_AVAILABLE = False
    print("Performance Optimizer not available")

# Import aggressive memory optimizer for ultra-low memory usage
try:
    from aggressive_memory_optimizer import force_memory_under_target, continuous_memory_management
    AGGRESSIVE_MEMORY_OPTIMIZER_AVAILABLE = True
except ImportError:
    AGGRESSIVE_MEMORY_OPTIMIZER_AVAILABLE = False
    print("Aggressive Memory Optimizer not available")
# Import optimized renderer with single path
try:
    from renderer.migration_helper import create_graphics_output_widget, check_gpu_support
    gpu_info = check_gpu_support()
    _USE_NEW_RENDERER = bool(gpu_info.get('opengl_available') or gpu_info.get('d3d_available'))
    
    # OPTIMIZATION: Use single renderer path to avoid duplication
    if _USE_NEW_RENDERER:
        print(f"Using GPU renderer (OpenGL: {gpu_info.get('opengl_available')})")
        # Import enhanced version for GPU
        from enhanced_graphics_output import EnhancedGraphicsOutputWidget as GraphicsOutputWidget
    else:
        print("Using CPU renderer (fallback mode)")
        # Try to use enhanced graphics output as fallback
        from enhanced_graphics_output import EnhancedGraphicsOutputWidget as GraphicsOutputWidget
except ImportError as e:
    print(f"Renderer import error, using fallback: {e}")
    # Create a fallback minimal graphics output widget
    from PyQt6.QtWidgets import QLabel
    from PyQt6.QtGui import QImage, QPixmap
    from PyQt6.QtCore import QSize, Qt
    
    class GraphicsOutputWidget(QLabel):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setStyleSheet("background-color: black; color: white;")
            self.setText("Graphics Output")
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        def render_to_image(self, size):
            img = QImage(size, QImage.Format.Format_RGBA8888)
            img.fill(0)  # Black
            return img
        
        def set_preview_render_size(self, size):
            pass
        
        def get_current_source(self):
            return None
        
        def render_source_only(self, size):
            return self.render_to_image(size)
    
    _USE_NEW_RENDERER = False
from text_overlay import TextOverlayControls, TextOverlayMiniBar
from config import app_config
from streaming import StreamController
# Import enhanced display controller that fixes pixelation
try:
    from enhanced_external_display import EnhancedDisplayMirrorController
    _USE_ENHANCED_MIRROR = True
    print("Using enhanced display mirror controller (pixelation fixes)")
except ImportError as e:
    print(f"Enhanced mirror not available, using fallback: {e}")
    from external_display import DisplayMirrorController
    _USE_ENHANCED_MIRROR = False
from recording import RecorderController
from recording_settings_dialog import RecordingSettingsDialog

# Enhanced bundled FFmpeg support - ensures internal FFmpeg is always used
from ffmpeg_utils import setup_ffmpeg_environment, get_ffmpeg_path

# Initialize FFmpeg environment
_bundled_ffmpeg_path = setup_ffmpeg_environment()
if _bundled_ffmpeg_path:
    print(f"✓ Using bundled FFmpeg: {_bundled_ffmpeg_path}")
else:
    print("⚠ Bundled FFmpeg not found, will try system FFmpeg")

# Resolve bundled data files (effects, icons, ui) across dev, PyInstaller onedir, and macOS .app Resources
def _get_data_path(*parts: str) -> str:
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = []
        # 1) Next to executable (PyInstaller onedir typically puts datas in MacOS for some layouts)
        candidates.append(os.path.join(base_dir, *parts))
        # 2) macOS .app Resources
        candidates.append(os.path.join(base_dir, '..', 'Resources', *parts))
        # 3) PyInstaller onefile temporary extraction dir
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.append(os.path.join(meipass, *parts))
        for p in candidates:
            if os.path.exists(p):
                return os.path.normpath(p)
        # fallback to dev root (source layout)
        return os.path.normpath(os.path.join(base_dir, *parts))
    except Exception:
        return os.path.join(*parts)

def _get_writable_cache_dir(app_name: str, subdir: str = '') -> str:
    try:
        if sys.platform == 'darwin':
            root = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', app_name)
        elif sys.platform.startswith('win'):
            root = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), app_name)
        else:
            root = os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.join(os.path.expanduser('~'), '.cache')), app_name)
        if subdir:
            root = os.path.join(root, subdir)
        os.makedirs(root, exist_ok=True)
        return root
    except Exception:
        # very last resort: current working directory subdir
        root = os.path.join(os.getcwd(), subdir or 'cache')
        os.makedirs(root, exist_ok=True)
        return root

def qt_message_handler(mode, context, message):
    """Custom Qt message handler to suppress libpng warnings"""
    if "libpng warning" in message and "iCCP" in message:
        return  # Suppress libpng iCCP warnings
    # Allow other messages to pass through
    if mode == QtMsgType.QtDebugMsg:
        print(f"Qt Debug: {message}")
    elif mode == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        print(f"Qt Critical: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        print(f"Qt Fatal: {message}")

# Install the custom message handler
qInstallMessageHandler(qt_message_handler)


# ---------- Startup health check: memory & low-memory mode ----------
try:
    import psutil
    from aggressive_memory_optimizer import get_aggressive_optimizer, force_memory_under_target, continuous_memory_management
    from smart_cache import smart_cache
    from memory_pool import general_memory_pool, image_memory_pool
    # Check current memory and trigger optimizations if above target
    proc = psutil.Process()
    mem_mb = proc.memory_info().rss / 1024 / 1024
    TARGET_MB = 250
    if mem_mb > TARGET_MB:
        print(f"⚠ High memory at startup: {mem_mb:.1f}MB — enabling low-memory fallback and running optimizations")
        # Try light cache/pool clear first
        try:
            smart_cache.clear()
        except Exception:
            pass
        try:
            general_memory_pool.clear()
        except Exception:
            pass
        try:
            image_memory_pool.clear()
        except Exception:
            pass

        # Run aggressive cleanup to attempt to get under target
        try:
            success = force_memory_under_target(TARGET_MB)
            print(f"Memory cleanup success: {success}")
        except Exception as e:
            print(f"Error running aggressive memory cleanup: {e}")

        # Reduce quality proactively
        try:
            from adaptive_quality import QualityLevel, quality_manager
            quality_manager.set_quality_level(QualityLevel.LOW)
        except Exception:
            pass

            # Continuous memory management enabled
            try:
                continuous_memory_management()
            except Exception:
                pass

        # If still above target, apply extra low-memory fallbacks
        try:
            proc_mem_mb = proc.memory_info().rss / 1024 / 1024
            if proc_mem_mb > TARGET_MB:
                print(f"⚠ Memory still high ({proc_mem_mb:.1f}MB), applying extra low-memory fallbacks")
                # Lower preview FPS and disable previews/effects in config
                try:
                    app_config.settings['ui']['preview_fps'] = 15
                    app_config.settings['ui']['preview_quality'] = 'low'
                    app_config.settings['ui']['show_tooltips'] = False
                    app_config.settings['recording']['quality'] = 'low'
                    app_config.save_settings()
                except Exception:
                    pass

                # Reduce memory pool caps
                try:
                    general_memory_pool.max_memory = 100 * 1024 * 1024  # 100MB
                    general_memory_pool.optimize()
                except Exception:
                    pass

                try:
                    image_memory_pool.max_memory = 150 * 1024 * 1024  # 150MB
                    image_memory_pool.optimize()
                except Exception:
                    pass

                # Shrink smart cache sizes
                try:
                    smart_cache.l1_max_size = 5
                    smart_cache.l2_max_size = 10
                    smart_cache.l3_cache.max_size_bytes = 50 * 1024 * 1024
                    smart_cache.clear()
                except Exception:
                    pass

                # Final garbage collect
                try:
                    import gc
                    gc.collect()
                except Exception:
                    pass
        except Exception:
            pass
except Exception:
    # If psutil or optimizer unavailable, skip health check
    pass


class AspectRatioFrame(QFrame):
    """Custom QFrame that maintains 16:9 aspect ratio"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.aspect_ratio = 16.0 / 9.0
        # Make sure this widget prefers width-driven sizing
        from PyQt6.QtWidgets import QSizePolicy
        sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
    
    def sizeHint(self):
        """Return preferred size maintaining 16:9 aspect ratio"""
        return QSize(320, 180)  # 16:9 ratio
    
    def minimumSizeHint(self):
        """Return minimum size maintaining 16:9 aspect ratio"""
        return QSize(160, 90)   # 16:9 ratio
    
    def hasHeightForWidth(self):
        """Enable height-for-width layout"""
        return True
    
    def heightForWidth(self, width):
        """Calculate height based on width to maintain 16:9 aspect ratio"""
        return int(width / self.aspect_ratio)
    
    def resizeEvent(self, event):
        """Maintain aspect ratio during resize"""
        super().resizeEvent(event)
        # Force the frame to keep 16:9 by clamping its height based on current width
        w = max(1, self.width())
        desired_h = int(w / self.aspect_ratio)
        if desired_h != self.height():
            # Avoid infinite loops by only adjusting when different
            self.setMinimumHeight(desired_h)
            self.setMaximumHeight(desired_h)
        # Ensure any child label will scale inside
        if hasattr(self, '_video_label'):
            self._video_label.setMinimumSize(1, 1)
            self._video_label.setMaximumSize(16777215, 16777215)

class ResponsiveEffectsWidget(QWidget):
    """Responsive widget that automatically adjusts effect thumbnails based on available width"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QGridLayout
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setSpacing(3)  # Reduced spacing between items
        self.grid_layout.setContentsMargins(3, 3, 3, 3)  # Reduced edge padding
        self.effects_buttons = []
        self.columns = 4  # Fixed 4 columns
        self.aspect_ratio = 16.0 / 9.0
        self.cache_dir = None
        self._pending_icons = []
        self._batch_timer = None
        self._selected_path = None
        self._click_cb = None
        self._dblclick_cb = None
        
    def set_cache_dir(self, cache_dir):
        self.cache_dir = cache_dir

    def add_effects(self, png_files, click_callback, dblclick_callback=None):
        """Add effect buttons lazily. click_callback(path) single-click; dblclick_callback(path) optional."""
        from PyQt6.QtWidgets import QPushButton
        import os
        self._click_cb = click_callback
        self._dblclick_cb = dblclick_callback
        
        for png_file in png_files:
            try:
                # Create clickable button for each image
                image_button = QPushButton()
                image_button.setStyleSheet("""
                    QPushButton {
                        border: 2px solid #555;
                        border-radius: 4px;
                        background-color: #2b2b2b;
                    }
                    QPushButton:hover {
                        border: 2px solid #0078d4;
                        background-color: #333;
                    }
                    QPushButton:pressed {
                        background-color: #0078d4;
                    }
                """)
                # Store file path and pixmap for later use
                image_button.effect_file_path = png_file
                image_button.effect_name = os.path.basename(png_file)
                image_button._has_icon = False
                
                # Connect click event
                image_button.clicked.connect(lambda checked, path=png_file: self._handle_click(path))
                # Double-click support
                def _dbl(ev, path=png_file, btn=image_button):
                    if self._dblclick_cb:
                        self._dblclick_cb(path)
                    ev.accept()
                image_button.mouseDoubleClickEvent = _dbl
                
                # Add tooltip with filename
                image_button.setToolTip(os.path.basename(png_file))
                
                self.effects_buttons.append(image_button)
                
            except Exception as e:
                print(f"Error loading image {png_file}: {e}")
                continue
        
        # Defer initial layout until widget is properly sized
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.update_layout)

    def _handle_click(self, path):
        if self._click_cb:
            self._click_cb(path)
        self.update_selection(path)
    
    def _thumb_path(self, src_path, w, h):
        import hashlib, os
        try:
            st = os.stat(src_path)
            key = f"{src_path}|{int(st.st_mtime)}|{st.st_size}|{w}x{h}".encode('utf-8')
        except Exception:
            key = f"{src_path}|{w}x{h}".encode('utf-8')
        name = hashlib.md5(key).hexdigest() + ".jpg"
        if not self.cache_dir:
            return None
        os.makedirs(self.cache_dir, exist_ok=True)
        return os.path.join(self.cache_dir, name)

    def _ensure_button_icon(self, button, button_width):
        """Ensure the button has its icon set, using cached thumbnail if possible."""
        from PyQt6.QtGui import QIcon, QImageReader, QPixmap
        from PyQt6.QtCore import QSize
        if getattr(button, '_has_icon', False):
            return
        bw = max(32, button_width - 4)
        bh = int(bw / self.aspect_ratio)
        button.setFixedSize(bw + 4, bh + 4)
        thumb_path = self._thumb_path(button.effect_file_path, bw, bh)
        pix = QPixmap()
        loaded = False
        if thumb_path and os.path.exists(thumb_path):
            loaded = pix.load(thumb_path)
        if not loaded:
            # Decode at target size (fast and memory-efficient)
            reader = QImageReader(button.effect_file_path)
            reader.setAutoTransform(True)
            reader.setScaledSize(QSize(bw, bh))
            img = reader.read()
            if not img.isNull():
                pix = QPixmap.fromImage(img)
                if thumb_path:
                    try:
                        img.save(thumb_path, 'JPG', quality=80)
                    except Exception:
                        pass
        if not pix.isNull():
            button.setIcon(QIcon(pix))
            button.setIconSize(pix.size())
            button._has_icon = True

    def update_layout(self):
        """Update the grid layout with fixed 4 columns and responsive button sizing"""
        if not self.effects_buttons:
            return
            
        # Get parent widget dimensions for better width calculation
        parent_widget = self.parent()
        while parent_widget and not hasattr(parent_widget, 'width'):
            parent_widget = parent_widget.parent()
            
        # Calculate available width more accurately
        if parent_widget and hasattr(parent_widget, 'width'):
            available_width = max(parent_widget.width() - 10, 400)  # Minimal margin
        else:
            available_width = max(self.width() - 6, 400) if self.width() > 0 else 600
        
        # Clear existing layout
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        # Fixed 4 columns - calculate button width to fill available space
        spacing = self.grid_layout.spacing()
        margins = self.grid_layout.contentsMargins()
        total_spacing = (self.columns - 1) * spacing + margins.left() + margins.right()
        button_width = max(120, (available_width - total_spacing) // self.columns)
        
        # Update all buttons and add to grid; defer heavy icon work to batches
        row = 0
        col = 0
        self._pending_icons = []
        for button in self.effects_buttons:
            # Size the button; icon will be applied in batches
            btn_h = int(button_width / self.aspect_ratio)
            button.setFixedSize(button_width, btn_h)
            self._pending_icons.append((button, button_width))
            
            # Add to grid
            self.grid_layout.addWidget(button, row, col)
            
            col += 1
            if col >= self.columns:
                col = 0
                row += 1

        # Process icons in small batches to keep UI responsive
        self._start_icon_batch()

    def resizeEvent(self, event):
        """Handle resize events to update layout"""
        super().resizeEvent(event)
        # Add a small delay to prevent excessive updates during resize
        from PyQt6.QtCore import QTimer
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.update_layout)
        self._resize_timer.start(50)

    def _start_icon_batch(self):
        from PyQt6.QtCore import QTimer
        if self._batch_timer:
            self._batch_timer.stop()
        self._batch_timer = QTimer(self)
        self._batch_timer.timeout.connect(self._process_icon_batch)
        self._batch_timer.start(10)

    def _process_icon_batch(self):
        if not self._pending_icons:
            if self._batch_timer:
                self._batch_timer.stop()
            return
        # Process up to N icons per tick
        batch = 24
        for _ in range(min(batch, len(self._pending_icons))):
            button, bw = self._pending_icons.pop(0)
            try:
                self._ensure_button_icon(button, bw)
            except Exception:
                pass

    def update_selection(self, selected_path: str | None):
        """Visually highlight the selected button by path."""
        self._selected_path = selected_path
        # Styles
        base_style = """
            QPushButton { border: 2px solid #555; border-radius: 4px; background-color: #2b2b2b; }
            QPushButton:hover { border: 2px solid #0078d4; background-color: #333; }
            QPushButton:pressed { background-color: #0078d4; }
        """
        sel_style = """
            QPushButton { border: 3px solid #00aaff; border-radius: 4px; background-color: #2f2f2f; }
        """
        for b in self.effects_buttons:
            try:
                if getattr(b, 'effect_file_path', None) == selected_path and selected_path:
                    b.setStyleSheet(sel_style)
                else:
                    b.setStyleSheet(base_style)
            except Exception:
                pass

class GoLiveStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        # Initialize all optimization systems first
        self._init_optimization_systems()
        # Initialize unified timer system
        timer_manager.initialize(self)
        self.load_ui()
        # Connect UI signals to their slots
        self.connect_signals()
        # Initialize application state
        self.init_app_state()
        # Set performance mode based on system capabilities
        self._set_performance_mode()
        # Connect quality manager signals
        self._connect_quality_signals()
        
        # Initialize global FPS controller
        if FPS_CONTROLLER_AVAILABLE:
            try:
                self.fps_controller = get_fps_controller()
                self.streaming_manager = get_streaming_manager()
                
                # Set initial FPS from configuration
                initial_fps = int(app_config.get('ui.preview_fps', 60))
                self.fps_controller.set_target_fps(initial_fps)
                self.fps_controller.start()
                
                print(f"Global FPS Controller initialized at {initial_fps} FPS")
            except Exception as e:
                print(f"FPS Controller initialization error: {e}")
        
        # Start deferred systems that use QTimer (must be after QObject/QApplication ready)
        try:
            event_coalescer.start()
            ui_coalescer.start()
        except Exception as _e:
            print(f"Deferred coalescers start warning: {_e}")
        try:
            performance_monitor.start_monitoring()
        except Exception as _e:
            print(f"Performance monitor start warning: {_e}")
    
    def _init_optimization_systems(self):
        """Initialize all optimization systems."""
        # Initialize GL context manager
        gl_context_manager.initialize()
        
        # Set up memory pools
        general_memory_pool.optimize()
        image_memory_pool.optimize()
        
        # Configure smart cache
        smart_cache.clear()  # Start fresh
        
        # Set up event coalescers
        event_coalescer.register_handler('ui_update', self._handle_coalesced_ui_update)
        event_coalescer.register_handler('fps_update', self._handle_coalesced_fps_update)
        
        # Initialize optimization systems
        print("Optimization systems initialized")
        
        # Initialize performance optimizer for better memory and FPS management
        if PERFORMANCE_OPTIMIZER_AVAILABLE:
            self.performance_optimizer = get_performance_optimizer()
            # Force initial memory optimization
            optimize_performance_now()
            print("Performance optimizer initialized with aggressive memory management")
        else:
            self.performance_optimizer = None
        
        # Apply ultra-aggressive memory optimization to meet 250MB target
        if AGGRESSIVE_MEMORY_OPTIMIZER_AVAILABLE:
            success = force_memory_under_target(250)
            if success:
                print("✅ Memory successfully optimized to under 250MB target")
            else:
                print("⚠️ Memory optimization applied, but target not fully met")
            
            # Enable continuous memory management
            continuous_memory_management()
            print("Continuous memory management enabled")
    
    def _connect_quality_signals(self):
        """Connect adaptive quality manager signals."""
        quality_manager.quality_changed.connect(self._on_quality_changed)
        quality_manager.settings_updated.connect(self._on_quality_settings_updated)
    
    def _on_quality_changed(self, level: str):
        """Handle quality level change."""
        print(f"Adaptive quality changed to: {level}")
        # Update UI to reflect quality change
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(f"Quality: {level}", 2000)
    
    def _on_quality_settings_updated(self, settings: dict):
        """Apply new quality settings."""
        try:
            # Update FPS
            if 'fps' in settings and hasattr(self, '_graphics_output'):
                self._graphics_output.set_target_fps(settings['fps'])
            
            # Update resolution
            if 'resolution' in settings:
                width, height = settings['resolution']
                # Update output resolution
                app_config.set('recording.width', width)
                app_config.set('recording.height', height)
            
            # Update effects
            if 'effects_enabled' in settings:
                # Enable/disable effects based on quality
                pass  # Implement as needed
            
            # Update cache sizes
            if 'cache_size' in settings:
                from premiere_effects_panel_final import ThumbnailCache
                cache = ThumbnailCache()
                cache._max_cache_size = settings['cache_size']
        except Exception as e:
            print(f"Error applying quality settings: {e}")
    
    def _handle_coalesced_ui_update(self, data):
        """Handle coalesced UI updates."""
        # Process batched UI updates
        if data and isinstance(data, set):
            for widget in data:
                try:
                    widget.update()
                except:
                    pass
    
    def _handle_coalesced_fps_update(self, data):
        """Handle coalesced FPS updates."""
        # Process batched FPS updates
        pass
    
    def _set_performance_mode(self):
        """Set performance mode based on system capabilities."""
        try:
            import psutil
            cpu_count = psutil.cpu_count(logical=False) or 4
            memory_gb = psutil.virtual_memory().total / (1024**3)
            
            if cpu_count >= 8 and memory_gb >= 16:
                fps_manager.set_performance_mode('quality')
                print("Performance mode: Quality (High-end system detected)")
            elif cpu_count >= 4 and memory_gb >= 8:
                fps_manager.set_performance_mode('balanced')
                print("Performance mode: Balanced (Mid-range system detected)")
            else:
                fps_manager.set_performance_mode('performance')
                print("Performance mode: Performance (Resource-constrained system)")
        except:
            fps_manager.set_performance_mode('balanced')
            print("Performance mode: Balanced (default)")
        try:
            overscan = app_config.get('ui.overscan', 1.00)
            fps = app_config.get('ui.preview_fps', 60)
            if self._graphics_output is not None:
                self._graphics_output.set_overscan(overscan)
                self._graphics_output.set_target_fps(fps)
            # Don't auto-restore last effect - effects should be cleared by default
            # last_effect = app_config.get('ui.last_effect', None)
            # if last_effect and os.path.exists(last_effect) and self._graphics_output is not None:
            #     self._graphics_output.set_overlay_from_path(last_effect)
        except Exception as e:
            print(f"Error restoring settings: {e}")

        # Transitions
        self.transition_manager = TransitionManager(self)
        # Lock to prevent normal output updates during transitions (prevents flicker)
        self._transition_running = False
        self.selected_transition = app_config.get('ui.transition.type', 'None')
        self.transition_duration_ms = int(app_config.get('ui.transition.duration_ms', 700))
        self.transition_easing = app_config.get('ui.transition.easing', 'ease_in_out')
        try:
            self.setup_transitions_panel()
        except Exception as e:
            print(f"Error setting up transitions panel: {e}")

        # Streaming controller
        self.stream_controller = StreamController(self)
        self.stream_controller.set_frame_provider(self._provide_stream_frame)
        try:
            self.stream_controller.statusChanged.connect(self._on_stream_status_changed)
        except Exception:
            pass

        # External Display Mirror controller - Enhanced version fixes pixelation
        try:
            if _USE_ENHANCED_MIRROR:
                self.mirror_controller = EnhancedDisplayMirrorController(self)
                print("Enhanced Display Mirror Controller initialized with pixelation fixes")
            else:
                self.mirror_controller = DisplayMirrorController(self)
                print("Standard Display Mirror Controller initialized")
            self.mirror_controller.set_frame_provider(self._provide_stream_frame)
        except Exception as e:
            print(f"Error initializing DisplayMirrorController: {e}")

        # Independent RTMP stream controllers (Stream 1 and Stream 2)
        try:
            print("🎬 Initializing stream controllers...")
            self.stream_controllers = {
                1: StreamController(self),
                2: StreamController(self),
            }
            for stream_id, sc in self.stream_controllers.items():
                sc.set_frame_provider(self._provide_stream_frame)
                sc.statusChanged.connect(self._on_stream_status_changed)
                print(f"✅ Stream {stream_id} controller initialized")
            
            # Initialize stream states
            self.stream1_active = False
            self.stream2_active = False
            print("✅ Stream controllers initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing StreamControllers: {e}")
            import traceback
            traceback.print_exc()

        # Enhanced Recording controller
        try:
            print("🎥 Initializing recording controller...")
            self.recorder_controller = RecorderController(self)
            # Provide program output frames to the recorder
            self.recorder_controller.set_frame_provider(self._provide_stream_frame)
            self.recorder_controller.on_log(self._on_record_log)
            self.recorder_controller.statusChanged.connect(self._on_record_status_changed)
            
            # Initialize recording state
            self.recording = False
            
            print("✅ Recording controller initialized successfully")
            
            # Show recording health info on startup
            self.show_recording_health_info()
        except Exception as e:
            print(f"❌ Error initializing RecorderController: {e}")
            import traceback
            traceback.print_exc()

        # Install graphics output view if not present yet
        try:
            self._ensure_output_preview_label()
        except Exception:
            pass

        # Add compact Text Overlay mini bar beside Switching Controls (without altering other UI)
        try:
            if hasattr(self, 'horizontalLayout_allButtons'):
                lay = self.horizontalLayout_allButtons
                self.textOverlayMini = TextOverlayMiniBar(self)
                # Insert before the right-side spacer (last item)
                try:
                    insert_pos = max(0, lay.count() - 1)
                except Exception:
                    insert_pos = lay.count()
                lay.insertWidget(insert_pos, self.textOverlayMini)

                # Wire to graphics output
                def _on_overlay_changed(d: dict):
                    if hasattr(self, '_graphics_output') and self._graphics_output is not None:
                        self._graphics_output.set_text_overlay(d)
                self.textOverlayMini.overlayChanged.connect(_on_overlay_changed)

                # Apply defaults once UI is ready
                def _emit_defaults():
                    try:
                        p = self.textOverlayMini.props_ref.props
                        init = {
                            **p,
                            'color': p['color'].rgba(),
                            'stroke_color': p['stroke_color'].rgba(),
                            'bg_color': p['bg_color'].rgba(),
                        }
                        _on_overlay_changed(init)
                    except Exception:
                        pass
                QTimer.singleShot(0, _emit_defaults)
        except Exception as e:
            print(f"Error installing Text Overlay mini bar: {e}")

    def load_ui(self):
        """Load UI from .ui file directly"""
        try:
            # Get the absolute path to the .ui file
            ui_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mainwindow.ui")
            
            # Load the .ui file directly
            uic.loadUi(ui_file_path, self)
            # print("UI loaded successfully from mainwindow.ui")
            
            # Set icons programmatically after UI is loaded
            self.set_ui_icons()
            
            # Apply 16:9 aspect ratio to video widgets
            self.apply_aspect_ratio_constraints()

            # Enforce 50/50 split between left and right main panels
            self.apply_main_panel_stretch()

            # Load effects from folder into tabs
            self.load_effects_into_tabs()

            # Make transitions panel grow to fill extra space on the right
            self.apply_right_panel_stretch()

            # Make effects tabs grow to fill extra space on the left
            self.apply_left_panel_stretch()

            # Install a vertical splitter in the left panel: Output (top) | Effects (bottom)
            self.apply_left_splitter()

            # Install a vertical splitter in the right panel: Sources grid (top) | Transitions (bottom)
            self.apply_right_splitter()

            # After layout is ready, set splitter sizes to sane defaults
            QTimer.singleShot(0, self._init_splitter_sizes)

            # Install output aspect guard to enforce 16:9 based on actual width
            QTimer.singleShot(0, self._install_output_aspect_guard)
            # Install calibration shortcut (Ctrl+Shift+C)
            try:
                from PyQt6.QtGui import QShortcut, QKeySequence
                self._calib_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
                self._calib_shortcut.activated.connect(self.open_calibration_tool)
            except Exception:
                pass
            # Audio delay correction will be applied automatically when needed
            # Populate audio outputs if the combo exists
            try:
                self._populate_audio_outputs_combo()
            except Exception:
                pass
            
        except Exception as e:
            print(f"Failed to load UI file: {e}")
            sys.exit(-1)
    
    def get_icon(self, icon_name):
        """Get icon from icons folder with cross-platform path handling"""
        try:
            # Get the directory where this script is located
            if getattr(sys, 'frozen', False):
                # If running as compiled executable
                base_path = sys._MEIPASS
            else:
                # If running as script
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            icon_path = os.path.join(base_path, "icons", icon_name)
            
            if os.path.exists(icon_path):
                return QIcon(icon_path)
            else:
                # Fallback to a default icon or empty icon
                print(f"Warning: Icon not found: {icon_path}")
                return QIcon()  # Empty icon
        except Exception as e:
            print(f"Error loading icon {icon_name}: {e}")
            return QIcon()  # Empty icon
    
    def connect_signals(self):
        """Connect UI signals to their respective slots"""
        try:
            # Record buttons
            if hasattr(self, 'recordRedCircle'):
                self.recordRedCircle.clicked.connect(self.toggle_recording)
            if hasattr(self, 'playButton'):
                self.playButton.clicked.connect(self.toggle_playback)
            if hasattr(self, 'captureButton'):
                self.captureButton.clicked.connect(self.capture_screenshot)
            if hasattr(self, 'settingsRecordButton'):
                # Simple direct connection to recording settings
                self.settingsRecordButton.clicked.connect(self.open_record_settings)
                self.settingsRecordButton.setToolTip("Recording Settings")
                print("✅ Connected recording settings button")
            
            # Check for text overlay button
            if hasattr(self, 'textOverlayButton'):
                self.textOverlayButton.clicked.connect(self.show_text_overlay_settings)
                self.textOverlayButton.setToolTip("Text Overlay Settings")
                print("✅ Connected text overlay settings button")
            elif hasattr(self, 'overlayButton'):
                self.overlayButton.clicked.connect(self.show_text_overlay_settings)
                self.overlayButton.setToolTip("Text Overlay Settings")
                print("✅ Connected overlay settings button")
            
            # Stream buttons - Settings buttons open settings dialog, separate toggle mechanism
            if hasattr(self, 'stream1SettingsBtn'):
                # Left-click opens settings dialog
                self.stream1SettingsBtn.clicked.connect(lambda: self.open_stream_settings_dialog(1))
                self.stream1SettingsBtn.setToolTip("Stream 1 Settings")
                print("✅ Connected Stream 1 settings button")
            else:
                print("❌ Stream 1 settings button not found")
            
            if hasattr(self, 'stream2SettingsBtn'):
                # Left-click opens settings dialog
                self.stream2SettingsBtn.clicked.connect(lambda: self.open_stream_settings_dialog(2))
                self.stream2SettingsBtn.setToolTip("Stream 2 Settings")
                print("✅ Connected Stream 2 settings button")
            else:
                print("❌ Stream 2 settings button not found")
            
            # Connect stream labels for toggling streams
            if hasattr(self, 'stream1Label'):
                # Make stream label clickable to toggle streaming
                self.stream1Label.mousePressEvent = lambda event: self.handle_stream_button_click(1)
                self.stream1Label.setToolTip("Click to toggle Stream 1")
                self.stream1Label.setStyleSheet("QLabel:hover { background-color: #3a3a3a; border-radius: 4px; }")
                print("✅ Connected Stream 1 label for toggling")
            
            if hasattr(self, 'stream2Label'):
                # Make stream label clickable to toggle streaming
                self.stream2Label.mousePressEvent = lambda event: self.handle_stream_button_click(2)
                self.stream2Label.setToolTip("Click to toggle Stream 2")
                self.stream2Label.setStyleSheet("QLabel:hover { background-color: #3a3a3a; border-radius: 4px; }")
                print("✅ Connected Stream 2 label for toggling")
            
            # Audio buttons in Additional section
            # Top button is Global Mute toggle for the entire app (inputs + media)
            if hasattr(self, 'audioTopButton'):
                self.audioTopButton.clicked.connect(self.toggle_global_mute)
                try:
                    self.audioTopButton.setToolTip("Global Mute (mute all inputs and media)")
                except Exception:
                    pass
            # Second button: Clear Visuals (restored to original functionality)
            if hasattr(self, 'bottomButton2'):
                try:
                    # Ensure no menu is attached
                    try:
                        self.bottomButton2.setMenu(None)
                    except Exception:
                        pass
                    # Click to clear visuals
                    self.bottomButton2.clicked.connect(self.action_clear_visuals)
                    self.bottomButton2.setToolTip("Clear Visuals (remove overlay and hide text)")
                except Exception:
                    pass
            
            # Combo boxes
            if hasattr(self, 'outputSizeComboBox'):
                # Populate Output Size profiles and set initial selection
                try:
                    self._populate_output_size_combo()
                except Exception:
                    pass
                self.outputSizeComboBox.currentTextChanged.connect(self.on_output_size_changed)
            if hasattr(self, 'fpsComboBox'):
                # Set default FPS selection
                try:
                    current_fps = int(app_config.get('ui.preview_fps', 60))
                    if current_fps == 30:
                        self.fpsComboBox.setCurrentText("30 FPS")
                    else:
                        self.fpsComboBox.setCurrentText("60 FPS")
                except Exception:
                    self.fpsComboBox.setCurrentText("60 FPS")
                self.fpsComboBox.currentTextChanged.connect(self.on_fps_changed)
            if hasattr(self, 'audioOutputComboBox'):
                self.audioOutputComboBox.currentTextChanged.connect(self.on_audio_output_changed)
            
            # Connect input settings buttons to camera selection dialogs
            if hasattr(self, 'input1SettingsButton'):
                self.input1SettingsButton.clicked.connect(lambda: self.show_camera_selection_dialog(1))
                print("✅ Connected Input 1 settings button")
            else:
                print("❌ Input 1 settings button not found")
            
            if hasattr(self, 'input2SettingsButton'):
                self.input2SettingsButton.clicked.connect(lambda: self.show_camera_selection_dialog(2))
                print("✅ Connected Input 2 settings button")
            else:
                print("❌ Input 2 settings button not found")
                
            if hasattr(self, 'input3SettingsButton'):
                self.input3SettingsButton.clicked.connect(lambda: self.show_camera_selection_dialog(3))
                print("✅ Connected Input 3 settings button")
            else:
                print("❌ Input 3 settings button not found")
            
            # Connect media settings buttons to media file selection dialogs
            if hasattr(self, 'media1SettingsButton'):
                self.media1SettingsButton.clicked.connect(lambda: self.show_media_selection_dialog(1))
                print("✅ Connected Media 1 settings button")
            else:
                print("❌ Media 1 settings button not found")
                
            if hasattr(self, 'media2SettingsButton'):
                self.media2SettingsButton.clicked.connect(lambda: self.show_media_selection_dialog(2))
                print("✅ Connected Media 2 settings button")
            else:
                print("❌ Media 2 settings button not found")
                
            if hasattr(self, 'media3SettingsButton'):
                self.media3SettingsButton.clicked.connect(lambda: self.show_media_selection_dialog(3))
                print("✅ Connected Media 3 settings button")
            else:
                print("❌ Media 3 settings button not found")
        
            # Connect media control buttons (play/pause) mapped to UI names pushButton_19/20/21
            if hasattr(self, 'pushButton_19'):
                self.pushButton_19.clicked.connect(lambda: self.toggle_media_playback(1))
            if hasattr(self, 'pushButton_20'):
                self.pushButton_20.clicked.connect(lambda: self.toggle_media_playback(2))
            if hasattr(self, 'pushButton_21'):
                self.pushButton_21.clicked.connect(lambda: self.toggle_media_playback(3))
        
            # Connect audio toggle buttons for inputs
            if hasattr(self, 'input1AudioButton'):
                self.input1AudioButton.clicked.connect(lambda: self.toggle_input_audio(1))
            if hasattr(self, 'input2AudioButton'):
                self.input2AudioButton.clicked.connect(lambda: self.toggle_input_audio(2))
            if hasattr(self, 'input3AudioButton'):
                self.input3AudioButton.clicked.connect(lambda: self.toggle_input_audio(3))

            # Connect audio toggle buttons for media
            if hasattr(self, 'media1AudioButton'):
                self.media1AudioButton.clicked.connect(lambda: self.toggle_media_audio(1))
            if hasattr(self, 'media2AudioButton'):
                self.media2AudioButton.clicked.connect(lambda: self.toggle_media_audio(2))
            if hasattr(self, 'media3AudioButton'):
                self.media3AudioButton.clicked.connect(lambda: self.toggle_media_audio(3))
        
            # Connect progress sliders for media seeking (0-100 percent)
            if hasattr(self, 'horizontalSlider'):
                self.horizontalSlider.valueChanged.connect(lambda value: self.seek_media(1, value))
            if hasattr(self, 'horizontalSlider_2'):
                self.horizontalSlider_2.valueChanged.connect(lambda value: self.seek_media(2, value))
            if hasattr(self, 'horizontalSlider_3'):
                self.horizontalSlider_3.valueChanged.connect(lambda value: self.seek_media(3, value))

            # print("UI signals connected successfully")
        except Exception as e:
            print(f"Error connecting UI signals: {e}")

        # Connect switching controls
        try:
            if hasattr(self, 'switchInput1Btn'):
                self.switchInput1Btn.clicked.connect(lambda: self.set_output_source('input', 1))
            if hasattr(self, 'switchInput2Btn'):
                self.switchInput2Btn.clicked.connect(lambda: self.set_output_source('input', 2))
            if hasattr(self, 'switchInput3Btn'):
                self.switchInput3Btn.clicked.connect(lambda: self.set_output_source('input', 3))
            if hasattr(self, 'switchMedia1Btn'):
                self.switchMedia1Btn.clicked.connect(lambda: self.set_output_source('media', 1))
            if hasattr(self, 'switchMedia2Btn'):
                self.switchMedia2Btn.clicked.connect(lambda: self.set_output_source('media', 2))
            if hasattr(self, 'switchMedia3Btn'):
                self.switchMedia3Btn.clicked.connect(lambda: self.set_output_source('media', 3))
        except Exception as e:
            print(f"Error connecting switching controls: {e}")
    def toggle_media_playback(self, media_index):
        """Toggle playback for the specified media (Qt Multimedia)"""
        player = self.media_players[media_index]
        if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            player.pause()
        else:
            # Ensure only one media plays at a time
            self._pause_all_media_except(media_index)
            player.play()
            # If this media is currently on program output, apply audio delay correction
            if getattr(self, 'current_output', None) == ('media', media_index):
                print(f"Media {media_index} started playing on program output - applying audio delay correction...")
                self._auto_apply_audio_delay_correction()
        self.update_media_controls(media_index)

    def toggle_media_audio(self, media_index):
        """Toggle audio mute for the specified media (Qt Multimedia)"""
        # Only allow unmuting if this media is the current output; otherwise enforce mute
        is_current_output = getattr(self, 'current_output', None) == ('media', media_index)
        audio_output = self.media_audio_outputs[media_index]
        if is_current_output:
            # Respect Global Mute: if enabled, force muted
            if getattr(self, 'global_audio_muted', False):
                print("Global mute is enabled; media will remain muted until global mute is disabled.")
                audio_output.setMuted(True)
            else:
                audio_output.setMuted(not audio_output.isMuted())
        else:
            # Enforce muted when not on program output
            audio_output.setMuted(True)
            print(f"Media {media_index} audio can only be unmuted when routed to output.")
        # Persist and reflect state
        setattr(self, f"media{media_index}_audio_muted", audio_output.isMuted())
        btn_attr = f"media{media_index}AudioButton"
        if hasattr(self, btn_attr):
            btn = getattr(self, btn_attr)
            # If global mute is on, always show Mute icon
            force_muted = audio_output.isMuted() or getattr(self, 'global_audio_muted', False)
            btn.setIcon(self.get_icon("Mute.png" if force_muted else "Volume.png"))

    def seek_media(self, media_index, position_percent):
        """Seek in media based on percent (0-100)"""
        player = self.media_players[media_index]
        dur = max(1, player.duration())
        target_ms = int(dur * (position_percent / 100.0))
        player.setPosition(target_ms)
        # If this media is on Program and streaming is active, resync stream to this new position
        try:
            if getattr(self, 'current_output', None) == ('media', media_index) and hasattr(self, 'stream_controller'):
                sc = self.stream_controller
                if hasattr(sc, 'is_running') and sc.is_running():
                    media_path = self.get_current_program_media_audio_path()
                    if media_path:
                        sc.resync_to_media(media_path, target_ms)
                        # Apply audio delay correction after seeking
                        print(f"Media {media_index} seeked - reapplying audio delay correction...")
                        self._auto_apply_audio_delay_correction()
        except Exception as e:
            print(f"Error resyncing stream on seek: {e}")

    def load_media(self, media_index, file_path):
        """Load the specified media file (Qt Multimedia)"""
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                print(f"Error: Media file does not exist: {file_path}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "File Not Found", 
                                   f"The selected file does not exist:\n{file_path}")
                return
            
            # Get file info
            file_size = os.path.getsize(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            print(f"Loading Media {media_index}: {file_path}")
            print(f"  File size: {file_size:,} bytes")
            print(f"  File extension: {file_ext}")
            
            player = self.media_players[media_index]
            
            # Stop any current playback
            if player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                player.stop()
            
            # Clear current source
            player.setSource(QUrl())
            
            # Set new source
            url = QUrl.fromLocalFile(file_path)
            print(f"  Setting source URL: {url.toString()}")
            player.setSource(url)
            
            # Wait a moment for media to load
            QApplication.processEvents()
            
            # Media should be paused by default when loaded
            player.pause()
            self.update_media_controls(media_index)
            
            print(f"  Media {media_index} loaded successfully (paused by default)")
            print(f"  Audio delay correction will be applied automatically when streaming (configurable)")
            
            # If this media becomes active and there's a 5-second delay issue, 
            # automatically apply a negative offset to compensate
            if hasattr(self, '_auto_sync_correction') and self._auto_sync_correction:
                print(f"  Auto-sync correction enabled for Media {media_index}")

            # Remember media file path for streaming audio mapping
            if not hasattr(self, 'media_paths'):
                self.media_paths = {}
            self.media_paths[media_index] = file_path

            # Immediately set output if this media is selected (use original image if available)
            if not getattr(self, '_transition_running', False) and self.current_output == ('media', media_index):
                if media_index in self.last_media_image:
                    self._set_output_image(self.last_media_image[media_index])
                elif media_index in self.last_media_pixmap:
                    self._set_output_pixmap(self.last_media_pixmap[media_index])
                    
        except Exception as e:
            print(f"Error loading media {media_index}: {e}")
            import traceback
            traceback.print_exc()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Media Load Error", 
                               f"Failed to load media file:\n{str(e)}")

    def _on_media_position_changed(self, media_index, pos_ms):
        """Update UI when media position changes"""
        # Update slider
        slider_attr = {1: 'horizontalSlider', 2: 'horizontalSlider_2', 3: 'horizontalSlider_3'}.get(media_index)
        if slider_attr and hasattr(self, slider_attr):
            slider = getattr(self, slider_attr)
            dur = max(1, self.media_players[media_index].duration())
            percent = int((pos_ms / dur) * 100)
            slider.blockSignals(True)
            slider.setValue(percent)
            slider.blockSignals(False)
        # Update controls (icon)
        self.update_media_controls(media_index)

    def _on_media_duration_changed(self, media_index, dur_ms):
        """Handle duration updates if needed (placeholder for future)"""
        pass
    
    def _on_media_error(self, media_index, error):
        """Handle media player errors"""
        error_string = {
            QMediaPlayer.Error.NoError: "No error",
            QMediaPlayer.Error.ResourceError: "Resource/file error",
            QMediaPlayer.Error.FormatError: "Format not supported",
            QMediaPlayer.Error.NetworkError: "Network error",
            QMediaPlayer.Error.AccessDeniedError: "Access denied"
        }.get(error, f"Unknown error: {error}")
        
        print(f"Media {media_index} error: {error_string}")
        
        # Show error message to user
        if error != QMediaPlayer.Error.NoError:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, f"Media {media_index} Error", 
                               f"Failed to load media: {error_string}\n\n"
                               f"Please check that the file exists and is in a supported format.")
    
    def _on_media_status_changed(self, media_index, status):
        """Handle media status changes for debugging"""
        status_string = {
            QMediaPlayer.MediaStatus.NoMedia: "No media",
            QMediaPlayer.MediaStatus.LoadingMedia: "Loading media",
            QMediaPlayer.MediaStatus.LoadedMedia: "Media loaded",
            QMediaPlayer.MediaStatus.StalledMedia: "Media stalled",
            QMediaPlayer.MediaStatus.BufferingMedia: "Buffering media",
            QMediaPlayer.MediaStatus.BufferedMedia: "Media buffered",
            QMediaPlayer.MediaStatus.EndOfMedia: "End of media",
            QMediaPlayer.MediaStatus.InvalidMedia: "Invalid media"
        }.get(status, f"Unknown status: {status}")
        
        print(f"Media {media_index} status: {status_string}")
        
        # If media is invalid, show error
        if status == QMediaPlayer.MediaStatus.InvalidMedia:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, f"Media {media_index} Invalid", 
                               f"The selected media file is invalid or corrupted.\n"
                               f"Please select a different file.")
    
    def _on_playback_state_changed(self, media_index, state):
        """Handle playback state changes"""
        state_string = {
            QMediaPlayer.PlaybackState.StoppedState: "Stopped",
            QMediaPlayer.PlaybackState.PlayingState: "Playing",
            QMediaPlayer.PlaybackState.PausedState: "Paused"
        }.get(state, f"Unknown state: {state}")
        
        print(f"Media {media_index} playback state: {state_string}")

    def _on_media_frame(self, media_index, video_frame):
        """Handle incoming media frames from QVideoSink and render to the media frame and output preview if selected"""
        try:
            image = video_frame.toImage()
            if image is not None and not image.isNull():
                # Debug: Only log first few frames to avoid spam
                if not hasattr(self, '_media_frame_count'):
                    self._media_frame_count = {}
                if media_index not in self._media_frame_count:
                    self._media_frame_count[media_index] = 0
                self._media_frame_count[media_index] += 1
                if self._media_frame_count[media_index] <= 3:
                    print(f"🎬 Media-{media_index}: Received frame {image.width()}x{image.height()}")
            
            # Update the current source in graphics output if this media is on program
            if hasattr(self, '_graphics_output') and hasattr(self, 'outputSource') and \
               self.outputSource == 'media' and self.outputSourceIndex == media_index:
                self._graphics_output._current_source = {'type': 'media', 'index': media_index}
                self._graphics_output._last_frame = image
            if image.isNull():
                return
            # ✅ APPLY MEDIA PROCESSING (speed, scaling, effects, etc.)
            processed_image = image
            try:
                from media_processor import media_processors
                # Only process if settings are actually applied (not default values)
                if media_processors[media_index].is_enabled():
                    processed_result = media_processors[media_index].process_frame(image)
                    if processed_result is not None:
                        processed_image = processed_result
                        print(f"✅ Applied media processing to Media-{media_index}")
            except Exception as e:
                print(f"Media processing error for Media-{media_index}: {e}")
            
            # Cache processed image for high-quality output scaling
            self.last_media_image[media_index] = processed_image.copy()
            pix = QPixmap.fromImage(processed_image)
            # Ensure media label exists
            self._ensure_media_label(media_index)
            frame_attr = f"mediaVideoFrame{media_index}"
            if hasattr(self, frame_attr):
                frame = getattr(self, frame_attr)
                target_size = frame.size()
                if target_size.width() <= 1 or target_size.height() <= 1:
                    ms = frame.minimumSize()
                    target_size = ms if ms.isValid() else QSize(320, 180)
                scaled = pix.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if hasattr(frame, '_video_label'):
                    frame._video_label.setPixmap(scaled)
                # Store last and update output if selected
                self.last_media_pixmap[media_index] = scaled
                if not getattr(self, '_transition_running', False) and self.current_output == ('media', media_index):
                    # Use original for output to avoid double-scaling loss
                    self._set_output_image(self.last_media_image[media_index])
        except Exception as e:
            print(f"Error rendering media frame for Media-{media_index}: {e}")

    def _ensure_media_label(self, media_index):
        """Ensure a QLabel exists inside media frame to render pixmap"""
        frame_attr = f"mediaVideoFrame{media_index}"
        if hasattr(self, frame_attr):
            frame = getattr(self, frame_attr)
            if not hasattr(frame, '_video_label'):
                from PyQt6.QtWidgets import QLabel, QVBoxLayout, QSizePolicy
                label = QLabel(frame)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                if not frame.layout():
                    layout = QVBoxLayout(frame)
                    layout.setContentsMargins(0, 0, 0, 0)
                    frame.setLayout(layout)
                frame.layout().addWidget(label)
                frame._video_label = label

    # Phase 2: Input audio monitoring helpers
    def _ensure_input_audio(self, input_number):
        """Create QAudioSource and QAudioSink to monitor input audio (PyQt6)."""
        if not hasattr(self, 'input_audio_sources'):
            self.input_audio_sources = {}
        if not hasattr(self, 'input_audio_sinks'):
            self.input_audio_sinks = {}
        if not hasattr(self, 'input_audio_timers'):
            self.input_audio_timers = {}

        if input_number in self.input_audio_sources:
            return
        # Use default input/output devices for now
        input_dev = QMediaDevices.defaultAudioInput()
        output_dev = QMediaDevices.defaultAudioOutput()
        source = QAudioSource(input_dev)
        sink = QAudioSink(output_dev)
        self.input_audio_sources[input_number] = source
        self.input_audio_sinks[input_number] = sink

        # Start monitoring immediately unless muted: shuttle bytes from mic to speaker
        if not getattr(self, f"input{input_number}_audio_muted", True):
            out_dev = sink.start()
            in_dev = source.start()
            from PyQt6.QtCore import QTimer
            t = QTimer(self)
            t.setInterval(10)
            def pump():
                try:
                    data = in_dev.read(4096)
                    if data:
                        out_dev.write(data)
                except Exception:
                    pass
            t.timeout.connect(pump)
            t.start()
            self.input_audio_timers[input_number] = t

    def _stop_input_audio(self, input_number):
        if hasattr(self, 'input_audio_timers') and input_number in self.input_audio_timers:
            try:
                self.input_audio_timers[input_number].stop()
            except Exception:
                pass
            del self.input_audio_timers[input_number]
        if hasattr(self, 'input_audio_sources') and input_number in self.input_audio_sources:
            try:
                self.input_audio_sources[input_number].stop()
            except Exception:
                pass
            del self.input_audio_sources[input_number]
        if input_number in self.input_audio_sinks:
            try:
                self.input_audio_sinks[input_number].stop()
            except Exception:
                pass
            del self.input_audio_sinks[input_number]

    def apply_main_panel_stretch(self):
        """Set 50/50 stretch for left and right panels at the top level layout."""
        try:
            cw = self.centralWidget()
            if not cw:
                return
            top_layout = cw.layout()
            if not top_layout or not hasattr(top_layout, 'setStretch'):
                return
            # Find indices of items that contain the left and right panel layouts
            left_idx = right_idx = None
            for i in range(top_layout.count()):
                item = top_layout.itemAt(i)
                lay = item.layout() if item is not None else None
                if lay and lay.objectName() == 'verticalLayout_leftPanel':
                    left_idx = i
                if lay and lay.objectName() == 'verticalLayout_rightPanel':
                    right_idx = i
            # If not found as direct children, try to inspect child widgets' layouts
            if left_idx is None or right_idx is None:
                for i in range(top_layout.count()):
                    item = top_layout.itemAt(i)
                    w = item.widget() if item is not None else None
                    if w and hasattr(w, 'layout') and w.layout():
                        lay = w.layout()
                        # Check children of this layout
                        for j in range(lay.count()):
                            sub_item = lay.itemAt(j)
                            sub_lay = sub_item.layout() if sub_item else None
                            if sub_lay:
                                if sub_lay.objectName() == 'verticalLayout_leftPanel':
                                    left_idx = i
                                if sub_lay.objectName() == 'verticalLayout_rightPanel':
                                    right_idx = i
            if left_idx is not None and right_idx is not None:
                top_layout.setStretch(left_idx, 1)
                top_layout.setStretch(right_idx, 1)
        except Exception as e:
            print(f"Error applying main panel stretch: {e}")

    def apply_right_panel_stretch(self):
        """Ensure the transitions panel grows to absorb extra vertical space on the right panel.
        This prevents large empty gaps below 16:9 video boxes when the window is tall.
        """
        try:
            if not hasattr(self, 'tabWidget_transitions'):
                return
            # Ensure transitions widget is willing to expand
            from PyQt6.QtWidgets import QSizePolicy
            self.tabWidget_transitions.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            # Find its immediate parent layout and set stretch
            parent = self.tabWidget_transitions.parent()
            while parent and (not hasattr(parent, 'layout') or parent.layout() is None):
                parent = parent.parent()
            if not parent:
                return
            lay = parent.layout()
            if not lay or not hasattr(lay, 'setStretch'):
                return
            trans_index = None
            for i in range(lay.count()):
                item = lay.itemAt(i)
                if item and item.widget() is self.tabWidget_transitions:
                    trans_index = i
                    break
            if trans_index is None:
                return
            # Minimize stretch for other rows, maximize for transitions row
            for i in range(lay.count()):
                lay.setStretch(i, 0)
            lay.setStretch(trans_index, 1)
        except Exception as e:
            print(f"Error applying right panel stretch: {e}")

    def apply_left_panel_stretch(self):
        """Prioritize outputPreview height in the left panel. Ensure output grows more than
        the effects area when the window is tall, keeping output 16:9 and avoiding width-only stretching.
        """
        try:
            from PyQt6.QtWidgets import QSizePolicy
            # Determine which effects UI is present
            has_tabs = hasattr(self, 'tabWidget_effects') and self.tabWidget_effects is not None
            has_pep = hasattr(self, 'premiere_effects_panel') and self.premiere_effects_panel is not None
            if not (has_tabs or has_pep):
                return
            # Effects can expand but shouldn't steal priority from output
            if has_tabs:
                self.tabWidget_effects.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if has_pep:
                self.premiere_effects_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            cw = self.centralWidget()
            if not cw or not cw.layout():
                return
            # Find left panel vertical layout
            left_layout = None
            tl = cw.layout()
            for i in range(tl.count()):
                item = tl.itemAt(i)
                lay = item.layout() if item else None
                if lay and lay.objectName() == 'verticalLayout_leftPanel':
                    left_layout = lay
                    break
                w = item.widget() if item else None
                if w and hasattr(w, 'layout') and w.layout() and w.layout().objectName() == 'verticalLayout_leftPanel':
                    left_layout = w.layout()
                    break
            if not left_layout or not hasattr(left_layout, 'setStretch'):
                return

            # Locate container indexes
            output_idx = None
            effects_idx = None
            for i in range(left_layout.count()):
                item = left_layout.itemAt(i)
                w = item.widget() if item else None
                if w and getattr(w, 'objectName', lambda: '')() == 'outputPreview':
                    output_idx = i
                if w and hasattr(w, 'findChild'):
                    # Old tabs container
                    if has_tabs:
                        tw = w.findChild(type(self.tabWidget_effects), 'tabWidget_effects')
                        if tw is not None:
                            effects_idx = i
                    # New Premiere panel container
                    try:
                        from premiere_effects_panel_final import FinalEffectsPanel as _PEP
                        if has_pep and w.findChild(_PEP) is not None:
                            effects_idx = i
                    except Exception:
                        pass

            # Default: last item is effects
            if effects_idx is None and left_layout.count() > 0:
                effects_idx = left_layout.count() - 1

            # Apply stretches: output gets higher priority
            for i in range(left_layout.count()):
                left_layout.setStretch(i, 0)
            if output_idx is not None:
                left_layout.setStretch(output_idx, 3)
            if effects_idx is not None:
                left_layout.setStretch(effects_idx, 1)
        except Exception as e:
            print(f"Error applying left panel stretch: {e}")

    def apply_left_splitter(self):
        """Replace the left panel stack with a QSplitter so Output keeps priority height
        and the user gets a robust, resizable layout. Output stays 16:9 via AspectRatioFrame.
        """
        try:
            cw = self.centralWidget()
            if not cw or not cw.layout():
                return
            # Find the left panel vertical layout
            left_layout = None
            tl = cw.layout()
            for i in range(tl.count()):
                item = tl.itemAt(i)
                lay = item.layout() if item else None
                if lay and lay.objectName() == 'verticalLayout_leftPanel':
                    left_layout = lay
                    break
                w = item.widget() if item else None
                if w and hasattr(w, 'layout') and w.layout() and w.layout().objectName() == 'verticalLayout_leftPanel':
                    left_layout = w.layout()
                    break
            if not left_layout:
                return

            # Identify direct child widgets: output container and effects container
            output_widget = None
            effects_container = None
            for i in range(left_layout.count()):
                item = left_layout.itemAt(i)
                w = item.widget() if item else None
                if not w:
                    continue
                if getattr(w, 'objectName', lambda: '')() == 'outputPreview':
                    output_widget = w
                # Check if this widget contains tabWidget_effects
                if hasattr(self, 'tabWidget_effects') and hasattr(w, 'findChild'):
                    found = w.findChild(type(self.tabWidget_effects), 'tabWidget_effects')
                    if found is not None:
                        effects_container = w
                # Also support the new PremiereEffectsPanel as the marker for the effects area
                try:
                    from premiere_effects_panel_v2 import PremiereEffectsPanelV2 as _PEP
                    # If the panel itself is the widget, or the widget contains it
                    if isinstance(w, _PEP) or (hasattr(w, 'findChild') and w.findChild(_PEP) is not None):
                        effects_container = w
                except Exception:
                    pass

            # If effects container not detected, fall back to last widget in layout
            if effects_container is None:
                # Try to find an existing PremiereEffectsPanel anywhere and move it under left panel
                try:
                    from premiere_effects_panel_v2 import PremiereEffectsPanelV2 as _PEP
                    found_panel = None
                    # Look in all children of the main window
                    for child in self.findChildren(_PEP):
                        found_panel = child
                        break
                    if found_panel is not None:
                        # Remove from its current layout
                        try:
                            par = found_panel.parent()
                            if par and hasattr(par, 'layout') and par.layout():
                                par.layout().removeWidget(found_panel)
                        except Exception:
                            pass
                        # Insert as a new widget at the bottom of the left layout
                        left_layout.addWidget(found_panel)
                        effects_container = found_panel
                except Exception:
                    pass
                # Final fallback to last item
                if effects_container is None and left_layout.count() > 0:
                    last_item = left_layout.itemAt(left_layout.count() - 1)
                    effects_container = last_item.widget() if last_item else None

            if not output_widget or not effects_container:
                return

            # Remove both from layout without deleting
            for target in (output_widget, effects_container):
                for i in range(left_layout.count() - 1, -1, -1):
                    if left_layout.itemAt(i) and left_layout.itemAt(i).widget() is target:
                        left_layout.takeAt(i)
                        break

            # Create splitter
            splitter = QSplitter(Qt.Orientation.Vertical, cw)
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(6)
            splitter.addWidget(output_widget)
            splitter.addWidget(effects_container)
            splitter.setStretchFactor(0, 3)  # Output priority
            splitter.setStretchFactor(1, 1)  # Effects grows but less

            # Insert splitter back into left layout
            left_layout.addWidget(splitter)
            # Keep a handle to tune sizes later
            self._left_splitter = splitter
        except Exception as e:
            print(f"Error applying left splitter: {e}")

    def apply_right_splitter(self):
        """Replace the right panel stack with a QSplitter so Transitions can absorb extra height
        while keeping the sources grid compact. This avoids large blank gaps under 16:9 tiles.
        """
        try:
            cw = self.centralWidget()
            if not cw or not cw.layout():
                return
            # Find the right panel vertical layout
            right_layout = None
            tl = cw.layout()
            for i in range(tl.count()):
                item = tl.itemAt(i)
                lay = item.layout() if item else None
                if lay and lay.objectName() == 'verticalLayout_rightPanel':
                    right_layout = lay
                    break
                w = item.widget() if item else None
                if w and hasattr(w, 'layout') and w.layout() and w.layout().objectName() == 'verticalLayout_rightPanel':
                    right_layout = w.layout()
                    break
            if not right_layout:
                return

            # Identify transitions and the block above it (sources cluster)
            transitions_widget = getattr(self, 'tabWidget_transitions', None)
            sources_container = None
            trans_idx = None
            for i in range(right_layout.count()):
                it = right_layout.itemAt(i)
                w = it.widget() if it else None
                if w is transitions_widget:
                    trans_idx = i
                    # Previous visible widget is considered sources container
                    # Look upward for the nearest widget item
                    for j in range(i - 1, -1, -1):
                        prev = right_layout.itemAt(j)
                        if prev and prev.widget():
                            sources_container = prev.widget()
                            break
                    break
            if not transitions_widget or not sources_container:
                return

            # Take both out of layout (without deleting)
            for target in (sources_container, transitions_widget):
                for i in range(right_layout.count() - 1, -1, -1):
                    if right_layout.itemAt(i) and right_layout.itemAt(i).widget() is target:
                        right_layout.takeAt(i)
                        break

            # Create splitter and set factors
            splitter = QSplitter(Qt.Orientation.Vertical, cw)
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(6)
            splitter.addWidget(sources_container)
            splitter.addWidget(transitions_widget)
            splitter.setStretchFactor(0, 2)  # Sources
            splitter.setStretchFactor(1, 3)  # Transitions grows more

            right_layout.addWidget(splitter)
            # Keep a handle to tune sizes later
            self._right_splitter = splitter
        except Exception as e:
            print(f"Error applying right splitter: {e}")

    def _init_splitter_sizes(self):
        """Initialize splitter sizes based on current window height for a good default layout."""
        try:
            h = max(1, self.height())
            # Left: Output ~65%, Effects ~35%
            if hasattr(self, '_left_splitter') and self._left_splitter:
                self._left_splitter.setSizes([int(h * 0.65), int(h * 0.35)])
            # Right: Sources ~40%, Transitions ~60%
            if hasattr(self, '_right_splitter') and self._right_splitter:
                self._right_splitter.setSizes([int(h * 0.40), int(h * 0.60)])
            # One more pass to align left with actual width/aspect once laid out
            QTimer.singleShot(0, self._adjust_splitters_for_aspect)
        except Exception as e:
            print(f"Error initializing splitter sizes: {e}")

    def resizeEvent(self, event):
        """Keep output 16:9 and dominant by adjusting splitter on window resize."""
        super().resizeEvent(event)
        # Defer to let Qt finish layout, then adjust
        QTimer.singleShot(0, self._adjust_splitters_for_aspect)

    def _adjust_splitters_for_aspect(self):
        try:
            if hasattr(self, '_left_splitter') and self._left_splitter and hasattr(self, 'outputPreview'):
                splitter = self._left_splitter
                # Available panel height and the ACTUAL width of the output frame
                avail_h = max(1, splitter.height())
                frame = self.outputPreview
                # If frame hasn't been laid out yet, fall back to splitter width
                avail_w = max(1, frame.width() if frame.width() > 1 else splitter.width())
                aspect = 16.0 / 9.0
                # Ideal output height based on current width
                ideal_out_h = int(avail_w / aspect)
                # Use as much height as needed for an exact 16:9 based on current width
                min_effects = 100  # keep effects usable but secondary
                out_h = min(ideal_out_h, max(0, avail_h - min_effects))
                # Ensure output gets most of the panel height
                min_out_ratio = 0.85
                if out_h < int(avail_h * min_out_ratio):
                    out_h = int(avail_h * min_out_ratio)
                eff_h = max(min_effects, avail_h - out_h)
                splitter.setSizes([out_h, eff_h])
                # Also clamp the output frame to this height for exact 16:9
                try:
                    frame.setMinimumHeight(out_h)
                    frame.setMaximumHeight(out_h)
                except Exception:
                    pass
                # Resize-driven refresh
                self.refresh_output_preview()
        except Exception as e:
            print(f"Error adjusting splitters for aspect: {e}")

    def _ensure_output_preview_label(self):
        """Install the GraphicsOutputWidget into outputPreview container."""
        if hasattr(self, 'outputPreview'):
            from PyQt6.QtWidgets import QVBoxLayout, QSizePolicy
            frame = self.outputPreview
            if self._graphics_output is None:
                # Try enhanced graphics output first (fixes pixelation)
                try:
                    from enhanced_graphics_output import EnhancedGraphicsOutputWidget
                    view = EnhancedGraphicsOutputWidget(frame)
                    print("Created Enhanced Graphics Output Widget (pixelation fixes enabled)")
                except ImportError:
                    if _USE_NEW_RENDERER:
                        # Prefer GPU only when supported; factory will still fall back to CPU safely
                        view = create_graphics_output_widget(frame, prefer_gpu=True)
                        renderer_type = "GPU" if hasattr(view, 'renderer') and getattr(view, 'renderer') else "CPU"
                        print(f"Created graphics output: {renderer_type}")
                    else:
                        # Force legacy CPU path to guarantee full feature parity
                        from graphics_output import GraphicsOutputWidget as _LegacyGOW
                        view = _LegacyGOW(frame)
                view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                if not frame.layout():
                    layout = QVBoxLayout(frame)
                    layout.setContentsMargins(0, 0, 0, 0)
                    frame.setLayout(layout)
                else:
                    # Clear existing children (e.g., old QLabel)
                    while frame.layout().count():
                        item = frame.layout().takeAt(0)
                        w = item.widget()
                        if w:
                            w.setParent(None)
                frame.layout().addWidget(view)
                self._graphics_output = view

    def _install_output_aspect_guard(self):
        try:
            if not hasattr(self, 'outputPreview') or self.outputPreview is None:
                return
            if hasattr(self, '_output_aspect_guard') and self._output_aspect_guard:
                return
            class _Guard(QObject):
                def __init__(self, outer):
                    super().__init__(outer)
                    self.outer = outer
                def eventFilter(self, obj, event):
                    if event.type() == QEvent.Type.Resize and hasattr(self.outer, 'outputPreview'):
                        frame = self.outer.outputPreview
                        aspect = 16.0/9.0
                        w = max(1, frame.width())
                        target_h = int(w / aspect)
                        # Clamp frame to exact 16:9 height
                        try:
                            frame.setMinimumHeight(target_h)
                            frame.setMaximumHeight(target_h)
                        except Exception:
                            pass
                        # Nudge left splitter if present
                        if hasattr(self.outer, '_left_splitter') and self.outer._left_splitter:
                            avail_h = max(1, self.outer._left_splitter.height())
                            eff_h = max(100, avail_h - target_h)
                            self.outer._left_splitter.setSizes([target_h, eff_h])
                    return QObject.eventFilter(self, obj, event)
            self._output_aspect_guard = _Guard(self)
            # Monitor both the output frame and its parent container for resizes
            self.outputPreview.installEventFilter(self._output_aspect_guard)
            if self.outputPreview.parent():
                self.outputPreview.parent().installEventFilter(self._output_aspect_guard)
        except Exception as e:
            print(f"Error installing output aspect guard: {e}")

    def _set_output_pixmap(self, pixmap):
        """Backward-compatible: convert to QImage and pass to graphics output."""
        if pixmap is None or pixmap.isNull():
            self._set_output_image(None)
            return
        self._set_output_image(pixmap.toImage())

    def _set_output_image(self, image: QImage):
        """Send frame to graphics output widget; falls back to black if None."""
        # ✅ APPLY TEXT OVERLAY BEFORE SENDING TO OUTPUT
        final_image = image
        if image is not None:
            try:
                from text_overlay_renderer import text_overlay_renderer
                if text_overlay_renderer.is_enabled():
                    final_image = text_overlay_renderer.render_overlay(image)
            except Exception as e:
                print(f"Text overlay error: {e}")
                # Continue with original image if overlay fails
                final_image = image
        
        if self._graphics_output is not None:
            self._graphics_output.set_frame(final_image)

    def set_output_source(self, source_type, index):
        """Switch the main output to the selected source.
        If a transition is selected, perform animated switch; otherwise immediate.
        """
        # If we're already in a transition, ignore new requests
        if self._transition_running:
            return
        # Notify streaming backends to clear old audio and add a small safety delay
        try:
            self._notify_stream_source_switch(delay_ms=150)
        except Exception:
            pass
            
        # Update the current source in graphics output
        if hasattr(self, '_graphics_output'):
            if source_type == 'input':
                self._graphics_output._current_source = {'type': 'input', 'index': index}
            elif source_type == 'media':
                self._graphics_output._current_source = {'type': 'media', 'index': index}
            else:
                self._graphics_output._current_source = {'type': None, 'index': -1}
        try:
            sel = (self.selected_transition or 'None').strip()
            if sel.lower() not in ('none', ''):
                self.begin_transition_to(source_type, index)
                return
        except Exception:
            pass
        self._set_output_source_immediate(source_type, index)

    def _pause_all_media_except(self, active_media_index=None):
        """Pause all media players except the specified one"""
        paused_media = []
        for media_idx in [1, 2, 3]:
            if media_idx != active_media_index:
                player = self.media_players[media_idx]
                if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    player.pause()
                    self.update_media_controls(media_idx)
                    paused_media.append(media_idx)
        if paused_media:
            print(f"Paused media: {paused_media} (ensuring only one media plays at a time)")

    def _set_output_source_immediate(self, source_type, index):
        """Existing immediate switch behavior (extracted from original)."""
        # Handle media playback logic: pause all media, then start selected media if it's a media source
        if source_type == 'media':
            # Pause all media first
            self._pause_all_media_except()
            # Start the selected media
            selected_player = self.media_players[index]
            if selected_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                selected_player.play()
                self.update_media_controls(index)
                print(f"Started playback for Media {index} (switched to program output)")
            else:
                print(f"Media {index} already playing (switched to program output)")
            
            # Automatically apply audio delay correction for streaming
            self._auto_apply_audio_delay_correction()
        else:
            # If switching to input source, pause all media
            self._pause_all_media_except()
            print(f"Switched to Input {index} (paused all media)")
        
        self.current_output = (source_type, index)
        # Attempt to immediately update output with last known frame
        if getattr(self, '_transition_running', False):
            return
        if source_type == 'input':
            if index in self.last_input_image:
                self._set_output_image(self.last_input_image[index])
            elif index in self.last_input_pixmap:
                self._set_output_pixmap(self.last_input_pixmap[index])
        elif source_type == 'media':
            if index in self.last_media_image:
                self._set_output_image(self.last_media_image[index])
            elif index in self.last_media_pixmap:
                self._set_output_pixmap(self.last_media_pixmap[index])

        # Enforce media audio policy: only unmute the media routed to output; mute all others.
        # Respect Global Mute: if enabled, force all media muted regardless of program source.
        try:
            for i in (1, 2, 3):
                if getattr(self, 'global_audio_muted', False):
                    should_mute = True
                else:
                    should_mute = not (source_type == 'media' and index == i)
                # Persist state flag
                setattr(self, f"media{i}_audio_muted", should_mute)
                # Apply to actual audio output if available
                if hasattr(self, 'media_audio_outputs') and i in self.media_audio_outputs:
                    self.media_audio_outputs[i].setMuted(should_mute)
                # Reflect on UI button icon if present
                btn_attr = f"media{i}AudioButton"
                if hasattr(self, btn_attr):
                    btn = getattr(self, btn_attr)
                    btn.setIcon(self.get_icon("Mute.png" if should_mute else "Volume.png"))
        except Exception as e:
            print(f"Error enforcing media audio policy: {e}")

        # Auto-manage input audio monitoring so the selected input is heard
        try:
            for i in (1, 2, 3):
                if source_type == 'input' and index == i and not getattr(self, f"input{i}_audio_muted", True):
                    self._ensure_input_audio(i)
                else:
                    self._stop_input_audio(i)
        except Exception as e:
            print(f"Error managing input audio monitoring: {e}")

        # If streaming and the new program is a media, resync streaming audio to the current position
        try:
            if source_type == 'media' and hasattr(self, 'stream_controller'):
                sc = self.stream_controller
                if hasattr(sc, 'is_running') and sc.is_running():
                    media_path = self.get_current_program_media_audio_path()
                    pos_ms = self.get_current_program_media_position_ms() or 0
                    if media_path:
                        sc.resync_to_media(media_path, pos_ms)
        except Exception as e:
            print(f"Error resyncing stream on source switch: {e}")

        # Keep external display mirror in perfect sync: match FPS and maximize resolution
        try:
            if hasattr(self, 'mirror_controller') and self.mirror_controller and self.mirror_controller.is_running():
                from config import app_config as _cfg
                cur_fps = int(_cfg.get('ui.preview_fps', 60))
                self.mirror_controller.update({'fps': cur_fps, 'maximize': True})
        except Exception:
            pass

    def _notify_stream_source_switch(self, delay_ms: int = 150):
        """Inform all running streaming controllers that program source switched.
        This lets the PyAV master-clock backend discard buffered audio and apply
        a tiny delay so the new source's audio does not lead video.
        """
        try:
            # New multi-stream controllers
            if hasattr(self, 'stream_controllers') and isinstance(self.stream_controllers, dict):
                for sc in self.stream_controllers.values():
                    try:
                        if hasattr(sc, 'is_running') and sc.is_running():
                            if hasattr(sc, 'on_source_switch'):
                                sc.on_source_switch(int(max(0, delay_ms)))
                    except Exception:
                        pass
            # Legacy single controller
            elif hasattr(self, 'stream_controller') and self.stream_controller is not None:
                sc = self.stream_controller
                if hasattr(sc, 'is_running') and sc.is_running():
                    if hasattr(sc, 'on_source_switch'):
                        sc.on_source_switch(int(max(0, delay_ms)))
        except Exception:
            pass

    def begin_transition_to(self, source_type: str, index: int):
        """Run a non-blocking transition from the current program frame to the target source."""
        try:
            if not self._graphics_output:
                self._set_output_source_immediate(source_type, index)
                return
            # Capture current composited frame from preview
            size = self._graphics_output._scene_size() if hasattr(self._graphics_output, '_scene_size') else self._graphics_output.size()
            if hasattr(size, 'width') and hasattr(size, 'height'):
                target_size = QSize(max(1, size.width()), max(1, size.height()))
            else:
                target_size = QSize(1280, 720)
            # Build base frames WITHOUT overlay for both current and target
            cur_src = getattr(self, 'current_output', None)
            if not cur_src or not isinstance(cur_src, tuple) or len(cur_src) != 2:
                # If we don't know current, fall back to immediate
                self._set_output_source_immediate(source_type, index)
                return
            a_base = self._get_base_frame_for_source(cur_src[0], int(cur_src[1]), target_size)
            b_base = self._get_base_frame_for_source(source_type, index, target_size)
            if a_base is None or a_base.isNull() or b_base is None or b_base.isNull():
                self._set_output_source_immediate(source_type, index)
                return
            tname = (self.selected_transition or 'Fade')
            dur = int(self.transition_duration_ms or 400)
            easing = (self.transition_easing or 'ease_in_out')
            # Start animated transition (pause normal updates until done)
            self._transition_running = True
            self.transition_manager.start_transition(
                a_base,
                b_base,
                transition_type=tname,
                duration_ms=dur,
                easing=easing,
                # IMPORTANT: send the raw transitioned video frame; the overlay is drawn by GraphicsOutputWidget.
                on_frame=lambda img: self._set_output_image(img),
                on_done=lambda st=source_type, idx=index: self._on_transition_done(st, idx)
            )
        except Exception as e:
            print(f"Transition error: {e}")
            self._set_output_source_immediate(source_type, index)

    def _finalize_switch_to(self, source_type: str, index: int):
        """After transition completes, set the new source for normal updates."""
        self._set_output_source_immediate(source_type, index)

    def _on_transition_done(self, source_type: str, index: int):
        """Clear transition lock and finalize switch safely."""
        try:
            self._transition_running = False
        except Exception:
            pass
        self._finalize_switch_to(source_type, index)

    def _compose_frame_for_source(self, source_type: str, index: int, target_size: QSize) -> QImage | None:
        """Compose the target source frame with current overlay, off-screen."""
        try:
            # Base image from caches
            base: QImage | None = None
            if source_type == 'input':
                base = self.last_input_image.get(index) if hasattr(self, 'last_input_image') else None
                if base is None and hasattr(self, 'last_input_pixmap') and index in self.last_input_pixmap:
                    base = self.last_input_pixmap[index].toImage()
            elif source_type == 'media':
                base = self.last_media_image.get(index) if hasattr(self, 'last_media_image') else None
                if base is None and hasattr(self, 'last_media_pixmap') and index in self.last_media_pixmap:
                    base = self.last_media_pixmap[index].toImage()
            if base is None or base.isNull():
                return None
            # Ensure format
            if base.format() != QImage.Format.Format_ARGB32 and base.format() != QImage.Format.Format_RGBA8888:
                try:
                    base = base.convertToFormat(QImage.Format.Format_ARGB32)
                except Exception:
                    pass
            # Overlay composition using current overlay path (if any)
            eff = EffectManager()
            overlay_path = self._graphics_output.get_overlay_path() if hasattr(self._graphics_output, 'get_overlay_path') else None
            if overlay_path:
                eff.set_effect(overlay_path)
                composed = eff.compose(base, target_size)
            else:
                # Scale base to target, preserving aspect
                composed = base.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                # Center on canvas
                canvas = QImage(target_size, QImage.Format.Format_ARGB32)
                from PyQt6.QtGui import QColor, QPainter
                canvas.fill(QColor(0, 0, 0, 255))
                p = QPainter(canvas)
                x = (target_size.width() - composed.width()) // 2
                y = (target_size.height() - composed.height()) // 2
                p.drawImage(x, y, composed)
                p.end()
                composed = canvas
            return composed
        except Exception:
            return None

    def _get_base_frame_for_source(self, source_type: str, index: int, target_size: QSize) -> QImage | None:
        """Return a base frame (no overlay applied), scaled and centered on a canvas of target_size."""
        try:
            # Fetch from last caches
            base: QImage | None = None
            if source_type == 'input':
                base = self.last_input_image.get(index) if hasattr(self, 'last_input_image') else None
                if base is None and hasattr(self, 'last_input_pixmap') and index in self.last_input_pixmap:
                    base = self.last_input_pixmap[index].toImage()
            elif source_type == 'media':
                base = self.last_media_image.get(index) if hasattr(self, 'last_media_image') else None
                if base is None and hasattr(self, 'last_media_pixmap') and index in self.last_media_pixmap:
                    base = self.last_media_pixmap[index].toImage()
            if base is None or base.isNull():
                return None
            # Scale with aspect and center on black canvas
            scaled = base.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            canvas = QImage(target_size, QImage.Format.Format_ARGB32)
            from PyQt6.QtGui import QColor, QPainter
            canvas.fill(QColor(0, 0, 0, 255))
            p = QPainter(canvas)
            try:
                x = (target_size.width() - scaled.width()) // 2
                y = (target_size.height() - scaled.height()) // 2
                p.drawImage(x, y, scaled)
            finally:
                p.end()
            return canvas
        except Exception:
            return None

    def _apply_overlay_once(self, frame: QImage, target_size: QSize, eff: EffectManager | None) -> QImage:
        """Apply the current overlay exactly once over the provided frame."""
        try:
            if eff is None:
                return frame
            # EffectManager.compose clips to opening and draws overlay; it expects base content
            composed = eff.compose(frame, target_size)
            return composed if composed and not composed.isNull() else frame
        except Exception:
            return frame

    def setup_transitions_panel(self):
        """Dynamically create and populate the transitions grid from the catalog."""
        try:
            from PyQt6.QtWidgets import QPushButton, QGridLayout
            grid: QGridLayout = self.gridLayout_trans1
            if not grid:
                return

            # Clear any placeholder widgets from the UI file
            while grid.count():
                item = grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

            # Store dynamically created buttons here
            self.transition_buttons = []
            entries = [('None', 'No transition (instant switch)')] + TRANSITIONS_CATALOG
            cols = 3
            row, col = 0, 0

            for name, desc in entries:
                btn = QPushButton(name)
                btn.setToolTip(desc)
                btn.setCheckable(True)
                btn.setProperty("transition_name", name)
                # Improved stylesheet for text wrapping and visibility
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #404040;
                        border: 2px solid #404040;
                        border-radius: 4px;
                        color: #ffffff;
                        font-size: 10px;
                        font-weight: bold;
                        padding: 4px;
                        text-align: center;
                        min-height: 48px;
                    }
                    QPushButton:hover {
                        background-color: #505050;
                        border-color: #555;
                    }
                    QPushButton:checked {
                        border-color: #00aaff;
                        background-color: #4a4a4a;
                    }
                """)
                btn.clicked.connect(self._on_transition_selected)
                grid.addWidget(btn, row, col)
                self.transition_buttons.append(btn)
                col += 1
                if col >= cols:
                    col = 0
                    row += 1
            
            # Restore selection
            self._update_transition_selection_ui()

        except Exception as e:
            print(f"Error dynamically populating transitions panel: {e}")

    def _on_transition_selected(self):
        """Handle click on any transition button."""
        sender = self.sender()
        if not sender:
            return
        name = sender.property("transition_name")
        self.selected_transition = name
        app_config.set('ui.transition.type', name)
        app_config.save_settings()
        self._update_transition_selection_ui()

    def _update_transition_selection_ui(self):
        """Update the visual state of all transition buttons based on current selection."""
        try:
            sel = self.selected_transition or 'None'
            if hasattr(self, 'transition_buttons'):
                for btn in self.transition_buttons:
                    is_checked = (btn.property("transition_name") == sel)
                    btn.setChecked(is_checked)
        except Exception as e:
            print(f"Error updating transition UI selection: {e}")

    def get_current_program_media_audio_path(self) -> str | None:
        """Return the file path of the media currently on program, if any."""
        try:
            if getattr(self, 'current_output', None) and self.current_output[0] == 'media':
                idx = self.current_output[1]
                if hasattr(self, 'media_paths'):
                    return self.media_paths.get(idx)
        except Exception:
            pass
        return None

    def get_current_program_media_position_ms(self) -> int | None:
        """Return current playback position (ms) of the media on program, if any."""
        try:
            if getattr(self, 'current_output', None) and self.current_output[0] == 'media':
                idx = self.current_output[1]
                player = self.media_players.get(idx)
                if player:
                    return int(player.position())
        except Exception:
            pass
        return None

    def get_active_media_info(self) -> dict | None:
        """Return information about the currently active (playing) media for streaming."""
        try:
            # Check if current output is media and it's playing
            if getattr(self, 'current_output', None) and self.current_output[0] == 'media':
                idx = self.current_output[1]
                player = self.media_players.get(idx)
                if player and player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    media_path = self.media_paths.get(idx) if hasattr(self, 'media_paths') else None
                    if media_path:
                        return {
                            'index': idx,
                            'path': media_path,
                            'position_ms': int(player.position()),
                            'duration_ms': int(player.duration())
                        }
        except Exception:
            pass
        return None

    def adjust_audio_sync_delay(self, delay_ms: int):
        """Dynamically adjust audio sync delay for active streams."""
        try:
            # Update primary stream controller
            if hasattr(self, 'stream_controller') and self.stream_controller.is_running():
                active_media = self.get_active_media_info()
                if active_media:
                    self.stream_controller.update_av_delay_and_resync(
                        delay_ms, 
                        active_media['path'], 
                        active_media['position_ms']
                    )
                    print(f"Updated audio sync delay to {delay_ms}ms for active stream")
                else:
                    self.stream_controller.update_av_delay_and_resync(delay_ms)
                    print(f"Updated audio sync delay to {delay_ms}ms")
            
            # Update independent stream controllers
            if hasattr(self, 'stream_controllers'):
                for stream_id, sc in self.stream_controllers.items():
                    if sc.is_running():
                        active_media = self.get_active_media_info()
                        if active_media:
                            sc.update_av_delay_and_resync(
                                delay_ms, 
                                active_media['path'], 
                                active_media['position_ms']
                            )
                        else:
                            sc.update_av_delay_and_resync(delay_ms)
                        print(f"Updated audio sync delay to {delay_ms}ms for stream {stream_id}")
                        
        except Exception as e:
            print(f"Error adjusting audio sync delay: {e}")
    
    def fix_audio_delay_issue(self):
        """Quick fix for 5-second audio delay issue."""
        print("\n=== AUDIO SYNC DELAY FIX ===")
        print("Applying audio delay correction for 5-second delay issue...")
        
        # Check if streaming is active
        streaming_active = False
        if hasattr(self, 'stream_controller') and self.stream_controller.is_running():
            streaming_active = True
        if hasattr(self, 'stream_controllers'):
            for sc in self.stream_controllers.values():
                if sc.is_running():
                    streaming_active = True
                    break
        
        if not streaming_active:
            print("WARNING: No active streams detected. Start streaming first, then apply this fix.")
            print("The fix will be applied when you start streaming.")
            # Set flag for auto-correction when streaming starts
            self._needs_delay_correction = True
            return
        
        # Apply a negative delay to compensate for the 5-second delay
        # This effectively moves audio earlier relative to video
        corrected_delay = -4800  # Negative 4.8 seconds to compensate for 5s delay
        self.adjust_audio_sync_delay(corrected_delay)
        print(f"✓ Applied {corrected_delay}ms audio offset to correct sync issue")
        print("\nIf audio is still not in sync:")
        print("1. Use Ctrl+Shift+A to re-apply this fix")
        print("2. Manually adjust in Stream Settings > A/V Sync Offset")
        print("3. Try values between -5000ms to -4000ms for fine-tuning")
        print("===============================\n")

    def _auto_apply_audio_delay_correction(self):
        """Automatically apply audio delay correction when media is selected for streaming."""
        try:
            # Check if any streaming is active
            streaming_active = False
            if hasattr(self, 'stream_controller') and self.stream_controller.is_running():
                streaming_active = True
            if hasattr(self, 'stream_controllers'):
                for sc in self.stream_controllers.values():
                    if sc.is_running():
                        streaming_active = True
                        break
            
            if streaming_active:
                print("Auto-applying audio delay correction for streaming...")
                # Pull correction from config; default to -1500 ms to address ~0.5s residual delay
                try:
                    corrected_delay = int(app_config.get('streaming.av_sync_correction_ms', -1500))
                except Exception:
                    corrected_delay = -1500
                self.adjust_audio_sync_delay(corrected_delay)
                print(f"✓ Automatically applied {corrected_delay} ms audio offset for sync correction")
            else:
                print("No active streams - audio correction will be applied when streaming starts")
                
        except Exception as e:
            print(f"Error in auto audio delay correction: {e}")

    def update_media_controls(self, media_number):
        """Update media control buttons (play/pause icon) for the given media slot"""
        try:
            button_map = {1: 'pushButton_19', 2: 'pushButton_20', 3: 'pushButton_21'}
            button_name = button_map.get(media_number)
            if not button_name:
                return
            if hasattr(self, button_name):
                button = getattr(self, button_name)
                player = self.media_players.get(media_number)
                if player:
                    playing = player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                    button.setIcon(self.get_icon("Pause.png" if playing else "Play.png"))
                    button.setToolTip(("Pause" if playing else "Play") + f" Media {media_number}")
                    button.setMinimumSize(22, 22)
                    button.setMaximumSize(22, 22)
        except Exception as e:
            print(f"Error updating media controls: {e}")

    def toggle_input_audio(self, input_number):
        """Toggle input audio monitor (default device) and update button icon"""
        try:
            # Track mute flags per input
            flag_attr = f"input{input_number}_audio_muted"
            current = getattr(self, flag_attr, True)
            new_state = not current
            setattr(self, flag_attr, new_state)

            # Start/stop monitoring
            if new_state:  # muted
                self._stop_input_audio(input_number)
            else:
                # Respect Global Mute: do not actually start audio while master mute is on
                if getattr(self, 'global_audio_muted', False):
                    print("Global mute is enabled; input will remain silenced until global mute is disabled.")
                    # Keep monitor stopped despite desired unmute
                    self._stop_input_audio(input_number)
                else:
                    self._ensure_input_audio(input_number)

            # Update icon on the dedicated input audio button
            btn_attr = f"input{input_number}AudioButton"
            if hasattr(self, btn_attr):
                btn = getattr(self, btn_attr)
                # If global mute is on, always show Mute icon
                force_muted = new_state or getattr(self, 'global_audio_muted', False)
                btn.setIcon(self.get_icon("Mute.png" if force_muted else "Volume.png"))

            print(f"Input {input_number} audio {'muted' if new_state else 'unmuted'}")
        except Exception as e:
            print(f"Error toggling input audio: {e}")
    def set_ui_icons(self):
        """Set icons for UI elements programmatically"""
        try:
            # Main control buttons
            if hasattr(self, 'settingsRecordButton'):
                self.settingsRecordButton.setIcon(self.get_icon("Settings.png"))
            if hasattr(self, 'recordRedCircle'):
                self.recordRedCircle.setIcon(self.get_icon("Record.png"))
            if hasattr(self, 'playButton'):
                self.playButton.setIcon(self.get_icon("Play.png"))
            if hasattr(self, 'captureButton'):
                self.captureButton.setIcon(self.get_icon("capture.png"))
            
            # Stream buttons
            if hasattr(self, 'stream1SettingsBtn'):
                self.stream1SettingsBtn.setIcon(self.get_icon("Settings.png"))
            if hasattr(self, 'stream1AudioBtn'):
                self.stream1AudioBtn.setIcon(self.get_icon("Stream.png"))
            if hasattr(self, 'stream2SettingsBtn'):
                self.stream2SettingsBtn.setIcon(self.get_icon("Settings.png"))
            if hasattr(self, 'stream2AudioBtn'):
                self.stream2AudioBtn.setIcon(self.get_icon("Stream.png"))
            
            # Additional section buttons initial icons
            # Global mute button reflects master state
            if hasattr(self, 'audioTopButton'):
                self.audioTopButton.setIcon(self.get_icon("Mute.png" if getattr(self, 'global_audio_muted', False) else "Volume.png"))
            # bottomButton2 is Clear Visuals button – set clear icon
            if hasattr(self, 'bottomButton2'):
                try:
                    self.bottomButton2.setIcon(self.get_icon("Clear.png"))
                except Exception:
                    pass
            
            # Input audio buttons (reflect muted state)
            if hasattr(self, 'input1AudioButton'):
                self.input1AudioButton.setIcon(self.get_icon("Mute.png" if getattr(self, 'input1_audio_muted', True) else "Volume.png"))
            if hasattr(self, 'input2AudioButton'):
                self.input2AudioButton.setIcon(self.get_icon("Mute.png" if getattr(self, 'input2_audio_muted', True) else "Volume.png"))
            if hasattr(self, 'input3AudioButton'):
                self.input3AudioButton.setIcon(self.get_icon("Mute.png" if getattr(self, 'input3_audio_muted', True) else "Volume.png"))
            
            # Input settings buttons
            if hasattr(self, 'input1SettingsButton'):
                self.input1SettingsButton.setIcon(self.get_icon("Settings.png"))
            if hasattr(self, 'input2SettingsButton'):
                self.input2SettingsButton.setIcon(self.get_icon("Settings.png"))
            if hasattr(self, 'input3SettingsButton'):
                self.input3SettingsButton.setIcon(self.get_icon("Settings.png"))
            
            # Media audio buttons (reflect muted state)
            if hasattr(self, 'media1AudioButton'):
                self.media1AudioButton.setIcon(self.get_icon("Mute.png" if getattr(self, 'media1_audio_muted', False) else "Volume.png"))
            if hasattr(self, 'media2AudioButton'):
                self.media2AudioButton.setIcon(self.get_icon("Mute.png" if getattr(self, 'media2_audio_muted', False) else "Volume.png"))
            if hasattr(self, 'media3AudioButton'):
                self.media3AudioButton.setIcon(self.get_icon("Mute.png" if getattr(self, 'media3_audio_muted', False) else "Volume.png"))
            
            # Media settings buttons & play buttons default icons
            if hasattr(self, 'media1SettingsButton'):
                self.media1SettingsButton.setIcon(self.get_icon("Settings.png"))
            if hasattr(self, 'media2SettingsButton'):
                self.media2SettingsButton.setIcon(self.get_icon("Settings.png"))
            if hasattr(self, 'media3SettingsButton'):
                self.media3SettingsButton.setIcon(self.get_icon("Settings.png"))
            # Set default play icons for media control buttons
            if hasattr(self, 'pushButton_19'):
                self.pushButton_19.setIcon(self.get_icon("Play.png"))
            if hasattr(self, 'pushButton_20'):
                self.pushButton_20.setIcon(self.get_icon("Play.png"))
            if hasattr(self, 'pushButton_21'):
                self.pushButton_21.setIcon(self.get_icon("Play.png"))
            
            # print("UI icons set successfully")
        except Exception as e:
            print(f"Error setting UI icons: {e}")
    
    def apply_aspect_ratio_constraints(self):
        """Apply 16:9 aspect ratio constraints to all video widgets"""
        try:
            from PyQt6.QtWidgets import QSizePolicy
            from PyQt6.QtCore import QSize
            
            # List of video widget names that should maintain 16:9 aspect ratio
            video_widgets = [
                'outputPreview',
                'inputVideoFrame1', 'inputVideoFrame2', 'inputVideoFrame3',
                'mediaVideoFrame1', 'mediaVideoFrame2', 'mediaVideoFrame3'
            ]
            
            for widget_name in video_widgets:
                if hasattr(self, widget_name):
                    widget = getattr(self, widget_name)
                    if widget:
                        # Replace the widget with AspectRatioFrame if it's not already one
                        if not isinstance(widget, AspectRatioFrame):
                            parent = widget.parent()
                            if parent:
                                # Get the current layout position
                                layout = parent.layout()
                                if layout:
                                    # Find the widget's position in the layout
                                    for i in range(layout.count()):
                                        item = layout.itemAt(i)
                                        if item and item.widget() == widget:
                                            # Remove the old widget
                                            layout.removeWidget(widget)
                                            widget.setParent(None)
                                            
                                            # Create new AspectRatioFrame
                                            new_frame = AspectRatioFrame(parent)
                                            # Ensure it expands properly in layouts
                                            from PyQt6.QtWidgets import QSizePolicy
                                            new_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                                            new_frame.setObjectName(widget_name)
                                            
                                            # Copy original widget properties
                                            new_frame.setFrameStyle(widget.frameStyle())
                                            original_style = widget.styleSheet()
                                            
                                            # Set minimum size based on widget type
                                            if widget_name == 'outputPreview':
                                                new_frame.setMinimumSize(320, 180)
                                            else:
                                                new_frame.setMinimumSize(160, 90)
                                            
                                            # Ensure the frame is visible with proper styling
                                            if 'media' in widget_name.lower():
                                                media_style = """
                                                    QFrame {
                                                        background-color: #2a2a2a;
                                                        border: 1px solid #555;
                                                        border-radius: 4px;
                                                    }
                                                """
                                                new_frame.setStyleSheet(original_style + media_style)
                                            else:
                                                new_frame.setStyleSheet(original_style)
                                            
                                            # Add to layout at the same position
                                            layout.insertWidget(i, new_frame)
                                            
                                            # Update the reference
                                            setattr(self, widget_name, new_frame)
                                            
                                           # print(f"Replaced {widget_name} with AspectRatioFrame")
                                            break
                        else:
                            print(f"{widget_name} is already an AspectRatioFrame")
            
            # print("16:9 aspect ratio constraints applied to all video widgets")
            
        except Exception as e:
            print(f"Error applying aspect ratio constraints: {e}")
    
    def detect_camera_sources(self):
        """Detect available camera sources with platform-specific handling"""
        import cv2
        import platform
        from PyQt6.QtMultimedia import QMediaDevices
        
        camera_sources = []
        try:
            system = platform.system()
            if system == "Darwin":
                # On macOS, enumerate with Qt; optionally probe with PyAV if available.
                try:
                    qt_devices = list(QMediaDevices.videoInputs())
                except Exception:
                    qt_devices = []
                if qt_devices:
                    # Check if PyAV is importable for probing
                    _can_probe = False
                    try:
                        import av_capture as _avc  # lazy av import happens inside
                        _ = getattr(_avc, 'probe_device', None)
                        if _:
                            _can_probe = True
                    except Exception:
                        _can_probe = False
                    for d in qt_devices:
                        name = ''
                        try:
                            name = d.description()
                            width = height = 0
                            fps_val = 0
                            if _can_probe:
                                try:
                                    info = _avc.probe_device(name, sample_seconds=0.8)
                                except Exception:
                                    info = {'ok': False}
                                if info.get('ok'):
                                    width = int(info.get('width') or 0)
                                    height = int(info.get('height') or 0)
                                    fps_val = int(round(float(info.get('fps') or 0.0)))
                                else:
                                    # Fall back to max format hints if probe fails
                                    best_key = (-1.0, 0, 0)
                                    for fmt in d.videoFormats():
                                        try:
                                            fps_max = float(fmt.maxFrameRate())
                                        except Exception:
                                            fps_max = 0.0
                                        size = fmt.resolution()
                                        w = int(size.width()) if hasattr(size, 'width') else int(getattr(size, 'width', 0))
                                        h = int(size.height()) if hasattr(size, 'height') else int(getattr(size, 'height', 0))
                                        key = (fps_max, w, h)
                                        if (key > best_key) or (abs(fps_max - best_key[0]) < 0.1 and (w, h) == (1920, 1080)):
                                            best_key = key
                                    width = best_key[1]
                                    height = best_key[2]
                                    fps_val = int(best_key[0]) if best_key[0] > 0 else 0
                            else:
                                # No probe available; at least report name
                                pass
                            camera_sources.append({
                                'index': -1,
                                'name': name or 'Camera',
                                'resolution': f"{width}x{height}" if width and height else "Unknown",
                                'fps': fps_val if fps_val > 0 else 30,
                                'backend': 'avf_pyav' if _can_probe else 'qt'
                            })
                        except Exception:
                            # Never drop device; add minimal record
                            if name:
                                camera_sources.append({
                                    'index': -1,
                                    'name': name,
                                    'resolution': "Unknown",
                                    'fps': 30,
                                    'backend': 'qt'
                                })
                    print(f"Detected {len(camera_sources)} camera sources (Qt enumeration with optional PyAV probe)")
                    self._last_camera_sources = camera_sources
                    return camera_sources
                # Fallback to OpenCV probing if Qt enumeration failed
                indices = list(range(0, 10))
                backends_to_try = [cv2.CAP_AVFOUNDATION, 0]
            else:
                indices = list(range(0, 10))
                backends_to_try = [0]
            
            # Try to get device names from Qt (more reliable than OpenCV)
            qt_devices = []
            try:
                qt_devices = list(QMediaDevices.videoInputs())
            except Exception:
                qt_devices = []
            qt_names = [d.description() for d in qt_devices] if qt_devices else []
            if qt_names:
                try:
                    print("Qt Video Inputs:")
                    for n in qt_names:
                        print(f"  - {n}")
                except Exception:
                    pass
            
            for i in indices:
                opened = False
                used_backend = None
                width = height = fps = 0
                for be in backends_to_try:
                    cap = cv2.VideoCapture(i, be) if be != 0 else cv2.VideoCapture(i)
                    if cap.isOpened():
                        opened = True
                        used_backend = be
                        
                        # First, try to detect camera's current/native settings without changing anything
                        print(f"Testing camera {i} capabilities...")
                        
                        # Get camera's current native settings - don't change anything, just read
                        native_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                        native_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        native_fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        print(f"  Camera's native settings: {native_width}x{native_height} @ {native_fps}fps")
                        
                        # Use the camera's actual configured settings without modification
                        width = native_width
                        height = native_height
                        fps = native_fps
                        
                        # Apply minimal optimizations without changing FPS/resolution
                        try:
                            # Set buffer size to 1 to reduce latency
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            # Use MJPEG codec for better performance if supported
                            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
                        except Exception as e:
                            print(f"    Warning: Could not set camera optimizations: {e}")
                        
                        print(f"Using camera {i} native configuration: {width}x{height} @ {fps}fps")
                        
                        cap.release()
                        break
                    cap.release()
                if opened:
                    # Best-effort: map OpenCV index to a Qt device name by order if available
                    name = None
                    if qt_names and i < len(qt_names):
                        name = qt_names[i]
                    if not name:
                        name = f"Camera {i} ({'macOS' if system == 'Darwin' else system})"
                    camera_info = {
                        'index': i,
                        'name': name,
                        'resolution': f"{int(width)}x{int(height)}" if width and height else "Unknown",
                        'fps': int(fps) if fps and fps > 0 else 30,
                        'backend': int(used_backend) if used_backend is not None else 0,
                    }
                    camera_sources.append(camera_info)
            print(f"Detected {len(camera_sources)} camera sources")
            # Store for later reference
            self._last_camera_sources = camera_sources
        except Exception as e:
            print(f"Error detecting cameras: {e}")
        return camera_sources
    
    def force_external_camera_detection(self, camera_index, is_external=True):
        """Force a camera to be treated as external (HDMI/USB) or built-in
        
        Args:
            camera_index (int): Camera index (0, 1, 2, etc.)
            is_external (bool): True to treat as external camera, False as built-in
        """
        key = f'camera.force_external.{camera_index}'
        if is_external:
            app_config.set(key, True)
            print(f"Camera {camera_index} will be treated as external camera")
        else:
            app_config.remove(key)
            print(f"Camera {camera_index} will use automatic detection")
        app_config.save_settings()
        print("Call refresh_camera_capabilities() to re-detect with new settings")

    def set_camera_priority(self, prioritize_resolution=True):
        """Set whether to prioritize resolution or FPS when detecting cameras
        
        Args:
            prioritize_resolution (bool): If True, prefer higher resolution over FPS.
                                        If False, prefer higher FPS over resolution.
        """
        app_config.set('camera.prioritize_resolution', prioritize_resolution)
        app_config.save_settings()
        priority_type = "resolution" if prioritize_resolution else "FPS"
        print(f"Camera priority set to: {priority_type} first")
        print("Call refresh_camera_capabilities() to re-detect with new priority")

    def refresh_camera_capabilities(self):
        """Force refresh of camera capabilities detection"""
        try:
            print("Refreshing camera capabilities...")
            self._last_camera_sources = self.detect_camera_sources()
            print(f"Refreshed: Found {len(self._last_camera_sources)} cameras")
            for cam in self._last_camera_sources:
                print(f"  - {cam['name']}: {cam['resolution']} @ {cam['fps']}fps")
        except Exception as e:
            print(f"Error refreshing camera capabilities: {e}")

    def set_camera_fps_override(self, input_number, fps):
        """Allow user to override camera FPS for performance tuning"""
        try:
            if fps <= 0:
                # Remove override, use camera's native FPS
                app_config.remove(f'camera.input{input_number}.fps_override')
                print(f"Removed FPS override for Input-{input_number}, using camera native FPS")
            else:
                app_config.set(f'camera.input{input_number}.fps_override', int(fps))
                print(f"Set FPS override for Input-{input_number}: {fps}fps")
            app_config.save_settings()
            
            # If camera is currently active, restart it with new settings
            if hasattr(self, 'camera_captures') and input_number in self.camera_captures:
                print(f"Restarting Input-{input_number} with new FPS settings...")
                # Get current camera info
                current_camera = None
                for camera_info in getattr(self, '_last_camera_sources', []):
                    if camera_info.get('index') == self.input_camera_indices.get(input_number):
                        current_camera = camera_info
                        break
                if current_camera:
                    self.start_camera_capture(current_camera, input_number)
        except Exception as e:
            print(f"Error setting camera FPS override: {e}")

    def show_camera_selection_dialog(self, input_number):
        """Show enhanced camera selection dialog for the specified input"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                                   QPushButton, QLabel, QListWidgetItem, QMessageBox, QProgressBar)
        from PyQt6.QtCore import Qt, QThread, pyqtSignal
        from PyQt6.QtGui import QFont, QIcon
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Camera Source - Input {input_number}")
        dialog.setModal(True)
        dialog.resize(500, 400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
            QListWidget {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                selection-background-color: #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 4px;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton#cancelButton {
                background-color: #666666;
            }
            QPushButton#cancelButton:hover {
                background-color: #777777;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title with icon
        title_layout = QHBoxLayout()
        title_label = QLabel(f"Select Camera Source for Input-{input_number}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # Status label
        status_label = QLabel("Scanning for available cameras...")
        status_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        layout.addWidget(status_label)
        
        # Progress bar
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 0)  # Indeterminate progress
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #3c3c3c;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
        """)
        layout.addWidget(progress_bar)
        
        # Camera list
        camera_list = QListWidget()
        camera_list.setMinimumHeight(200)
        layout.addWidget(camera_list)
        
        # Info label
        info_label = QLabel("Select a camera from the list above and click OK to connect.")
        info_label.setStyleSheet("color: #cccccc; font-size: 10px; margin-top: 10px;")
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        refresh_button = QPushButton("🔄 Refresh")
        refresh_button.setObjectName("refreshButton")
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancelButton")
        ok_button = QPushButton("Connect")
        
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)
        
        # Load cameras
        def load_cameras():
            progress_bar.hide()
            status_label.setText("Ready")
            camera_sources = self.detect_camera_sources()
            
            camera_list.clear()
            if not camera_sources:
                no_camera_item = QListWidgetItem("❌ No cameras detected")
                no_camera_item.setFlags(Qt.ItemFlag.NoItemFlags)
                camera_list.addItem(no_camera_item)
                ok_button.setEnabled(False)
                info_label.setText("No cameras found. Please check your camera connections and try refreshing.")
            else:
                ok_button.setEnabled(False)  # Don't enable until user selects
                for i, camera in enumerate(camera_sources):
                    item_text = f"📹 {camera['name']} - {camera['resolution']} @ {camera['fps']}fps"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, camera)
                    camera_list.addItem(item)
                    # Don't auto-select any camera
                
                info_label.setText(f"Found {len(camera_sources)} camera(s). Select one and click Connect.")
        
        # Enable OK button when user selects a camera
        def on_camera_selection_changed():
            current_item = camera_list.currentItem()
            if current_item and current_item.data(Qt.ItemDataRole.UserRole):
                ok_button.setEnabled(True)
            else:
                ok_button.setEnabled(False)
        
        # Connect signals
        ok_button.clicked.connect(lambda: self.on_camera_selected(dialog, camera_list, input_number))
        cancel_button.clicked.connect(dialog.reject)
        refresh_button.clicked.connect(load_cameras)
        camera_list.itemSelectionChanged.connect(on_camera_selection_changed)
        
        # Initial load
        load_cameras()
        
        dialog.exec()
    
    def on_camera_selected(self, dialog, camera_list, input_number):
        """Handle camera selection and start video capture"""
        current_item = camera_list.currentItem()
        if current_item and current_item.data(Qt.ItemDataRole.UserRole):
            camera_info = current_item.data(Qt.ItemDataRole.UserRole)
            self.start_camera_capture(camera_info, input_number)
            dialog.accept()
        else:
            dialog.reject()
    
    def start_camera_capture(self, camera_info, input_number):
        """Start capturing video from selected camera"""
        import cv2
        import platform
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QImage, QPixmap
        
        try:
            # Stop any existing capture for this input
            self.stop_camera_capture(input_number)
            
            # Prevent multiple inputs from sharing the same camera index
            if not hasattr(self, 'input_camera_indices'):
                self.input_camera_indices = {}
            # Stop any other input using the same camera index
            for other_input, idx in getattr(self, 'input_camera_indices', {}).items():
                try:
                    if other_input != input_number and idx == camera_info['index']:
                        self.stop_camera_capture(other_input)
                except Exception:
                    pass
            # Ensure containers
            if not hasattr(self, 'camera_captures'):
                self.camera_captures = {}
            if not hasattr(self, 'camera_timers'):
                self.camera_timers = {}
            if not hasattr(self, 'last_input_image'):
                self.last_input_image = {}
            if not hasattr(self, 'last_input_pixmap'):
                self.last_input_pixmap = {}
            
            # On macOS prefer Qt Camera by device description to avoid AVFoundation index ambiguity
            system = platform.system()
            used_qt_camera = False
            if system == "Darwin":
                try:
                    target_name = str(camera_info.get('name', '') or '')
                    from PyQt6.QtMultimedia import QMediaDevices
                    dev = None
                    for d in QMediaDevices.videoInputs():
                        if d.description() == target_name:
                            dev = d
                            break
                    # Prefer AVFoundation via PyAV for high-FPS capture when available
                    prefer_pyav = app_config.get('camera.prefer_pyav', True)
                    if prefer_pyav:
                        try:
                            import av_capture as _avc
                            if not hasattr(self, 'avf_captures'):
                                self.avf_captures = {}
                            # Resolution from detection (optional)
                            w = h = None
                            res_str = camera_info.get('resolution', '')
                            if isinstance(res_str, str) and 'x' in res_str:
                                try:
                                    w, h = map(int, res_str.split('x'))
                                except Exception:
                                    w = h = None
                            # FPS request override
                            req = app_config.get(f'camera.input{input_number}.fps_request', None)
                            req = int(req) if req is not None and int(req) > 0 else None
                            avf = _avc.AVFVideoCapture(input_number, target_name, width=w, height=h, fps=req)
                            avf.frameReady.connect(self._on_avf_frame)
                            avf.error.connect(lambda msg, idx=input_number: print(f"AVF[{idx}] {msg}"))
                            if avf.start():
                                self.avf_captures[input_number] = avf
                                used_qt_camera = True  # signal-driven
                                print(f"Started AVFoundation (PyAV) capture for Input-{input_number}: {target_name}")
                        except Exception as _avfe:
                            print(f"PyAV AVFoundation capture failed; falling back to Qt: {_avfe}")
                    if not used_qt_camera and dev is not None:
                        if not hasattr(self, 'qt_cameras'):
                            self.qt_cameras = {}
                        if not hasattr(self, 'qt_sessions'):
                            self.qt_sessions = {}
                        if not hasattr(self, 'qt_sinks'):
                            self.qt_sinks = {}
                        # Prepare a simple FPS measurement buffer per input
                        if not hasattr(self, '_fps_measure'):
                            self._fps_measure = {}
                        from collections import deque
                        self._fps_measure[input_number] = {
                            'times': deque(maxlen=120),  # ~2s at 60fps
                            'last_report': 0.0,
                            'measured_fps': None,
                        }
                        cam = QCamera(dev)
                        # Choose the best available camera format by max FPS, prefer 1920x1080 on ties
                        try:
                            best_fmt = None
                            best_key = (-1.0, 0, 0)  # fps, w, h
                            all_fmt_log = []
                            for fmt in dev.videoFormats():
                                try:
                                    fps_max = float(fmt.maxFrameRate())
                                except Exception:
                                    fps_max = 0.0
                                size = fmt.resolution()
                                w = int(size.width()) if hasattr(size, 'width') else int(getattr(size, 'width', 0))
                                h = int(size.height()) if hasattr(size, 'height') else int(getattr(size, 'height', 0))
                                key = (fps_max, w, h)
                                all_fmt_log.append((w, h, fps_max))
                                if (key > best_key) or (abs(fps_max - best_key[0]) < 0.1 and (w, h) == (1920, 1080)):
                                    best_key = key
                                    best_fmt = fmt
                            try:
                                if all_fmt_log:
                                    print("Qt camera supported formats:")
                                    for (w,h,fpsm) in sorted(all_fmt_log, key=lambda t: (t[2], t[0]*t[1]), reverse=True):
                                        print(f"  - {w}x{h} @ up to {fpsm:.0f}fps")
                            except Exception:
                                pass
                            if best_fmt is not None:
                                cam.setCameraFormat(best_fmt)
                                try:
                                    print(f"Selected Qt camera format: {best_key[1]}x{best_key[2]} @ {best_key[0]:.0f}fps")
                                except Exception:
                                    pass
                        except Exception as e:
                            print(f"Warning: could not set Qt camera format: {e}")
                        sink = QVideoSink()
                        sess = QMediaCaptureSession()
                        sess.setCamera(cam)
                        sess.setVideoSink(sink)
                        # Connect frame signal
                        sink.videoFrameChanged.connect(lambda vf, idx=input_number: self._on_qt_camera_frame(idx, vf))
                        cam.start()
                        self.qt_cameras[input_number] = cam
                        self.qt_sessions[input_number] = sess
                        self.qt_sinks[input_number] = sink
                        used_qt_camera = True
                        print(f"Started Qt camera for Input-{input_number}: {target_name}")
                except Exception as e:
                    print(f"Qt camera start failed, falling back to OpenCV: {e}")

            if not used_qt_camera:
                # Create capture using the backend that worked during detection; try fallbacks
                be_pref = int(camera_info.get('backend', 0)) if isinstance(camera_info, dict) else 0
                index = int(camera_info.get('index', 0))
                tried = []
                def try_open(backend):
                    cap_local = cv2.VideoCapture(index, backend) if backend != 0 else cv2.VideoCapture(index)
                    tried.append(backend)
                    return cap_local if cap_local.isOpened() else None
                cap = None
                if be_pref:
                    cap = try_open(be_pref)
                if cap is None and system == "Darwin":
                    cap = try_open(cv2.CAP_AVFOUNDATION)
                if cap is None:
                    cap = try_open(0)
                if cap is None:
                    raise RuntimeError(f"Failed to open camera index {index} with backends {tried}")
                
                # Configure camera resolution only if explicitly provided; do NOT force FPS
                if isinstance(camera_info, dict):
                    # Only set resolution if provided; avoid forcing FPS to honor device timing
                    try:
                        res_str = camera_info.get('resolution', '')
                        if 'x' in res_str:
                            w, h = map(int, res_str.split('x'))
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                        # Do not set CAP_PROP_FPS unless user explicitly overrides
                        user_fps_override = app_config.get(f'camera.input{input_number}.fps_override', None)
                        if user_fps_override and user_fps_override > 0:
                            cap.set(cv2.CAP_PROP_FPS, int(user_fps_override))
                            print(f"Using user FPS override: {int(user_fps_override)}fps")
                        
                        # Apply the same optimizations as in detection
                        try:
                            # Disable auto-exposure for consistent FPS
                            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                            # Set buffer size to 1 to reduce latency and frame drops
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            # Use MJPEG codec for better performance
                            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
                        except Exception as e:
                            print(f"    Warning: Could not set camera optimizations: {e}")
                        
                        # Report what the driver says now (may be 0/NaN on some backends)
                        actual_fps = cap.get(cv2.CAP_PROP_FPS)
                        actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                        actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        print(f"OpenCV reports: {actual_w}x{actual_h} @ {actual_fps}fps")
                    except Exception as e:
                        print(f"Warning: Could not configure camera properties: {e}")
                
                self.camera_captures[input_number] = cap
                self.input_camera_indices[input_number] = int(camera_info.get('index', 0))
            
            # Create timer for frame updates
            timer = QTimer()
            if used_qt_camera:
                # With Qt/PyAV cameras, frames arrive via signal; no polling required
                timer.timeout.connect(lambda: None)
            else:
                timer.timeout.connect(lambda: self.update_camera_frame(input_number))
            # Use camera's configured FPS (which may be user-overridden). For Qt path, rely on runtime measurement.
            if used_qt_camera:
                # Start a light idle timer; frame updates come via signal
                timer.start(1000)  # 1s no-op
                print("Qt camera uses signal-driven frames; timer is idle.")
                self.camera_timers[input_number] = timer
            else:
                if isinstance(camera_info, dict):
                    detected_fps = camera_info.get('fps', 60)
                    user_fps_override = app_config.get(f'camera.input{input_number}.fps_override', None)
                    if user_fps_override and user_fps_override > 0:
                        camera_fps = min(user_fps_override, detected_fps)
                    else:
                        camera_fps = detected_fps
                else:
                    camera_fps = 60
                interval_ms = max(4, int(1000 / camera_fps))
                timer.start(interval_ms)
                print(f"Camera timer set to {interval_ms}ms intervals ({camera_fps}fps)")
                self.camera_timers[input_number] = timer
                # Update graphics and preview config to match this non-Qt camera rate
                if hasattr(self, '_graphics_output'):
                    self._graphics_output.set_target_fps(int(camera_fps))
                app_config.set('ui.preview_fps', int(camera_fps))
                app_config.save_settings()
            
            print(f"Started camera capture for Input-{input_number}: {camera_info['name']}")
            
        except Exception as e:
            print(f"Error starting camera capture: {e}")
    
    def update_camera_frame(self, input_number):
        """Update camera frame in the video widget"""
        import cv2
        try:
            # Update the current source in graphics output if this camera is on program
            if hasattr(self, '_graphics_output') and hasattr(self, 'outputSource') and \
               self.outputSource == 'input' and self.outputSourceIndex == input_number:
                self._graphics_output._current_source = {'type': 'input', 'index': input_number}
            if not hasattr(self, 'camera_captures') or input_number not in self.camera_captures:
                return
            
            cap = self.camera_captures[input_number]
            ret, frame = cap.read()
            
            if ret:
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channel = rgb_frame.shape
                bytes_per_line = 3 * width
                
                # Create QImage
                q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                
                # Convert to QPixmap
                pixmap = QPixmap.fromImage(q_image)
                # Cache original image for high-quality output scaling
                self.last_input_image[input_number] = q_image.copy()
                
                # Get the video widget (AspectRatioFrame) by correct object name
                # The UI uses names: inputVideoFrame1, inputVideoFrame2, inputVideoFrame3
                video_widget = getattr(self, f'inputVideoFrame{input_number}')
                
                # Scale pixmap to fit widget while maintaining aspect ratio
                widget_size = video_widget.size()
                # Fallback to minimum size if current size is not yet laid out
                if widget_size.width() <= 1 or widget_size.height() <= 1:
                    min_size = video_widget.minimumSize()
                    widget_size = min_size if min_size.isValid() else QSize(320, 180)
                if widget_size.width() > 0 and widget_size.height() > 0:
                    scaled_pixmap = pixmap.scaled(
                        widget_size, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    # For AspectRatioFrame, set the pixmap on its label
                    if hasattr(video_widget, 'label'):
                        video_widget.label.setPixmap(scaled_pixmap)
                    else:
                        # Fallback - try to set pixmap directly or use stylesheet
                        if hasattr(video_widget, 'setPixmap'):
                            video_widget.setPixmap(scaled_pixmap)
                        else:
                            # Create a label inside the frame if it doesn't exist
                            if not hasattr(video_widget, '_video_label'):
                                from PyQt6.QtWidgets import QLabel, QVBoxLayout, QSizePolicy
                                video_widget._video_label = QLabel(video_widget)
                                if not video_widget.layout():
                                    layout = QVBoxLayout(video_widget)
                                    layout.setContentsMargins(0, 0, 0, 0)
                                    video_widget.setLayout(layout)
                                video_widget._video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                                video_widget.layout().addWidget(video_widget._video_label)
                                video_widget._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                                video_widget._video_label.setScaledContents(True)
                            
                            video_widget._video_label.setPixmap(scaled_pixmap)

                    # Store last pixmap and update output if selected
                    self.last_input_pixmap[input_number] = scaled_pixmap
                    if not getattr(self, '_transition_running', False) and self.current_output == ('input', input_number):
                        # Use original for output to avoid double-scaling loss
                        self._set_output_image(self.last_input_image[input_number])
                    
        except Exception as e:
            print(f"Error updating camera frame for input {input_number}: {e}")
    
    def _on_avf_frame(self, input_number: int, qimg: QImage, measured_fps: float):
        """Handle frames from AVFoundation (PyAV) capture."""
        try:
            if qimg is None or qimg.isNull():
                return
            # Cache originals
            if not hasattr(self, 'last_input_image'):
                self.last_input_image = {}
            if not hasattr(self, 'last_input_pixmap'):
                self.last_input_pixmap = {}
            
            # ✅ APPLY CAMERA PROCESSING (brightness, contrast, chroma key, etc.)
            processed_img = qimg
            try:
                from camera_processor import camera_processors
                # Always try to process - the processor will handle if no effects are enabled
                processed_result = camera_processors[input_number].process_frame(qimg)
                if processed_result is not None:
                    processed_img = processed_result
                    # Only log when effects are actually applied
                    if camera_processors[input_number].is_enabled():
                        print(f"✅ Applied camera processing to Input-{input_number}")
            except Exception as e:
                print(f"Camera processing error for Input-{input_number}: {e}")
            
            self.last_input_image[input_number] = processed_img.copy()
            pixmap = QPixmap.fromImage(processed_img)
            video_widget = getattr(self, f'inputVideoFrame{input_number}', None)
            if not video_widget:
                return
            widget_size = video_widget.size()
            if widget_size.width() <= 1 or widget_size.height() <= 1:
                ms = video_widget.minimumSize()
                widget_size = ms if ms.isValid() else QSize(320, 180)
            scaled_pixmap = pixmap.scaled(
                widget_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if hasattr(video_widget, 'label'):
                video_widget.label.setPixmap(scaled_pixmap)
            else:
                if not hasattr(video_widget, '_video_label'):
                    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QSizePolicy
                    video_widget._video_label = QLabel(video_widget)
                    if not video_widget.layout():
                        layout = QVBoxLayout(video_widget)
                        layout.setContentsMargins(0, 0, 0, 0)
                        video_widget.setLayout(layout)
                    video_widget._video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    video_widget.layout().addWidget(video_widget._video_label)
                    video_widget._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    video_widget._video_label.setScaledContents(True)
                video_widget._video_label.setPixmap(scaled_pixmap)

            self.last_input_pixmap[input_number] = scaled_pixmap
            # If on program, send original image to output
            if not getattr(self, '_transition_running', False) and self.current_output == ('input', input_number):
                self._set_output_image(self.last_input_image[input_number])

            # Runtime FPS adaptation (same policy as Qt path)
            try:
                measured = float(measured_fps or 0.0)
                if measured > 1.0:
                    new_fps = int(round(min(240, measured)))
                    app_config.set('ui.preview_fps', new_fps)
                    app_config.save_settings()
                    # Log measured FPS
                    # Use FPS stabilizer to prevent excessive updates
                    should_update, stable_fps = fps_manager.update_component_fps(f'input_{input_number}', measured)
                    if should_update:
                        print(f"Input-{input_number} FPS stabilized at {stable_fps}fps (was {measured:.1f}fps)")
                        if getattr(self, 'current_output', (None, None)) == ('input', input_number):
                            if hasattr(self, '_graphics_output'):
                                self._graphics_output.set_target_fps(stable_fps)
                                print(f"Graphics output FPS updated to {stable_fps}fps")
                        if hasattr(self, 'mirror_controller') and self.mirror_controller and self.mirror_controller.is_running():
                            self.mirror_controller.update({'fps': new_fps})
                        if hasattr(self, 'stream_controllers'):
                            for sc in self.stream_controllers.values():
                                try:
                                    if sc.is_running():
                                        sc.set_fps(new_fps)
                                except Exception:
                                    pass
            except Exception:
                pass
        except Exception as e:
            print(f"AVF camera frame error (Input-{input_number}): {e}")

    def _on_qt_camera_frame(self, input_number, video_frame):
        """Handle frames from Qt camera (QVideoSink) for the given input. Also measure actual FPS."""
        try:
            img = video_frame.toImage()
            if img is None or img.isNull():
                print(f"⚠️ Input-{input_number}: Received null/empty frame")
                return
            
            # Debug: Only log first few frames to avoid spam
            if not hasattr(self, '_frame_count'):
                self._frame_count = {}
            if input_number not in self._frame_count:
                self._frame_count[input_number] = 0
            self._frame_count[input_number] += 1
            if self._frame_count[input_number] <= 3:
                print(f"📹 Input-{input_number}: Received frame {img.width()}x{img.height()}")
            # FPS measurement using arrival timestamps
            try:
                import time
                if hasattr(self, '_fps_measure') and input_number in self._fps_measure:
                    rec = self._fps_measure[input_number]
                    now = time.time()
                    rec['times'].append(now)
                    # Compute instantaneous FPS over last ~1s
                    if len(rec['times']) >= 5:
                        t0 = rec['times'][0]
                        t1 = rec['times'][-1]
                        dt = max(1e-3, t1 - t0)
                        measured = (len(rec['times']) - 1) / dt
                        rec['measured_fps'] = measured
                        # If measured FPS is much lower than device capability, auto-correct by switching format once
                        try:
                            if measured < 25.0:
                                cam = self.qt_cameras.get(input_number)
                                sess = self.qt_sessions.get(input_number)
                                sink = self.qt_sinks.get(input_number)
                                if cam is not None and sess is not None and sink is not None:
                                    dev = cam.cameraDevice()
                                    # Find highest-FPS format again
                                    best_fmt = None
                                    best_key = (-1.0, 0, 0)
                                    for fmt in dev.videoFormats():
                                        try:
                                            fps_max = float(fmt.maxFrameRate())
                                        except Exception:
                                            fps_max = 0.0
                                        size = fmt.resolution()
                                        w = int(size.width()) if hasattr(size, 'width') else int(getattr(size, 'width', 0))
                                        h = int(size.height()) if hasattr(size, 'height') else int(getattr(size, 'height', 0))
                                        key = (fps_max, w, h)
                                        if (key > best_key) or (abs(fps_max - best_key[0]) < 0.1 and (w, h) == (1920, 1080)):
                                            best_key = key
                                            best_fmt = fmt
                                    if best_fmt is not None and best_key[0] >= 50.0:
                                        # Apply format and restart camera once
                                        try:
                                            print(f"Measured {measured:.1f}fps; switching to {best_key[1]}x{best_key[2]} @ {best_key[0]:.0f}fps")
                                        except Exception:
                                            pass
                                        cam.stop()
                                        cam.setCameraFormat(best_fmt)
                                        cam.start()
                                        # Reset measurement buffer after switch
                                        rec['times'].clear()
                        except Exception:
                            pass
                        # Throttle logs/updates to ~2 Hz
                        if now - rec.get('last_report', 0.0) > 0.5:
                            rec['last_report'] = now
                            # Use FPS stabilizer for Qt camera
                            should_update, stable_fps = fps_manager.update_component_fps(f'qt_input_{input_number}', measured)
                            if should_update:
                                print(f"Input-{input_number} FPS stabilized at {stable_fps}fps (measured: {measured:.1f}fps)")
                                app_config.set('ui.preview_fps', stable_fps)
                                app_config.save_settings()
                                if getattr(self, 'current_output', (None, None)) == ('input', input_number):
                                    if hasattr(self, '_graphics_output'):
                                        self._graphics_output.set_target_fps(stable_fps)
                                # Also update external mirror FPS live if running
                                try:
                                    if hasattr(self, 'mirror_controller') and self.mirror_controller and self.mirror_controller.is_running():
                                        self.mirror_controller.update({'fps': stable_fps})
                                except Exception:
                                    pass
                                # Also update any running streams to the same FPS
                                try:
                                    if hasattr(self, 'stream_controllers'):
                                        for sc in self.stream_controllers.values():
                                            try:
                                                if sc.is_running():
                                                    sc.set_fps(stable_fps)
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
            except Exception:
                pass
            # Ensure caches
            if not hasattr(self, 'last_input_image'):
                self.last_input_image = {}
            if not hasattr(self, 'last_input_pixmap'):
                self.last_input_pixmap = {}
            # ✅ APPLY CAMERA PROCESSING (brightness, contrast, chroma key, etc.)
            try:
                from camera_processor import camera_processors
                # Always try to process - the processor will handle if no effects are enabled
                processed_img = camera_processors[input_number].process_frame(img)
                if processed_img is not None:
                    img = processed_img
                    # Only log when effects are actually applied
                    if camera_processors[input_number].is_enabled():
                        if self._frame_count[input_number] <= 3:  # Only log first few times
                            print(f"✅ Applied camera processing to Input-{input_number}")
            except Exception as e:
                print(f"Camera processing error for Input-{input_number}: {e}")
            
            # Cache processed image
            self.last_input_image[input_number] = img.copy()
            pixmap = QPixmap.fromImage(img)
            # Target widget
            video_widget = getattr(self, f'inputVideoFrame{input_number}', None)
            if not video_widget:
                return
            widget_size = video_widget.size()
            if widget_size.width() <= 1 or widget_size.height() <= 1:
                ms = video_widget.minimumSize()
                widget_size = ms if ms.isValid() else QSize(320, 180)
            scaled_pixmap = pixmap.scaled(
                widget_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Ensure label and set pixmap
            if hasattr(video_widget, 'label'):
                video_widget.label.setPixmap(scaled_pixmap)
            else:
                if not hasattr(video_widget, '_video_label'):
                    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QSizePolicy
                    video_widget._video_label = QLabel(video_widget)
                    if not video_widget.layout():
                        layout = QVBoxLayout(video_widget)
                        layout.setContentsMargins(0, 0, 0, 0)
                        video_widget.setLayout(layout)
                    video_widget._video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    video_widget.layout().addWidget(video_widget._video_label)
                    video_widget._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    video_widget._video_label.setScaledContents(True)
                video_widget._video_label.setPixmap(scaled_pixmap)
            # Cache pixmap and update program output if selected
            self.last_input_pixmap[input_number] = scaled_pixmap
            if not getattr(self, '_transition_running', False) and self.current_output == ('input', input_number):
                self._set_output_image(self.last_input_image[input_number])
        except Exception as e:
            print(f"Qt camera frame error (Input-{input_number}): {e}")

    def stop_camera_capture(self, input_number):
        """Stop camera capture for specified input"""
        try:
            if hasattr(self, 'camera_timers') and input_number in self.camera_timers:
                self.camera_timers[input_number].stop()
                del self.camera_timers[input_number]
            
            if hasattr(self, 'camera_captures') and input_number in self.camera_captures:
                self.camera_captures[input_number].release()
                del self.camera_captures[input_number]
            # Stop Qt camera pipeline if present
            if hasattr(self, 'qt_cameras') and input_number in self.qt_cameras:
                try:
                    cam = self.qt_cameras.pop(input_number)
                    cam.stop()
                except Exception:
                    pass
            if hasattr(self, 'qt_sessions') and input_number in self.qt_sessions:
                try:
                    self.qt_sessions.pop(input_number)
                except Exception:
                    pass
            if hasattr(self, 'qt_sinks') and input_number in self.qt_sinks:
                try:
                    sink = self.qt_sinks.pop(input_number)
                    sink.videoFrameChanged.disconnect()
                except Exception:
                    pass
            
            print(f"Stopped camera capture for Input-{input_number}")
        except Exception as e:
            print(f"Error stopping camera capture for Input-{input_number}: {e}")
    
    def show_media_selection_dialog(self, media_number):
        """Show enhanced media file selection dialog for the specified media slot"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                                   QLabel, QFileDialog, QListWidget, QListWidgetItem,
                                   QSplitter, QTextEdit, QProgressBar)
        from PyQt6.QtCore import Qt, QFileInfo, QThread, pyqtSignal
        from PyQt6.QtGui import QFont, QPixmap
        import os
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Media Selection - Media {media_number}")
        dialog.setModal(True)
        dialog.resize(700, 500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
            QListWidget {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                selection-background-color: #0078d4;
            }
            QTextEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
                font-size: 10px;
            }
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 4px;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton#cancelButton {
                background-color: #666666;
            }
            QPushButton#cancelButton:hover {
                background-color: #777777;
            }
            QPushButton#browseButton {
                background-color: #28a745;
            }
            QPushButton#browseButton:hover {
                background-color: #218838;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel(f"Select Media File for Media-{media_number}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Simple file selection approach
        info_label = QLabel("Click 'Browse Files' to select a media file (video or audio)")
        info_label.setStyleSheet("color: #cccccc; margin: 10px 0;")
        layout.addWidget(info_label)
        
        # File info display
        file_info = QTextEdit()
        file_info.setMaximumHeight(100)
        file_info.setReadOnly(True)
        file_info.setText("No file selected")
        layout.addWidget(file_info)
        
        # Status label
        status_label = QLabel("Ready to select media file")
        status_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        layout.addWidget(status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        browse_button = QPushButton("📁 Browse Files")
        browse_button.setObjectName("browseButton")
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancelButton")
        load_button = QPushButton("Load Media")
        load_button.setEnabled(False)
        
        button_layout.addWidget(browse_button)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(load_button)
        layout.addLayout(button_layout)
        
        # Variables to store selected file
        selected_file_path = None
        
        def browse_files():
            nonlocal selected_file_path
            file_path, _ = QFileDialog.getOpenFileName(
                dialog,
                f"Select Media File for Media-{media_number}",
                "",
                "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v *.3gp);;Audio Files (*.mp3 *.wav *.aac *.flac *.ogg *.m4a);;All Files (*)"
            )
            
            if file_path:
                selected_file_path = file_path
                update_file_info(file_path)
                status_label.setText(f"Selected: {os.path.basename(file_path)}")
                load_button.setEnabled(True)
        
        def update_file_info(file_path):
            if not file_path or not os.path.exists(file_path):
                return
                
            file_info_obj = QFileInfo(file_path)
            file_size = file_info_obj.size()
            file_name = file_info_obj.fileName()
            file_dir = file_info_obj.absolutePath()
            
            # Format file size
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            elif file_size < 1024 * 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{file_size / (1024 * 1024 * 1024):.1f} GB"
            
            info_text = f"""File Name: {file_name}
Location: {file_dir}
Size: {size_str}
Type: {file_info_obj.suffix().upper() if file_info_obj.suffix() else 'Unknown'}

Ready to load this media file."""
            
            file_info.setText(info_text)
        
        def load_selected_media():
            if selected_file_path:
                # Use Qt Multimedia pipeline
                self.load_media(media_number, selected_file_path)
                dialog.accept()
        
        # Connect signals
        browse_button.clicked.connect(browse_files)
        cancel_button.clicked.connect(dialog.reject)
        load_button.clicked.connect(load_selected_media)
        
        dialog.exec()
    
    
    def load_effects_into_tabs(self):
        """Set up new Premiere Pro-style effects panel."""
        try:
            # Import the final panel class
            from premiere_effects_panel_final import FinalEffectsPanel
            
            # Get effects folder path (support dev, PyInstaller onedir, and macOS .app Resources)
            effects_path = _get_data_path("effects")
            
            if not os.path.exists(effects_path):
                print(f"Effects folder not found: {effects_path}")
                return
            
            # Get the effects tab widget container
            if not hasattr(self, 'tabWidget_effects'):
                print("Effects tab widget not found")
                return
            
            # Replace the tab widget with our new Premiere Pro-style panel
            tab_widget = self.tabWidget_effects
            # Find left panel layout to ensure placement under output
            left_layout = None
            cw = self.centralWidget()
            if cw and cw.layout():
                tl = cw.layout()
                for i in range(tl.count()):
                    it = tl.itemAt(i)
                    lay = it.layout() if it else None
                    if lay and lay.objectName() == 'verticalLayout_leftPanel':
                        left_layout = lay
                        break
                    w = it.widget() if it else None
                    if w and hasattr(w, 'layout') and w.layout() and w.layout().objectName() == 'verticalLayout_leftPanel':
                        left_layout = w.layout()
                        break

            inserted = False
            if left_layout is not None:
                # Find index of the existing tab widget in left layout
                idx_in_left = None
                for i in range(left_layout.count()):
                    it = left_layout.itemAt(i)
                    if it and it.widget() is tab_widget:
                        idx_in_left = i
                        break
                if idx_in_left is None:
                    # Fallback: remove from its parent layout and append to left layout
                    idx_in_left = left_layout.count()
                # Remove tab widget from its layout (wherever it is)
                try:
                    if tab_widget.parent() and hasattr(tab_widget.parent(), 'layout') and tab_widget.parent().layout():
                        tab_widget.parent().layout().removeWidget(tab_widget)
                except Exception:
                    pass
                tab_widget.hide()

                # Create new panel and insert at same index
                self.premiere_effects_panel = FinalEffectsPanel(effects_path, left_layout.parentWidget())
                self.premiere_effects_panel.effect_selected.connect(self.on_effect_clicked)
                self.premiere_effects_panel.effect_cleared.connect(self.on_effect_cleared)
                left_layout.insertWidget(idx_in_left, self.premiere_effects_panel)
                inserted = True

            if not inserted:
                # Fallback: replace within the original parent layout
                parent_widget = tab_widget.parent()
                if parent_widget and hasattr(parent_widget, 'layout') and parent_widget.layout():
                    layout = parent_widget.layout()
                    layout.removeWidget(tab_widget)
                    tab_widget.hide()
                    self.premiere_effects_panel = FinalEffectsPanel(effects_path, parent_widget)
                    self.premiere_effects_panel.effect_selected.connect(self.on_effect_clicked)
                    self.premiere_effects_panel.effect_cleared.connect(self.on_effect_cleared)
                    layout.addWidget(self.premiere_effects_panel)
                    inserted = True

            if inserted:
                # Re-apply splitter and stretch to enforce placement and sizing
                try:
                    self.apply_left_splitter()
                    self.apply_left_panel_stretch()
                except Exception:
                    pass
                print("Successfully placed Premiere Effects panel under output (left panel)")
            else:
                print("Could not place Premiere Effects panel; left panel layout not found")
             
        except Exception as e:
            print(f"Error loading Premiere Pro effects panel: {e}")
            import traceback
            traceback.print_exc()
    
    def on_effect_clicked(self, effect_path):
        """Handle effect image click"""
        try:
            effect_name = os.path.basename(effect_path)
            # Set overlay on graphics output and refresh
            if self._graphics_output is not None:
                self._graphics_output.set_overlay_from_path(effect_path)
            # Persist last effect
            try:
                app_config.set('ui.last_effect', effect_path)
                app_config.save_settings()
            except Exception:
                pass
            # Highlight selected in new effects panel
            if hasattr(self, 'premiere_effects_panel'):
                # Selection is already handled by the panel itself
                pass
            # Legacy: Highlight selected in old tab system (if still present)
            elif hasattr(self, '_effects_tabs') and hasattr(self, 'tabWidget_effects'):
                idx = self.tabWidget_effects.currentIndex()
                data = self._effects_tabs.get(idx)
                if data and 'widget' in data and data['widget']:
                    data['widget'].update_selection(effect_path)
            self.refresh_output_preview()
        except Exception as e:
            print(f"Error handling effect click: {e}")

    def on_effect_double_clicked(self, effect_path):
        """Remove effect on double-click if it's the selected one."""
        self.on_effect_cleared()

    def on_effect_cleared(self):
        """Clear the current effect."""
        try:
            # Clear overlay
            if self._graphics_output is not None:
                self._graphics_output.clear_overlay()
            # Persist cleared effect
            try:
                app_config.set('ui.last_effect', None)
                app_config.save_settings()
            except Exception:
                pass
            # Clear highlight in new effects panel
            if hasattr(self, 'premiere_effects_panel'):
                self.premiere_effects_panel.clear_selection()
            # Legacy: Clear highlight in old tab system (if still present)
            elif hasattr(self, '_effects_tabs') and hasattr(self, 'tabWidget_effects'):
                idx = self.tabWidget_effects.currentIndex()
                data = self._effects_tabs.get(idx)
                if data and 'widget' in data and data['widget']:
                    data['widget'].update_selection(None)
            self.refresh_output_preview()
        except Exception as e:
            print(f"Error clearing effect: {e}")

    def open_calibration_tool(self):
        """Open calibration dialog for current overlay to define opening rect JSON."""
        try:
            if self._graphics_output is None:
                return
            overlay_path = self._graphics_output.get_overlay_path()
            if not overlay_path or not os.path.exists(overlay_path):
                print("No overlay selected for calibration")
                return
            from calibration_tool import CalibrateOpeningDialog
            dlg = CalibrateOpeningDialog(self, overlay_path)
            if dlg.exec():
                # Reload overlay to apply new opening
                self._graphics_output.set_overlay_from_path(overlay_path)
        except Exception as e:
            print(f"Calibration tool error: {e}")

    def refresh_output_preview(self):
        """Re-render the output preview with current effect and last frame (or black)."""
        try:
            if getattr(self, '_transition_running', False):
                # During transitions, frames are driven by the transition engine.
                return
            if not hasattr(self, 'current_output') or self.current_output is None:
                # No source selected; render effect over black
                self._set_output_image(None)
                return
            st, idx = self.current_output
            if st == 'input':
                img = self.last_input_image.get(idx)
                if img is not None:
                    self._set_output_image(img)
                else:
                    self._set_output_image(None)
            elif st == 'media':
                img = self.last_media_image.get(idx)
                if img is not None:
                    self._set_output_image(img)
                else:
                    self._set_output_image(None)
            else:
                self._set_output_image(None)
        except Exception as e:
            print(f"Error refreshing output preview: {e}")
    
    def init_app_state(self):
        """Initialize the application state"""
        self.recording = False
        self.playing = False
        self.stream1_active = False
        self.stream2_active = False
        self.audio_monitor_muted = False
        # Global audio mute state (master mute)
        self.global_audio_muted = False
        # Tools button states
        self.passthrough_enabled = False
        self.controls_locked = False
        
        # Renderer performance tracking
        self._renderer_stats = {
            'frame_count': 0,
            'last_fps_check': 0,
            'current_fps': 0
        }
        # Previous per-channel states to restore after global unmute
        self._prev_audio_states = {
            'inputs': {1: True, 2: True, 3: True},
            'media': {1: True, 2: True, 3: True},
        }
        self.input1_audio_muted = False
        self.input2_audio_muted = False
        self.input3_audio_muted = False
        # Media audio should be muted by default; only the selected output media gets unmuted
        self.media1_audio_muted = True
        self.media2_audio_muted = True
        self.media3_audio_muted = True
        self.media_playing = False
        self.current_1A_source = None
        self.current_2B_source = None

        # Graphics output scene-based preview
        self._graphics_output: GraphicsOutputWidget | None = None

        # Output selection state (for switching controls)
        self.current_output = None  # no auto program selection at startup
        # Previews (downscaled for right panel)
        self.last_input_pixmap = {}
        self.last_media_pixmap = {}
        # Originals (full-res) for high-quality output screen scaling
        self.last_input_image = {}
        self.last_media_image = {}

        # Ensure output preview label exists
        self._ensure_output_preview_label()

        # Initialize Qt Multimedia media players and outputs (Phase 1)
        self.media_players = {
            1: QMediaPlayer(self),
            2: QMediaPlayer(self),
            3: QMediaPlayer(self),
        }
        self.media_audio_outputs = {
            1: QAudioOutput(self),
            2: QAudioOutput(self),
            3: QAudioOutput(self),
        }
        # Attach audio outputs and set default mute state (muted by default)
        for i in (1, 2, 3):
            self.media_players[i].setAudioOutput(self.media_audio_outputs[i])
            self.media_audio_outputs[i].setMuted(getattr(self, f"media{i}_audio_muted", True))

        # Use QVideoSink to receive frames for media and render to frames and output
        self.media_sinks = {}
        for i in (1, 2, 3):
            sink = QVideoSink(self)
            sink.videoFrameChanged.connect(lambda frame, idx=i: self._on_media_frame(idx, frame))
            self.media_sinks[i] = sink
            self.media_players[i].setVideoOutput(sink)
            # Position/duration signals for slider
            self.media_players[i].positionChanged.connect(lambda pos, idx=i: self._on_media_position_changed(idx, pos))
            self.media_players[i].durationChanged.connect(lambda dur, idx=i: self._on_media_duration_changed(idx, dur))
            # Add error handling and media status monitoring
            self.media_players[i].errorOccurred.connect(lambda error, idx=i: self._on_media_error(idx, error))
            self.media_players[i].mediaStatusChanged.connect(lambda status, idx=i: self._on_media_status_changed(idx, status))
            self.media_players[i].playbackStateChanged.connect(lambda state, idx=i: self._on_playback_state_changed(idx, state))

        # Initialize input audio monitors (Phase 2) containers
        self.input_audio_inputs = {}
        self.input_audio_sinks = {}
        
        # Clear effects and ensure text overlay is disabled by default
        if self._graphics_output is not None:
            self._graphics_output.clear_overlay()
            # Ensure text overlay is disabled
            default_text_props = {
                'visible': False,
                'text': '',
                'font_size': 36,
                'font_family': '',
                'color': 0xFFFFFFFF,  # rgba format
                'stroke_color': 0xFF000000,
                'stroke_width': 3,
                'bg_enabled': False,
                'bg_color': 0xA0000000,
                'pos_x': 50,
                'pos_y': 90,
                'anchor': 'center',
                'scroll': False,
                'scroll_speed': 50,
            }
            self._graphics_output.set_text_overlay(default_text_props)

        # Update status
        self.update_record_status("Ready", "#777777")

    def closeEvent(self, event):
        """Ensure clean shutdown of background processes and persist settings."""
        # Print performance report
        print("\nGenerating final performance report...")
        try:
            performance_monitor.print_performance_summary()
        except:
            pass
        
        try:
            # Stop streaming controllers (primary)
            try:
                if hasattr(self, 'stream_controller') and self.stream_controller:
                    self.stream_controller.stop()
            except Exception:
                pass
            # Stop independent stream controllers (Stream 1 & 2)
            try:
                if hasattr(self, 'stream_controllers') and isinstance(self.stream_controllers, dict):
                    for _sc in self.stream_controllers.values():
                        try:
                            _sc.stop()
                        except Exception:
                            pass
            except Exception:
                pass
            # Stop recorder
            try:
                if hasattr(self, 'recorder_controller') and self.recorder_controller:
                    self.recorder_controller.stop()
            except Exception:
                pass
            # Stop mirror controller
            try:
                if hasattr(self, 'mirror_controller') and self.mirror_controller:
                    self.mirror_controller.stop()
            except Exception:
                pass
            # Save UI/session settings
            try:
                if self._graphics_output is not None:
                    # Keep existing config values (overscan/fps tracked elsewhere)
                    pass
                app_config.save_settings()
            except Exception:
                pass
            
            # Cleanup optimization systems
            print("Cleaning up optimization systems...")
            try:
                if timer_manager.get_system():
                    timer_manager.get_system().cleanup()
            except:
                pass
            try:
                thread_pool.shutdown(wait=False)
            except:
                pass
            try:
                event_coalescer.stop()
            except:
                pass
            try:
                gl_context_manager.cleanup()
            except:
                pass
            try:
                smart_cache.clear()
                texture_pool.clear()
                general_memory_pool.clear()
                image_memory_pool.clear()
            except:
                pass
                
        except Exception:
            pass
        super().closeEvent(event)

    def cleanup_on_exit(self):
        """Called from QApplication.aboutToQuit to ensure all processes are stopped before teardown."""
        try:
            try:
                if hasattr(self, 'stream_controller') and self.stream_controller:
                    self.stream_controller.stop()
            except Exception:
                pass
            try:
                if hasattr(self, 'mirror_controller') and self.mirror_controller:
                    self.mirror_controller.stop()
            except Exception:
                pass
        except Exception:
            pass
    
    def toggle_recording(self):
        """Enhanced toggle recording with better error handling and user feedback"""
        try:
            current_state = getattr(self, 'recording', False)
            
            if not current_state:
                # Start recording
                print("🎥 Starting recording...")
                success = self.start_recording()
                if success:
                    self.recording = True
                    print("✅ Recording started successfully")
                else:
                    self.recording = False
                    print("❌ Failed to start recording")
            else:
                # Stop recording
                print("🛑 Stopping recording...")
                self.stop_recording()
                self.recording = False
                print("✅ Recording stopped")
                
        except Exception as e:
            print(f"❌ Error toggling recording: {e}")
            self.recording = False
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Recording Error", f"Failed to toggle recording:\n{str(e)}")

    def toggle_global_mute(self):
        """Toggle master mute for all inputs and media. Restores previous states on unmute."""
        try:
            new_state = not getattr(self, 'global_audio_muted', False)
            if new_state:
                # Save current per-channel states
                self._prev_audio_states = {
                    'inputs': {
                        1: getattr(self, 'input1_audio_muted', True),
                        2: getattr(self, 'input2_audio_muted', True),
                        3: getattr(self, 'input3_audio_muted', True),
                    },
                    'media': {
                        1: getattr(self, 'media1_audio_muted', True),
                        2: getattr(self, 'media2_audio_muted', True),
                        3: getattr(self, 'media3_audio_muted', True),
                    }
                }
                # Mute all inputs (stop monitors) and set icons
                self.input1_audio_muted = True
                self.input2_audio_muted = True
                self.input3_audio_muted = True
                for i in (1, 2, 3):
                    try:
                        self._stop_input_audio(i)
                    except Exception:
                        pass
                if hasattr(self, 'input1AudioButton'):
                    self.input1AudioButton.setIcon(self.get_icon("Mute.png"))
                if hasattr(self, 'input2AudioButton'):
                    self.input2AudioButton.setIcon(self.get_icon("Mute.png"))
                if hasattr(self, 'input3AudioButton'):
                    self.input3AudioButton.setIcon(self.get_icon("Mute.png"))

                # Mute all media and set icons
                for i in (1, 2, 3):
                    setattr(self, f"media{i}_audio_muted", True)
                    if hasattr(self, 'media_audio_outputs') and i in self.media_audio_outputs:
                        try:
                            self.media_audio_outputs[i].setMuted(True)
                        except Exception:
                            pass
                    btn_attr = f"media{i}AudioButton"
                    if hasattr(self, btn_attr):
                        getattr(self, btn_attr).setIcon(self.get_icon("Mute.png"))

                print("Global audio muted")
            else:
                # Restore previous states for inputs
                for i in (1, 2, 3):
                    prev = self._prev_audio_states.get('inputs', {}).get(i, True)
                    setattr(self, f"input{i}_audio_muted", prev)
                    # If input should be active (unmuted) and currently on program, ensure monitor
                    try:
                        if not prev and getattr(self, 'current_output', (None, -1))[0] == 'input' and getattr(self, 'current_output', (None, -1))[1] == i:
                            self._ensure_input_audio(i)
                        else:
                            self._stop_input_audio(i)
                    except Exception:
                        pass
                    btn_attr = f"input{i}AudioButton"
                    if hasattr(self, btn_attr):
                        getattr(self, btn_attr).setIcon(self.get_icon("Mute.png" if prev else "Volume.png"))

                # Restore previous states for media and apply
                for i in (1, 2, 3):
                    prev = self._prev_audio_states.get('media', {}).get(i, True)
                    setattr(self, f"media{i}_audio_muted", prev)
                    if hasattr(self, 'media_audio_outputs') and i in self.media_audio_outputs:
                        try:
                            # Also respect current media policy (it may immediately re-mute others on next switch)
                            self.media_audio_outputs[i].setMuted(prev)
                        except Exception:
                            pass
                    btn_attr = f"media{i}AudioButton"
                    if hasattr(self, btn_attr):
                        getattr(self, btn_attr).setIcon(self.get_icon("Mute.png" if prev else "Volume.png"))

                print("Global audio unmuted (previous states restored)")

            # Update master icon and state
            self.global_audio_muted = new_state
            if hasattr(self, 'audioTopButton'):
                self.audioTopButton.setIcon(self.get_icon("Mute.png" if self.global_audio_muted else "Volume.png"))
        except Exception as e:
            print(f"Error toggling global mute: {e}")
    
    def start_recording(self) -> bool:
        """Enhanced start recording with better validation and error handling."""
        try:
            print("🎬 Initializing recording...")
            
            # Check if recorder controller exists
            if not hasattr(self, 'recorder_controller') or not self.recorder_controller:
                print("❌ Recorder controller not available")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Recording Error", "Recording system not initialized properly.")
                return False
            
            # Check if already recording
            if self.recorder_controller.is_running():
                print("⚠️ Recording already in progress")
                return False
            
            # Ensure we have a save path
            out_path = app_config.get('recording.output_path', '') or ''
            include_audio = bool(app_config.get('recording.audio_enabled', True))
            
            print(f"📁 Output path: {out_path}")
            print(f"🎧 Include audio: {include_audio}")
            
            if not out_path:
                print("⚠️ No output path configured, opening settings...")
                # Prompt settings dialog if no path saved yet
                self.open_record_settings()
                out_path = app_config.get('recording.output_path', '') or ''
                include_audio = bool(app_config.get('recording.audio_enabled', True))
                if not out_path:
                    print("❌ User cancelled or no path provided")
                    return False

            # Determine output size and fps (follow Output Size selection), then clamp for recording
            fps = int(app_config.get('ui.preview_fps', 60) or 60)
            width = int(app_config.get('ui.output_width', 1920))
            height = int(app_config.get('ui.output_height', 1080))

            # Clamp recording FPS to 24 to further prevent pipe backpressure
            rec_fps = min(24, max(10, fps))

            # Downscale large resolutions for recording to 960x540 to reduce raw pipe bandwidth
            rec_width, rec_height = width, height
            if width * height > 960 * 540:
                aspect = width / max(1, height)
                rec_width = 960
                rec_height = int(round(rec_width / aspect))
                # Ensure multiple of 2 for encoders
                if rec_height % 2:
                    rec_height += 1

            print(f"🎯 Effective recording resolution: {rec_width}x{rec_height} @ {rec_fps}fps (source: {width}x{height} @ {fps}fps)")

            # Audio strategy: if a media is on program, mux its original audio; otherwise optionally capture system
            program_media_audio_path = self.get_current_program_media_audio_path() or ''
            # Determine media start position so recorded audio aligns with current playback
            program_media_audio_start_ms = 0
            try:
                if getattr(self, 'current_output', (None, None))[0] == 'media':
                    m_idx = getattr(self, 'current_output', (None, None))[1]
                    player = self.media_players.get(m_idx)
                    if player is not None:
                        program_media_audio_start_ms = int(getattr(player, 'position')() or 0)
            except Exception:
                program_media_audio_start_ms = 0

            audio_device = ''
            # Validate output directory
            import os
            output_dir = os.path.dirname(out_path)
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    print(f"📁 Created output directory: {output_dir}")
                except Exception as e:
                    print(f"❌ Cannot create output directory: {e}")
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.critical(self, "Recording Error", f"Cannot create output directory:\n{output_dir}\n\nError: {e}")
                    return False
            
            # Check disk space (warn if less than 1GB)
            try:
                import shutil
                free_space = shutil.disk_usage(output_dir).free
                free_gb = free_space / (1024**3)
                print(f"💾 Available disk space: {free_gb:.1f} GB")
                if free_gb < 1.0:
                    from PyQt6.QtWidgets import QMessageBox
                    reply = QMessageBox.warning(
                        self, "Low Disk Space", 
                        f"Warning: Only {free_gb:.1f} GB of disk space available.\n\nContinue recording anyway?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return False
            except Exception:
                pass
            
            # Audio configuration
            if include_audio and not program_media_audio_path:
                try:
                    # Reuse streaming's auto device detection for convenience
                    if hasattr(self, 'stream_controller') and hasattr(self.stream_controller, '_auto_select_audio_device'):
                        audio_device = self.stream_controller._auto_select_audio_device() or ''
                        print(f"🎤 Audio device: {audio_device}")
                except Exception:
                    audio_device = ''
            
            # Get advanced settings from recording settings dialog
            advanced_settings = self._get_recording_advanced_settings()
            # Adjust bitrate for reduced resolution to avoid encoder backpressure
            eff_bitrate = int(advanced_settings.get('bitrate_kbps', 12000))
            if rec_width * rec_height <= 960 * 540 and eff_bitrate > 6000:
                eff_bitrate = 6000
            
            print(f"📺 Recording settings:")
            print(f"  Resolution: {width}x{height}")
            print(f"  FPS: {fps}")
            print(f"  Bitrate: {eff_bitrate} kbps")
            print(f"  Format: {advanced_settings.get('format', 'MP4')}")
            # Respect user include_audio setting when not muxing media audio
            
            settings = {
                'file_path': out_path,
                'width': rec_width,
                'height': rec_height,
                'fps': rec_fps,
                'bitrate_kbps': eff_bitrate,
                'video_preset': advanced_settings.get('video_preset', 'veryfast'),
                'capture_audio': include_audio and not program_media_audio_path,
                'audio_device': audio_device,
                'program_media_audio_path': program_media_audio_path,
                # Align media audio to current playback position
                'program_media_audio_start_ms': program_media_audio_start_ms,
                # Keep A/V delay at 0 when using direct media audio; recorder can add minimal if needed
                'av_sync_delay_ms': 0,
            }
            
            try:
                print("🚀 Starting recorder controller...")
                self.recorder_controller.start(settings)
                
                # Update UI
                self.update_record_status("Recording", "#ff0000")
                
                # Update record button icon to show recording state
                if hasattr(self, 'recordRedCircle'):
                    self.recordRedCircle.setStyleSheet("background-color: #ff0000; border-radius: 15px;")
                
                # Show Pause icon on play button
                if hasattr(self, 'playButton'):
                    self.playButton.setIcon(self.get_icon("Pause.png"))
                
                print("✅ Recording started successfully")
                return True
                
            except Exception as e:
                print(f"❌ Failed to start recording: {e}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Recording Error", f"Failed to start recording:\n{str(e)}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting recording: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_recording_health(self) -> dict:
        """Check recording system health and return diagnostic information."""
        health = {
            'status': 'unknown',
            'issues': [],
            'recommendations': [],
            'system_info': {}
        }
        
        try:
            # Check recorder controller
            if not hasattr(self, 'recorder_controller') or not self.recorder_controller:
                health['status'] = 'error'
                health['issues'].append("Recording controller not initialized")
                health['recommendations'].append("Restart the application")
                return health
            
            # Check if recording is active
            is_running = self.recorder_controller.is_running()
            is_paused = self.recorder_controller.is_paused() if is_running else False
            
            if is_running:
                if is_paused:
                    health['status'] = 'paused'
                else:
                    health['status'] = 'recording'
            else:
                health['status'] = 'ready'
            
            # Check output path configuration
            out_path = app_config.get('recording.output_path', '') or ''
            if not out_path:
                health['issues'].append("No output path configured")
                health['recommendations'].append("Configure recording output path in settings")
            else:
                # Check if output directory exists and is writable
                import os
                output_dir = os.path.dirname(out_path)
                if not os.path.exists(output_dir):
                    health['issues'].append(f"Output directory does not exist: {output_dir}")
                    health['recommendations'].append("Create output directory or choose different path")
                elif not os.access(output_dir, os.W_OK):
                    health['issues'].append(f"Output directory not writable: {output_dir}")
                    health['recommendations'].append("Check directory permissions")
                
                # Check disk space
                try:
                    import shutil
                    free_space = shutil.disk_usage(output_dir).free
                    free_gb = free_space / (1024**3)
                    health['system_info']['free_space_gb'] = round(free_gb, 1)
                    
                    if free_gb < 0.5:
                        health['issues'].append(f"Very low disk space: {free_gb:.1f} GB")
                        health['recommendations'].append("Free up disk space or choose different location")
                    elif free_gb < 2.0:
                        health['issues'].append(f"Low disk space: {free_gb:.1f} GB")
                        health['recommendations'].append("Consider freeing up disk space")
                except Exception:
                    pass
            
            # Check FFmpeg availability
            try:
                from ffmpeg_utils import get_ffmpeg_path
                import subprocess
                ffmpeg_path = get_ffmpeg_path()
                result = subprocess.run([ffmpeg_path, '-version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    health['system_info']['ffmpeg_available'] = True
                    # Extract version info
                    for line in result.stdout.split('\n'):
                        if 'ffmpeg version' in line.lower():
                            health['system_info']['ffmpeg_version'] = line.strip()
                            break
                else:
                    health['issues'].append("FFmpeg not working properly")
                    health['recommendations'].append("Reinstall FFmpeg")
            except Exception as e:
                health['issues'].append(f"FFmpeg not available: {str(e)}")
                health['recommendations'].append("Install FFmpeg")
            
            # Overall health assessment
            if not health['issues']:
                health['status'] = 'healthy' if health['status'] == 'ready' else health['status']
            elif len(health['issues']) > 2:
                health['status'] = 'critical'
            else:
                health['status'] = 'warning'
                
        except Exception as e:
            health['status'] = 'error'
            health['issues'].append(f"Health check failed: {str(e)}")
            
        return health
    
    def show_recording_health_info(self):
        """Display recording health information to user."""
        health = self.check_recording_health()
        
        print(f"\n🎥 Recording System Health Check:")
        print("=" * 50)
        print(f"Status: {health['status'].upper()}")
        
        if health['system_info']:
            print("\n📊 System Info:")
            for key, value in health['system_info'].items():
                print(f"  • {key}: {value}")
        
        if health['issues']:
            print(f"\n⚠️ Issues Found ({len(health['issues'])}):")
            for issue in health['issues']:
                print(f"  • {issue}")
        
        if health['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in health['recommendations']:
                print(f"  • {rec}")
        
        print("=" * 50)
    
    def _get_recording_advanced_settings(self) -> dict:
        """Get advanced recording settings from config."""
        return {
            'bitrate_kbps': int(app_config.get('recording.bitrate_kbps', 12000)),
            'video_preset': app_config.get('recording.video_preset', 'veryfast'),
            'format': app_config.get('recording.format', 'MP4'),
            'crf': int(app_config.get('recording.crf', 18)),
            'hardware_acceleration': bool(app_config.get('recording.hardware_acceleration', True)),
        }
    
    def stop_recording(self):
        """Enhanced stop recording with better feedback."""
        try:
            print("🛑 Stopping recording...")
            
            if hasattr(self, 'recorder_controller') and self.recorder_controller:
                if self.recorder_controller.is_running():
                    self.recorder_controller.stop()
                    print("✅ Recorder controller stopped")
                else:
                    print("⚠️ Recorder was not running")
            else:
                print("❌ Recorder controller not available")
            
            # Update UI
            self.update_record_status("Ready", "#777777")
            
            # Reset record button appearance
            if hasattr(self, 'recordRedCircle'):
                self.recordRedCircle.setStyleSheet("background-color: #404040; border-radius: 15px;")
            
            # Reset play button to Play icon
            if hasattr(self, 'playButton'):
                self.playButton.setIcon(self.get_icon("Play.png"))
            
            print("✅ Recording stopped successfully")
            
        except Exception as e:
            print(f"❌ Error stopping recording: {e}")
            import traceback
            traceback.print_exc()
    
    def toggle_playback(self):
        """Enhanced play/pause button: pauses/resumes the recorder if running."""
        try:
            rc = getattr(self, 'recorder_controller', None)
            if rc and rc.is_running():
                if rc.is_paused():
                    print("▶️ Resuming recording...")
                    rc.resume()
                    if hasattr(self, 'playButton'):
                        self.playButton.setIcon(self.get_icon("Pause.png"))
                    self.update_record_status("Recording", "#ff0000")
                    print("✅ Recording resumed")
                else:
                    print("⏸️ Pausing recording...")
                    rc.pause()
                    if hasattr(self, 'playButton'):
                        self.playButton.setIcon(self.get_icon("Play.png"))
                    self.update_record_status("Paused", "#ffaa00")
                    print("✅ Recording paused")
                return
            else:
                print("⚠️ No active recording to pause/resume")
                
        except Exception as e:
            print(f"❌ Error toggling record pause: {e}")
            
        # Fallback: toggle local state and icon if recorder not present
        self.playing = not getattr(self, 'playing', False)
        if self.playing:
            if hasattr(self, 'playButton'):
                self.playButton.setIcon(self.get_icon("Pause.png"))
        else:
            if hasattr(self, 'playButton'):
                self.playButton.setIcon(self.get_icon("Play.png"))
    
    def capture_screenshot(self):
        """Capture a screenshot of the output panel and save next to the recording output path."""
        try:
            # Determine output directory from recording settings
            out_path = app_config.get('recording.output_path', '') or ''
            if not out_path:
                QMessageBox.information(self, "Screenshot", "Please set a recording path first in Recording Settings.")
                return
            out_dir = os.path.dirname(out_path)
            if not out_dir:
                out_dir = os.path.expanduser('~')
            # Render current output using selected Output Size
            ow = int(app_config.get('ui.output_width', 1920))
            oh = int(app_config.get('ui.output_height', 1080))
            target_size = QSize(ow, oh)
            if hasattr(self, '_graphics_output') and self._graphics_output is not None:
                img = self._graphics_output.render_to_image(target_size)
            else:
                img = QImage(target_size, QImage.Format.Format_ARGB32)
                img.fill(0)
            # Filename with timestamp
            from PyQt6.QtCore import QDateTime
            ts = QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')
            base = os.path.splitext(os.path.basename(out_path))[0] or 'recording'
            fname = f"{base}_{ts}.png"
            fpath = os.path.join(out_dir, fname)
            ok = img.save(fpath)
            if ok:
                print(f"Screenshot saved: {fpath}")
            else:
                QMessageBox.warning(self, "Screenshot", "Failed to save screenshot.")
        except Exception as e:
            print(f"Screenshot error: {e}")
    
    def open_record_settings(self):
        """Open recording settings dialog to choose file path and audio option."""
        try:
            print("🎥 Opening recording settings dialog...")
            initial = app_config.get('recording.output_path', '') or ''
            include_audio = bool(app_config.get('recording.audio_enabled', True))
            print(f"📁 Initial path: {initial}")
            print(f"🎧 Include audio: {include_audio}")
            
            dlg = RecordingSettingsDialog(self, initial_path=initial, include_audio=include_audio)
            print("✅ Recording settings dialog created successfully")
            
            if dlg.exec():
                path, audio = dlg.get_values()
                advanced = dlg.get_advanced_settings()
                print(f"💾 User saved settings:")
                print(f"  📁 Path: {path}")
                print(f"  🎧 Audio: {audio}")
                print(f"  🎬 Format: {advanced.get('format', 'Unknown')}")
                print(f"  ⭐ Quality: CRF {advanced.get('crf', 'Unknown')}")
                
                if path:
                    app_config.set('recording.output_path', path)
                    app_config.set('recording.audio_enabled', bool(audio))
                    app_config.save_settings()
                    print("✅ Recording settings saved to config")
                else:
                    print("⚠️ No path specified, settings not saved")
            else:
                print("❌ User cancelled recording settings")
                
        except Exception as e:
            print(f"❌ Recording settings error: {e}")
            import traceback
            traceback.print_exc()
    
    def _debug_open_record_settings(self):
        """Debug wrapper for recording settings."""
        print("🎥 DEBUG: Recording Settings menu item clicked")
        self.open_record_settings()
    
    def _debug_show_text_overlay_settings(self):
        """Debug wrapper for text overlay settings."""
        print("✍️ DEBUG: Text Overlay Settings menu item clicked")
        self.show_text_overlay_settings()

    def _on_record_status_changed(self, status: str):
        try:
            st = (status or '').lower()
            if 'started' in st:
                self.update_record_status("Recording", "#ff0000")
            elif 'paused' in st:
                self.update_record_status("Paused", "#ffaa00")
            elif 'error' in st:
                self.update_record_status("Record Error", "#ff4444")
            else:
                # Stopped or unknown
                self.update_record_status("Ready", "#777777")
        except Exception as e:
            print(f"Record status UI error: {e}")

    def _on_record_log(self, text: str):
        try:
            if text:
                print(text, end='' if text.endswith('\n') else '\n')
        except Exception:
            pass
    
    def get_stream_controller(self, stream_id: int) -> StreamController:
        try:
            return self.stream_controllers.get(stream_id)
        except Exception:
            return None

    def handle_stream_button_click(self, stream_id: int):
        """Handle stream button click - toggles stream on/off."""
        print(f"🎬 Stream {stream_id} button clicked - toggling stream...")
        self.toggle_stream(stream_id)
    
    def toggle_stream(self, stream_id: int):
        """Toggle stream on/off using independent StreamController and saved settings."""
        key_prefix = f'streaming.stream{stream_id}'
        active_attr = f'stream{stream_id}_active'
        current = getattr(self, active_attr, False)
        controller = self.get_stream_controller(stream_id)
        if controller is None:
            print(f"❌ Stream controller for stream {stream_id} not available")
            return
        
        if not current:
            # Start streaming
            settings = self._load_stream_settings(stream_id)
            print(f"🚀 Starting Stream {stream_id} with settings: {settings}")
            
            # Check if settings are configured
            if not settings.get('url') and settings.get('platform') != 'External Display (Mirror)':
                print(f"⚠️ Stream {stream_id} not configured - opening settings dialog")
                self.open_stream_settings_dialog(stream_id)
                return
            
            try:
                # Apply streaming optimizations for YouTube
                if settings.get('platform') == 'YouTube Live':
                    self._apply_youtube_optimizations(settings)
                
                controller.start(settings)
                setattr(self, active_attr, True)
                
                # Update button appearance - keep settings icon but change background
                btn = getattr(self, f'stream{stream_id}SettingsBtn', None)
                if btn:
                    btn.setIcon(self.get_icon("Settings.png"))  # Keep settings icon
                    btn.setStyleSheet("border-radius: 5px; background-color: #ff4444;")  # Red when streaming
                
                self.update_record_status(f"Streaming {stream_id}", "#00aa00")
                print(f"✅ Stream {stream_id} started successfully")
                
                # Show streaming health info
                self._show_streaming_health_info(stream_id, settings)
                
                # Automatically apply audio delay correction when streaming starts
                print(f"🎧 Applying audio delay correction for Stream {stream_id}...")
                self._auto_apply_audio_delay_correction()
                
            except Exception as e:
                print(f"❌ Failed to start Stream {stream_id}: {e}")
                # Show error to user
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, f"Stream {stream_id} Error", 
                                   f"Failed to start stream:\n{str(e)}\n\nCheck your stream settings.")
        else:
            # Stop streaming
            print(f"🛑 Stopping Stream {stream_id}...")
            controller.stop()
            setattr(self, active_attr, False)
            
            # Update button appearance
            btn = getattr(self, f'stream{stream_id}SettingsBtn', None)
            if btn:
                btn.setIcon(self.get_icon("Settings.png"))
                btn.setStyleSheet("border-radius: 5px; background-color: #404040;")  # Gray when stopped
            
            self.update_record_status("Ready", "#777777")
            print(f"✅ Stream {stream_id} stopped")
    
    def open_stream_settings_dialog(self, stream_id: int):
        try:
            print(f"🎬 Opening Stream {stream_id} settings dialog...")
            from streaming_settings_dialog_improved import StreamingSettingsDialog
            dlg = StreamingSettingsDialog(self, stream_id, app_config)
            print(f"✅ Stream {stream_id} settings dialog created successfully")
            
            result = dlg.exec()
            print(f"📝 Stream {stream_id} settings dialog closed with result: {result}")
            
            # If user saved settings, ask if they want to start streaming
            if result == dlg.DialogCode.Accepted:
                from PyQt6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self, 
                    f"Stream {stream_id} Settings Saved", 
                    f"Stream {stream_id} settings have been saved.\n\nWould you like to start streaming now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    print(f"🚀 User chose to start Stream {stream_id}")
                    self.toggle_stream(stream_id)
                    
        except Exception as e:
            print(f"❌ Error opening Stream {stream_id} settings dialog: {e}")
            import traceback
            traceback.print_exc()
    
    def toggle_stream2(self):
        """Toggle Stream2 state"""
        self.stream2_active = not self.stream2_active
        if self.stream2_active:
            print("Starting Stream2...")
            if hasattr(self, 'stream2AudioBtn'):
                self.stream2AudioBtn.setIcon(self.get_icon("Stop.png"))
        else:
            print("Stopping Stream2...")
            if hasattr(self, 'stream2AudioBtn'):
                self.stream2AudioBtn.setIcon(self.get_icon("Stream.png"))
        # Add your stream2 logic here
    
    def _save_stream_settings(self, stream_id: int, settings: dict):
        prefix = f'streaming.stream{stream_id}'
        for k, v in settings.items():
            app_config.set(f'{prefix}.{k}', v)
        app_config.save_settings()

    def _load_stream_settings(self, stream_id: int) -> dict:
        prefix = f'streaming.stream{stream_id}'
        
        # Get current settings
        settings = {
            'platform': app_config.get(f'{prefix}.platform', 'custom'),
            'url': app_config.get(f'{prefix}.url', ''),
            'key': app_config.get(f'{prefix}.key', ''),
            'width': app_config.get(f'{prefix}.width', 1920),
            'height': app_config.get(f'{prefix}.height', 1080),
            'fps': app_config.get(f'{prefix}.fps', 60),
            # Audio capture settings
            'capture_audio': app_config.get(f'{prefix}.capture_audio', False),
            'audio_device': app_config.get(f'{prefix}.audio_device', ''),
            # Advanced encoding and sync
            'video_preset': app_config.get(f'{prefix}.video_preset', 'veryfast'),
            'crf': app_config.get(f'{prefix}.crf', 20),
            'av_sync_delay_ms': int(app_config.get(f'{prefix}.av_sync_delay_ms', 50)),
            'bitrate_kbps': int(app_config.get(f'{prefix}.bitrate_kbps', 0) or 0),
            'use_av_master_clock': bool(app_config.get(f'{prefix}.use_av_master_clock', True)),
            # Background Music (BGM)
            'bgm_enabled': bool(app_config.get(f'{prefix}.bgm_enabled', False)),
            'bgm_path': app_config.get(f'{prefix}.bgm_path', ''),
            'bgm_playlist': app_config.get(f'{prefix}.bgm_playlist', []) or [],
            'bgm_loop': bool(app_config.get(f'{prefix}.bgm_loop', True)),
            'bgm_volume': int(app_config.get(f'{prefix}.bgm_volume', 50)),
        }
        
        # AUTO-FIX: Ensure adequate bitrate for YouTube streaming
        if settings['platform'] == 'YouTube Live':
            min_bitrate = self._get_recommended_bitrate(settings['width'], settings['height'], settings['fps'])
            if settings['bitrate_kbps'] < min_bitrate:
                print(f"⚠️ Stream {stream_id}: Bitrate too low ({settings['bitrate_kbps']} kbps)")
                print(f"🔧 Auto-adjusting to recommended bitrate: {min_bitrate} kbps")
                settings['bitrate_kbps'] = min_bitrate
                # Save the corrected bitrate
                app_config.set(f'{prefix}.bitrate_kbps', min_bitrate)
                app_config.save_settings()
        
        return settings
    
    def _get_recommended_bitrate(self, width: int, height: int, fps: int) -> int:
        """Get recommended bitrate for YouTube streaming based on resolution and FPS."""
        # YouTube recommended bitrates (kbps)
        if height >= 2160:  # 4K
            return 35000 if fps > 30 else 20000
        elif height >= 1440:  # 1440p
            return 16000 if fps > 30 else 9000
        elif height >= 1080:  # 1080p
            return 8000 if fps > 30 else 5000
        elif height >= 720:   # 720p
            return 5000 if fps > 30 else 3000
        else:  # 480p and below
            return 2500 if fps > 30 else 1500
    
    def _apply_youtube_optimizations(self, settings: dict):
        """Apply YouTube-specific streaming optimizations to prevent buffering."""
        print("🎬 Applying YouTube streaming optimizations...")
        
        # Ensure keyframe interval is set correctly (2 seconds for YouTube)
        target_fps = settings.get('fps', 30)
        keyframe_interval = target_fps * 2  # 2 seconds
        settings['keyframe_interval'] = keyframe_interval
        
        # Use CBR (Constant Bitrate) for more stable streaming
        settings['rate_control'] = 'cbr'
        
        # Set buffer size to 2x bitrate for stable upload
        bitrate = settings.get('bitrate_kbps', 5000)
        settings['buffer_size'] = bitrate * 2
        
        # Use faster preset for real-time encoding
        if settings.get('video_preset') in ['slow', 'slower', 'veryslow']:
            settings['video_preset'] = 'fast'
            print("🔧 Changed encoding preset to 'fast' for better real-time performance")
        
        # Enable low-latency optimizations
        settings['tune'] = 'zerolatency'
        settings['threads'] = 0  # Auto-detect CPU cores
        
        print(f"✅ YouTube optimizations applied:")
        print(f"  📊 Bitrate: {bitrate} kbps")
        print(f"  🎯 Keyframe interval: {keyframe_interval} frames ({keyframe_interval/target_fps:.1f}s)")
        print(f"  ⚡ Preset: {settings.get('video_preset')}")
        print(f"  📦 Buffer size: {settings.get('buffer_size')} kb")
    
    def _show_streaming_health_info(self, stream_id: int, settings: dict):
        """Display streaming health information to help diagnose issues."""
        print(f"\n📊 Stream {stream_id} Health Check:")
        print("=" * 50)
        
        # Resolution and quality info
        width = settings.get('width', 1920)
        height = settings.get('height', 1080)
        fps = settings.get('fps', 30)
        bitrate = settings.get('bitrate_kbps', 5000)
        
        print(f"📺 Resolution: {width}x{height} @ {fps}fps")
        print(f"📊 Bitrate: {bitrate} kbps")
        
        # Check if bitrate is adequate
        recommended = self._get_recommended_bitrate(width, height, fps)
        if bitrate >= recommended:
            print(f"✅ Bitrate is adequate (recommended: {recommended} kbps)")
        else:
            print(f"⚠️ Bitrate may be too low (recommended: {recommended} kbps)")
            print(f"💡 Consider increasing bitrate in stream settings")
        
        # Platform-specific tips
        platform = settings.get('platform', 'Custom')
        print(f"🎬 Platform: {platform}")
        
        if platform == 'YouTube Live':
            print("💡 YouTube Tips:")
            print("   • Use CBR (Constant Bitrate) for stable streaming")
            print("   • Keyframe interval should be 2 seconds")
            print("   • Upload speed should be 1.5x your bitrate")
            print(f"   • Recommended upload speed: {int(bitrate * 1.5 / 1000)} Mbps")
        
        print("=" * 50)

    def _provide_stream_frame(self, size: QSize, direct_passthrough: bool = False) -> QImage:
        """Render the current program output at desired size for streaming.
        
        PIXELATION FIX: This method now renders at the exact requested size
        to prevent upscaling artifacts when mirroring to external displays.
        
        Args:
            size: Target size of the output frame (CRITICAL: render at this exact size)
            direct_passthrough: If True, bypass all effects and return raw input/media source
        """
        # Debug frame provider calls (only log first few calls to avoid spam)
        if not hasattr(self, '_frame_provider_call_count'):
            self._frame_provider_call_count = 0
        self._frame_provider_call_count += 1
        
        if self._frame_provider_call_count <= 5 or self._frame_provider_call_count % 100 == 0:
            print(f"🎬 Frame provider called #{self._frame_provider_call_count}, size: {size.width()}x{size.height()}")
        
        if self._graphics_output is None:
            if self._frame_provider_call_count <= 3:
                print("⚠️ Graphics output is None, returning black frame")
            # Return a black frame if no graphics output
            img = QImage(size, QImage.Format.Format_RGBA8888)
            img.fill(0)  # Black
            return img
        
        try:
            # Force graphics refresh during recording
            if hasattr(self, 'recording') and self.recording and hasattr(self._graphics_output, 'update'):
                self._graphics_output.update()
            
            # PIXELATION FIX: Set the graphics output to render at the exact target size
            # This prevents upscaling artifacts by rendering directly at external display resolution
            if hasattr(self._graphics_output, 'set_preview_render_size'):
                self._graphics_output.set_preview_render_size(size)
            
            # Prefer explicit request, otherwise honor global passthrough flag
            if direct_passthrough or getattr(self, 'passthrough_enabled', False):
                # Get the current active source directly without any effects
                current_source = self._graphics_output.get_current_source()
                if current_source and current_source['type'] == 'media':
                    # For media, get the current frame from the media player
                    media_index = current_source['index']
                    media_player = self.media_players.get(media_index)
                    if media_player and media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                        # Get the video frame from the video sink if available
                        video_sink = self.media_sinks.get(media_index)
                        if video_sink and hasattr(video_sink, 'videoFrame'):
                            frame = video_sink.videoFrame()
                            if not frame.isValid():
                                return QImage(size, QImage.Format.Format_RGBA8888)
                            # PIXELATION FIX: Always use SmoothTransformation
                            return frame.toImage().scaled(size, Qt.AspectRatioMode.KeepAspectRatio, 
                                                       Qt.TransformationMode.SmoothTransformation)
                
                # For camera or no valid media, get the current source frame
                frame = self._graphics_output.render_source_only(size)
            else:
                # Normal mode with all effects applied - render at exact target size
                frame = self._graphics_output.render_to_image(size)
            
            if frame.isNull():
                if self._frame_provider_call_count <= 3:
                    print("⚠️ Graphics output returned null frame, using black frame")
                # Fallback to black frame
                frame = QImage(size, QImage.Format.Format_RGBA8888)
                frame.fill(0)
                
            return frame
            
        except Exception as e:
            print(f"Error rendering stream frame: {e}")
            import traceback
            traceback.print_exc()
            # Return black frame on error
            img = QImage(size, QImage.Format.Format_RGBA8888)
            img.fill(0)
            return img
    
    def toggle_audio_monitor(self):
        """Toggle audio monitor mute"""
        self.audio_monitor_muted = not self.audio_monitor_muted
        if self.audio_monitor_muted:
            print("Muting audio monitor...")
        else:
            print("Unmuting audio monitor...")
        # Add your audio monitor logic here

    def action_clear_visuals(self):
        """Clear overlay/effects and hide any text overlay (non-destructive to state)."""
        try:
            if hasattr(self, '_graphics_output') and self._graphics_output is not None:
                self._graphics_output.clear_overlay()
                # Hide text overlay immediately
                self._graphics_output.set_text_overlay({'visible': False, 'text': ''})
            # Sync mini UI if present
            try:
                if hasattr(self, 'textOverlayMini') and self.textOverlayMini:
                    self.textOverlayMini.props_ref.apply_props({'visible': False, 'text': ''}, emit=True)
                    if hasattr(self.textOverlayMini, 'chk_visible'):
                        self.textOverlayMini.chk_visible.setChecked(False)
            except Exception:
                pass
            print("Visuals cleared (overlay and text hidden)")
        except Exception as e:
            print(f"Error clearing visuals: {e}")

    def action_toggle_passthrough(self, enabled: bool):
        """Toggle direct passthrough mode (bypass effects/overlays in rendering path)."""
        try:
            self.passthrough_enabled = bool(enabled)
            # Update menu check if exists
            try:
                if hasattr(self, '_tools_menu_act_pass'):
                    self._tools_menu_act_pass.setChecked(self.passthrough_enabled)
            except Exception:
                pass
            # Force preview refresh to reflect change immediately
            try:
                self.refresh_output_preview()
            except Exception:
                pass
            print(f"Direct Passthrough {'enabled' if self.passthrough_enabled else 'disabled'}")
        except Exception as e:
            print(f"Error toggling passthrough: {e}")

    def _apply_controls_lock_state(self):
        """Enable/disable key interactive controls based on controls_locked."""
        try:
            lock = bool(getattr(self, 'controls_locked', False))
            widgets = []
            # Recording controls
            for n in ('settingsRecordButton','recordRedCircle','playButton','captureButton'):
                if hasattr(self, n): widgets.append(getattr(self, n))
            # Stream controls
            for n in ('stream1SettingsBtn','stream1AudioBtn','stream2SettingsBtn','stream2AudioBtn'):
                if hasattr(self, n): widgets.append(getattr(self, n))
            # Input audio and settings
            for n in ('input1AudioButton','input2AudioButton','input3AudioButton','input1SettingsButton','input2SettingsButton','input3SettingsButton'):
                if hasattr(self, n): widgets.append(getattr(self, n))
            # Media audio/settings/play
            for n in ('media1AudioButton','media2AudioButton','media3AudioButton','media1SettingsButton','media2SettingsButton','media3SettingsButton','pushButton_19','pushButton_20','pushButton_21'):
                if hasattr(self, n): widgets.append(getattr(self, n))
            # Global audio mute button
            if hasattr(self, 'audioTopButton'): widgets.append(self.audioTopButton)
            # Tools button itself remains enabled to unlock
            for w in widgets:
                try:
                    w.setEnabled(not lock)
                except Exception:
                    pass
        except Exception:
            pass

    def action_toggle_controls_lock(self, enabled: bool):
        """Toggle UI lock to prevent accidental clicks on critical controls."""
        try:
            self.controls_locked = bool(enabled)
            # Update menu check if exists
            try:
                if hasattr(self, '_tools_menu_act_lock'):
                    self._tools_menu_act_lock.setChecked(self.controls_locked)
            except Exception:
                pass
            self._apply_controls_lock_state()
            print(f"Controls {'locked' if self.controls_locked else 'unlocked'}")
        except Exception as e:
            print(f"Error toggling controls lock: {e}")
    
    def get_renderer_info(self) -> dict:
        """Get information about the current renderer"""
        info = {
            'using_new_renderer': _USE_NEW_RENDERER,
            'renderer_type': 'Unknown',
            'gpu_accelerated': False,
            'performance': self._renderer_stats.copy()
        }
        
        if hasattr(self, '_graphics_output') and self._graphics_output:
            if _USE_NEW_RENDERER and hasattr(self._graphics_output, 'get_performance_info'):
                info.update(self._graphics_output.get_performance_info())
            else:
                info['renderer_type'] = 'CPU (Legacy)'
        
        return info
    
    def on_output_size_changed(self, text):
        """Handle output size change"""
        print(f"Output size changed to: {text}")
        try:
            if not hasattr(self, 'outputSizeComboBox'):
                return
            idx = self.outputSizeComboBox.currentIndex()
            if idx < 0:
                return
            data = self.outputSizeComboBox.itemData(idx)
            if not isinstance(data, dict):
                return
            w = int(data.get('width', 1920))
            h = int(data.get('height', 1080))
            fps = int(data.get('fps', 60))
            label = data.get('label', text)
            
            # Update FPS combo box to match the profile's FPS
            if hasattr(self, 'fpsComboBox'):
                self.fpsComboBox.blockSignals(True)
                if fps == 30:
                    self.fpsComboBox.setCurrentText("30 FPS")
                else:
                    self.fpsComboBox.setCurrentText("60 FPS")
                self.fpsComboBox.blockSignals(False)
            
            self._apply_output_profile(w, h, fps, label)
        except Exception as e:
            print(f"Output size apply error: {e}")

    def _apply_output_profile(self, width: int, height: int, fps: int, label: str):
        """Apply output profile to preview and running mirror; persist to config."""
        try:
            # Persist selection
            app_config.set('ui.output_width', int(width))
            app_config.set('ui.output_height', int(height))
            app_config.set('ui.preview_fps', int(fps))
            app_config.set('ui.output_profile_label', str(label or ''))
            app_config.save_settings()
        except Exception:
            pass
        # Update preview timer FPS
        try:
            if hasattr(self, '_graphics_output') and self._graphics_output is not None:
                self._graphics_output.set_target_fps(int(fps))
                # Compose preview at selected resolution for fidelity
                from PyQt6.QtCore import QSize as _QSize
                self._graphics_output.set_preview_render_size(_QSize(int(width), int(height)))
                # Force an immediate refresh so both video and text update right away
                try:
                    self.refresh_output_preview()
                except Exception:
                    pass
        except Exception:
            pass
        # Live-update external display mirror if running
        try:
            if hasattr(self, 'mirror_controller') and self.mirror_controller and self.mirror_controller.is_running():
                # For mirror, prefer full-screen maximize and matching FPS to avoid pixelation
                self.mirror_controller.update({'width': int(width), 'height': int(height), 'fps': int(fps), 'maximize': True})
        except Exception:
            pass
        print(f"Applied output profile: {label} -> {width}x{height} @ {fps}fps")

    def _populate_output_size_combo(self):
        """Populate Output Size combo with video standard, resolution, and fps options."""
        if not hasattr(self, 'outputSizeComboBox'):
            return
        cb = self.outputSizeComboBox
        cb.blockSignals(True)
        try:
            cb.clear()
            # Only quality presets
            profiles = [
                { 'label': '144p',  'width': 256, 'height': 144,  'fps': 60 },
                { 'label': '240p',  'width': 426, 'height': 240,  'fps': 60 },
                { 'label': '360p',  'width': 640, 'height': 360,  'fps': 60 },
                { 'label': '480p',  'width': 854, 'height': 480,  'fps': 60 },
                { 'label': '720p',  'width': 1280,'height': 720,  'fps': 60 },
                { 'label': '1080p', 'width': 1920,'height': 1080, 'fps': 60 },
            ]
            # Restore last selection if available
            last_label = app_config.get('ui.output_profile_label', '') or ''
            last_w = int(app_config.get('ui.output_width', 1920))
            last_h = int(app_config.get('ui.output_height', 1080))
            last_fps = int(app_config.get('ui.preview_fps', 60))
            select_index = -1
            for i, p in enumerate(profiles):
                label = p['label']
                cb.addItem(label, { **p, 'label': label })
                if select_index == -1:
                    if last_label and label == last_label:
                        select_index = i
                    elif (p['width'], p['height'], p['fps']) == (last_w, last_h, last_fps):
                        select_index = i
            if select_index >= 0:
                cb.setCurrentIndex(select_index)
                data = cb.itemData(select_index)
                self._apply_output_profile(int(data['width']), int(data['height']), int(data['fps']), data['label'])
            else:
                # Default to 1080p
                idx = next((i for i,p in enumerate(profiles) if p['label'] == '1080p'), len(profiles) - 1)
                cb.setCurrentIndex(idx)
                data = cb.itemData(idx)
                self._apply_output_profile(int(data['width']), int(data['height']), int(data['fps']), data['label'])
        finally:
            cb.blockSignals(False)
    
    def on_fps_changed(self, text):
        """Handle FPS change with global FPS controller integration"""
        print(f"FPS changed to: {text}")
        try:
            # Extract FPS value from text (e.g., "30 FPS" -> 30)
            fps_value = 60  # default
            if "30" in text:
                fps_value = 30
            elif "60" in text:
                fps_value = 60
            
            # Update global FPS controller if available
            if FPS_CONTROLLER_AVAILABLE:
                set_global_fps(fps_value)
                print(f"Global FPS controller updated to {fps_value} FPS")
            
            # Update configuration
            app_config.set('ui.preview_fps', fps_value)
            app_config.save_settings()
            
            # Update current output profile if one is selected
            if hasattr(self, 'outputSizeComboBox'):
                idx = self.outputSizeComboBox.currentIndex()
                if idx >= 0:
                    data = self.outputSizeComboBox.itemData(idx)
                    if isinstance(data, dict):
                        width = int(data.get('width', 1920))
                        height = int(data.get('height', 1080))
                        label = data.get('label', 'Custom')
                        self._apply_output_profile(width, height, fps_value, label)
            
            # Update streaming manager if available
            if FPS_CONTROLLER_AVAILABLE:
                streaming_manager = get_streaming_manager()
                # Restart any active streams with new FPS
                active_streams = streaming_manager.get_active_streams()
                for stream_url in active_streams:
                    print(f"Restarting stream {stream_url} with new FPS: {fps_value}")
            
            print(f"FPS updated to: {fps_value}")
        except Exception as e:
            print(f"FPS change error: {e}")

    def on_audio_output_changed(self, text):
        """Handle audio output change"""
        print(f"Audio output changed to: {text}")
        try:
            from PyQt6.QtMultimedia import QMediaDevices
            # Find matching output device by description
            target = None
            for dev in QMediaDevices.audioOutputs():
                if dev.description() == text:
                    target = dev
                    break
            if target is None:
                print("Selected audio output device not found; keeping current devices.")
                return
            # Apply to media audio outputs
            if hasattr(self, 'media_audio_outputs'):
                for i in (1, 2, 3):
                    ao = self.media_audio_outputs.get(i)
                    if ao:
                        try:
                            ao.setDevice(target)
                        except Exception:
                            pass
            # Recreate input audio sinks with the new device for monitoring
            if hasattr(self, 'input_audio_sinks') and hasattr(self, 'input_audio_sources'):
                active_inputs = []
                for i, sink in list(self.input_audio_sinks.items()):
                    # Determine if this input should remain active
                    is_active = getattr(self, f"input{i}_audio_muted", True) is False and getattr(self, 'current_output', (None,None)) == ('input', i)
                    # Stop existing
                    try:
                        self._stop_input_audio(i)
                    except Exception:
                        pass
                    if is_active:
                        # Recreate with new sink device
                        try:
                            # Ensure structures exist
                            from PyQt6.QtMultimedia import QAudioSource, QAudioSink, QMediaDevices
                            input_dev = QMediaDevices.defaultAudioInput()
                            source = QAudioSource(input_dev)
                            sink = QAudioSink(target)
                            self.input_audio_sources[i] = source
                            self.input_audio_sinks[i] = sink
                            out_dev = sink.start()
                            in_dev = source.start()
                            from PyQt6.QtCore import QTimer
                            t = QTimer(self)
                            t.setInterval(10)
                            def pump():
                                try:
                                    data = in_dev.read(4096)
                                    if data:
                                        out_dev.write(data)
                                except Exception:
                                    pass
                            t.timeout.connect(pump)
                            t.start()
                            if not hasattr(self, 'input_audio_timers'):
                                self.input_audio_timers = {}
                            self.input_audio_timers[i] = t
                        except Exception:
                            pass
        except Exception as e:
            print(f"Error applying audio output device: {e}")

    def _populate_audio_outputs_combo(self):
        """Populate the audioOutputComboBox with system output devices, selecting default."""
        if not hasattr(self, 'audioOutputComboBox'):
            return
        try:
            from PyQt6.QtMultimedia import QMediaDevices
            combo = self.audioOutputComboBox
            combo.blockSignals(True)
            combo.clear()
            default_desc = QMediaDevices.defaultAudioOutput().description() if QMediaDevices.defaultAudioOutput() else ''
            for dev in QMediaDevices.audioOutputs():
                combo.addItem(dev.description())
            # Select default device if present
            if default_desc:
                idx = combo.findText(default_desc)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        except Exception as e:
            print(f"Error populating audio outputs: {e}")
    
    def update_record_status(self, status_text, color):
        """Update the record status text and color"""
        try:
            if hasattr(self, 'recordStatusText'):
                self.recordStatusText.setText(status_text)
                self.recordStatusText.setStyleSheet(f"color: {color};")
            else:
                print(f"Record status update: {status_text}")
        except AttributeError:
            print(f"Record status update: {status_text}")

    def _on_stream_status_changed(self, status: str):
        """Handle StreamController status updates and reflect them in the UI."""
        try:
            st = (status or '').lower()
            if 'started' in st:
                self.update_record_status("Streaming", "#00aa00")
            elif 'reconnecting' in st:
                self.update_record_status("Reconnecting...", "#ffaa00")
            elif 'error' in st:
                self.update_record_status("Stream Error", "#ff4444")
            else:
                # Stopped or unknown
                self.update_record_status("Ready", "#777777")
        except Exception as e:
            print(f"Status UI error: {e}")
    
    # Input panel methods
    def open_input1_settings(self):
        """Open Input-1 settings dialog"""
        print("Opening Input-1 settings...")
        # Add your input1 settings dialog here
    
    def toggle_input1_audio(self):
        """Toggle Input-1 audio mute"""
        self.input1_audio_muted = not self.input1_audio_muted
        if self.input1_audio_muted:
            print("Muting Input-1 audio...")
            if hasattr(self, 'input1AudioButton'):
                self.input1AudioButton.setIcon(self.get_icon("Mute.png"))
        else:
            print("Unmuting Input-1 audio...")
            if hasattr(self, 'input1AudioButton'):
                self.input1AudioButton.setIcon(self.get_icon("Volume.png"))
        # Add your input1 audio logic here
    
    def open_input2_settings(self):
        """Open Input-2 settings dialog"""
        print("Opening Input-2 settings...")
        # Add your input2 settings dialog here
    
    def toggle_input2_audio(self):
        """Toggle Input-2 audio mute"""
        self.input2_audio_muted = not self.input2_audio_muted
        if self.input2_audio_muted:
            print("Muting Input-2 audio...")
            if hasattr(self, 'input2AudioButton'):
                self.input2AudioButton.setIcon(self.get_icon("Mute.png"))
        else:
            print("Unmuting Input-2 audio...")
            if hasattr(self, 'input2AudioButton'):
                self.input2AudioButton.setIcon(self.get_icon("Volume.png"))
        # Add your input2 audio logic here
    
    def open_input3_settings(self):
        """Open Input 3 settings dialog"""
        print("Opening Input 3 settings...")
        # TODO: Implement input settings dialog
    
    def toggle_input3_audio(self):
        """Toggle input 3 audio mute state"""
        self.input3_audio_muted = not self.input3_audio_muted
        icon_name = "Mute.png" if self.input3_audio_muted else "Volume.png"
        if hasattr(self, 'input3AudioButton'):
            self.input3AudioButton.setIcon(self.get_icon(icon_name))
        print(f"Input 3 audio {'muted' if self.input3_audio_muted else 'unmuted'}")
    
    def open_media1_settings(self):
        """Open Media 1 settings dialog"""
        print("Opening Media 1 settings...")
        # TODO: Implement media settings dialog
    
    def toggle_media1_audio(self):
        """Toggle media 1 audio mute state"""
        self.media1_audio_muted = not self.media1_audio_muted
        icon_name = "Mute.png" if self.media1_audio_muted else "Volume.png"
        if hasattr(self, 'media1AudioButton'):
            self.media1AudioButton.setIcon(self.get_icon(icon_name))
        print(f"Media 1 audio {'muted' if self.media1_audio_muted else 'unmuted'}")
    
    def open_media2_settings(self):
        """Open Media 2 settings dialog"""
        print("Opening Media 2 settings...")
        # TODO: Implement media settings dialog
    
    def toggle_media2_audio(self):
        """Toggle media 2 audio mute state"""
        self.media2_audio_muted = not self.media2_audio_muted
        icon_name = "Mute.png" if self.media2_audio_muted else "Volume.png"
        if hasattr(self, 'media2AudioButton'):
            self.media2AudioButton.setIcon(self.get_icon(icon_name))
        print(f"Media 2 audio {'muted' if self.media2_audio_muted else 'unmuted'}")
    
    def open_media3_settings(self):
        """Open Media 3 settings dialog"""
        print("Opening Media 3 settings...")
        # TODO: Implement media settings dialog
    
    def toggle_media3_audio(self):
        """Toggle media 3 audio mute state"""
        self.media3_audio_muted = not self.media3_audio_muted
        icon_name = "Mute.png" if self.media3_audio_muted else "Volume.png"
        if hasattr(self, 'media3AudioButton'):
            self.media3AudioButton.setIcon(self.get_icon(icon_name))
        print(f"Media 3 audio {'muted' if self.media3_audio_muted else 'unmuted'}")

    def set_source_1A(self, source_name):
        """Set source for 1A output"""
        self.current_1A_source = source_name
        print(f"1A source set to: {source_name}")
        # TODO: Implement actual source switching logic
    
    def set_source_2B(self, source_name):
        """Set source for 2B output"""
        self.current_2B_source = source_name
        print(f"2B source set to: {source_name}")
        # TODO: Implement actual source switching logic
    
    def apply_transition(self, transition_id):
        """Apply transition effect"""
        print(f"Applying transition {transition_id}")
        # TODO: Implement transition effects
        
    # ===== Enhanced Dialog Methods =====
    
    def show_camera_selection_dialog(self, input_number: int):
        """Show enhanced camera settings dialog with real-time updates."""
        try:
            print(f"📹 Opening Input {input_number} settings dialog...")
            from input_settings_dialog import InputSettingsDialog
            from camera_processor import camera_processors
            
            dialog = InputSettingsDialog(self, input_number)
            print(f"✅ Input {input_number} settings dialog created successfully")
            
            # Load existing settings if any
            current_settings = camera_processors[input_number].get_current_settings()
            if current_settings:
                dialog.load_current_settings(current_settings)
                print(f"📝 Loaded existing settings for Input {input_number}")
            
            # Connect real-time updates and camera selection
            dialog.settingsChanged.connect(lambda settings: self._on_camera_settings_changed(input_number, settings))
            dialog.camera_combo.currentIndexChanged.connect(lambda: self._on_camera_selected_in_dialog(input_number, dialog))
            
            # Show dialog (no need to check result since updates are real-time)
            result = dialog.exec()
            print(f"📝 Input {input_number} settings dialog closed with result: {result}")
            
        except Exception as e:
            print(f"❌ Error opening Input {input_number} settings dialog: {e}")
            import traceback
            traceback.print_exc()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to open camera settings: {str(e)}")
    
    def _on_camera_settings_changed(self, input_number: int, settings: dict):
        """Handle real-time camera settings changes."""
        try:
            from camera_processor import camera_processors
            
            # Apply settings to processor
            camera_processors[input_number].update_settings(settings)
            
            # Force refresh of current frame if this input is active
            if hasattr(self, 'current_output') and self.current_output == ('input', input_number):
                if input_number in getattr(self, 'last_input_image', {}):
                    # Re-process and display the last frame with new settings
                    original_img = self.last_input_image[input_number]
                    if camera_processors[input_number].is_enabled():
                        processed_img = camera_processors[input_number].process_frame(original_img)
                        if processed_img:
                            self._set_output_image(processed_img)
            
            print(f"🎨 Real-time camera settings applied to Input {input_number}")
            
        except Exception as e:
            print(f"Error applying camera settings: {e}")
    
    def _on_camera_selected_in_dialog(self, input_number: int, dialog):
        """Handle camera selection in dialog."""
        try:
            camera_device = dialog.camera_combo.currentData()
            if camera_device:  # Only start if a real camera is selected (not "Select Camera...")
                camera_info = {
                    'name': dialog.camera_combo.currentText(),
                    'index': 0,
                    'device': camera_device
                }
                self.start_camera_capture(camera_info, input_number)
                print(f"✅ Started camera capture for input {input_number}: {camera_info['name']}")
        except Exception as e:
            print(f"❌ Failed to start camera capture: {e}")
    
    def show_media_selection_dialog(self, media_number: int):
        """Show enhanced media file selection and settings dialog."""
        try:
            from media_settings_dialog import MediaSettingsDialog
            from media_processor import media_processors
            
            # Get current media path if any
            current_path = ""  # TODO: Get current media path from media player
            
            dialog = MediaSettingsDialog(self, media_number, current_path)
            if dialog.exec() == dialog.DialogCode.Accepted:
                settings = dialog.get_settings()
                
                # ✅ ACTUALLY APPLY THE MEDIA SETTINGS
                media_processors[media_number].update_settings(settings, current_path)
                
                # ✅ LOAD THE MEDIA FILE
                file_path = settings.get('file_path')
                if file_path:
                    try:
                        self.load_media(media_number, file_path)
                        print(f"✅ Loaded media file for media {media_number}: {file_path}")
                    except Exception as e:
                        print(f"❌ Failed to load media file: {e}")
                
                print(f"✅ Applied media settings for media {media_number}:", settings)
                
                # Show confirmation
                from PyQt6.QtWidgets import QMessageBox
                effects_list = []
                if settings.get('file_path'):
                    effects_list.append(f"File: {settings['file_path'].split('/')[-1]}")
                if settings.get('speed', 1.0) != 1.0:
                    effects_list.append(f"Speed: {settings['speed']}x")
                if settings.get('scale_mode', 'Fit (Maintain Aspect)') != 'Fit (Maintain Aspect)':
                    effects_list.append(f"Scale: {settings['scale_mode']}")
                if settings.get('brightness', 0) != 0:
                    effects_list.append(f"Brightness: {settings['brightness']:+d}")
                if settings.get('contrast', 0) != 0:
                    effects_list.append(f"Contrast: {settings['contrast']:+d}")
                if settings.get('flip_horizontal', False):
                    effects_list.append("Horizontal Flip")
                
                # Removed confirmation dialog - settings applied silently
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to open media settings: {str(e)}")
    
    def show_text_overlay_settings(self):
        """Show enhanced text overlay settings dialog."""
        try:
            from text_overlay_settings_dialog import TextOverlaySettingsDialog
            from text_overlay_renderer import text_overlay_renderer
            
            dialog = TextOverlaySettingsDialog(self)
            if dialog.exec() == dialog.DialogCode.Accepted:
                settings = dialog.get_settings()
                print("Applied text overlay settings:", settings)
                
                # ✅ ACTUALLY APPLY THE SETTINGS
                text_overlay_renderer.update_settings(settings)
                
                # Refresh output preview to show the overlay
                self.refresh_output_preview()
                
                # Show confirmation
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Text Overlay", 
                    f"✅ Text overlay applied!\n\nText: '{settings.get('text', '')[:50]}{'...' if len(settings.get('text', '')) > 50 else ''}'")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to open text overlay settings: {str(e)}")

def main():
    """Main application entry point"""
    # Enable high DPI scaling; on Qt6 AA_UseHighDpiPixmaps may not exist, so guard it
    from PyQt6.QtGui import QGuiApplication
    try:
        attr = getattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps', None)
        if attr is not None:
            QGuiApplication.setAttribute(attr, True)
    except Exception:
        pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    # Provide a safe substitution for missing Monospace fonts to silence alias warning
    try:
        QFont.insertSubstitution("Monospace", "Menlo")
    except Exception:
        pass
    app.setApplicationName("GoLive Studio")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("GoLive Studio")
    
    # Set application style for better cross-platform appearance
    app.setStyle('Fusion')
    
    # Create and show main window
    window = GoLiveStudio()
    window.show()
    # Ensure background processes are stopped before app quits
    try:
        app.aboutToQuit.connect(window.cleanup_on_exit)
    except Exception:
        pass
    
    # Start event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
