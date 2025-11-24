from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGroupBox, QTabWidget, QWidget, QSlider, QCheckBox, QSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtMultimedia import QMediaDevices, QCamera, QVideoFrame

RESOLUTION_PRESETS = [
    (3840, 2160, "4K UHD (2160p)"),
    (2560, 1440, "QHD (1440p)"),
    (1920, 1080, "1080p (Full HD)"),
    (1280, 720, "720p (HD)"),
    (640, 480, "480p (SD)"),
]

FPS_PRESETS = [15, 24, 30, 60, 120]

class InputSettingsDialog(QDialog):
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None, input_number: int = 1):
        super().__init__(parent)
        self.setWindowTitle(f"📹 Input {input_number} Camera Settings")
        self.setModal(True)
        self.setMinimumSize(650, 550)
        self.input_number = input_number
        
        # Modern dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                font-weight: bold;
                color: #ffffff;
                background-color: #252525;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #4fc3f7;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                background-color: #252525;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #b0b0b0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #3a7ca5;
                color: #ffffff;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3a3a3a;
                color: #ffffff;
            }
            QComboBox, QSpinBox {
                background-color: #2d2d2d;
                border: 1px solid #4a4a4a;
                border-radius: 5px;
                padding: 6px;
                color: #e0e0e0;
                min-height: 28px;
            }
            QComboBox:focus, QSpinBox:focus {
                border: 2px solid #4fc3f7;
            }
            QPushButton {
                background-color: #3a7ca5;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #4a8cb5;
            }
            QPushButton:pressed {
                background-color: #2a6c95;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #4a4a4a;
                border-radius: 4px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #4fc3f7;
                border-color: #4fc3f7;
            }
            QSlider::groove:horizontal {
                border: 1px solid #4a4a4a;
                height: 6px;
                background-color: #2d2d2d;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background-color: #4fc3f7;
                border: 2px solid #3a7ca5;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background-color: #6dd5ff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Create tabs
        tabs = QTabWidget()
        
        # ===== DEVICE TAB =====
        device_tab = QWidget()
        device_layout = QVBoxLayout(device_tab)
        device_layout.setSpacing(12)
        
        # Camera selection group
        camera_group = QGroupBox("📷 Camera Selection")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setSpacing(10)
        
        # Camera dropdown
        camera_row = QHBoxLayout()
        camera_label = QLabel("Camera:")
        camera_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        camera_row.addWidget(camera_label)
        
        self.camera_combo = QComboBox()
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        camera_row.addWidget(self.camera_combo, 1)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._populate_cameras)
        camera_row.addWidget(refresh_btn)
        camera_layout.addLayout(camera_row)
        
        # Resolution preset
        res_row = QHBoxLayout()
        res_label = QLabel("Resolution:")
        res_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        res_row.addWidget(res_label)
        
        self.resolution_combo = QComboBox()
        for w, h, desc in RESOLUTION_PRESETS:
            self.resolution_combo.addItem(f"{desc} ({w}×{h})", (w, h))
        self.resolution_combo.setCurrentIndex(2)  # Default 1080p
        res_row.addWidget(self.resolution_combo, 1)
        camera_layout.addLayout(res_row)
        
        # FPS preset
        fps_row = QHBoxLayout()
        fps_label = QLabel("Framerate:")
        fps_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        fps_row.addWidget(fps_label)
        
        self.fps_combo = QComboBox()
        for fps in FPS_PRESETS:
            self.fps_combo.addItem(f"{fps} FPS", fps)
        self.fps_combo.setCurrentIndex(2)  # Default 30 FPS
        fps_row.addWidget(self.fps_combo, 1)
        camera_layout.addLayout(fps_row)
        
        # Auto-detect button
        auto_btn = QPushButton("🎯 Auto-Detect Best Settings")
        auto_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        auto_btn.clicked.connect(self._auto_detect_settings)
        camera_layout.addWidget(auto_btn)
        
        device_layout.addWidget(camera_group)
        
        # Status info
        self.status_label = QLabel("ℹ️ Select a camera to configure")
        self.status_label.setStyleSheet("color: #b0b0b0; font-size: 11px; font-style: italic;")
        self.status_label.setWordWrap(True)
        device_layout.addWidget(self.status_label)
        
        device_layout.addStretch()
        tabs.addTab(device_tab, "Device")
        
        # ===== PICTURE TAB =====
        picture_tab = QWidget()
        picture_layout = QVBoxLayout(picture_tab)
        picture_layout.setSpacing(12)
        
        # Picture adjustments group
        picture_group = QGroupBox("🎨 Picture Adjustments")
        picture_group_layout = QVBoxLayout(picture_group)
        picture_group_layout.setSpacing(10)
        
        # Brightness
        brightness_row = QHBoxLayout()
        brightness_label = QLabel("Brightness:")
        brightness_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        brightness_row.addWidget(brightness_label)
        
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(lambda v: self.brightness_value.setText(f"{v:+d}"))
        brightness_row.addWidget(self.brightness_slider, 1)
        
        self.brightness_value = QLabel("0")
        self.brightness_value.setStyleSheet("font-weight: bold; color: #4fc3f7; min-width: 40px;")
        brightness_row.addWidget(self.brightness_value)
        picture_group_layout.addLayout(brightness_row)
        
        # Contrast
        contrast_row = QHBoxLayout()
        contrast_label = QLabel("Contrast:")
        contrast_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        contrast_row.addWidget(contrast_label)
        
        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(-100, 100)
        self.contrast_slider.setValue(0)
        self.contrast_slider.valueChanged.connect(lambda v: self.contrast_value.setText(f"{v:+d}"))
        contrast_row.addWidget(self.contrast_slider, 1)
        
        self.contrast_value = QLabel("0")
        self.contrast_value.setStyleSheet("font-weight: bold; color: #4fc3f7; min-width: 40px;")
        contrast_row.addWidget(self.contrast_value)
        picture_group_layout.addLayout(contrast_row)
        
        # Saturation
        saturation_row = QHBoxLayout()
        saturation_label = QLabel("Saturation:")
        saturation_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        saturation_row.addWidget(saturation_label)
        
        self.saturation_slider = QSlider(Qt.Orientation.Horizontal)
        self.saturation_slider.setRange(-100, 100)
        self.saturation_slider.setValue(0)
        self.saturation_slider.valueChanged.connect(lambda v: self.saturation_value.setText(f"{v:+d}"))
        saturation_row.addWidget(self.saturation_slider, 1)
        
        self.saturation_value = QLabel("0")
        self.saturation_value.setStyleSheet("font-weight: bold; color: #4fc3f7; min-width: 40px;")
        saturation_row.addWidget(self.saturation_value)
        picture_group_layout.addLayout(saturation_row)
        
        # Reset button
        reset_btn = QPushButton("↺ Reset to Defaults")
        reset_btn.clicked.connect(self._reset_picture_settings)
        picture_group_layout.addWidget(reset_btn)
        
        picture_layout.addWidget(picture_group)
        picture_layout.addStretch()
        
        tabs.addTab(picture_tab, "Picture")
        
        # ===== ADVANCED TAB =====
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.setSpacing(12)
        
        # Transform group
        transform_group = QGroupBox("🔄 Transform")
        transform_layout = QVBoxLayout(transform_group)
        transform_layout.setSpacing(10)
        
        self.flip_h_check = QCheckBox("↔️ Flip Horizontal (Mirror)")
        self.flip_h_check.setStyleSheet("font-weight: 500;")
        transform_layout.addWidget(self.flip_h_check)
        
        self.flip_v_check = QCheckBox("↕️ Flip Vertical")
        self.flip_v_check.setStyleSheet("font-weight: 500;")
        transform_layout.addWidget(self.flip_v_check)
        
        # Rotation
        rotation_row = QHBoxLayout()
        rotation_label = QLabel("Rotation:")
        rotation_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        rotation_row.addWidget(rotation_label)
        
        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["0° (None)", "90° (Clockwise)", "180° (Upside Down)", "270° (Counter-Clockwise)"])
        rotation_row.addWidget(self.rotation_combo, 1)
        transform_layout.addLayout(rotation_row)
        
        advanced_layout.addWidget(transform_group)
        
        # Enhancement group
        enhancement_group = QGroupBox("✨ Enhancement")
        enhancement_layout = QVBoxLayout(enhancement_group)
        enhancement_layout.setSpacing(10)
        
        self.low_light_check = QCheckBox("🌙 Low-Light Boost")
        self.low_light_check.setStyleSheet("font-weight: 500;")
        enhancement_layout.addWidget(self.low_light_check)
        
        self.noise_reduction_check = QCheckBox("🔇 Noise Reduction")
        self.noise_reduction_check.setStyleSheet("font-weight: 500;")
        enhancement_layout.addWidget(self.noise_reduction_check)
        
        self.auto_focus_check = QCheckBox("🎯 Auto Focus")
        self.auto_focus_check.setChecked(True)
        self.auto_focus_check.setStyleSheet("font-weight: 500;")
        enhancement_layout.addWidget(self.auto_focus_check)
        
        advanced_layout.addWidget(enhancement_group)
        advanced_layout.addStretch()
        
        tabs.addTab(advanced_tab, "Advanced")
        
        # ===== EFFECTS TAB =====
        effects_tab = QWidget()
        effects_layout = QVBoxLayout(effects_tab)
        effects_layout.setSpacing(12)
        
        # Chroma key group
        chroma_group = QGroupBox("🟢 Chroma Key (Green Screen)")
        chroma_layout = QVBoxLayout(chroma_group)
        chroma_layout.setSpacing(10)
        
        self.chroma_enable_check = QCheckBox("✅ Enable Chroma Key")
        self.chroma_enable_check.setStyleSheet("font-size: 13px; font-weight: 600; color: #4fc3f7;")
        self.chroma_enable_check.toggled.connect(self._on_chroma_toggled)
        chroma_layout.addWidget(self.chroma_enable_check)
        
        # Color selection
        color_row = QHBoxLayout()
        color_label = QLabel("Key Color:")
        color_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        color_row.addWidget(color_label)
        
        self.chroma_color_combo = QComboBox()
        self.chroma_color_combo.addItems(["Green", "Blue", "Custom"])
        self.chroma_color_combo.setEnabled(False)
        color_row.addWidget(self.chroma_color_combo, 1)
        chroma_layout.addLayout(color_row)
        
        # Threshold
        threshold_row = QHBoxLayout()
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        threshold_row.addWidget(threshold_label)
        
        self.chroma_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.chroma_threshold_slider.setRange(0, 100)
        self.chroma_threshold_slider.setValue(30)
        self.chroma_threshold_slider.setEnabled(False)
        self.chroma_threshold_slider.valueChanged.connect(lambda v: self.chroma_threshold_value.setText(f"{v}"))
        threshold_row.addWidget(self.chroma_threshold_slider, 1)
        
        self.chroma_threshold_value = QLabel("30")
        self.chroma_threshold_value.setStyleSheet("font-weight: bold; color: #4fc3f7; min-width: 30px;")
        threshold_row.addWidget(self.chroma_threshold_value)
        chroma_layout.addLayout(threshold_row)
        
        effects_layout.addWidget(chroma_group)
        effects_layout.addStretch()
        
        tabs.addTab(effects_tab, "Effects")
        
        # Add tabs to main layout
        layout.addWidget(tabs)
        
        # Action buttons - Only Close button for dynamic updates
        btns = QHBoxLayout()
        btns.addStretch(1)
        
        close_btn = QPushButton("✅ Close")
        close_btn.setMinimumHeight(36)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2e7d32, stop:1 #1b5e20);
                font-size: 13px;
                padding: 10px 24px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #388e3c, stop:1 #2e7d32);
            }
        """)
        close_btn.clicked.connect(self.accept)
        
        btns.addWidget(close_btn)
        layout.addLayout(btns)
        
        # Initialize
        self._populate_cameras()
        
        # Connect real-time updates
        self._connect_real_time_updates()
    
    def _populate_cameras(self):
        """Populate camera dropdown with available cameras."""
        try:
            self.camera_combo.clear()
            
            # Add default "Select Camera" option
            self.camera_combo.addItem("📹 Select Camera...", None)
            
            cameras = QMediaDevices.videoInputs()
            
            if not cameras:
                self.camera_combo.addItem("No cameras detected", None)
                self.status_label.setText("⚠️ No cameras found. Please connect a camera.")
                return
            
            for camera in cameras:
                try:
                    desc = camera.description()
                    self.camera_combo.addItem(f"📹 {desc}", camera)
                except Exception:
                    self.camera_combo.addItem("📹 Camera", camera)
            
            # Keep "Select Camera..." as default selection
            self.camera_combo.setCurrentIndex(0)
            self.status_label.setText(f"✅ Found {len(cameras)} camera(s) - Select one to configure")
        except Exception as e:
            print(f"Error populating cameras: {e}")
            self.camera_combo.addItem("Error detecting cameras", None)
    
    def _on_camera_changed(self, index):
        """Handle camera selection change."""
        camera_info = self.camera_combo.currentData()
        if camera_info:
            self.status_label.setText(f"📹 Selected: {self.camera_combo.currentText()}")
    
    def _auto_detect_settings(self):
        """Auto-detect best resolution and FPS for selected camera."""
        try:
            # Default to 1080p @ 30 FPS for most cameras
            self.resolution_combo.setCurrentIndex(2)
            self.fps_combo.setCurrentIndex(2)
            self.status_label.setText("✅ Auto-detected: 1080p @ 30 FPS")
        except Exception as e:
            print(f"Error auto-detecting: {e}")
    
    def _reset_picture_settings(self):
        """Reset all picture adjustments to defaults."""
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.saturation_slider.setValue(0)
    
    def _on_chroma_toggled(self, checked: bool):
        """Enable/disable chroma key controls."""
        self.chroma_color_combo.setEnabled(checked)
        self.chroma_threshold_slider.setEnabled(checked)
    
    def get_settings(self) -> dict:
        """Return all camera settings."""
        camera_info = self.camera_combo.currentData()
        resolution = self.resolution_combo.currentData()
        fps = self.fps_combo.currentData()
        rotation_text = self.rotation_combo.currentText()
        rotation_map = {"0° (None)": 0, "90° (Clockwise)": 90, "180° (Upside Down)": 180, "270° (Counter-Clockwise)": 270}
        
        return {
            'camera': camera_info,
            'camera_name': self.camera_combo.currentText(),
            'resolution': resolution,
            'fps': fps,
            'brightness': self.brightness_slider.value(),
            'contrast': self.contrast_slider.value(),
            'saturation': self.saturation_slider.value(),
            'flip_horizontal': self.flip_h_check.isChecked(),
            'flip_vertical': self.flip_v_check.isChecked(),
            'rotation': rotation_map.get(rotation_text, 0),
            'low_light_boost': self.low_light_check.isChecked(),
            'noise_reduction': self.noise_reduction_check.isChecked(),
            'auto_focus': self.auto_focus_check.isChecked(),
            'chroma_key_enabled': self.chroma_enable_check.isChecked(),
            'chroma_color': self.chroma_color_combo.currentText(),
            'chroma_threshold': self.chroma_threshold_slider.value(),
        }
    
    def _connect_real_time_updates(self):
        """Connect all controls to real-time updates."""
        # Picture adjustments
        self.brightness_slider.valueChanged.connect(self._on_setting_changed)
        self.contrast_slider.valueChanged.connect(self._on_setting_changed)
        self.saturation_slider.valueChanged.connect(self._on_setting_changed)
        
        # Transforms
        self.flip_h_check.toggled.connect(self._on_setting_changed)
        self.flip_v_check.toggled.connect(self._on_setting_changed)
        self.rotation_combo.currentTextChanged.connect(self._on_setting_changed)
        
        # Chroma key
        self.chroma_enable_check.toggled.connect(self._on_setting_changed)
        self.chroma_color_combo.currentTextChanged.connect(self._on_setting_changed)
        self.chroma_threshold_slider.valueChanged.connect(self._on_setting_changed)
    
    def _on_setting_changed(self):
        """Handle real-time setting changes."""
        try:
            # Get current settings
            settings = self.get_settings()
            
            # Apply to camera processor immediately
            from camera_processor import camera_processors
            camera_processors[self.input_number].update_settings(settings)
            
            # Emit signal for parent to handle
            self.settingsChanged.emit(settings)
            
        except Exception as e:
            print(f"Real-time update error: {e}")
    
    def load_current_settings(self, settings: dict):
        """Load existing settings into the dialog."""
        if not settings:
            return
        
        try:
            # Camera selection
            camera_name = settings.get('camera_name', '')
            if camera_name:
                # Find and select the camera in dropdown
                for i in range(self.camera_combo.count()):
                    if camera_name in self.camera_combo.itemText(i):
                        self.camera_combo.setCurrentIndex(i)
                        break
            
            # Picture adjustments
            self.brightness_slider.setValue(settings.get('brightness', 0))
            self.contrast_slider.setValue(settings.get('contrast', 0))
            self.saturation_slider.setValue(settings.get('saturation', 0))
            
            # Transforms
            self.flip_h_check.setChecked(settings.get('flip_horizontal', False))
            self.flip_v_check.setChecked(settings.get('flip_vertical', False))
            
            # Rotation
            rotation = settings.get('rotation', 0)
            rotation_map = {0: 0, 90: 1, 180: 2, 270: 3}
            self.rotation_combo.setCurrentIndex(rotation_map.get(rotation, 0))
            
            # Chroma key
            self.chroma_enable_check.setChecked(settings.get('chroma_key_enabled', False))
            chroma_color = settings.get('chroma_color', 'Green')
            color_index = self.chroma_color_combo.findText(chroma_color)
            if color_index >= 0:
                self.chroma_color_combo.setCurrentIndex(color_index)
            self.chroma_threshold_slider.setValue(settings.get('chroma_threshold', 30))
            
        except Exception as e:
            print(f"Error loading settings: {e}")
