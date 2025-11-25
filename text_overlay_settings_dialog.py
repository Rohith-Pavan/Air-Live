from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTabWidget, QWidget, QSlider, QCheckBox, QComboBox,
    QTextEdit, QFontComboBox, QSpinBox, QColorDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

POSITION_PRESETS = {
    "Top Left": {"x": 5, "y": 5, "align": "left"},
    "Top Center": {"x": 50, "y": 5, "align": "center"},
    "Top Right": {"x": 95, "y": 5, "align": "right"},
    "Middle Left": {"x": 5, "y": 50, "align": "left"},
    "Middle Center": {"x": 50, "y": 50, "align": "center"},
    "Middle Right": {"x": 95, "y": 50, "align": "right"},
    "Bottom Left": {"x": 5, "y": 95, "align": "left"},
    "Bottom Center": {"x": 50, "y": 95, "align": "center"},
    "Bottom Right": {"x": 95, "y": 95, "align": "right"},
}

STYLE_PRESETS = {
    "Lower Third": {"font_size": 36, "text_color": "#ffffff", "bg_color": "#3a7ca5", "bg_opacity": 80},
    "Title Card": {"font_size": 72, "text_color": "#ffffff", "bg_color": "#000000", "bg_opacity": 0},
    "Subtitle": {"font_size": 24, "text_color": "#ffffff", "bg_color": "#000000", "bg_opacity": 70},
    "Watermark": {"font_size": 18, "text_color": "#ffffff", "bg_color": "#000000", "bg_opacity": 0},
}

class TextOverlaySettingsDialog(QDialog):
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✍️ Text Overlay Settings")
        self.setModal(True)
        self.setMinimumSize(750, 650)
        
        self.text_color = QColor("#ffffff")
        self.bg_color = QColor("#000000")
        
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #e0e0e0; }
            QGroupBox { border: 2px solid #3a3a3a; border-radius: 8px; margin-top: 12px; padding-top: 8px; font-weight: bold; color: #ffffff; background-color: #252525; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; color: #4fc3f7; }
            QTabWidget::pane { border: 1px solid #3a3a3a; border-radius: 6px; background-color: #252525; }
            QTabBar::tab { background-color: #2d2d2d; color: #b0b0b0; padding: 10px 20px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: 500; }
            QTabBar::tab:selected { background-color: #3a7ca5; color: #ffffff; font-weight: bold; }
            QTabBar::tab:hover:!selected { background-color: #3a3a3a; color: #ffffff; }
            QComboBox, QSpinBox, QFontComboBox, QTextEdit { background-color: #2d2d2d; border: 1px solid #4a4a4a; border-radius: 5px; padding: 6px; color: #e0e0e0; min-height: 28px; }
            QComboBox:focus, QSpinBox:focus, QFontComboBox:focus, QTextEdit:focus { border: 2px solid #4fc3f7; }
            QPushButton { background-color: #3a7ca5; color: #ffffff; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600; min-height: 32px; }
            QPushButton:hover { background-color: #4a8cb5; }
            QCheckBox { color: #e0e0e0; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #4a4a4a; border-radius: 4px; background-color: #2d2d2d; }
            QCheckBox::indicator:checked { background-color: #4fc3f7; border-color: #4fc3f7; }
            QSlider::groove:horizontal { border: 1px solid #4a4a4a; height: 6px; background-color: #2d2d2d; border-radius: 3px; }
            QSlider::handle:horizontal { background-color: #4fc3f7; border: 2px solid #3a7ca5; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)
        
        tabs = QTabWidget()
        
        # Content tab
        content_tab = QWidget()
        content_layout = QVBoxLayout(content_tab)
        text_group = QGroupBox("📝 Text Content")
        text_layout = QVBoxLayout(text_group)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Enter your text here...")
        self.text_edit.setMaximumHeight(100)
        text_layout.addWidget(self.text_edit)
        content_layout.addWidget(text_group)
        
        font_group = QGroupBox("🔤 Font Settings")
        font_layout = QVBoxLayout(font_group)
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font:"))
        self.font_combo = QFontComboBox()
        font_row.addWidget(self.font_combo, 1)
        font_layout.addLayout(font_row)
        
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(12, 144)
        self.font_size_slider.setValue(36)
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_value.setText(f"{v} pt"))
        size_row.addWidget(self.font_size_slider, 1)
        self.font_size_value = QLabel("36 pt")
        self.font_size_value.setStyleSheet("font-weight: bold; color: #4fc3f7; min-width: 50px;")
        size_row.addWidget(self.font_size_value)
        font_layout.addLayout(size_row)
        
        style_row = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.italic_check = QCheckBox("Italic")
        self.underline_check = QCheckBox("Underline")
        style_row.addWidget(self.bold_check)
        style_row.addWidget(self.italic_check)
        style_row.addWidget(self.underline_check)
        style_row.addStretch()
        font_layout.addLayout(style_row)
        
        # Advanced button box for color and stroke
        advanced_row = QHBoxLayout()
        advanced_row.addWidget(QLabel("Text:"))
        
        # Color preview box
        self.text_color_preview = QPushButton()
        self.text_color_preview.setFixedSize(60, 32)
        self.text_color_preview.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.text_color.name()};
                border: 2px solid #4a4a4a;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #4fc3f7;
            }}
        """)
        self.text_color_preview.setToolTip("Text Color")
        self.text_color_preview.clicked.connect(lambda: self._choose_color('text'))
        advanced_row.addWidget(self.text_color_preview)
        
        # Stroke color preview box
        self.stroke_color = QColor("#000000")
        self.stroke_color_preview = QPushButton()
        self.stroke_color_preview.setFixedSize(60, 32)
        self.stroke_color_preview.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.stroke_color.name()};
                border: 2px solid #4a4a4a;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #4fc3f7;
            }}
        """)
        self.stroke_color_preview.setToolTip("Stroke Color")
        self.stroke_color_preview.clicked.connect(lambda: self._choose_color('stroke'))
        advanced_row.addWidget(self.stroke_color_preview)
        
        # Width spinbox
        advanced_row.addWidget(QLabel("W"))
        self.stroke_width_spin = QSpinBox()
        self.stroke_width_spin.setRange(0, 20)
        self.stroke_width_spin.setValue(3)
        self.stroke_width_spin.setFixedWidth(70)
        self.stroke_width_spin.setToolTip("Stroke Width")
        advanced_row.addWidget(self.stroke_width_spin)
        
        advanced_row.addStretch()
        font_layout.addLayout(advanced_row)
        
        content_layout.addWidget(font_group)
        content_layout.addStretch()
        tabs.addTab(content_tab, "Content")
        
        # Position tab
        position_tab = QWidget()
        position_layout = QVBoxLayout(position_tab)
        preset_group = QGroupBox("📍 Position Presets")
        preset_layout = QVBoxLayout(preset_group)
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.position_preset_combo = QComboBox()
        self.position_preset_combo.addItems(POSITION_PRESETS.keys())
        self.position_preset_combo.currentTextChanged.connect(self._apply_position_preset)
        preset_row.addWidget(self.position_preset_combo, 1)
        preset_layout.addLayout(preset_row)
        position_layout.addWidget(preset_group)
        
        custom_group = QGroupBox("🎯 Custom Position")
        custom_layout = QVBoxLayout(custom_group)
        x_row = QHBoxLayout()
        x_row.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 100)
        self.x_spin.setValue(50)
        self.x_spin.setSuffix(" %")
        x_row.addWidget(self.x_spin, 1)
        custom_layout.addLayout(x_row)
        
        y_row = QHBoxLayout()
        y_row.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 100)
        self.y_spin.setValue(50)
        self.y_spin.setSuffix(" %")
        y_row.addWidget(self.y_spin, 1)
        custom_layout.addLayout(y_row)
        
        align_row = QHBoxLayout()
        align_row.addWidget(QLabel("Align:"))
        self.align_combo = QComboBox()
        self.align_combo.addItems(["Left", "Center", "Right"])
        self.align_combo.setCurrentIndex(1)
        align_row.addWidget(self.align_combo, 1)
        custom_layout.addLayout(align_row)
        position_layout.addWidget(custom_group)
        position_layout.addStretch()
        tabs.addTab(position_tab, "Position")
        
        # Style tab
        style_tab = QWidget()
        style_layout = QVBoxLayout(style_tab)
        bg_group = QGroupBox("🎨 Background")
        bg_layout = QVBoxLayout(bg_group)
        self.bg_enable_check = QCheckBox("✅ Enable background box")
        self.bg_enable_check.toggled.connect(self._on_bg_toggled)
        bg_layout.addWidget(self.bg_enable_check)
        
        bg_color_row = QHBoxLayout()
        bg_color_row.addWidget(QLabel("Background:"))
        self.bg_color_preview = QPushButton()
        self.bg_color_preview.setFixedSize(60, 32)
        self.bg_color_preview.setEnabled(False)
        self.bg_color_preview.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.bg_color.name()};
                border: 2px solid #4a4a4a;
                border-radius: 4px;
            }}
            QPushButton:hover:enabled {{
                border: 2px solid #4fc3f7;
            }}
            QPushButton:disabled {{
                opacity: 0.5;
            }}
        """)
        self.bg_color_preview.setToolTip("Background Color")
        self.bg_color_preview.clicked.connect(lambda: self._choose_color('bg'))
        bg_color_row.addWidget(self.bg_color_preview)
        bg_color_row.addStretch()
        bg_layout.addLayout(bg_color_row)
        
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacity:"))
        self.bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity_slider.setRange(0, 100)
        self.bg_opacity_slider.setValue(70)
        self.bg_opacity_slider.setEnabled(False)
        self.bg_opacity_slider.valueChanged.connect(lambda v: self.bg_opacity_value.setText(f"{v}%"))
        opacity_row.addWidget(self.bg_opacity_slider, 1)
        self.bg_opacity_value = QLabel("70%")
        self.bg_opacity_value.setStyleSheet("font-weight: bold; color: #4fc3f7;")
        opacity_row.addWidget(self.bg_opacity_value)
        bg_layout.addLayout(opacity_row)
        style_layout.addWidget(bg_group)
        
        outline_group = QGroupBox("✏️ Outline")
        outline_layout = QVBoxLayout(outline_group)
        self.outline_enable_check = QCheckBox("✅ Enable outline")
        self.outline_enable_check.toggled.connect(self._on_outline_toggled)
        outline_layout.addWidget(self.outline_enable_check)
        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("Width:"))
        self.outline_width_spin = QSpinBox()
        self.outline_width_spin.setRange(1, 10)
        self.outline_width_spin.setValue(2)
        self.outline_width_spin.setSuffix(" px")
        self.outline_width_spin.setEnabled(False)
        width_row.addWidget(self.outline_width_spin, 1)
        outline_layout.addLayout(width_row)
        style_layout.addWidget(outline_group)
        
        shadow_group = QGroupBox("🌑 Shadow")
        shadow_layout = QVBoxLayout(shadow_group)
        self.shadow_enable_check = QCheckBox("✅ Enable shadow")
        shadow_layout.addWidget(self.shadow_enable_check)
        style_layout.addWidget(shadow_group)
        style_layout.addStretch()
        tabs.addTab(style_tab, "Style")
        
        # Presets tab
        presets_tab = QWidget()
        presets_layout = QVBoxLayout(presets_tab)
        presets_group = QGroupBox("⭐ Style Presets")
        presets_group_layout = QVBoxLayout(presets_group)
        preset_list_row = QHBoxLayout()
        preset_list_row.addWidget(QLabel("Preset:"))
        self.style_preset_combo = QComboBox()
        self.style_preset_combo.addItems(STYLE_PRESETS.keys())
        preset_list_row.addWidget(self.style_preset_combo, 1)
        load_btn = QPushButton("📥 Load")
        load_btn.clicked.connect(self._load_style_preset)
        preset_list_row.addWidget(load_btn)
        presets_group_layout.addLayout(preset_list_row)
        presets_layout.addWidget(presets_group)
        presets_layout.addStretch()
        tabs.addTab(presets_tab, "Presets")
        
        layout.addWidget(tabs)
        
        # ✅ ADD LIVE PREVIEW SECTION
        preview_group = QGroupBox("👁️ Live Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(400, 200)
        self.preview_label.setMaximumSize(400, 200)
        self.preview_label.setStyleSheet("border: 2px solid #4a4a4a; border-radius: 6px; background-color: #1a1a1a;")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setScaledContents(True)
        preview_layout.addWidget(self.preview_label)
        
        preview_btn_row = QHBoxLayout()
        preview_btn_row.addStretch()
        update_preview_btn = QPushButton("🔄 Update Preview")
        update_preview_btn.clicked.connect(self._update_preview)
        preview_btn_row.addWidget(update_preview_btn)
        preview_btn_row.addStretch()
        preview_layout.addLayout(preview_btn_row)
        
        layout.addWidget(preview_group)
        
        self._base_settings = None
        self._preview_renderer = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(60)
        self._preview_timer.timeout.connect(self._update_preview)
        changes_group = QGroupBox("Changes")
        changes_layout = QVBoxLayout(changes_group)
        self.changes_label = QLabel("No changes")
        self.changes_label.setStyleSheet("color: #b0b0b0;")
        self.changes_label.setWordWrap(True)
        changes_layout.addWidget(self.changes_label)
        layout.addWidget(changes_group)
        
        btns = QHBoxLayout()
        btns.addStretch(1)
        
        # Change button text to "Save & Apply"
        apply_btn = QPushButton("💾 Save & Apply")
        apply_btn.setMinimumHeight(36)
        apply_btn.setStyleSheet("QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2e7d32, stop:1 #1b5e20); font-size: 13px; padding: 10px 24px; }")
        apply_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)
        
        btns.addWidget(apply_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        # Connect all controls to update preview automatically
        self._connect_preview_updates()
        
        # Connect stroke width to preview
        self.stroke_width_spin.valueChanged.connect(self._update_preview)
        
        # Initial preview
        self._update_preview()
    
    def _choose_color(self, color_type: str):
        if color_type == 'text':
            color = QColorDialog.getColor(self.text_color, self)
            if color.isValid():
                self.text_color = color
                self.text_color_preview.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color.name()};
                        border: 2px solid #4a4a4a;
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        border: 2px solid #4fc3f7;
                    }}
                """)
                self._update_preview()  # Update preview when color changes
        elif color_type == 'stroke':
            color = QColorDialog.getColor(self.stroke_color, self)
            if color.isValid():
                self.stroke_color = color
                self.stroke_color_preview.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color.name()};
                        border: 2px solid #4a4a4a;
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        border: 2px solid #4fc3f7;
                    }}
                """)
                self._update_preview()  # Update preview when color changes
        elif color_type == 'bg':
            color = QColorDialog.getColor(self.bg_color, self)
            if color.isValid():
                self.bg_color = color
                self.bg_color_preview.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color.name()};
                        border: 2px solid #4a4a4a;
                        border-radius: 4px;
                    }}
                    QPushButton:hover:enabled {{
                        border: 2px solid #4fc3f7;
                    }}
                    QPushButton:disabled {{
                        opacity: 0.5;
                    }}
                """)
                self._update_preview()  # Update preview when color changes
    
    def _apply_position_preset(self, preset_name: str):
        if preset_name in POSITION_PRESETS:
            preset = POSITION_PRESETS[preset_name]
            self.x_spin.setValue(preset['x'])
            self.y_spin.setValue(preset['y'])
            align_map = {"left": 0, "center": 1, "right": 2}
            self.align_combo.setCurrentIndex(align_map.get(preset['align'], 1))
    
    def _on_bg_toggled(self, checked: bool):
        self.bg_color_preview.setEnabled(checked)
        self.bg_opacity_slider.setEnabled(checked)
    
    def _on_outline_toggled(self, checked: bool):
        self.outline_width_spin.setEnabled(checked)
    
    def _load_style_preset(self):
        preset_name = self.style_preset_combo.currentText()
        if preset_name in STYLE_PRESETS:
            preset = STYLE_PRESETS[preset_name]
            self.font_size_slider.setValue(preset['font_size'])
            self.text_color = QColor(preset['text_color'])
            self.text_color_preview.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.text_color.name()};
                    border: 2px solid #4a4a4a;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 2px solid #4fc3f7;
                }}
            """)
            self.bg_color = QColor(preset['bg_color'])
            self.bg_color_preview.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.bg_color.name()};
                    border: 2px solid #4a4a4a;
                    border-radius: 4px;
                }}
                QPushButton:hover:enabled {{
                    border: 2px solid #4fc3f7;
                }}
                QPushButton:disabled {{
                    opacity: 0.5;
                }}
            """)
            self.bg_opacity_slider.setValue(preset['bg_opacity'])
            self.bg_enable_check.setChecked(preset['bg_opacity'] > 0)
            self._update_preview()  # Update preview when preset is loaded
    
    def get_settings(self) -> dict:
        return {
            'text': self.text_edit.toPlainText(),
            'font_family': self.font_combo.currentFont().family(),
            'font_size': self.font_size_slider.value(),
            'bold': self.bold_check.isChecked(),
            'italic': self.italic_check.isChecked(),
            'underline': self.underline_check.isChecked(),
            'text_color': self.text_color.name(),
            'stroke_color': self.stroke_color.name(),
            'stroke_width': self.stroke_width_spin.value(),
            'position_x': self.x_spin.value(),
            'position_y': self.y_spin.value(),
            'alignment': self.align_combo.currentText().lower(),
            'bg_enabled': self.bg_enable_check.isChecked(),
            'bg_color': self.bg_color.name(),
            'bg_opacity': self.bg_opacity_slider.value() / 100.0,
            'outline_enabled': self.outline_enable_check.isChecked(),
            'outline_width': self.outline_width_spin.value(),
            'shadow_enabled': self.shadow_enable_check.isChecked(),
        }

    def apply_settings(self, settings: dict):
        """Prefill dialog controls from existing overlay settings.
        Accepts either QColor/rgba-int or hex strings for colors.
        """
        def to_qcolor(val, fallback):
            from PyQt6.QtGui import QColor
            if isinstance(val, QColor):
                return val
            try:
                # rgba int
                c = QColor()
                if isinstance(val, int):
                    c.setRgba(int(val))
                else:
                    c.setNamedColor(str(val))
                if c.isValid():
                    return c
            except Exception:
                pass
            return QColor(fallback)

        # Text
        if 'text' in settings:
            self.text_edit.setText(str(settings.get('text', '')))
        # Font
        if 'font_family' in settings:
            try:
                self.font_combo.setCurrentText(str(settings.get('font_family', '')))
            except Exception:
                pass
        if 'font_size' in settings:
            try:
                self.font_size_slider.setValue(int(settings.get('font_size', 36)))
            except Exception:
                pass
        # Colors
        if 'text_color' in settings:
            self.text_color = to_qcolor(settings.get('text_color'), '#ffffff')
            self.text_color_preview.setStyleSheet(f"""
                QPushButton {{ background-color: {self.text_color.name()}; border: 2px solid #4a4a4a; border-radius: 4px; }}
                QPushButton:hover {{ border: 2px solid #4fc3f7; }}
            """)
        if 'stroke_color' in settings:
            self.stroke_color = to_qcolor(settings.get('stroke_color'), '#000000')
            self.stroke_color_preview.setStyleSheet(f"""
                QPushButton {{ background-color: {self.stroke_color.name()}; border: 2px solid #4a4a4a; border-radius: 4px; }}
                QPushButton:hover {{ border: 2px solid #4fc3f7; }}
            """)
        if 'stroke_width' in settings:
            try:
                self.stroke_width_spin.setValue(int(settings.get('stroke_width', 3)))
            except Exception:
                pass
        # Background
        if 'bg_enabled' in settings:
            self.bg_enable_check.setChecked(bool(settings.get('bg_enabled', False)))
        if 'bg_color' in settings:
            self.bg_color = to_qcolor(settings.get('bg_color'), '#000000')
            self.bg_color_preview.setStyleSheet(f"""
                QPushButton {{ background-color: {self.bg_color.name()}; border: 2px solid #4a4a4a; border-radius: 4px; }}
                QPushButton:hover:enabled {{ border: 2px solid #4fc3f7; }}
                QPushButton:disabled {{ opacity: 0.5; }}
            """)
        if 'bg_opacity' in settings:
            try:
                # settings may be 0..1 float or 0..255 int
                v = settings.get('bg_opacity', 0)
                if isinstance(v, float):
                    self.bg_opacity_slider.setValue(int(max(0, min(100, round(v * 100)))))
                else:
                    # assume 0..255
                    self.bg_opacity_slider.setValue(int(max(0, min(100, round(int(v) / 255.0 * 100)))))
            except Exception:
                pass
        # Position
        if 'position_x' in settings:
            try: self.x_spin.setValue(int(settings.get('position_x', 50)))
            except Exception: pass
        if 'position_y' in settings:
            try: self.y_spin.setValue(int(settings.get('position_y', 50)))
            except Exception: pass
        if 'alignment' in settings:
            try:
                align = str(settings.get('alignment', 'center')).capitalize()
                idx = self.align_combo.findText(align)
                if idx >= 0:
                    self.align_combo.setCurrentIndex(idx)
            except Exception:
                pass
        # Outline/shadow
        if 'outline_enabled' in settings:
            self.outline_enable_check.setChecked(bool(settings.get('outline_enabled', False)))
        if 'outline_width' in settings:
            try: self.outline_width_spin.setValue(int(settings.get('outline_width', 2)))
            except Exception: pass
        if 'shadow_enabled' in settings:
            self.shadow_enable_check.setChecked(bool(settings.get('shadow_enabled', False)))
        
        # Refresh preview
        try:
            self._update_preview()
        except Exception:
            pass
        try:
            if self._base_settings is None:
                self._base_settings = dict(settings)
            self._update_changes_summary()
        except Exception:
            pass

    def set_base_settings(self, settings: dict):
        self._base_settings = dict(settings)
        try:
            self._update_changes_summary()
        except Exception:
            pass
    
    def _connect_preview_updates(self):
        """Connect all controls to automatically update preview."""
        # Text content
        self.text_edit.textChanged.connect(self._schedule_preview)
        
        # Font settings
        self.font_combo.currentFontChanged.connect(self._schedule_preview)
        self.font_size_slider.valueChanged.connect(self._schedule_preview)
        self.bold_check.toggled.connect(self._schedule_preview)
        self.italic_check.toggled.connect(self._schedule_preview)
        self.underline_check.toggled.connect(self._schedule_preview)
        
        # Position
        self.x_spin.valueChanged.connect(self._schedule_preview)
        self.y_spin.valueChanged.connect(self._schedule_preview)
        self.align_combo.currentTextChanged.connect(self._schedule_preview)
        
        # Style
        self.bg_enable_check.toggled.connect(self._schedule_preview)
        self.bg_opacity_slider.valueChanged.connect(self._schedule_preview)
        self.outline_enable_check.toggled.connect(self._schedule_preview)
        self.outline_width_spin.valueChanged.connect(self._schedule_preview)
        self.shadow_enable_check.toggled.connect(self._schedule_preview)
        
        
    def _schedule_preview(self):
        try:
            if not self._preview_timer.isActive():
                self._preview_timer.start()
            else:
                self._preview_timer.start()
        except Exception:
            self._update_preview()
    
    def _update_preview(self):
        """Update the live preview with current settings."""
        try:
            from text_overlay_renderer import TextOverlayRenderer
            from PyQt6.QtGui import QPixmap
        
            if self._preview_renderer is None:
                self._preview_renderer = TextOverlayRenderer()
            
            # Get current settings
            settings = self.get_settings()
            
            # Only show preview if there's text
            if not settings.get('text', '').strip():
                self.preview_label.setText("Enter text to see preview...")
                self.preview_label.setStyleSheet("border: 2px solid #4a4a4a; border-radius: 6px; background-color: #1a1a1a; color: #888; font-size: 14px;")
                return
            
            self._preview_renderer.update_settings(settings)
            
            preview_image = self._preview_renderer.get_preview_image(400, 200)
            
            # Convert to pixmap and display
            pixmap = QPixmap.fromImage(preview_image)
            self.preview_label.setPixmap(pixmap)
            self.preview_label.setStyleSheet("border: 2px solid #4a4a4a; border-radius: 6px;")
            try:
                if self._base_settings is not None:
                    self._update_changes_summary()
            except Exception:
                pass
            
        except Exception as e:
            print(f"Preview update error: {e}")
            self.preview_label.setText(f"Preview error: {str(e)}")
            self.preview_label.setStyleSheet("border: 2px solid #ff4444; border-radius: 6px; background-color: #1a1a1a; color: #ff4444; font-size: 12px;")

    def _update_changes_summary(self):
        """Update the 'Changes' box to list pending changes vs base settings."""
        try:
            if not self._base_settings:
                self.changes_label.setText("No changes")
                return
            cur = self.get_settings()
            base = self._base_settings
            pretty = {
                'text': 'Text',
                'font_family': 'Font',
                'font_size': 'Size',
                'text_color': 'Text Color',
                'stroke_color': 'Stroke Color',
                'stroke_width': 'Stroke Width',
                'bg_enabled': 'Background',
                'bg_color': 'Background Color',
                'bg_opacity': 'Background Opacity',
                'alignment': 'Anchor',
                'position_x': 'X',
                'position_y': 'Y',
            }
            lines = []
            for k, label in pretty.items():
                if k in cur and k in base and cur[k] != base[k]:
                    lines.append(f"• {label}: {base[k]} → {cur[k]}")
            self.changes_label.setText("No changes" if not lines else "\n".join(lines))
        except Exception:
            self.changes_label.setText("No changes")
