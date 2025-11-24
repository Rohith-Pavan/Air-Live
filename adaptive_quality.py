#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoLive Studio - Adaptive Quality System
Dynamically adjusts quality based on system performance
"""

import time
import psutil
from typing import Dict, Any, Optional
from enum import Enum
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class QualityLevel(Enum):
    """Quality level presets."""
    ULTRA = "ultra"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ADAPTIVE = "adaptive"


class QualitySettings:
    """Quality settings for different levels."""
    
    PRESETS = {
        QualityLevel.ULTRA: {
            'fps': 60,
            'resolution': (1920, 1080),
            'bitrate': 8000,
            'effects_enabled': True,
            'transitions_enabled': True,
            'smooth_scaling': True,
            'overscan': 1.03,
            'thumbnail_quality': 85,
            'cache_size': 100,
            'preview_quality': 'high'
        },
        QualityLevel.HIGH: {
            'fps': 30,
            'resolution': (1920, 1080),
            'bitrate': 6000,
            'effects_enabled': True,
            'transitions_enabled': True,
            'smooth_scaling': True,
            'overscan': 1.02,
            'thumbnail_quality': 75,
            'cache_size': 50,
            'preview_quality': 'high'
        },
        QualityLevel.MEDIUM: {
            'fps': 30,
            'resolution': (1280, 720),
            'bitrate': 4000,
            'effects_enabled': True,
            'transitions_enabled': False,
            'smooth_scaling': False,
            'overscan': 1.0,
            'thumbnail_quality': 60,
            'cache_size': 30,
            'preview_quality': 'medium'
        },
        QualityLevel.LOW: {
            'fps': 24,
            'resolution': (1280, 720),
            'bitrate': 2500,
            'effects_enabled': False,
            'transitions_enabled': False,
            'smooth_scaling': False,
            'overscan': 1.0,
            'thumbnail_quality': 40,
            'cache_size': 20,
            'preview_quality': 'low'
        }
    }


class AdaptiveQualityManager(QObject):
    """
    Manages adaptive quality based on system performance.
    Automatically adjusts settings to maintain smooth operation.
    """
    
    # Signals
    quality_changed = pyqtSignal(str)  # Emitted when quality level changes
    settings_updated = pyqtSignal(dict)  # Emitted when settings are updated
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Current state
        self.current_level = QualityLevel.HIGH
        self.current_settings = QualitySettings.PRESETS[QualityLevel.HIGH].copy()
        self.adaptive_mode = True
        
        # Performance metrics
        self.performance_history = []
        self.history_size = 10
        
        # Thresholds for quality adjustment
        self.thresholds = {
            'cpu_high': 80,
            'cpu_medium': 60,
            'cpu_low': 40,
            'memory_high': 85,
            'memory_medium': 70,
            'memory_low': 50,
            'gpu_high': 80,
            'gpu_medium': 60,
            'gpu_low': 40
        }
        
        # Monitoring
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_performance)
        self.monitor_interval = 2000  # 2 seconds
        
        # Statistics
        self.stats = {
            'quality_changes': 0,
            'time_at_ultra': 0,
            'time_at_high': 0,
            'time_at_medium': 0,
            'time_at_low': 0,
            'last_change_time': time.time()
        }
        
        # Start monitoring if adaptive
        if self.adaptive_mode:
            self.monitor_timer.start(self.monitor_interval)
    
    def set_quality_level(self, level: QualityLevel):
        """Manually set quality level."""
        if level == QualityLevel.ADAPTIVE:
            self.adaptive_mode = True
            self.monitor_timer.start(self.monitor_interval)
        else:
            self.adaptive_mode = False
            self.monitor_timer.stop()
            self._apply_quality_level(level)
    
    def _apply_quality_level(self, level: QualityLevel):
        """Apply a specific quality level."""
        if level == self.current_level:
            return
        
        # Update time statistics
        current_time = time.time()
        time_spent = current_time - self.stats['last_change_time']
        
        if self.current_level == QualityLevel.ULTRA:
            self.stats['time_at_ultra'] += time_spent
        elif self.current_level == QualityLevel.HIGH:
            self.stats['time_at_high'] += time_spent
        elif self.current_level == QualityLevel.MEDIUM:
            self.stats['time_at_medium'] += time_spent
        elif self.current_level == QualityLevel.LOW:
            self.stats['time_at_low'] += time_spent
        
        # Apply new level
        self.current_level = level
        self.current_settings = QualitySettings.PRESETS[level].copy()
        self.stats['quality_changes'] += 1
        self.stats['last_change_time'] = current_time
        
        # Emit signals
        self.quality_changed.emit(level.value)
        self.settings_updated.emit(self.current_settings)
        
        print(f"Quality level changed to: {level.value}")
    
    def _monitor_performance(self):
        """Monitor system performance and adjust quality."""
        if not self.adaptive_mode:
            return
        
        try:
            # Get current metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            # Try to get GPU usage (platform-specific)
            gpu_percent = self._get_gpu_usage()
            
            # Store in history
            metrics = {
                'cpu': cpu_percent,
                'memory': memory_percent,
                'gpu': gpu_percent,
                'timestamp': time.time()
            }
            
            self.performance_history.append(metrics)
            if len(self.performance_history) > self.history_size:
                self.performance_history.pop(0)
            
            # Analyze and adjust
            self._adjust_quality_based_on_metrics()
            
        except Exception as e:
            print(f"Performance monitoring error: {e}")
    
    def _get_gpu_usage(self) -> float:
        """Get GPU usage (platform-specific implementation needed)."""
        # This would need platform-specific implementation
        # For now, return a default value
        return 50.0
    
    def _adjust_quality_based_on_metrics(self):
        """Adjust quality based on performance metrics."""
        if len(self.performance_history) < 3:
            return  # Need more data
        
        # Calculate averages
        avg_cpu = sum(m['cpu'] for m in self.performance_history) / len(self.performance_history)
        avg_memory = sum(m['memory'] for m in self.performance_history) / len(self.performance_history)
        avg_gpu = sum(m['gpu'] for m in self.performance_history if m['gpu']) / max(1, sum(1 for m in self.performance_history if m['gpu']))
        
        # Determine target quality level
        target_level = self._determine_target_level(avg_cpu, avg_memory, avg_gpu)
        
        # Apply if different from current
        if target_level != self.current_level:
            # Add hysteresis to prevent rapid switching
            if self._should_change_quality(target_level):
                self._apply_quality_level(target_level)
    
    def _determine_target_level(self, cpu: float, memory: float, gpu: float) -> QualityLevel:
        """Determine target quality level based on metrics."""
        # Critical: System under heavy load
        if cpu > self.thresholds['cpu_high'] or memory > self.thresholds['memory_high']:
            return QualityLevel.LOW
        
        # High load: Reduce quality
        if cpu > self.thresholds['cpu_medium'] or memory > self.thresholds['memory_medium']:
            return QualityLevel.MEDIUM
        
        # Moderate load: Balanced quality
        if cpu > self.thresholds['cpu_low'] or memory > self.thresholds['memory_low']:
            return QualityLevel.HIGH
        
        # Low load: Maximum quality
        return QualityLevel.ULTRA
    
    def _should_change_quality(self, target_level: QualityLevel) -> bool:
        """Check if quality should be changed (with hysteresis)."""
        # Don't change too frequently
        time_since_change = time.time() - self.stats['last_change_time']
        if time_since_change < 5.0:  # 5 second minimum between changes
            return False
        
        # Check if change is significant
        level_order = [QualityLevel.LOW, QualityLevel.MEDIUM, 
                      QualityLevel.HIGH, QualityLevel.ULTRA]
        
        current_index = level_order.index(self.current_level)
        target_index = level_order.index(target_level)
        
        # Require at least 2 level difference for rapid changes
        if abs(current_index - target_index) >= 2:
            return True
        
        # For single level changes, require more time
        if time_since_change > 10.0:
            return True
        
        return False
    
    def get_current_settings(self) -> Dict[str, Any]:
        """Get current quality settings."""
        return self.current_settings.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get quality management statistics."""
        total_time = time.time() - (self.stats['last_change_time'] - 
                                    self.stats['time_at_ultra'] - 
                                    self.stats['time_at_high'] - 
                                    self.stats['time_at_medium'] - 
                                    self.stats['time_at_low'])
        
        return {
            'current_level': self.current_level.value,
            'adaptive_mode': self.adaptive_mode,
            'quality_changes': self.stats['quality_changes'],
            'time_distribution': {
                'ultra': self.stats['time_at_ultra'] / max(1, total_time),
                'high': self.stats['time_at_high'] / max(1, total_time),
                'medium': self.stats['time_at_medium'] / max(1, total_time),
                'low': self.stats['time_at_low'] / max(1, total_time)
            },
            'current_metrics': self.performance_history[-1] if self.performance_history else None
        }
    
    def optimize_for_streaming(self):
        """Optimize settings specifically for streaming."""
        custom_settings = {
            'fps': 30,  # Stable FPS for streaming
            'resolution': (1920, 1080),
            'bitrate': 4500,  # YouTube recommended
            'effects_enabled': True,
            'transitions_enabled': False,  # Disable for stability
            'smooth_scaling': True,
            'overscan': 1.0,
            'thumbnail_quality': 60,
            'cache_size': 30,
            'preview_quality': 'medium'
        }
        
        self.current_settings = custom_settings
        self.settings_updated.emit(self.current_settings)
    
    def optimize_for_recording(self):
        """Optimize settings specifically for recording."""
        custom_settings = {
            'fps': 60,  # High FPS for recording
            'resolution': (1920, 1080),
            'bitrate': 10000,  # High quality
            'effects_enabled': True,
            'transitions_enabled': True,
            'smooth_scaling': True,
            'overscan': 1.03,
            'thumbnail_quality': 85,
            'cache_size': 50,
            'preview_quality': 'high'
        }
        
        self.current_settings = custom_settings
        self.settings_updated.emit(self.current_settings)


# Global adaptive quality manager
quality_manager = AdaptiveQualityManager()
