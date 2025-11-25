"""
Enhanced Graphics Output Widget - Fixes Pixelation Issues
Replaces the original graphics_output.py with hardware-accelerated rendering
that maintains full resolution for external display mirroring.

Key Improvements:
1. Always renders at target resolution (no upscaling artifacts)
2. Uses QOpenGLWidget for hardware acceleration
3. Proper Qt.SmoothTransformation for all scaling operations
4. Overlays and text rendered at full resolution
5. Optimized for external display mirroring
"""

from __future__ import annotations
from typing import Optional, Tuple, Dict, Any
from PyQt6.QtWidgets import QFrame, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QFont, QPainterPath, QPen
from PyQt6.QtCore import Qt, QRectF, QSize, QTimer, QElapsedTimer
import os
import json
import math
import numpy as np

# Import FPS controller for global timing
try:
    from fps_controller import get_fps_controller, FrameTimestamp
    FPS_CONTROLLER_AVAILABLE = True
except ImportError:
    FPS_CONTROLLER_AVAILABLE = False
    print("FPS Controller not available, using fallback timing")

# Import performance optimizer
try:
    from performance_optimizer import get_performance_optimizer
    PERFORMANCE_OPTIMIZER_AVAILABLE = True
except ImportError:
    PERFORMANCE_OPTIMIZER_AVAILABLE = False
    print("Performance Optimizer not available")


class EnhancedGraphicsOutputWidget(QOpenGLWidget):
    """
    Hardware-accelerated graphics output widget that fixes pixelation issues.
    
    PIXELATION FIXES:
    - Always renders at target resolution (no upscaling)
    - Uses GPU acceleration via QOpenGLWidget
    - All scaling uses Qt.SmoothTransformation
    - Overlays rendered at full resolution
    - Text rendered at native resolution
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Enable hardware acceleration and high-quality rendering
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        
        # FPS Controller integration
        self.fps_controller = None
        self.source_id = f"graphics_output_{id(self)}"
        if FPS_CONTROLLER_AVAILABLE:
            self.fps_controller = get_fps_controller()
            self.fps_controller.register_input_source(self.source_id)
            self.fps_controller.fps_changed.connect(self._on_fps_changed)
        
        # Track current source for direct passthrough
        self._current_source = {'type': None, 'index': -1}
        
        # Frame data
        self._last_frame: Optional[QImage] = None
        self._overlay_image: Optional[QImage] = None
        self._overlay_path: Optional[str] = None
        self._opening_norm: Optional[Tuple[float, float, float, float]] = None
        
        # Transition system for smooth effect changes
        self._transition_active = False
        self._transition_timer = QTimer(self)
        self._transition_timer.timeout.connect(self._update_transition)
        self._transition_duration_ms = 400  # 400ms fade duration - faster, less noticeable
        self._transition_start_time = 0
        self._transition_old_overlay: Optional[QImage] = None
        self._transition_new_overlay: Optional[QImage] = None
        self._transition_old_opening: Optional[Tuple[float, float, float, float]] = None
        self._transition_new_opening: Optional[Tuple[float, float, float, float]] = None
        self._transition_new_path: Optional[str] = None
        self._transition_progress = 0.0  # 0.0 = old overlay, 1.0 = new overlay
        
        # Rendering settings
        self._overscan = 1.03
        self._target_fps = 60 if not self.fps_controller else self.fps_controller.get_target_fps()
        self._target_interval_ms = int(1000.0 / self._target_fps)  # Convert to milliseconds
        
        # Cache for masks to avoid recomputation (limited size for memory optimization)
        self._mask_cache: Dict[Tuple[int, int, int], QImage] = {}
        self._max_cache_size = 10  # Limit cache size to reduce memory usage
        
        # Performance optimizer integration
        self.performance_optimizer = None
        if PERFORMANCE_OPTIMIZER_AVAILABLE:
            self.performance_optimizer = get_performance_optimizer()
            self.performance_optimizer.performance_updated.connect(self._on_performance_update)
        
        # Memory management
        self._frame_count = 0
        self._memory_cleanup_interval = 100  # Cleanup every 100 frames
        self._offscreen: Optional[QImage] = None
        
        # Text overlay properties
        self._text_props: Dict[str, Any] = {
            'visible': False,
            'text': '',
            'font_size': 36,
            'font_family': '',
            'color': QColor(255, 255, 255, 255),
            'stroke_color': QColor(0, 0, 0, 255),
            'stroke_width': 3,
            'bg_enabled': False,
            'bg_color': QColor(0, 0, 0, 160),
            'pos_x': 50,
            'pos_y': 90,
            'anchor': 'center',
            'scroll': False,
            'scroll_speed': 50,
        }
        
        # Scrolling text state
        self._scroll_px: float = 0.0
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(16)  # 60fps for smooth scrolling
        self._scroll_timer.timeout.connect(self._on_scroll_tick)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        
        # Update timer for frame rendering
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self.update)
        
        # CRITICAL FIX: Always render at target resolution to prevent pixelation
        self._render_output_size: Optional[QSize] = None
        
        print("Enhanced Graphics Output Widget initialized with hardware acceleration")
    
    def get_current_source(self) -> Dict[str, Any]:
        """Get the currently active source information."""
        return self._current_source
    
    def set_preview_render_size(self, size: Optional[QSize]):
        """
        PIXELATION FIX: Set target render size for high-quality output.
        This ensures we always render at the target resolution instead of upscaling.
        """
        if size is not None and (not isinstance(size, QSize) or not size.isValid()):
            size = None
        self._render_output_size = size
        self.update()
    
    def set_frame(self, frame: Optional[QImage]):
        """Set the current video frame with FPS controller integration."""
        self._last_frame = frame
        
        # CRITICAL FIX: Always update display during transitions to prevent video freezing
        if self._transition_active:
            # During transitions, immediately update to show the new frame
            # Skip FPS controller processing to avoid conversion issues
            self._update_display()
            return
        
        # Process frame through FPS controller if available (only when not transitioning)
        if self.fps_controller and frame is not None and not self._transition_active:
            try:
                # Convert QImage to numpy array for processing
                frame_array = self._qimage_to_numpy(frame)
                if frame_array.size > 0:  # Only process if conversion was successful
                    timestamped_frame = self.fps_controller.process_input_frame(self.source_id, frame_array)
                    
                    if timestamped_frame:
                        # Frame was accepted by FPS controller, update display
                        self._update_display()
                        return
            except Exception as e:
                # Silently handle FPS controller errors to avoid spam
                pass
        
        # Fallback: direct update or throttled updates
        if self._transition_active:
            # During transitions, update immediately
            self._update_display()
        else:
            # Normal operation: throttle updates to target FPS
            if not self._update_timer.isActive():
                self._update_timer.start(self._target_interval_ms)
    
    def _qimage_to_numpy(self, qimage: QImage) -> np.ndarray:
        """Convert QImage to numpy array with memory optimization"""
        try:
            if qimage.isNull() or qimage.width() == 0 or qimage.height() == 0:
                return np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Convert to RGB format if needed
            if qimage.format() != QImage.Format.Format_RGB888:
                qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
            
            # Get image dimensions
            width = qimage.width()
            height = qimage.height()
            
            # Get the raw data
            ptr = qimage.constBits()
            if ptr is None:
                return np.zeros((height, width, 3), dtype=np.uint8)
            
            # Calculate expected size
            expected_size = height * width * 3
            
            # Convert to numpy array with proper size checking
            buffer = ptr.asarray(expected_size)
            if len(buffer) != expected_size:
                return np.zeros((height, width, 3), dtype=np.uint8)
            
            # Use view instead of copy for memory efficiency
            arr = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 3)
            
            # Only copy if we need to modify the array
            return arr  # Return view for memory efficiency
        except Exception as e:
            # Return a properly sized fallback array
            return np.zeros((480, 640, 3), dtype=np.uint8)
    
    def _update_display(self):
        """Update the display immediately with performance tracking"""
        start_time = time.time()
        
        # Increment frame count and perform periodic cleanup
        self._frame_count += 1
        if self._frame_count % self._memory_cleanup_interval == 0:
            self._cleanup_memory()
        
        self.update()
        
        # Record frame latency for performance optimization
        if self.performance_optimizer:
            latency_ms = (time.time() - start_time) * 1000
            self.performance_optimizer.record_frame_latency(latency_ms)
    
    def _cleanup_memory(self):
        """Periodic memory cleanup to prevent memory leaks"""
        # Limit mask cache size
        if len(self._mask_cache) > self._max_cache_size:
            # Remove oldest entries
            keys_to_remove = list(self._mask_cache.keys())[:-self._max_cache_size//2]
            for key in keys_to_remove:
                del self._mask_cache[key]
        
        # Force garbage collection periodically
        if self._frame_count % (self._memory_cleanup_interval * 5) == 0:
            import gc
            gc.collect()
    
    def _on_performance_update(self, metrics: dict):
        """Handle performance updates from optimizer"""
        # Adjust rendering quality based on performance
        if not metrics.get('memory_target_met', True):
            # Reduce cache size if memory target not met
            self._max_cache_size = max(5, self._max_cache_size - 1)
        elif metrics.get('memory_target_met', False) and self._max_cache_size < 10:
            # Increase cache size if memory is good
            self._max_cache_size = min(10, self._max_cache_size + 1)
    
    def _on_fps_changed(self, new_fps: int):
        """Handle FPS change from global controller"""
        self._target_fps = new_fps
        self._target_interval_ms = int(1000.0 / new_fps)
        print(f"Graphics output FPS updated to {new_fps}fps (interval: {self._target_interval_ms}ms)")
    
    def set_overlay_from_path(self, path: Optional[str], use_transition: bool = True):
        """Set overlay from image path with smooth transition."""
        # If no transition requested or no current overlay, apply immediately
        if not use_transition or self._overlay_image is None:
            self._set_overlay_immediate(path)
            return
        
        # Start smooth transition
        self._start_overlay_transition(path)
    
    def _set_overlay_immediate(self, path: Optional[str]):
        """Set overlay immediately without transition."""
        if not path:
            self._overlay_image = None
            self._overlay_path = None
            self._opening_norm = None
            self._mask_cache.clear()
            self.update()
            return
        
        # Load overlay with high quality
        img = QImage(path)
        if img.isNull():
            return
        
        # Convert to high-quality format if needed
        if img.format() != QImage.Format.Format_ARGB32_Premultiplied:
            img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        
        self._overlay_image = img
        self._overlay_path = path
        
        # Detect opening area for masking
        opening = self._load_opening_override(path)
        if opening is None:
            opening = self._detect_opening_from_mask(path)
        if opening is None:
            opening = self._detect_opening_norm(img)
        self._opening_norm = opening
        
        # Clear mask cache for new overlay
        self._mask_cache.clear()
        self.update()
    
    def _start_overlay_transition(self, new_path: Optional[str]):
        """Start a smooth transition to a new overlay."""
        # Stop any existing transition
        if self._transition_active:
            self._transition_timer.stop()
            self._transition_active = False
        
        # Store current overlay as the "old" overlay
        self._transition_old_overlay = self._overlay_image
        self._transition_old_opening = self._opening_norm
        
        # Store new path
        self._transition_new_path = new_path
        
        # Load new overlay
        if new_path:
            img = QImage(new_path)
            if img.isNull():
                return
            
            # Convert to high-quality format if needed
            if img.format() != QImage.Format.Format_ARGB32_Premultiplied:
                img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            
            self._transition_new_overlay = img
            
            # Detect opening area for new overlay
            opening = self._load_opening_override(new_path)
            if opening is None:
                opening = self._detect_opening_from_mask(new_path)
            if opening is None:
                opening = self._detect_opening_norm(img)
            self._transition_new_opening = opening
        else:
            self._transition_new_overlay = None
            self._transition_new_opening = None
        
        # Start transition
        self._transition_active = True
        self._transition_progress = 0.0
        self._transition_start_time = self._elapsed.elapsed()
        
        # Disable FPS controller processing during transition for smoother video
        if hasattr(self, 'fps_controller') and self.fps_controller:
            try:
                self.fps_controller.unregister_input_source(self.source_id)
            except:
                pass
        
        # Use a slower timer to avoid conflicts with video updates
        self._transition_timer.start(33)  # ~30fps for smooth animation, less aggressive
    
    def _update_transition(self):
        """Update the transition animation."""
        if not self._transition_active:
            return
        
        # Calculate progress (0.0 to 1.0)
        elapsed = self._elapsed.elapsed() - self._transition_start_time
        progress = min(1.0, elapsed / self._transition_duration_ms)
        
        # Apply easing function for smooth animation (ease-in-out)
        self._transition_progress = self._ease_in_out(progress)
        
        # CRITICAL FIX: Force immediate repaint during transitions to ensure video continues
        # This ensures the video doesn't freeze during effect transitions
        self.update()
        
        # Check if transition is complete
        if progress >= 1.0:
            self._finish_transition()
    
    def _ease_in_out(self, t: float) -> float:
        """Smooth easing function for transitions."""
        return t * t * (3.0 - 2.0 * t)
    
    def _finish_transition(self):
        """Complete the transition and clean up."""
        self._transition_timer.stop()
        self._transition_active = False
        
        # Re-enable FPS controller processing after transition
        if hasattr(self, 'fps_controller') and self.fps_controller:
            try:
                self.fps_controller.register_input_source(self.source_id)
            except:
                pass
        
        # Apply the new overlay as the current overlay
        self._overlay_image = self._transition_new_overlay
        self._opening_norm = self._transition_new_opening
        self._overlay_path = self._transition_new_path
        
        # Clean up transition data
        self._transition_old_overlay = None
        self._transition_new_overlay = None
        self._transition_old_opening = None
        self._transition_new_opening = None
        self._transition_new_path = None
        self._transition_progress = 0.0
        
        # Clear mask cache for new overlay
        self._mask_cache.clear()
        self.update()
    
    def clear_overlay(self, use_transition: bool = True):
        """Clear the current overlay."""
        self.set_overlay_from_path(None, use_transition)
    
    def set_transition_duration(self, duration_ms: int):
        """Set the transition duration in milliseconds."""
        self._transition_duration_ms = max(100, min(3000, duration_ms))  # Clamp between 100ms and 3s
    
    def set_text_overlay(self, props: Dict[str, Any]):
        """Set text overlay properties."""
        if not isinstance(props, dict):
            return
        
        # Update properties
        self._text_props.update(props)
        
        # Convert color values if needed
        for color_key in ['color', 'stroke_color', 'bg_color']:
            if color_key in props:
                color_val = props[color_key]
                if isinstance(color_val, int):
                    # Convert RGBA int to QColor
                    a = (color_val >> 24) & 0xFF
                    b = (color_val >> 16) & 0xFF
                    g = (color_val >> 8) & 0xFF
                    r = color_val & 0xFF
                    self._text_props[color_key] = QColor(r, g, b, a)
        
        # Manage scrolling timer
        if props.get('scroll') and props.get('visible') and props.get('text'):
            if not self._scroll_timer.isActive():
                self._elapsed.restart()
                self._scroll_timer.start()
        else:
            self._scroll_timer.stop()
            self._scroll_px = 0.0
        
        self.update()
    
    def set_overscan(self, value: float):
        """Set overscan value for video scaling."""
        self._overscan = max(1.0, float(value))
        self.update()
    
    def set_target_fps(self, fps: int):
        """Set target rendering FPS to match camera FPS."""
        self._target_interval_ms = max(5, int(1000 / max(5, min(240, fps))))  # Support up to 240fps
        print(f"Graphics output FPS updated to {fps}fps (interval: {self._target_interval_ms}ms)")
    
    def paintGL(self):
        """
        MAIN RENDERING METHOD - Hardware accelerated with pixelation fixes.
        """
        # Get the target render size - this is CRITICAL for preventing pixelation
        render_size = self._get_effective_render_size()
        
        # Create or reuse high-quality offscreen output image
        if (
            self._offscreen is None
            or self._offscreen.size() != render_size
            or self._offscreen.format() != QImage.Format.Format_ARGB32_Premultiplied
        ):
            self._offscreen = QImage(render_size, QImage.Format.Format_ARGB32_Premultiplied)
        output = self._offscreen
        output.fill(QColor(0, 0, 0, 255))
        
        painter = QPainter(output)
        try:
            # Enable all high-quality rendering hints
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            
            # Render video layer
            self._render_video_layer(painter, render_size)
            
            # Render overlay layer
            self._render_overlay_layer(painter, render_size)
            
            # Render text layer
            self._render_text_layer(painter, render_size)
            
        finally:
            painter.end()
        
        # Display the rendered frame using QPainter on the widget
        # This is the correct way to draw on QOpenGLWidget
        widget_painter = QPainter(self)
        try:
            widget_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            
            # Scale to widget size if needed
            if render_size != self.size():
                display_img = output.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            else:
                display_img = output
            
            # Draw the final image
            widget_painter.drawImage(0, 0, display_img)
            
        finally:
            widget_painter.end()
    
    def _get_effective_render_size(self) -> QSize:
        """
        PIXELATION FIX: Always use the target render size if available.
        This prevents upscaling artifacts by rendering at native resolution.
        """
        if self._render_output_size and self._render_output_size.isValid():
            return self._render_output_size
        
        # Fallback to widget size
        size = self.size()
        if not size.isValid() or size.width() < 1 or size.height() < 1:
            return QSize(1920, 1080)  # Safe fallback
        
        return size
    
    def _render_video_layer(self, painter: QPainter, size: QSize):
        """
        PIXELATION FIX: Render video at target resolution with proper scaling and transition support.
        """
        if not self._last_frame or self._last_frame.isNull():
            return
        
        if self._transition_active:
            # Render video with transition between different masks/openings
            self._render_video_with_transition(painter, size)
        else:
            # Render video normally
            self._render_video_normal(painter, size)
    
    def _render_video_normal(self, painter: QPainter, size: QSize):
        """Render video normally without transitions."""
        # Calculate video placement
        video_rect = QRectF(0, 0, size.width(), size.height())
        
        # Apply opening mask if overlay is present
        if self._opening_norm and self._overlay_image:
            nx, ny, nw, nh = self._opening_norm
            # Scale opening to current render size
            video_rect = QRectF(
                nx * size.width(),
                ny * size.height(),
                nw * size.width(),
                nh * size.height()
            )
        
        # Scale video to cover the target area with overscan
        target_w = int(video_rect.width() * self._overscan)
        target_h = int(video_rect.height() * self._overscan)
        
        # CRITICAL: Use SmoothTransformation for high quality
        scaled_video = self._last_frame.scaled(
            QSize(target_w, target_h),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Center the scaled video in the target rect
        x = video_rect.x() + (video_rect.width() - scaled_video.width()) / 2
        y = video_rect.y() + (video_rect.height() - scaled_video.height()) / 2
        
        painter.drawImage(int(x), int(y), scaled_video)
        
        # Apply mask if needed
        if self._opening_norm and self._overlay_image:
            mask = self._build_opening_mask(size)
            if mask and not mask.isNull():
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(0, 0, mask)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    
    def _render_video_with_transition(self, painter: QPainter, size: QSize):
        """Render video during transition with blended masks - video continues playing smoothly."""
        # CRITICAL FIX: Ensure video continues playing during transitions
        # The key is to render the CURRENT video frame with both old and new effects
        
        if not self._last_frame or self._last_frame.isNull():
            return
        
        # Handle different transition scenarios
        
        # Scenario 1: Transitioning from overlay to overlay
        if self._transition_old_overlay and self._transition_new_overlay:
            self._render_overlay_to_overlay_transition(painter, size)
        
        # Scenario 2: Transitioning from overlay to no overlay (full screen)
        elif self._transition_old_overlay and self._transition_new_overlay is None:
            self._render_overlay_to_fullscreen_transition(painter, size)
        
        # Scenario 3: Transitioning from no overlay to overlay
        elif self._transition_old_overlay is None and self._transition_new_overlay:
            self._render_fullscreen_to_overlay_transition(painter, size)
        
        # Scenario 4: Fallback - render current video normally
        else:
            self._render_video_normal(painter, size)
    
    def _render_overlay_to_overlay_transition(self, painter: QPainter, size: QSize):
        """Transition between two overlays with different openings - video plays continuously."""
        painter.save()
        try:
            # Simple cross-fade approach - less complex, more reliable
            progress = self._transition_progress
            
            # Choose which opening to use based on progress
            if progress < 0.5:
                # First half: use old opening with decreasing opacity
                if self._transition_old_opening:
                    opacity = (1.0 - progress * 2.0)  # 1.0 -> 0.0
                    painter.setOpacity(opacity)
                    self._render_video_for_opening(painter, size, self._transition_old_opening)
            else:
                # Second half: use new opening with increasing opacity
                if self._transition_new_opening:
                    opacity = (progress - 0.5) * 2.0  # 0.0 -> 1.0
                    painter.setOpacity(opacity)
                    self._render_video_for_opening(painter, size, self._transition_new_opening)
                
        finally:
            painter.restore()
    
    def _render_overlay_to_fullscreen_transition(self, painter: QPainter, size: QSize):
        """Transition from overlay to full screen video - video plays continuously."""
        painter.save()
        try:
            # Simplified approach: render video with blended opening
            old_opacity = 1.0 - self._transition_progress
            new_opacity = self._transition_progress
            
            # Render video with old opening (fading out)
            if self._transition_old_opening and old_opacity > 0.0:
                painter.setOpacity(old_opacity)
                self._render_video_for_opening(painter, size, self._transition_old_opening)
            
            # Render full screen video (fading in)
            if new_opacity > 0.0:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
                painter.setOpacity(new_opacity)
                self._render_video_for_opening(painter, size, None)  # Full screen
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                
        finally:
            painter.restore()
    
    def _render_fullscreen_to_overlay_transition(self, painter: QPainter, size: QSize):
        """Transition from full screen to overlay video - video plays continuously."""
        painter.save()
        try:
            # Simplified approach: render video with blended opening
            old_opacity = 1.0 - self._transition_progress
            new_opacity = self._transition_progress
            
            # Render full screen video (fading out)
            if old_opacity > 0.0:
                painter.setOpacity(old_opacity)
                self._render_video_for_opening(painter, size, None)  # Full screen
            
            # Render video with new opening (fading in)
            if self._transition_new_opening and new_opacity > 0.0:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
                painter.setOpacity(new_opacity)
                self._render_video_for_opening(painter, size, self._transition_new_opening)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                
        finally:
            painter.restore()
    
    def _render_video_for_opening(self, painter: QPainter, size: QSize, opening_norm: Optional[Tuple[float, float, float, float]]):
        """Render video for a specific opening area."""
        # Calculate video placement
        if opening_norm:
            nx, ny, nw, nh = opening_norm
            video_rect = QRectF(
                nx * size.width(),
                ny * size.height(),
                nw * size.width(),
                nh * size.height()
            )
        else:
            # Full screen video
            video_rect = QRectF(0, 0, size.width(), size.height())
        
        # Scale video to cover the target area with overscan
        target_w = int(video_rect.width() * self._overscan)
        target_h = int(video_rect.height() * self._overscan)
        
        # CRITICAL: Use SmoothTransformation for high quality
        scaled_video = self._last_frame.scaled(
            QSize(target_w, target_h),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Center the scaled video in the target rect
        x = video_rect.x() + (video_rect.width() - scaled_video.width()) / 2
        y = video_rect.y() + (video_rect.height() - scaled_video.height()) / 2
        
        painter.drawImage(int(x), int(y), scaled_video)
        
        # Apply mask if opening is specified
        if opening_norm:
            mask = self._build_opening_mask_for_opening(size, opening_norm)
            if mask and not mask.isNull():
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(0, 0, mask)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    
    def _render_overlay_layer(self, painter: QPainter, size: QSize):
        """
        PIXELATION FIX: Render overlay at full resolution with smooth transitions.
        """
        if self._transition_active:
            # Render transition between old and new overlays
            self._render_transition_overlays(painter, size)
        elif self._overlay_image and not self._overlay_image.isNull():
            # Render single overlay
            self._render_single_overlay(painter, size, self._overlay_image)
    
    def _render_single_overlay(self, painter: QPainter, size: QSize, overlay_image: QImage):
        """Render a single overlay image."""
        # Scale overlay to fit the render size
        scaled_overlay = overlay_image.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Center the overlay
        x = (size.width() - scaled_overlay.width()) // 2
        y = (size.height() - scaled_overlay.height()) // 2
        
        painter.drawImage(x, y, scaled_overlay)
    
    def _render_transition_overlays(self, painter: QPainter, size: QSize):
        """Render overlays during transition with smooth blending."""
        # Save the current painter state
        painter.save()
        
        try:
            # Render old overlay with fading opacity
            if self._transition_old_overlay and not self._transition_old_overlay.isNull():
                old_opacity = 1.0 - self._transition_progress
                painter.setOpacity(old_opacity)
                self._render_single_overlay(painter, size, self._transition_old_overlay)
            
            # Render new overlay with increasing opacity
            if self._transition_new_overlay and not self._transition_new_overlay.isNull():
                new_opacity = self._transition_progress
                painter.setOpacity(new_opacity)
                self._render_single_overlay(painter, size, self._transition_new_overlay)
        
        finally:
            # Restore painter state
            painter.restore()
    
    def _render_text_layer(self, painter: QPainter, size: QSize):
        """
        PIXELATION FIX: Render text at native resolution to prevent blur.
        """
        if not self._text_props.get('visible') or not self._text_props.get('text'):
            return
        
        # Scale font size based on render resolution
        base_font_size = self._text_props.get('font_size', 36)
        scale_factor = size.height() / 1080.0  # Scale relative to 1080p
        scaled_font_size = max(8, int(base_font_size * scale_factor))
        
        # Setup font
        font = QFont()
        font.setPixelSize(scaled_font_size)
        font_family = self._text_props.get('font_family', '')
        if font_family:
            font.setFamily(font_family)
        
        # Create text path for precise rendering
        path = QPainterPath()
        path.addText(0, 0, font, self._text_props.get('text', ''))
        bounds = path.boundingRect()
        
        # Calculate position
        pos_x_pct = self._text_props.get('pos_x', 50)
        pos_y_pct = self._text_props.get('pos_y', 90)
        
        x = int(size.width() * pos_x_pct / 100.0)
        y = int(size.height() * pos_y_pct / 100.0)
        
        # Apply anchor
        anchor = self._text_props.get('anchor', 'center')
        if anchor == 'center':
            x -= int(bounds.width() / 2)
            y += int(bounds.height() / 2)
        elif anchor == 'right':
            x -= int(bounds.width())
            y += int(bounds.height() / 2)
        else:  # left
            y += int(bounds.height() / 2)
        
        # Apply scrolling
        if self._text_props.get('scroll', False):
            if self._scroll_px == 0.0:
                self._scroll_px = float(size.width())
            x = int(self._scroll_px)
            if x + bounds.width() < 0:
                self._scroll_px = float(size.width())
                x = int(self._scroll_px)
        
        # Draw background if enabled
        if self._text_props.get('bg_enabled', False):
            bg_color = self._text_props.get('bg_color', QColor(0, 0, 0, 160))
            if bg_color.alpha() > 0:
                stroke_width = self._text_props.get('stroke_width', 3)
                pad = max(4, int(stroke_width * scale_factor) + 4)
                bg_rect = QRectF(
                    x - pad,
                    y - bounds.height() - pad,
                    bounds.width() + 2 * pad,
                    bounds.height() + 2 * pad
                )
                painter.fillRect(bg_rect, bg_color)
        
        # Draw text with stroke
        painter.translate(x - bounds.left(), y - bounds.bottom())
        
        # Draw stroke
        stroke_width = self._text_props.get('stroke_width', 3)
        if stroke_width > 0:
            stroke_color = self._text_props.get('stroke_color', QColor(0, 0, 0, 255))
            if stroke_color.alpha() > 0:
                pen = QPen(stroke_color)
                pen.setWidth(max(1, int(stroke_width * scale_factor)))
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
        
        # Draw text fill
        text_color = self._text_props.get('color', QColor(255, 255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(text_color)
        painter.drawPath(path)
        
        painter.resetTransform()
    
    def render_to_image(self, size: QSize) -> QImage:
        """
        PIXELATION FIX: Export at exact target size without scaling artifacts.
        """
        if not size.isValid():
            size = QSize(1920, 1080)
        
        # Create high-quality output image
        output = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        output.fill(QColor(0, 0, 0, 255))
        
        painter = QPainter(output)
        try:
            # Enable all quality hints
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            
            # Render all layers at target size
            self._render_video_layer(painter, size)
            self._render_overlay_layer(painter, size)
            self._render_text_layer(painter, size)
            
        finally:
            painter.end()
        
        return output
    
    def render_source_only(self, size: QSize) -> QImage:
        """
        PIXELATION FIX: Render source at exact size with smooth scaling.
        """
        if not self._last_frame or self._last_frame.isNull():
            result = QImage(size, QImage.Format.Format_RGBA8888)
            result.fill(Qt.GlobalColor.black)
            return result
        
        # Scale with high quality
        scaled = self._last_frame.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Center on canvas
        result = QImage(size, QImage.Format.Format_RGBA8888)
        result.fill(Qt.GlobalColor.black)
        
        x = (size.width() - scaled.width()) // 2
        y = (size.height() - scaled.height()) // 2
        
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(x, y, scaled)
        painter.end()
        
        return result
    
    def _on_scroll_tick(self):
        """Update scrolling text animation."""
        try:
            ms = self._elapsed.restart()
            speed = float(self._text_props.get('scroll_speed', 50))
            self._scroll_px -= (speed * (ms / 1000.0))
            self.update()
        except Exception:
            pass
    
    # Opening detection methods (simplified versions)
    def _load_opening_override(self, effect_path: str) -> Optional[Tuple[float, float, float, float]]:
        """Load opening coordinates from JSON sidecar file."""
        try:
            base, _ = os.path.splitext(effect_path)
            json_path = base + '.json'
            if not os.path.exists(json_path):
                return None
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            opening = data.get('opening') if isinstance(data, dict) else None
            if isinstance(opening, (list, tuple)) and len(opening) == 4:
                nx, ny, nw, nh = [float(v) for v in opening]
                return (
                    max(0.0, min(1.0, nx)),
                    max(0.0, min(1.0, ny)),
                    max(0.01, min(1.0, nw)),
                    max(0.01, min(1.0, nh))
                )
            return None
        except Exception:
            return None
    
    def _detect_opening_from_mask(self, effect_path: str) -> Optional[Tuple[float, float, float, float]]:
        """Detect opening from mask file."""
        try:
            base, _ = os.path.splitext(effect_path)
            mask_path = base + '_mask.png'
            if not os.path.exists(mask_path):
                return None
            
            img = QImage(mask_path)
            if img.isNull():
                return None
            
            w, h = img.width(), img.height()
            min_x = min_y = float('inf')
            max_x = max_y = -1
            
            for y in range(h):
                for x in range(w):
                    c = img.pixelColor(x, y)
                    if c.red() > 200 and c.green() > 200 and c.blue() > 200 and c.alpha() > 200:
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)
            
            if max_x <= min_x or max_y <= min_y:
                return None
            
            return (min_x / w, min_y / h, (max_x - min_x + 1) / w, (max_y - min_y + 1) / h)
        except Exception:
            return None
    
    def _detect_opening_norm(self, img: QImage) -> Optional[Tuple[float, float, float, float]]:
        """Auto-detect opening area from transparency or brightness."""
        # Simplified version - detect transparent areas
        try:
            w, h = img.width(), img.height()
            if w <= 10 or h <= 10:
                return None
            
            # Find transparent bounding box
            min_x = min_y = float('inf')
            max_x = max_y = -1
            
            for y in range(h):
                for x in range(w):
                    if img.pixelColor(x, y).alpha() < 10:
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)
            
            if max_x <= min_x or max_y <= min_y:
                return None
            
            return (min_x / w, min_y / h, (max_x - min_x + 1) / w, (max_y - min_y + 1) / h)
        except Exception:
            return None
    
    def _build_opening_mask(self, size: QSize) -> Optional[QImage]:
        """Build opening mask for video clipping."""
        if not self._overlay_image or not self._opening_norm:
            return None
        
        # Use cache
        cache_key = (size.width(), size.height(), id(self._overlay_image))
        if cache_key in self._mask_cache:
            return self._mask_cache[cache_key]
        
        # Create mask
        mask = QImage(size, QImage.Format.Format_ARGB32)
        mask.fill(QColor(0, 0, 0, 0))
        
        nx, ny, nw, nh = self._opening_norm
        rect_x = int(nx * size.width())
        rect_y = int(ny * size.height())
        rect_w = max(1, int(nw * size.width()))
        rect_h = max(1, int(nh * size.height()))
        
        painter = QPainter(mask)
        painter.fillRect(rect_x, rect_y, rect_w, rect_h, QColor(255, 255, 255, 255))
        painter.end()
        
        self._mask_cache[cache_key] = mask
        return mask
    
    def _build_opening_mask_for_opening(self, size: QSize, opening_norm: Tuple[float, float, float, float]) -> Optional[QImage]:
        """Build opening mask for a specific opening area during transitions."""
        if not opening_norm:
            return None
        
        # Create mask
        mask = QImage(size, QImage.Format.Format_ARGB32)
        mask.fill(QColor(0, 0, 0, 0))
        
        nx, ny, nw, nh = opening_norm
        rect_x = int(nx * size.width())
        rect_y = int(ny * size.height())
        rect_w = max(1, int(nw * size.width()))
        rect_h = max(1, int(nh * size.height()))
        
        painter = QPainter(mask)
        painter.fillRect(rect_x, rect_y, rect_w, rect_h, QColor(255, 255, 255, 255))
        painter.end()
        
        return mask
    
    def get_overlay_path(self) -> Optional[str]:
        """Get current overlay path."""
        return self._overlay_path
