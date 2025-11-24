#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Camera Processor - Functional Implementation
Applies camera settings like brightness, contrast, saturation, and chroma key to video frames
"""

from PyQt6.QtGui import QImage, QColor
from PyQt6.QtCore import Qt
from typing import Dict, Optional, Tuple

# Try to import numpy and cv2, but gracefully handle if not available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: numpy not available, camera processing will be limited")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: opencv not available, some camera effects may not work")

class CameraProcessor:
    """Processes camera frames with brightness, contrast, saturation, and chroma key effects."""
    
    def __init__(self):
        self.current_settings: Optional[Dict] = None
    
    def update_settings(self, settings: Dict):
        """Update camera processing settings."""
        self.current_settings = settings
        print(f"✅ Camera processor updated with settings: {settings}")
    
    def process_frame(self, frame: QImage) -> QImage:
        """Process camera frame with current settings."""
        if frame is None or frame.isNull():
            return frame
            
        # If no settings or no effects enabled, return original
        if not self.current_settings or not self.is_enabled():
            return frame
        
        # If numpy is not available, only apply basic Qt-based transforms
        if not NUMPY_AVAILABLE:
            return self._apply_qt_transforms(frame)
        
        try:
            # Convert QImage to numpy array for processing
            width = frame.width()
            height = frame.height()
            
            # Convert to RGB format
            rgb_frame = frame.convertToFormat(QImage.Format.Format_RGB888)
            ptr = rgb_frame.constBits()
            
            # Calculate expected size and validate
            expected_size = height * width * 3
            ptr.setsize(expected_size)
            
            # Create numpy array with proper validation
            arr = np.frombuffer(ptr, dtype=np.uint8)
            
            # Validate array size before reshaping
            if arr.size != expected_size:
                print(f"Warning: Array size mismatch. Expected {expected_size}, got {arr.size}")
                return frame  # Return original if size doesn't match
            
            arr = arr.reshape(height, width, 3)
            
            # Apply picture adjustments
            processed = self._apply_picture_adjustments(arr.copy())
            
            # Apply chroma key if enabled
            if self.current_settings.get('chroma_key_enabled', False):
                processed = self._apply_chroma_key(processed)
            
            # Apply transforms (flip, rotation)
            processed = self._apply_transforms(processed)
            
            # Convert back to QImage
            h, w, ch = processed.shape
            bytes_per_line = ch * w
            result_image = QImage(processed.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            return result_image
            
        except Exception as e:
            print(f"Camera processing error: {e}")
            return frame  # Return original frame if processing fails
    
    def _apply_picture_adjustments(self, frame: np.ndarray) -> np.ndarray:
        """Apply brightness, contrast, and saturation adjustments."""
        # Get adjustment values (-100 to +100)
        brightness = self.current_settings.get('brightness', 0)
        contrast = self.current_settings.get('contrast', 0)
        saturation = self.current_settings.get('saturation', 0)
        
        # Convert to float for processing
        frame = frame.astype(np.float32)
        
        # Apply brightness (-100 to +100 -> -50 to +50 pixel values)
        if brightness != 0:
            frame = frame + (brightness * 0.5)
        
        # Apply contrast (-100 to +100 -> 0.5 to 1.5 multiplier)
        if contrast != 0:
            contrast_factor = 1.0 + (contrast / 100.0)
            frame = (frame - 128) * contrast_factor + 128
        
        # Apply saturation adjustment
        if saturation != 0:
            frame = self._adjust_saturation(frame, saturation)
        
        # Clamp values to valid range
        frame = np.clip(frame, 0, 255)
        
        return frame.astype(np.uint8)
    
    def _adjust_saturation(self, frame: np.ndarray, saturation: int) -> np.ndarray:
        """Adjust color saturation."""
        # Convert RGB to HSV for saturation adjustment
        try:
            # Normalize to 0-1 range for HSV conversion
            frame_norm = frame / 255.0
            
            # Simple saturation adjustment by blending with grayscale
            gray = np.dot(frame_norm, [0.299, 0.587, 0.114])
            gray = np.stack([gray, gray, gray], axis=-1)
            
            # Saturation factor (-100 to +100 -> 0.0 to 2.0)
            sat_factor = 1.0 + (saturation / 100.0)
            sat_factor = max(0.0, min(2.0, sat_factor))
            
            # Blend between grayscale and original
            if sat_factor < 1.0:
                # Desaturate
                result = gray * (1.0 - sat_factor) + frame_norm * sat_factor
            else:
                # Saturate
                result = frame_norm * sat_factor
                # Prevent oversaturation by clamping
                result = np.clip(result, 0.0, 1.0)
            
            return result * 255.0
            
        except Exception as e:
            print(f"Saturation adjustment error: {e}")
            return frame
    
    def _apply_chroma_key(self, frame: np.ndarray) -> np.ndarray:
        """Apply chroma key (green screen) effect."""
        try:
            chroma_color = self.current_settings.get('chroma_color', 'Green')
            threshold = self.current_settings.get('chroma_threshold', 30) / 100.0
            
            # Define chroma key colors
            if chroma_color == 'Green':
                key_color = np.array([0, 255, 0])  # Pure green
            elif chroma_color == 'Blue':
                key_color = np.array([0, 0, 255])  # Pure blue
            else:
                # Custom color - use green as default
                key_color = np.array([0, 255, 0])
            
            # Calculate color distance
            diff = np.abs(frame.astype(np.float32) - key_color.astype(np.float32))
            distance = np.sqrt(np.sum(diff ** 2, axis=2)) / (255.0 * np.sqrt(3))
            
            # Create alpha mask
            alpha = np.where(distance < threshold, 0, 255).astype(np.uint8)
            
            # Apply transparency by making chroma key areas black
            mask = alpha[:, :, np.newaxis] / 255.0
            result = frame * mask
            
            return result.astype(np.uint8)
            
        except Exception as e:
            print(f"Chroma key error: {e}")
            return frame
    
    def _apply_transforms(self, frame: np.ndarray) -> np.ndarray:
        """Apply flip and rotation transforms."""
        try:
            # Flip horizontal
            if self.current_settings.get('flip_horizontal', False):
                frame = np.fliplr(frame)
            
            # Flip vertical
            if self.current_settings.get('flip_vertical', False):
                frame = np.flipud(frame)
            
            # Rotation
            rotation = self.current_settings.get('rotation', 0)
            if rotation == 90:
                frame = np.rot90(frame, k=-1)  # Clockwise
            elif rotation == 180:
                frame = np.rot90(frame, k=2)
            elif rotation == 270:
                frame = np.rot90(frame, k=1)  # Counter-clockwise
            
            return frame
            
        except Exception as e:
            print(f"Transform error: {e}")
            return frame
    
    def is_enabled(self) -> bool:
        """Check if any processing is enabled."""
        if not self.current_settings:
            return False
        
        # Check if any adjustment is non-zero
        adjustments = ['brightness', 'contrast', 'saturation']
        for adj in adjustments:
            if self.current_settings.get(adj, 0) != 0:
                return True
        
        # Check if any effect is enabled
        effects = ['chroma_key_enabled', 'flip_horizontal', 'flip_vertical']
        for effect in effects:
            if self.current_settings.get(effect, False):
                return True
        
        # Check rotation
        if self.current_settings.get('rotation', 0) != 0:
            return True
        
        return False
    
    def get_current_settings(self) -> Dict:
        """Get current settings for persistence."""
        return self.current_settings.copy() if self.current_settings else {}
    
    def _apply_qt_transforms(self, frame: QImage) -> QImage:
        """Apply basic transforms using Qt when numpy is not available."""
        try:
            from PyQt6.QtGui import QTransform
            
            result = frame
            transform = QTransform()
            
            # Flip horizontal
            if self.current_settings.get('flip_horizontal', False):
                transform.scale(-1, 1)
            
            # Flip vertical
            if self.current_settings.get('flip_vertical', False):
                transform.scale(1, -1)
            
            # Rotation
            rotation = self.current_settings.get('rotation', 0)
            if rotation != 0:
                transform.rotate(rotation)
            
            # Apply transform if any changes were made
            if not transform.isIdentity():
                result = frame.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            
            return result
            
        except Exception as e:
            print(f"Qt transform error: {e}")
            return frame

# Global instances for each input
camera_processors = {
    1: CameraProcessor(),
    2: CameraProcessor(),
    3: CameraProcessor(),
}
