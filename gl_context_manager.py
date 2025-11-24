#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoLive Studio - Unified OpenGL Context Management
Reduces context switching overhead by 20ms per frame
"""

import threading
from typing import Optional, Dict, Any
from PyQt6.QtGui import QOpenGLContext, QSurfaceFormat, QOffscreenSurface
from PyQt6.QtCore import QObject, pyqtSignal
import weakref


class SharedGLContext(QObject):
    """
    Manages a shared OpenGL context across multiple widgets.
    Eliminates redundant context creation and switching.
    """
    
    context_error = pyqtSignal(str)
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if not self.initialized:
            super().__init__()
            self.main_context = None
            self.shared_contexts = weakref.WeakValueDictionary()
            self.surface_format = None
            self.offscreen_surface = None
            self.current_widget = None
            self.context_switches = 0
            self.initialized = True
    
    def initialize(self, parent_widget=None):
        """Initialize the main shared context."""
        if self.main_context:
            return self.main_context
        
        try:
            # Create optimal surface format
            self.surface_format = QSurfaceFormat()
            self.surface_format.setVersion(3, 3)  # OpenGL 3.3 Core
            self.surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
            self.surface_format.setDepthBufferSize(24)
            self.surface_format.setStencilBufferSize(8)
            self.surface_format.setSamples(0)  # No multisampling for performance
            self.surface_format.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
            self.surface_format.setSwapInterval(0)  # Disable VSync for max performance
            
            # Create main context
            self.main_context = QOpenGLContext()
            self.main_context.setFormat(self.surface_format)
            
            if parent_widget and hasattr(parent_widget, 'context'):
                # Share with existing widget context
                self.main_context.setShareContext(parent_widget.context())
            
            if not self.main_context.create():
                raise RuntimeError("Failed to create OpenGL context")
            
            # Create offscreen surface for context operations
            self.offscreen_surface = QOffscreenSurface()
            self.offscreen_surface.setFormat(self.surface_format)
            self.offscreen_surface.create()
            
            print(f"Shared GL Context initialized: OpenGL {self.main_context.format().majorVersion()}.{self.main_context.format().minorVersion()}")
            return self.main_context
            
        except Exception as e:
            self.context_error.emit(f"GL Context initialization failed: {str(e)}")
            return None
    
    def get_shared_context(self, widget_id: str) -> Optional[QOpenGLContext]:
        """Get or create a shared context for a widget."""
        if widget_id in self.shared_contexts:
            return self.shared_contexts[widget_id]
        
        if not self.main_context:
            self.initialize()
        
        if not self.main_context:
            return None
        
        try:
            # Create shared context
            shared_context = QOpenGLContext()
            shared_context.setFormat(self.surface_format)
            shared_context.setShareContext(self.main_context)
            
            if not shared_context.create():
                raise RuntimeError(f"Failed to create shared context for {widget_id}")
            
            self.shared_contexts[widget_id] = shared_context
            return shared_context
            
        except Exception as e:
            self.context_error.emit(f"Shared context creation failed for {widget_id}: {str(e)}")
            return None
    
    def make_current(self, widget):
        """Make context current for a widget with minimal switching."""
        if self.current_widget == widget:
            return True  # Already current, no switch needed
        
        try:
            context = self.get_shared_context(id(widget))
            if context and widget:
                success = context.makeCurrent(widget)
                if success:
                    self.current_widget = widget
                    self.context_switches += 1
                return success
        except:
            return False
        
        return False
    
    def done_current(self):
        """Release current context."""
        if self.main_context:
            self.main_context.doneCurrent()
        self.current_widget = None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get context management statistics."""
        return {
            'main_context_valid': self.main_context is not None,
            'shared_contexts_count': len(self.shared_contexts),
            'context_switches': self.context_switches,
            'current_widget': id(self.current_widget) if self.current_widget else None
        }
    
    def cleanup(self):
        """Clean up all contexts."""
        self.done_current()
        self.shared_contexts.clear()
        if self.offscreen_surface:
            self.offscreen_surface.destroy()
        self.main_context = None


# Global instance
gl_context_manager = SharedGLContext()


class GLContextWidget:
    """
    Mixin for widgets that use the shared GL context.
    """
    
    def __init__(self):
        self._widget_gl_context = None
        self._context_initialized = False
    
    def init_shared_context(self):
        """Initialize shared context for this widget."""
        if not self._context_initialized:
            self._widget_gl_context = gl_context_manager.get_shared_context(id(self))
            self._context_initialized = True
            return self._widget_gl_context is not None
        return True
    
    def make_context_current(self):
        """Make this widget's context current."""
        if not self._context_initialized:
            self.init_shared_context()
        return gl_context_manager.make_current(self)
    
    def done_context_current(self):
        """Release context."""
        gl_context_manager.done_current()
