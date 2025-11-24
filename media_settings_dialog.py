from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QTabWidget, QWidget, QSlider, QCheckBox, QComboBox,
    QFileDialog, QListWidget, QListWidgetItem, QDoubleSpinBox, QTimeEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QTime, pyqtSignal
from PyQt6.QtGui import QFont
import os

SCALE_MODES = [
    "Fit (Maintain Aspect)",
    "Fill (Crop to Fit)",
    "Stretch (Distort)",
    "Original Size",
]

SPEED_PRESETS = [
    (0.25, "0.25x (Slow Motion)"),
    (0.5, "0.5x (Half Speed)"),
    (1.0, "1.0x (Normal)"),
    (1.5, "1.5x (Fast)"),
    (2.0, "2.0x (Double Speed)"),
]

class MediaSettingsDialog(QDialog):
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None, media_number: int = 1, initial_path: str = ''):
        super().__init__(parent)
        self.setWindowTitle(f"🎞️ Media {media_number} File Settings")
        self.setModal(True)
        self.setMinimumSize(700, 600)
        self.media_number = media_number
        
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
            QLineEdit, QComboBox, QDoubleSpinBox, QTimeEdit {
                background-color: #2d2d2d;
                border: 1px solid #4a4a4a;
                border-radius: 5px;
                padding: 6px;
                color: #e0e0e0;
                min-height: 28px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {
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
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #3a7ca5;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
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
        
        # ===== FILE TAB =====
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.setSpacing(12)
        
        # File selection group
        file_group = QGroupBox("📁 File Selection")
        file_group_layout = QVBoxLayout(file_group)
        file_group_layout.setSpacing(10)
        
        # File path
        path_row = QHBoxLayout()
        path_label = QLabel("File:")
        path_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        path_row.addWidget(path_label)
        
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/path/to/video.mp4")
        if initial_path:
            self.path_edit.setText(initial_path)
        self.path_edit.textChanged.connect(self._on_file_changed)
        path_row.addWidget(self.path_edit, 1)
        
        browse_btn = QPushButton("📂 Browse")
        browse_btn.clicked.connect(self._browse_file)
        path_row.addWidget(browse_btn)
        file_group_layout.addLayout(path_row)
        
        # File info
        self.file_info_label = QLabel("ℹ️ No file selected")
        self.file_info_label.setStyleSheet("color: #b0b0b0; font-size: 11px; font-style: italic;")
        self.file_info_label.setWordWrap(True)
        file_group_layout.addWidget(self.file_info_label)
        
        file_layout.addWidget(file_group)
        
        # Recent files group
        recent_group = QGroupBox("🕒 Recent Files")
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(120)
        self.recent_list.itemDoubleClicked.connect(self._on_recent_selected)
        recent_layout.addWidget(self.recent_list)
        
        file_layout.addWidget(recent_group)
        file_layout.addStretch()
        
        tabs.addTab(file_tab, "File")
        
        # ===== PLAYBACK TAB =====
        playback_tab = QWidget()
        playback_layout = QVBoxLayout(playback_tab)
        playback_layout.setSpacing(12)
        
        # Trim group
        trim_group = QGroupBox("✂️ Trim Controls")
        trim_layout = QVBoxLayout(trim_group)
        trim_layout.setSpacing(10)
        
        # Start time
        start_row = QHBoxLayout()
        start_label = QLabel("Start Time:")
        start_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        start_row.addWidget(start_label)
        
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm:ss")
        self.start_time_edit.setTime(QTime(0, 0, 0))
        start_row.addWidget(self.start_time_edit, 1)
        
        start_btn = QPushButton("⏮️ Set to Current")
        start_btn.setMaximumWidth(150)
        start_row.addWidget(start_btn)
        trim_layout.addLayout(start_row)
        
        # End time
        end_row = QHBoxLayout()
        end_label = QLabel("End Time:")
        end_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        end_row.addWidget(end_label)
        
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm:ss")
        self.end_time_edit.setTime(QTime(0, 0, 0))
        end_row.addWidget(self.end_time_edit, 1)
        
        end_btn = QPushButton("⏭️ Set to Current")
        end_btn.setMaximumWidth(150)
        end_row.addWidget(end_btn)
        trim_layout.addLayout(end_row)
        
        # Use trim checkbox
        self.use_trim_check = QCheckBox("✅ Enable trim (use only selected portion)")
        self.use_trim_check.setStyleSheet("font-weight: 500;")
        trim_layout.addWidget(self.use_trim_check)
        
        playback_layout.addWidget(trim_group)
        
        # Playback options group
        playback_group = QGroupBox("▶️ Playback Options")
        playback_group_layout = QVBoxLayout(playback_group)
        playback_group_layout.setSpacing(10)
        
        # Loop
        self.loop_check = QCheckBox("🔁 Loop playback")
        self.loop_check.setStyleSheet("font-weight: 500;")
        playback_group_layout.addWidget(self.loop_check)
        
        # Speed
        speed_row = QHBoxLayout()
        speed_label = QLabel("Playback Speed:")
        speed_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        speed_row.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        for speed, desc in SPEED_PRESETS:
            self.speed_combo.addItem(desc, speed)
        self.speed_combo.setCurrentIndex(2)  # Default 1.0x
        speed_row.addWidget(self.speed_combo, 1)
        playback_group_layout.addLayout(speed_row)
        
        playback_layout.addWidget(playback_group)
        playback_layout.addStretch()
        
        tabs.addTab(playback_tab, "Playback")
        
        # ===== TRANSFORM TAB =====
        transform_tab = QWidget()
        transform_layout = QVBoxLayout(transform_tab)
        transform_layout.setSpacing(12)
        
        # Scale group
        scale_group = QGroupBox("📐 Scale & Position")
        scale_layout = QVBoxLayout(scale_group)
        scale_layout.setSpacing(10)
        
        # Scale mode
        scale_row = QHBoxLayout()
        scale_label = QLabel("Scale Mode:")
        scale_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        scale_row.addWidget(scale_label)
        
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(SCALE_MODES)
        scale_row.addWidget(self.scale_combo, 1)
        scale_layout.addLayout(scale_row)
        
        # Position X
        x_row = QHBoxLayout()
        x_label = QLabel("Position X:")
        x_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        x_row.addWidget(x_label)
        
        self.pos_x_spin = QDoubleSpinBox()
        self.pos_x_spin.setRange(-1000, 1000)
        self.pos_x_spin.setValue(0)
        self.pos_x_spin.setSuffix(" px")
        x_row.addWidget(self.pos_x_spin, 1)
        scale_layout.addLayout(x_row)
        
        # Position Y
        y_row = QHBoxLayout()
        y_label = QLabel("Position Y:")
        y_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        y_row.addWidget(y_label)
        
        self.pos_y_spin = QDoubleSpinBox()
        self.pos_y_spin.setRange(-1000, 1000)
        self.pos_y_spin.setValue(0)
        self.pos_y_spin.setSuffix(" px")
        y_row.addWidget(self.pos_y_spin, 1)
        scale_layout.addLayout(y_row)
        
        transform_layout.addWidget(scale_group)
        
        # Rotation group
        rotation_group = QGroupBox("🔄 Rotation & Flip")
        rotation_layout = QVBoxLayout(rotation_group)
        rotation_layout.setSpacing(10)
        
        # Rotation
        rotation_row = QHBoxLayout()
        rotation_label = QLabel("Rotation:")
        rotation_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        rotation_row.addWidget(rotation_label)
        
        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["0° (None)", "90° (Clockwise)", "180° (Upside Down)", "270° (Counter-Clockwise)"])
        rotation_row.addWidget(self.rotation_combo, 1)
        rotation_layout.addLayout(rotation_row)
        
        # Flip options
        self.flip_h_check = QCheckBox("↔️ Flip Horizontal")
        self.flip_h_check.setStyleSheet("font-weight: 500;")
        rotation_layout.addWidget(self.flip_h_check)
        
        self.flip_v_check = QCheckBox("↕️ Flip Vertical")
        self.flip_v_check.setStyleSheet("font-weight: 500;")
        rotation_layout.addWidget(self.flip_v_check)
        
        transform_layout.addWidget(rotation_group)
        
        # Opacity
        opacity_row = QHBoxLayout()
        opacity_label = QLabel("Opacity:")
        opacity_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        opacity_row.addWidget(opacity_label)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_value.setText(f"{v}%"))
        opacity_row.addWidget(self.opacity_slider, 1)
        
        self.opacity_value = QLabel("100%")
        self.opacity_value.setStyleSheet("font-weight: bold; color: #4fc3f7; min-width: 40px;")
        opacity_row.addWidget(self.opacity_value)
        transform_layout.addLayout(opacity_row)
        
        transform_layout.addStretch()
        
        tabs.addTab(transform_tab, "Transform")
        
        # ===== FILTERS TAB =====
        filters_tab = QWidget()
        filters_layout = QVBoxLayout(filters_tab)
        filters_layout.setSpacing(12)
        
        # Color correction group
        color_group = QGroupBox("🎨 Color Correction")
        color_layout = QVBoxLayout(color_group)
        color_layout.setSpacing(10)
        
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
        color_layout.addLayout(brightness_row)
        
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
        color_layout.addLayout(contrast_row)
        
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
        color_layout.addLayout(saturation_row)
        
        filters_layout.addWidget(color_group)
        
        # Preset filters group
        preset_group = QGroupBox("✨ Preset Filters")
        preset_layout = QVBoxLayout(preset_group)
        preset_layout.setSpacing(10)
        
        filter_row = QHBoxLayout()
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        filter_row.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "None",
            "Black & White",
            "Sepia",
            "Vintage",
            "Cool (Blue Tint)",
            "Warm (Orange Tint)",
            "High Contrast",
            "Soft Focus",
        ])
        filter_row.addWidget(self.filter_combo, 1)
        preset_layout.addLayout(filter_row)
        
        filters_layout.addWidget(preset_group)
        filters_layout.addStretch()
        
        tabs.addTab(filters_tab, "Filters")
        
        # Add tabs to main layout
        layout.addWidget(tabs)
        
        # Action buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        
        apply_btn = QPushButton("✅ Apply Settings")
        apply_btn.setMinimumHeight(36)
        apply_btn.setStyleSheet("""
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
        apply_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)
        
        btns.addWidget(apply_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        # Initialize
        self._populate_recent_files()
        if initial_path:
            self._on_file_changed(initial_path)
    
    def _browse_file(self):
        """Open file browser to select media file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media File",
            self.path_edit.text() or "",
            "Media Files (*.mp4 *.mov *.avi *.mkv *.mp3 *.wav *.m4a);;All Files (*)"
        )
        if path:
            self.path_edit.setText(path)
    
    def _on_file_changed(self, path: str):
        """Update file info when path changes."""
        try:
            if path and os.path.exists(path):
                size = os.path.getsize(path) / (1024 * 1024)  # MB
                ext = os.path.splitext(path)[1]
                self.file_info_label.setText(f"✅ File: {os.path.basename(path)} | Size: {size:.1f} MB | Type: {ext}")
            else:
                self.file_info_label.setText("⚠️ File not found or invalid path")
        except Exception as e:
            self.file_info_label.setText(f"❌ Error: {str(e)}")
    
    def _populate_recent_files(self):
        """Populate recent files list (placeholder)."""
        self.recent_list.clear()
        # Placeholder - would load from config in real implementation
        placeholder = QListWidgetItem("📁 No recent files")
        placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self.recent_list.addItem(placeholder)
    
    def _on_recent_selected(self, item: QListWidgetItem):
        """Load selected recent file."""
        # Would implement in real version
        pass
    
    def get_settings(self) -> dict:
        """Return all media settings."""
        rotation_text = self.rotation_combo.currentText()
        rotation_map = {"0° (None)": 0, "90° (Clockwise)": 90, "180° (Upside Down)": 180, "270° (Counter-Clockwise)": 270}
        
        return {
            'file_path': self.path_edit.text().strip(),
            'use_trim': self.use_trim_check.isChecked(),
            'start_time': self.start_time_edit.time().toString("HH:mm:ss"),
            'end_time': self.end_time_edit.time().toString("HH:mm:ss"),
            'loop': self.loop_check.isChecked(),
            'speed': self.speed_combo.currentData(),
            'scale_mode': self.scale_combo.currentText(),
            'position_x': self.pos_x_spin.value(),
            'position_y': self.pos_y_spin.value(),
            'rotation': rotation_map.get(rotation_text, 0),
            'flip_horizontal': self.flip_h_check.isChecked(),
            'flip_vertical': self.flip_v_check.isChecked(),
            'opacity': self.opacity_slider.value() / 100.0,
            'brightness': self.brightness_slider.value(),
            'contrast': self.contrast_slider.value(),
            'saturation': self.saturation_slider.value(),
            'filter': self.filter_combo.currentText(),
        }
