# macan_viewer19.py (Dengan Integrasi Preset)

import sys
import os
import cv2
import platform
import subprocess
import re
import requests
from glob import glob
import webbrowser
from functools import partial

# --- PENAMBAHAN: Library baru untuk Multimedia (Video) dan QStackedWidget ---
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

if platform.system() == "Windows":
    import ctypes
from PIL import Image
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QScrollArea,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMenu, QStatusBar, QToolBar,
    QSizePolicy, QPushButton, QRubberBand, QMessageBox, QToolButton,
    QFrame, QCheckBox, QLineEdit, QComboBox, QProgressBar, QSlider,
    QDialog, QDialogButtonBox, QRadioButton, QSpacerItem,
    # --- PENAMBAHAN: Widget untuk menumpuk view (gambar/video) ---
    QStackedWidget,
    # --- PENAMBAHAN: Widget untuk dialog preset ---
    QListWidget,
    QStyle
)
from PyQt6.QtGui import QPixmap, QImage, QAction, QIcon, QKeySequence, QPainter, QCursor
from PyQt6.QtCore import (
    Qt, QSize, QPoint, QRect, QByteArray, QThread, QObject, pyqtSignal, QTimer,
    QSettings,
    # --- PENAMBAHAN: Library URL untuk path file media ---
    QUrl
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from macan_efek import ImageEffects, CollageDialog, AdjustmentsDialog
from macan_search import ImageSearchApp
# --- PENAMBAHAN: Import modul preset ---
from macan_preset import PresetManager, apply_preset


# --- Konstanta untuk format file ---
SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif']
SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mkv', '.mov', '.wmv']
ALL_SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS

# --- KELAS DIALOG BARU UNTUK MANAJEMEN PRESET ---
class ManagePresetsDialog(QDialog):
    def __init__(self, preset_manager, parent=None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        
        self.setWindowTitle("Manage Presets")
        self.setMinimumSize(450, 350)
        self.setStyleSheet("""
            QDialog { background-color: #2E3440; color: #ECEFF4; }
            QListWidget { background-color: #3B4252; border: 1px solid #4C566A; }
            QPushButton {
                background-color: #5E81AC; color: #ECEFF4; border: none;
                padding: 8px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #81A1C1; }
        """)

        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Available Presets:"))
        self.preset_list_widget = QListWidget()
        layout.addWidget(self.preset_list_widget)

        button_layout = QHBoxLayout()
        add_button = QPushButton("Add Preset...")
        add_button.clicked.connect(self.add_preset)
        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_preset)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        layout.addLayout(button_layout)

        close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button.rejected.connect(self.accept)
        layout.addWidget(close_button)

        self.populate_list()

    def populate_list(self):
        self.preset_list_widget.clear()
        presets = self.preset_manager.get_presets()
        for name in sorted(presets.keys()):
            self.preset_list_widget.addItem(name)

    def add_preset(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select .xmp Preset File", "", "XMP Files (*.xmp)")
        if file_path:
            try:
                self.preset_manager.add_preset(file_path)
                self.populate_list()
            except FileExistsError as e:
                QMessageBox.warning(self, "Preset Exists", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add preset: {e}")

    def remove_preset(self):
        selected_item = self.preset_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Selection", "Please select a preset to remove.")
            return

        preset_name = selected_item.text()
        reply = QMessageBox.question(self, "Confirm Removal",
                                     f"Are you sure you want to permanently remove the preset '{preset_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.preset_manager.remove_preset(preset_name):
                self.populate_list()
            else:
                QMessageBox.critical(self, "Error", f"Could not remove preset '{preset_name}'.")

# Teks untuk Image Converter Widget (Tidak ada perubahan)
CONVERTER_TEXT = {
    "window_title": "Image Converter",
    "input_img_label": "1. Select Input Image File(s):",
    "output_img_label": "2. Select Output Folder:",
    "input_placeholder_single_img": "Select a single image file...",
    "input_placeholder_multi_img": "Select one or more image files...",
    "output_placeholder_img": "Select a destination folder...",
    "batch_mode_checkbox": "Batch Mode (Convert Multiple Files)",
    "img_options_label": "3. Set Image Conversion Options:",
    "output_format_label": "Output Format:",
    "resolution_label": "Resolution:",
    "quality_label": "Quality:",
    "img_formats": ["JPEG", "PNG", "WEBP", "BMP", "GIF"],
    "img_qualities": ["Maximum (100)", "Very Good (95)", "Good (85)", "Medium (75)", "Low (50)"],
    "start_img_conv_btn": "Start Image Conversion",
    "ready_status_img": "Ready to convert images.",
    "browse_btn": "Browse...",
    "invalid_input_title": "Invalid Input",
    "invalid_input_file_msg": "Please select a valid input file.",
    "invalid_output_folder_msg": "Please select a valid output folder.",
    "batch_no_files_msg": "Please select at least one file for batch mode.",
    "preparing_conversion": "Preparing conversion for {filename}...",
    "opening_image": "Opening {filename}...",
    "processing_image": "Processing image...",
    "saving_image": "Image saved successfully.",
    "image_conversion_success": "Success! The image has been converted to {format}.",
    "error_during_conversion": "An error occurred: {error}",
    "converting_batch_file": "Converting file {current} of {total}: {filename}",
    "batch_complete_msg": "Batch finished! All {count} files have been successfully converted.",
    "batch_complete_title": "Batch Complete",
    "error_in_batch": "Error on file {index}: {error}\n\nBatch process stopped.",
    "error_title": "Error",
    "done": "Done!",
}

# Kelas Worker untuk Konversi Gambar (Tidak ada perubahan)
class ImageConversionWorker(QObject):
    progress_updated = pyqtSignal(int, str)
    conversion_finished = pyqtSignal(str)
    conversion_error = pyqtSignal(str)

    def __init__(self, input_path, output_path, out_format, resolution, quality_str, lang_dict=None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.out_format = out_format
        self.resolution = resolution
        self.quality_str = quality_str
        self.is_running = True
        self.lang = lang_dict if lang_dict else CONVERTER_TEXT

    def stop(self):
        self.is_running = False
        
    def run(self):
        try:
            self.progress_updated.emit(0, self.lang["opening_image"].format(filename=os.path.basename(self.input_path)))
            if not self.is_running: return
            
            img = Image.open(self.input_path)

            if self.resolution != "Original Size":
                try:
                    res_parts = self.resolution.split(' ')[0].split('x')
                    new_size = (int(res_parts[0]), int(res_parts[1]))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                except (ValueError, IndexError):
                    self.conversion_error.emit(f"Invalid resolution format: {self.resolution}")
                    return

            self.progress_updated.emit(50, self.lang["processing_image"])
            if not self.is_running: return

            base_name = os.path.splitext(os.path.basename(self.input_path))[0]
            output_filename = os.path.join(self.output_path, f"{base_name}.{self.out_format.lower()}")
            
            save_options = {}
            if self.out_format.lower() in ['jpeg', 'jpg', 'webp']:
                quality_map = {
                    "Maximum (100)": 100, "Very Good (95)": 95, "Good (85)": 85,
                    "Medium (75)": 75, "Low (50)": 50
                }
                save_options['quality'] = quality_map.get(self.quality_str, 85)
            
            if self.out_format.lower() in ['jpeg', 'jpg']:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

            img.save(output_filename, **save_options)
            self.progress_updated.emit(100, self.lang["saving_image"])
            self.conversion_finished.emit(self.lang["image_conversion_success"].format(format=self.out_format.upper()))

        except Exception as e:
            self.conversion_error.emit(self.lang["error_during_conversion"].format(error=str(e)))


# Widget Baru untuk Image Converter (Tidak ada perubahan)
class ImageConverterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lang = CONVERTER_TEXT
        self.thread = None
        self.worker = None
        self.image_batch_files = []
        self.current_image_batch_index = 0
        
        self.setWindowTitle(self.lang["window_title"])
        self.setGeometry(150, 150, 600, 500)
        
        icon_path = "macan_viewer.ico"
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, icon_path)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self._setup_ui()
        self._apply_stylesheet()
        self._update_image_input_ui()
        self._update_image_options()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(15)

        img_io_frame = QFrame()
        img_io_frame.setObjectName("ioFrame")
        img_io_layout = QVBoxLayout(img_io_frame)
        
        self.img_input_label = QLabel(self.lang["input_img_label"])
        img_io_layout.addWidget(self.img_input_label)
        img_input_layout = QHBoxLayout()
        self.img_input_path_edit = QLineEdit()
        self.img_input_path_edit.setReadOnly(True)
        self.img_browse_btn = QPushButton(self.lang["browse_btn"])
        self.img_browse_btn.clicked.connect(self.browse_image_input_file)
        img_input_layout.addWidget(self.img_input_path_edit)
        img_input_layout.addWidget(self.img_browse_btn)
        img_io_layout.addLayout(img_input_layout)

        self.img_output_label = QLabel(self.lang["output_img_label"])
        img_io_layout.addWidget(self.img_output_label)
        img_output_layout = QHBoxLayout()
        self.img_output_path_edit = QLineEdit()
        self.img_output_path_edit.setPlaceholderText(self.lang["output_placeholder_img"])
        self.img_output_path_edit.setReadOnly(True)
        self.img_browse_output_btn = QPushButton(self.lang["browse_btn"])
        self.img_browse_output_btn.clicked.connect(self.browse_image_output_folder)
        img_output_layout.addWidget(self.img_output_path_edit)
        img_output_layout.addWidget(self.img_browse_output_btn)
        img_io_layout.addLayout(img_output_layout)

        self.img_batch_mode_checkbox = QCheckBox(self.lang["batch_mode_checkbox"])
        self.img_batch_mode_checkbox.stateChanged.connect(self._update_image_input_ui)
        img_io_layout.addWidget(self.img_batch_mode_checkbox)
        
        layout.addWidget(img_io_frame)

        img_settings_frame = QFrame()
        img_settings_frame.setObjectName("ioFrame")
        img_settings_layout = QVBoxLayout(img_settings_frame)
        self.img_options_label = QLabel(self.lang["img_options_label"])
        img_settings_layout.addWidget(self.img_options_label)

        format_layout = QHBoxLayout()
        self.img_format_label = QLabel(self.lang["output_format_label"])
        format_layout.addWidget(self.img_format_label)
        self.img_format_combo = QComboBox()
        self.img_format_combo.addItems(self.lang["img_formats"])
        self.img_format_combo.currentTextChanged.connect(self._update_image_options)
        format_layout.addWidget(self.img_format_combo, 1)
        img_settings_layout.addLayout(format_layout)

        res_quality_layout = QHBoxLayout()
        
        self.img_res_label = QLabel(self.lang["resolution_label"])
        res_quality_layout.addWidget(self.img_res_label)
        self.img_resolution_combo = QComboBox()
        self.img_resolution_combo.addItems([
            "Original Size", "320x240", "640x480", "800x600", "1280x720 (HD)", "1920x1080 (Full HD)", "2560x1440 (2K)", "3840x2160 (4K)"
        ])
        res_quality_layout.addWidget(self.img_resolution_combo, 1)
        
        res_quality_layout.addSpacing(20)

        self.img_quality_label = QLabel(self.lang["quality_label"])
        res_quality_layout.addWidget(self.img_quality_label)
        self.img_quality_combo = QComboBox()
        self.img_quality_combo.addItems(self.lang["img_qualities"])
        self.img_quality_combo.setCurrentText(self.lang["img_qualities"][2]) 
        res_quality_layout.addWidget(self.img_quality_combo, 1)

        img_settings_layout.addLayout(res_quality_layout)
        layout.addWidget(img_settings_frame)

        self.img_convert_btn = QPushButton(self.lang["start_img_conv_btn"])
        self.img_convert_btn.setObjectName("convertButton")
        self.img_convert_btn.clicked.connect(self.start_image_conversion)
        layout.addWidget(self.img_convert_btn)

        self.img_progress_bar = QProgressBar()
        self.img_progress_bar.setValue(0)
        self.img_progress_bar.setTextVisible(False)
        layout.addWidget(self.img_progress_bar)
        
        self.img_status_label = QLabel(self.lang["ready_status_img"])
        self.img_status_label.setObjectName("statusLabel")
        layout.addWidget(self.img_status_label)

        layout.addStretch()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #2E3440; color: #ECEFF4; font-family: Segoe UI, sans-serif;
            }
            #statusLabel { color: #A3BE8C; }
            QLabel { font-size: 10pt; }
            QCheckBox { font-size: 9pt; padding-top: 5px; }
            QLineEdit {
                background-color: #4C566A; border: 1px solid #5E81AC; border-radius: 4px;
                padding: 6px; color: #D8DEE9;
            }
            QPushButton {
                background-color: #5E81AC; color: #ECEFF4; border: none; padding: 8px 16px;
                border-radius: 4px; font-size: 10pt;
            }
            QPushButton:hover { background-color: #81A1C1; }
            QPushButton:pressed { background-color: #4C566A; }
            #convertButton { background-color: #A3BE8C; font-weight: bold; color: #2E3440; }
            #convertButton:hover { background-color: #B48EAD; }
            QComboBox {
                background-color: #4C566A; border: 1px solid #5E81AC; border-radius: 4px; padding: 6px;
            }
            QComboBox::drop-down { border: none; }
            QProgressBar {
                border: 1px solid #4C566A; border-radius: 4px; text-align: center; height: 10px;
            }
            QProgressBar::chunk { background-color: #88C0D0; border-radius: 4px; }
            #ioFrame {
                border: 1px solid #434C5E; border-radius: 5px; padding: 10px;
            }
        """)

    def _update_image_input_ui(self):
        is_batch = self.img_batch_mode_checkbox.isChecked()
        if is_batch:
            self.img_input_path_edit.setPlaceholderText(self.lang["input_placeholder_multi_img"])
        else:
            self.img_input_path_edit.setPlaceholderText(self.lang["input_placeholder_single_img"])
        self.img_input_path_edit.clear()
        self.image_batch_files = []

    def _update_image_options(self):
        selected_format = self.img_format_combo.currentText().lower()
        has_quality = selected_format in ['jpeg', 'jpg', 'webp']
        self.img_quality_label.setVisible(has_quality)
        self.img_quality_combo.setVisible(has_quality)

    def browse_image_input_file(self):
        is_batch = self.img_batch_mode_checkbox.isChecked()
        filter_str = "Image Files (*.png *.jpg *.jpeg *.bmp *.webp *.gif)"
        
        if is_batch:
            files, _ = QFileDialog.getOpenFileNames(self, self.lang["input_img_label"], "", filter_str)
            if files:
                self.image_batch_files = files
                self.img_input_path_edit.setText(f"{len(files)} file(s) selected.")
        else:
            file_path, _ = QFileDialog.getOpenFileName(self, self.lang["input_img_label"], "", filter_str)
            if file_path:
                self.img_input_path_edit.setText(file_path)

    def browse_image_output_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, self.lang["output_img_label"])
        if folder_path:
            self.img_output_path_edit.setText(folder_path)

    def start_image_conversion(self):
        output_path = self.img_output_path_edit.text()
        if not output_path or not os.path.isdir(output_path):
            QMessageBox.warning(self, self.lang["invalid_input_title"], self.lang["invalid_output_folder_msg"])
            return

        is_batch = self.img_batch_mode_checkbox.isChecked()
        if is_batch:
            if not self.image_batch_files:
                QMessageBox.warning(self, self.lang["invalid_input_title"], self.lang["batch_no_files_msg"])
                return
            self.current_image_batch_index = 0
            self._start_next_batch_image_conversion()
        else:
            input_path = self.img_input_path_edit.text()
            if not input_path or not os.path.exists(input_path):
                QMessageBox.warning(self, self.lang["invalid_input_title"], self.lang["invalid_input_file_msg"])
                return
            self._start_single_image_conversion(input_path)

    def _start_single_image_conversion(self, input_path):
        self.img_convert_btn.setEnabled(False)
        self.img_progress_bar.setValue(0)
        self.img_status_label.setText(self.lang["preparing_conversion"].format(filename=os.path.basename(input_path)))

        out_format = self.img_format_combo.currentText()
        resolution = self.img_resolution_combo.currentText()
        quality = self.img_quality_combo.currentText()
        output_path = self.img_output_path_edit.text()

        self.thread = QThread()
        self.worker = ImageConversionWorker(input_path, output_path, out_format, resolution, quality, self.lang)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress_updated.connect(self.on_image_progress_update)
        self.worker.conversion_finished.connect(self.on_image_conversion_finished)
        self.worker.conversion_error.connect(self.on_image_conversion_error)
        
        self.thread.start()

    def _start_next_batch_image_conversion(self):
        if self.current_image_batch_index < len(self.image_batch_files):
            input_path = self.image_batch_files[self.current_image_batch_index]
            self.img_status_label.setText(
                self.lang["converting_batch_file"].format(
                    current=self.current_image_batch_index + 1,
                    total=len(self.image_batch_files),
                    filename=os.path.basename(input_path)
                )
            )
            self._start_single_image_conversion(input_path)
        else:
            final_msg = self.lang["batch_complete_msg"].format(count=len(self.image_batch_files))
            self.img_status_label.setText(final_msg)
            self.img_convert_btn.setEnabled(True)
            QMessageBox.information(self, self.lang["batch_complete_title"], final_msg)
            self._open_output_folder(self.img_output_path_edit.text())
    
    def on_image_progress_update(self, value, text):
        is_batch = self.img_batch_mode_checkbox.isChecked()
        if is_batch and self.image_batch_files:
            current_file_info = f"File {self.current_image_batch_index + 1}/{len(self.image_batch_files)}"
            self.update_progress(self.img_progress_bar, self.img_status_label, value, f"({current_file_info}) {text}")
        else:
            self.update_progress(self.img_progress_bar, self.img_status_label, value, text)

    def on_image_conversion_finished(self, msg):
        is_batch = self.img_batch_mode_checkbox.isChecked()
        if is_batch and self.image_batch_files:
            self.img_progress_bar.setValue(100)
            self.current_image_batch_index += 1
            if self.thread:
                self.thread.quit()
                self.thread.wait()
            self._start_next_batch_image_conversion()
        else:
            self.conversion_finished(self.img_convert_btn, self.img_progress_bar, self.img_status_label, msg)

    def on_image_conversion_error(self, msg):
        is_batch = self.img_batch_mode_checkbox.isChecked()
        if is_batch and self.image_batch_files:
            error_msg = self.lang["error_in_batch"].format(index=self.current_image_batch_index + 1, error=msg)
            self.conversion_error(self.img_convert_btn, self.img_progress_bar, self.img_status_label, error_msg)
        else:
            self.conversion_error(self.img_convert_btn, self.img_progress_bar, self.img_status_label, msg)

    def update_progress(self, progress_bar, status_label, value, text):
        progress_bar.setValue(value)
        status_label.setText(text)

    def _open_output_folder(self, path):
        if not os.path.isdir(path): return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"Failed to open output folder: {e}")

    def conversion_finished(self, button, progress_bar, status_label, message):
        status_label.setText(message)
        progress_bar.setValue(100)
        button.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        
        QMessageBox.information(self, self.lang["done"], message)
        self._open_output_folder(self.img_output_path_edit.text())

    def conversion_error(self, button, progress_bar, status_label, message):
        status_label.setText(f"{self.lang['error_title']}: {message}")
        progress_bar.setValue(0)
        button.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        QMessageBox.critical(self, self.lang["error_title"], message)

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()
        event.accept()

# Kelas Dialog untuk fitur Resize Image (Tidak ada perubahan)
class ResizeDialog(QDialog):
    def __init__(self, original_size, original_filesize, parent=None):
        super().__init__(parent)
        self.original_width, self.original_height = original_size
        self.original_filesize = original_filesize
        self.aspect_ratio = self.original_width / self.original_height if self.original_height > 0 else 1
        self.aspect_ratio_locked = True
        
        self.setWindowTitle("Resize")
        self.setWindowIcon(parent.windowIcon())
        self.setMinimumWidth(450)

        self._setup_ui()
        self._apply_stylesheet()
        self.update_new_labels()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        self.pixels_radio = QRadioButton("Pixels")
        self.pixels_radio.setChecked(True)
        self.percentage_radio = QRadioButton("Percentage")
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.pixels_radio)
        radio_layout.addWidget(self.percentage_radio)
        main_layout.addLayout(radio_layout)
        
        self.pixels_radio.toggled.connect(self.on_mode_change)

        self.pixels_widget = QWidget()
        dim_layout = QHBoxLayout(self.pixels_widget)
        dim_layout.setContentsMargins(0, 0, 0, 0)
        
        dim_layout.addWidget(QLabel("Width (px)"))
        self.width_edit = QLineEdit(str(self.original_width))
        dim_layout.addWidget(self.width_edit)

        self.lock_button = QPushButton("↔")
        self.lock_button.setCheckable(True)
        self.lock_button.setChecked(True)
        self.lock_button.setFixedWidth(30)
        self.lock_button.setToolTip("Maintain aspect ratio")
        dim_layout.addWidget(self.lock_button)

        dim_layout.addWidget(QLabel("Height (px)"))
        self.height_edit = QLineEdit(str(self.original_height))
        dim_layout.addWidget(self.height_edit)
        main_layout.addWidget(self.pixels_widget)
        
        self.percentage_widget = QWidget()
        percentage_layout = QHBoxLayout(self.percentage_widget)
        percentage_layout.setContentsMargins(0, 0, 0, 0)
        
        self.percentage_label = QLabel("Percentage")
        self.percentage_slider = QSlider(Qt.Orientation.Horizontal)
        self.percentage_slider.setRange(1, 200)
        self.percentage_slider.setValue(100)
        self.percentage_value_label = QLabel("100%")
        
        percentage_layout.addWidget(self.percentage_label)
        percentage_layout.addWidget(self.percentage_slider)
        percentage_layout.addWidget(self.percentage_value_label)
        
        self.percentage_widget.setVisible(False)
        main_layout.addWidget(self.percentage_widget)

        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Quality: 100% (High)"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(100)
        self.quality_slider.valueChanged.connect(lambda val: options_layout.itemAt(0).widget().setText(f"Quality: {val}% ({'High' if val > 85 else 'Medium' if val > 60 else 'Low'})"))
        options_layout.addWidget(self.quality_slider)
        
        options_layout.addWidget(QLabel("File type"))
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItems(["PNG", "JPG", "WEBP", "BMP"])
        options_layout.addWidget(self.file_type_combo)
        main_layout.addLayout(options_layout)

        self.current_label = QLabel()
        self.new_label = QLabel()
        main_layout.addWidget(self.current_label)
        main_layout.addWidget(self.new_label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        self.width_edit.textChanged.connect(self.width_changed)
        self.height_edit.textChanged.connect(self.height_changed)
        self.lock_button.toggled.connect(self.toggle_aspect_lock)
        self.percentage_slider.valueChanged.connect(self.percentage_changed)
    
    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog { background-color: #2E3440; color: #ECEFF4; }
            QLabel, QRadioButton { color: #ECEFF4; font-size: 10pt; }
            QLineEdit, QComboBox {
                background-color: #4C566A; border: 1px solid #5E81AC;
                border-radius: 4px; padding: 6px; color: #D8DEE9;
            }
            QPushButton {
                background-color: #5E81AC; color: #ECEFF4; border: none;
                padding: 8px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #81A1C1; }
            QPushButton:checked { background-color: #A3BE8C; }
        """)
    
    def on_mode_change(self, checked):
        is_pixels_mode = self.pixels_radio.isChecked()
        self.pixels_widget.setVisible(is_pixels_mode)
        self.percentage_widget.setVisible(not is_pixels_mode)
        if not is_pixels_mode:
            self.percentage_slider.setValue(100)

    def toggle_aspect_lock(self, checked):
        self.aspect_ratio_locked = checked

    def width_changed(self, text):
        if not self.width_edit.hasFocus() or not self.aspect_ratio_locked:
            return
        try:
            new_width = int(text)
            if self.aspect_ratio > 0:
                new_height = int(new_width / self.aspect_ratio)
                self.height_edit.blockSignals(True)
                self.height_edit.setText(str(new_height))
                self.height_edit.blockSignals(False)
                self.update_new_labels()
        except ValueError:
            pass

    def height_changed(self, text):
        if not self.height_edit.hasFocus() or not self.aspect_ratio_locked:
            return
        try:
            new_height = int(text)
            if self.aspect_ratio > 0:
                new_width = int(new_height * self.aspect_ratio)
                self.width_edit.blockSignals(True)
                self.width_edit.setText(str(new_width))
                self.width_edit.blockSignals(False)
                self.update_new_labels()
        except ValueError:
            pass
            
    def percentage_changed(self, value):
        self.percentage_value_label.setText(f"{value}%")
        new_width = int(self.original_width * value / 100)
        new_height = int(self.original_height * value / 100)
        self.width_edit.setText(str(new_width))
        self.height_edit.setText(str(new_height))
        self.update_new_labels()

    def update_new_labels(self):
        filesize_str = f"{self.original_filesize/1024:.1f} KB" if self.original_filesize < 1024**2 else f"{self.original_filesize/1024**2:.1f} MB"
        self.current_label.setText(f"Current: {self.original_width} x {self.original_height} pixels   {filesize_str}   {os.path.splitext(self.parent().file_path)[1].upper()[1:]}")
        
        new_w = self.width_edit.text()
        new_h = self.height_edit.text()
        file_type = self.file_type_combo.currentText()
        self.new_label.setText(f"New:      {new_w} x {new_h} pixels   (Size depends on content)   {file_type}")

    def get_values(self):
        return {
            "width": int(self.width_edit.text()),
            "height": int(self.height_edit.text()),
            "quality": self.quality_slider.value(),
            "format": self.file_type_combo.currentText().lower()
        }


class ImageViewer(QMainWindow):
    """
    Aplikasi Image & Video Viewer dengan PyQt6.
    Fitur: Buka, Simpan, Zoom, Rotasi, Flip, Navigasi, Frameless, Drag, Crop, Wallpaper,
    Fullscreen, Drag-and-Drop, Image Converter, Zoom Slider, Slideshow, Pan, Context Menu,
    Resize Dialog, Filmstrip, Save State, Video Playback, XMP Preset.
    """
    def __init__(self):
        super().__init__()

        self.image_effects = ImageEffects()
        self.image_search = ImageSearchApp()
        
        # --- PENAMBAHAN: Inisialisasi Preset Manager ---
        self.preset_manager = PresetManager()

        self.settings = QSettings("DanxExodus", "MacanImageViewer")
        self.last_directory = ""

        # --- MODIFIKASI: Path file yang aktif, bisa gambar atau video ---
        self.file_path = None
        self.current_media_type = None # 'image' or 'video'
        
        self.current_folder_files = []
        self.current_file_index = -1
        self.cv_image = None
        self.display_image = None
        self.zoom_factor = 1.0
        self.fit_to_window = True
        
        self.undo_stack = []
        self.redo_stack = []
        
        self.old_pos = None
        self.is_resizing = False
        self.resize_edge = None
        self.resize_margin = 8

        self.rubber_band = None
        self.origin_point = None
        self.is_cropping = False
        
        self.is_panning = False
        self.pan_last_pos = QPoint()
        
        self.is_in_crop_mode = False
        
        self.converter_widget = None

        self.slideshow_timer = QTimer(self)
        self.slideshow_running = False
        # --- PENAMBAHAN: Variabel untuk menyimpan state window sebelum slideshow ---
        self.pre_slideshow_geometry = None
        self.pre_slideshow_state = None


        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle('Macan Image Viewer')
        self.setGeometry(100, 100, 1100, 650)
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)
        
        self.setAcceptDrops(True)
        icon_path = "macan_viewer.ico"
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, icon_path)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; border-radius: 8px; }
            QToolBar { background-color: #202020; border: none; padding: 5px; }
            QToolBar QToolButton { background-color: transparent; color: #f0f0f0; border: none; padding: 5px; margin: 0 2px; }
            QToolBar QToolButton:hover { background-color: #3c3c3c; border-radius: 3px; }
            QToolBar QToolButton:checked { background-color: #4C566A; border: 1px solid #88C0D0; border-radius: 3px; }
            QToolBar QToolButton#close_button:hover { background-color: #e81123; }
            QMenu { background-color: #2b2b2b; color: #f0f0f0; border: 1px solid #555; }
            QMenu::item:selected { background-color: #3c3c3c; }
            QStatusBar { background-color: #202020; color: #f0f0f0; border-top: 1px solid #555; }
            QStatusBar::item { border: none; }
            QLabel, QStatusBar QLabel { color: #f0f0f0; }
            QPushButton { background-color: #555555; color: #f0f0f0; border: 1px solid #666; padding: 5px 10px; border-radius: 3px; }
            QPushButton:hover { background-color: #666666; }
            QSlider::groove:horizontal { border: 1px solid #555; height: 4px; background: #3c3c3c; margin: 2px 0; border-radius: 2px; }
            QSlider::handle:horizontal { background: #88C0D0; border: 1px solid #88C0D0; width: 14px; margin: -6px 0; border-radius: 7px; }
        """)

        # --- PERUBAHAN: Setup Image View ---
        self.image_label = QLabel(self)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.image_label.setScaledContents(True)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMouseTracking(True)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #1e1e1e; }")
        self.scroll_area.setMouseTracking(True)

        # --- PENAMBAHAN: Setup Video View ---
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #1e1e1e;")
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        # Loop video
        self.media_player.mediaStatusChanged.connect(lambda status: self.media_player.play() if status == QMediaPlayer.MediaStatus.EndOfMedia else None)
        
        # --- PERUBAHAN: Gunakan QStackedWidget untuk beralih antara gambar dan video ---
        self.media_stack = QStackedWidget()
        self.media_stack.addWidget(self.scroll_area) # Index 0 for image
        self.media_stack.addWidget(self.video_widget) # Index 1 for video

        self.crop_button = QPushButton("Crop Selection", self)
        self.crop_button.hide()
        self.crop_button.clicked.connect(self.perform_crop)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        # --- PERUBAHAN: Tambahkan media_stack ke layout utama ---
        main_layout.addWidget(self.media_stack)
        
        self._create_filmstrip()
        main_layout.addWidget(self.filmstrip_scroll_area)

        main_widget.setMouseTracking(True)
        self.setCentralWidget(main_widget)

        self._create_status_bar()
        self._create_actions()
        self._create_tool_bar()

        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.image_label)
        self.rubber_band.setStyleSheet("QRubberBand { border: 1px dashed white; background-color: rgba(255, 255, 255, 50); }")

        self.image_label.mousePressEvent = self.image_mouse_press
        self.image_label.mouseMoveEvent = self.image_mouse_move
        self.image_label.mouseReleaseEvent = self.image_mouse_release
        
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(x, y)

    def _create_svg_icon(self, svg_xml):
        renderer = QSvgRenderer(QByteArray(svg_xml.encode('utf-8')))
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def _create_actions(self):
        self.print_action = QAction("Print...", self)
        self.print_action.triggered.connect(self.print_image)                
        self.save_pdf_action = QAction("Save as PDF...", self)
        self.save_pdf_action.triggered.connect(self.save_as_pdf)        
        self.set_wallpaper_action = QAction("Set as Wallpaper", self)
        self.set_wallpaper_action.triggered.connect(self.set_as_wallpaper)
        self.search_image_action = QAction("Search by Image", self)
        self.search_image_action.triggered.connect(self.open_search)
        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about_dialog)
        self.exit_action = QAction("Exit", self)
        self.exit_action.triggered.connect(self.close)
        self.converter_action = QAction("Image Converter", self)
        self.converter_action.triggered.connect(self.open_converter)
        
        # --- MODIFIKASI: Ganti nama aksi menjadi lebih umum ---
        self.open_action = QAction("&Open File...", self)
        self.open_action.triggered.connect(self.open_file)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        
        self.save_as_action = QAction("Save &As...", self)
        self.save_as_action.triggered.connect(self.save_image_as)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.copy_action = QAction("&Copy", self)
        self.copy_action.triggered.connect(self.copy_image_to_clipboard)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.open_explorer_action = QAction("Open in &File Explorer", self)
        self.open_explorer_action.triggered.connect(self.open_in_file_explorer)
        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.reset_zoom_action = QAction("Fit to Window", self)
        self.reset_zoom_action.triggered.connect(self.reset_zoom)
        self.reset_zoom_action.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_0))
        self.rotate_left_action = QAction("Rotate &Left", self)
        self.rotate_left_action.triggered.connect(self.rotate_left)
        self.rotate_right_action = QAction("Rotate &Right", self)
        self.rotate_right_action.triggered.connect(self.rotate_right)
        self.flip_horizontal_action = QAction("Flip Horizontal", self)
        self.flip_horizontal_action.triggered.connect(lambda: self.flip_image(1))
        self.flip_vertical_action = QAction("Flip Vertical", self)
        self.flip_vertical_action.triggered.connect(lambda: self.flip_image(0))
        self.crop_action = QAction("Crop Image", self)
        self.crop_action.setCheckable(True)
        self.crop_action.triggered.connect(self.toggle_crop_mode)

        # --- MODIFIKASI: Ganti nama aksi menjadi lebih umum ---
        self.prev_action = QAction("Pre&vious File", self)
        self.prev_action.triggered.connect(self.show_previous_file)
        self.prev_action.setShortcuts([QKeySequence.StandardKey.Back, QKeySequence(Qt.Key.Key_Left)])
        self.next_action = QAction("&Next File", self)
        self.next_action.triggered.connect(self.show_next_file)
        self.next_action.setShortcuts([QKeySequence.StandardKey.Forward, QKeySequence(Qt.Key.Key_Right)])
        
        self.slideshow_action = QAction("Start Slideshow", self)
        self.slideshow_action.triggered.connect(self.toggle_slideshow)
        self.undo_action = QAction("Undo", self)
        self.undo_action.triggered.connect(self.undo_image)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = QAction("Redo", self)
        self.redo_action.triggered.connect(self.redo_image)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.fullscreen_action = QAction("Fullscreen", self)
        self.fullscreen_action.setShortcut(QKeySequence(Qt.Key.Key_F11))
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)

        self.file_info_action = QAction("File Info", self)
        self.file_info_action.triggered.connect(self.show_file_info)
        self.resize_action = QAction("Resize Image...", self)
        self.resize_action.triggered.connect(self.resize_image)
        self.visual_search_action = QAction("Visual Search with Google", self)
        self.visual_search_action.triggered.connect(self.visual_search)
        self.filmstrip_action = QAction("Show Filmstrip", self)
        self.filmstrip_action.setCheckable(True)
        self.filmstrip_action.setChecked(True)
        self.filmstrip_action.triggered.connect(self.toggle_filmstrip)

        self._update_action_states(False)

    def _create_tool_bar(self):
        self.tool_bar = QToolBar("Main Toolbar")
        self.tool_bar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tool_bar)
        icon_color = "#f0f0f0"
        prev_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>'
        next_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M8.59 16.59L10 18l6-6-6-6-1.41 1.41L13.17 12z"/></svg>'
        self.play_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M8 5v14l11-7z"/></svg>'
        self.pause_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>'
        open_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-1 12H5V8h14v10z"/></svg>'
        save_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/></svg>'
        copy_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>'
        zoom_in_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM10 9h-1v1H8V9H7V8h1V7h1v1h1v1z"/></svg>'
        zoom_out_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM7 9h5v-1H7z"/></svg>'
        fit_window_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>'
        rotate_left_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M7.83 11H18v2H7.83l2.88 2.88-1.41 1.41L5 12l4.29-4.29 1.41 1.41L7.83 11zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/></svg>'
        rotate_right_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13.17L8.12 10.71 6.71 9.29 12 4l5.29 5.29-1.41 1.41L13 7.83V13h-2V7.83z" transform="rotate(90 12 12)"/></svg>'
        flip_h_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M15 21h2v-2h-2v2zm4-12h2V7h-2v2zM3 5v14c0 1.1.9 2 2 2h4v-2H5V5h4V3H5c-1.1 0-2 .9-2 2zm16-2v2h2c0-1.1-.9-2-2-2zm-8 20h2V1h-2v22zm8-6h2v-2h-2v2zm-4 0h2v-2h-2v2zm4-4h2v-2h-2v2zm-12 4h2v-2H7v2z"/></svg>'
        flip_v_svg = f'<svg viewBox="0 0 24 24" transform="rotate(90 12 12)"><path fill="{icon_color}" d="M15 21h2v-2h-2v2zm4-12h2V7h-2v2zM3 5v14c0 1.1.9 2 2 2h4v-2H5V5h4V3H5c-1.1 0-2 .9-2 2zm16-2v2h2c0-1.1-.9-2-2-2zm-8 20h2V1h-2v22zm8-6h2v-2h-2v2zm-4 0h2v-2h-2v2zm4-4h2v-2h-2v2zm-12 4h2v-2H7v2z"/></svg>'
        crop_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M17 15h2V7c0-1.1-.9-2-2-2H9v2h8v8zM7 17V1H5v4H1v2h4v10c0 1.1.9 2 2 2h10v4h2v-4h4v-2H7z"/></svg>'
        explorer_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>'
        undo_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"/></svg>'
        redo_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.91 16c1.05-3.19 4.05-5.5 7.59-5.5 1.96 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z"/></svg>'
        wallpaper_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M4 4h7V2H4c-1.1 0-2 .9-2 2v7h2V4zm6 9l-4 5h12l-3-4-2.03 2.71L10 13zm7-4.5c0-.83-.67-1.5-1.5-1.5S14 7.67 14 8.5s.67 1.5 1.5 1.5S17 9.33 17 8.5zM20 2h-7v2h7v7h2V4c0-1.1-.9-2-2-2zm0 18h-7v2h7c1.1 0 2-.9 2-2v-7h-2v7zM4 13H2v7c0 1.1.9 2 2 2h7v-2H4v-7z"/></svg>'
        self.fullscreen_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>'
        self.exit_fullscreen_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/></svg>'
        converter_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M14 6V4h-4v2h4zm5 3v2h-3v-2h3zm-4-6V1h-6v2h6zM6 9H3V7h3v2zm12 7l-1.41-1.41L15 16.17V12h-2v4.17l-1.59-1.59L10 16l4 4 4-4zM4 20l4-4-1.41-1.41L5 16.17V12H3v4.17l-1.59-1.59L0 16l4 4z"/></svg>'
        
        self.open_action.setIcon(self._create_svg_icon(open_svg))
        self.save_as_action.setIcon(self._create_svg_icon(save_svg))
        self.copy_action.setIcon(self._create_svg_icon(copy_svg))
        self.zoom_in_action.setIcon(self._create_svg_icon(zoom_in_svg))
        self.zoom_out_action.setIcon(self._create_svg_icon(zoom_out_svg))
        self.reset_zoom_action.setIcon(self._create_svg_icon(fit_window_svg))
        self.rotate_left_action.setIcon(self._create_svg_icon(rotate_left_svg))
        self.rotate_right_action.setIcon(self._create_svg_icon(rotate_right_svg))
        self.flip_horizontal_action.setIcon(self._create_svg_icon(flip_h_svg))
        self.flip_vertical_action.setIcon(self._create_svg_icon(flip_v_svg))
        self.crop_action.setIcon(self._create_svg_icon(crop_svg))
        self.open_explorer_action.setIcon(self._create_svg_icon(explorer_svg))
        self.prev_action.setIcon(self._create_svg_icon(prev_svg))
        self.next_action.setIcon(self._create_svg_icon(next_svg))
        self.slideshow_action.setIcon(self._create_svg_icon(self.play_svg))
        self.undo_action.setIcon(self._create_svg_icon(undo_svg))
        self.redo_action.setIcon(self._create_svg_icon(redo_svg))
        self.set_wallpaper_action.setIcon(self._create_svg_icon(wallpaper_svg))
        self.fullscreen_action.setIcon(self._create_svg_icon(self.fullscreen_svg))
        self.converter_action.setIcon(self._create_svg_icon(converter_svg))
        
        file_menu_button = QToolButton(self)
        file_menu_button.setText("File")
        file_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        file_menu = QMenu(self)
        file_menu.addAction(self.print_action)        
        file_menu.addAction(self.save_pdf_action)
        file_menu.addAction(self.set_wallpaper_action)
        file_menu.addSeparator()
        file_menu.addAction(self.search_image_action)
        file_menu.addAction(self.about_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        file_menu_button.setMenu(file_menu)
        
        converter_menu_button = QToolButton(self)
        converter_menu_button.setText("Converter")
        converter_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        converter_menu = QMenu(self)
        converter_menu.addAction(self.converter_action)
        converter_menu_button.setMenu(converter_menu)
        
        self.tool_bar.addWidget(file_menu_button)
        self.tool_bar.addWidget(converter_menu_button)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.prev_action)
        self.tool_bar.addAction(self.next_action)
        self.tool_bar.addAction(self.slideshow_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.open_action)
        self.tool_bar.addAction(self.save_as_action)
        self.tool_bar.addAction(self.copy_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.zoom_in_action)
        self.tool_bar.addAction(self.zoom_out_action)
        self.tool_bar.addAction(self.reset_zoom_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.rotate_left_action)
        self.tool_bar.addAction(self.rotate_right_action)
        self.tool_bar.addAction(self.flip_horizontal_action)
        self.tool_bar.addAction(self.flip_vertical_action)
        self.tool_bar.addAction(self.crop_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.undo_action)
        self.tool_bar.addAction(self.redo_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.open_explorer_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.tool_bar.addWidget(spacer)
        
        self.tool_bar.addAction(self.fullscreen_action)
        
        minimize_svg = f'<svg viewBox="0 0 24 24"><path fill="none" stroke="{icon_color}" stroke-width="2" d="M4 12 L20 12"></path></svg>'
        maximize_svg = f'<svg viewBox="0 0 24 24"><path fill="none" stroke="{icon_color}" stroke-width="2" d="M4 4 L20 4 L20 20 L4 20 Z"></path></svg>'
        self.restore_svg = f'<svg viewBox="0 0 24 24"><path fill="none" stroke="{icon_color}" stroke-width="2" d="M9 9 L20 9 L20 20 L9 20 Z M4 4 L15 4 L15 15 L4 15 Z"></path></svg>'
        close_svg = f'<svg viewBox="0 0 24 24"><path fill="none" stroke="{icon_color}" stroke-width="2" d="M6 6 L18 18 M18 6 L6 18"></path></svg>'

        self.minimize_icon = self._create_svg_icon(minimize_svg)
        self.maximize_icon = self._create_svg_icon(maximize_svg)
        self.restore_icon = self._create_svg_icon(self.restore_svg)
        self.close_icon = self._create_svg_icon(close_svg)

        self.minimize_action = QAction(self.minimize_icon, "Minimize", self)
        self.minimize_action.triggered.connect(self.showMinimized)
        self.maximize_action = QAction(self.maximize_icon, "Maximize", self)
        self.maximize_action.triggered.connect(self.toggle_maximize_restore)
        self.close_action = QAction(self.close_icon, "Close", self)
        self.close_action.setObjectName("close_button")
        self.close_action.triggered.connect(self.close)

        self.tool_bar.addAction(self.minimize_action)
        self.tool_bar.addAction(self.maximize_action)
        self.tool_bar.addAction(self.close_action)

    def _create_status_bar(self):
        self.statusbar = self.statusBar()
        self.filename_label = QLabel()
        self.statusbar.addWidget(self.filename_label, 1)
        self.dimensions_label = QLabel("  ")
        self.filesize_label = QLabel("  ")
        self.zoom_label = QLabel(" 100% ")
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 800)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.setToolTip("Adjust Zoom Level")
        self.zoom_slider.valueChanged.connect(self.slider_zoom)

        self.statusbar.addPermanentWidget(self.dimensions_label)
        self.statusbar.addPermanentWidget(self.filesize_label)
        self.statusbar.addPermanentWidget(self.zoom_label)
        self.statusbar.addPermanentWidget(self.zoom_slider)

    def _create_filmstrip(self):
        self.filmstrip_scroll_area = QScrollArea()
        self.filmstrip_scroll_area.setWidgetResizable(True)
        self.filmstrip_scroll_area.setFixedHeight(120)
        self.filmstrip_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.filmstrip_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.filmstrip_scroll_area.setStyleSheet("QScrollArea { background-color: #202020; border-top: 1px solid #555; }")

        self.filmstrip_widget = QWidget()
        self.filmstrip_layout = QHBoxLayout(self.filmstrip_widget)
        self.filmstrip_layout.setContentsMargins(5, 5, 5, 5)
        self.filmstrip_layout.setSpacing(10)
        
        self.filmstrip_scroll_area.setWidget(self.filmstrip_widget)
        self.filmstrip_scroll_area.hide()

    def _populate_filmstrip(self):
        while self.filmstrip_layout.count():
            child = self.filmstrip_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.current_folder_files:
            return

        for index, file_path in enumerate(self.current_folder_files):
            thumbnail_button = QPushButton()
            thumbnail_button.setFixedSize(130, 100)
            
            # --- MODIFIKASI: Tampilkan ikon video untuk file video ---
            _, ext = os.path.splitext(file_path)
            if ext.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                video_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DriveDVDIcon)
                thumbnail_button.setIcon(video_icon)
                thumbnail_button.setIconSize(QSize(64, 64))
            else:
                pixmap = QPixmap(file_path)
                scaled_pixmap = pixmap.scaled(130, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                thumbnail_button.setIcon(QIcon(scaled_pixmap))
                thumbnail_button.setIconSize(QSize(120, 90))

            thumbnail_button.setToolTip(os.path.basename(file_path))
            
            if index == self.current_file_index:
                thumbnail_button.setStyleSheet("background-color: #5E81AC; border: 1px solid #88C0D0;")
            else:
                thumbnail_button.setStyleSheet("background-color: #3c3c3c;")

            thumbnail_button.clicked.connect(partial(self.open_file, file_path))
            self.filmstrip_layout.addWidget(thumbnail_button)
            
        self.filmstrip_layout.addStretch()

    def _update_action_states(self, enabled):
        is_image = enabled and self.current_media_type == 'image'
        is_video = enabled and self.current_media_type == 'video'

        if self.slideshow_running:
            actions_to_disable = [
                self.open_action, self.save_as_action, self.copy_action, self.open_explorer_action,
                self.zoom_in_action, self.zoom_out_action, self.reset_zoom_action,
                self.rotate_left_action, self.rotate_right_action, self.flip_horizontal_action,
                self.flip_vertical_action, self.print_action, self.save_pdf_action, self.search_image_action,
                self.set_wallpaper_action, self.prev_action, self.next_action,
                self.undo_action, self.redo_action, self.crop_action, self.resize_action
            ]
            for action in actions_to_disable:
                action.setEnabled(False)
            self.zoom_slider.setEnabled(False)
            self.slideshow_action.setEnabled(True) 
            return

        # Actions for any media
        self.open_explorer_action.setEnabled(enabled)
        self.fullscreen_action.setEnabled(enabled)
        self.file_info_action.setEnabled(enabled)
        self.image_search.setEnabled(enabled)
        
        # Image-only actions
        image_actions = [
            self.save_as_action, self.copy_action, self.zoom_in_action, self.zoom_out_action,
            self.reset_zoom_action, self.rotate_left_action, self.rotate_right_action,
            self.flip_horizontal_action, self.flip_vertical_action, self.print_action,
            self.save_pdf_action, self.set_wallpaper_action, self.crop_action,
            self.resize_action, self.visual_search_action
        ]
        for action in image_actions:
            action.setEnabled(is_image)

        self.zoom_slider.setEnabled(is_image)
        self.undo_action.setEnabled(is_image and bool(self.undo_stack))
        self.redo_action.setEnabled(is_image and bool(self.redo_stack))
        
        # Navigation and slideshow
        self.prev_action.setEnabled(enabled and self.current_file_index > 0)
        self.next_action.setEnabled(enabled and self.current_file_index < len(self.current_folder_files) - 1)
        self.slideshow_action.setEnabled(enabled and len(self.current_folder_files) > 1)
        self.filmstrip_action.setEnabled(enabled)
        
    # --- REFAKTOR: Fungsi utama untuk membuka semua jenis file ---
    def open_file(self, file_path=None):
        if file_path and self.file_path == file_path: return

        if not file_path:
            self.stop_slideshow()
            # --- MODIFIKASI: Filter file dialog untuk semua format yang didukung ---
            img_filter = "Image Files (" + " ".join([f"*{ext}" for ext in SUPPORTED_IMAGE_EXTENSIONS]) + ")"
            vid_filter = "Video Files (" + " ".join([f"*{ext}" for ext in SUPPORTED_VIDEO_EXTENSIONS]) + ")"
            all_filter = "All Supported Files (" + " ".join([f"*{ext}" for ext in ALL_SUPPORTED_EXTENSIONS]) + ")"
            
            file_path, _ = QFileDialog.getOpenFileName(self, "Open File", self.last_directory, f"{all_filter};;{img_filter};;{vid_filter};;All Files (*)")
        
        if file_path:
            self.media_player.stop() # Hentikan media sebelumnya
            self.last_directory = os.path.dirname(file_path)
            
            if self.is_in_crop_mode:
                self.crop_action.setChecked(False)
        
            self.file_path = file_path
            
            # --- PENAMBAHAN: Tentukan jenis file dan panggil loader yang sesuai ---
            _, ext = os.path.splitext(file_path)
            if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                self._load_image(file_path)
            elif ext.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                self._load_video(file_path)
            else:
                self.statusbar.showMessage(f"Error: Unsupported file format {ext}", 5000)
                return

            self.setWindowTitle(f'{os.path.basename(self.file_path)} - Macan Viewer')
            
            is_new_folder = not self.current_folder_files or os.path.dirname(file_path) != os.path.dirname(self.current_folder_files[0])
            if is_new_folder:
                self._load_current_folder_files()
                self._populate_filmstrip()
            else:
                self.current_file_index = self.current_folder_files.index(self.file_path)
                for i in range(self.filmstrip_layout.count() -1):
                    btn = self.filmstrip_layout.itemAt(i).widget()
                    if i == self.current_file_index:
                        btn.setStyleSheet("background-color: #5E81AC; border: 1px solid #88C0D0;")
                    else:
                        btn.setStyleSheet("background-color: #3c3c3c;")

            self._update_action_states(True)
            self.toggle_filmstrip(self.filmstrip_action.isChecked())

    # --- PENAMBAHAN: Logika terpisah untuk memuat gambar ---
    def _load_image(self, file_path):
        self.current_media_type = 'image'
        self.cv_image = cv2.imread(file_path)
        if self.cv_image is None:
            self.statusbar.showMessage(f"Error: Failed to open image {os.path.basename(file_path)}", 5000)
            self.current_media_type = None
            return
            
        self.display_image = self.cv_image.copy()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.fit_to_window = True 
        
        self.media_stack.setCurrentWidget(self.scroll_area) # Tampilkan view gambar
        
        self._display_image()
        self._update_status_bar()

    # --- PENAMBAHAN: Logika terpisah untuk memuat video ---
    def _load_video(self, file_path):
        self.current_media_type = 'video'
        self.cv_image = None
        self.display_image = None
        
        self.media_stack.setCurrentWidget(self.video_widget) # Tampilkan view video
        
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self.media_player.play()
        self._update_status_bar()

    def open_in_file_explorer(self):
        if not self.file_path: return
        normalized_path = os.path.normpath(self.file_path)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{normalized_path}"')
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-R", normalized_path])
            else:
                folder = os.path.dirname(normalized_path)
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            self.statusbar.showMessage(f"Failed to open folder: {e}", 5000)
    
    def show_about_dialog(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About Macan Image Viewer")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        # --- MODIFIKASI: Memperbarui versi ---
        msg_box.setText("<b>Macan Image Viewer v2.8.0 (Preset Update)</b><br><br>" 
                          "Macan Viewer adalah aplikasi image & video viewer modern dan serbaguna yang dirancang "
                          "untuk kecepatan dan efisiensi. Dibuat dengan Python, PyQt6, dan didukung oleh "
                          "OpenCV, Macan Viewer memungkinkan Anda untuk melihat, mengedit, dan mengelola "
                          "koleksi media Anda dengan mudah, cepat, dan bebas hambatan."
                          "<br><br>©2025 - Danx Exodus")
        msg_box.setStyleSheet("QMessageBox { background-color: #f0f0f0; } QLabel { color: #1e1e1e; }")
        msg_box.exec()

    def set_as_wallpaper(self):
        if self.current_media_type != 'image' or self.file_path is None:
            self.statusbar.showMessage("No image to set as wallpaper.", 3000)
            return
        
        path = os.path.abspath(self.file_path)
        system = platform.system()
        
        try:
            if system == "Windows":
                ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
                self.statusbar.showMessage("Wallpaper set successfully.", 3000)
            elif system == "Darwin":
                subprocess.run(f'osascript -e \'tell application "Finder" to set desktop picture to POSIX file "{path}"\'', shell=True, check=True)
                self.statusbar.showMessage("Wallpaper set successfully.", 3000)
            else:
                desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
                if "gnome" in desktop_env or "cinnamon" in desktop_env:
                    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"], check=True)
                    self.statusbar.showMessage("Wallpaper set for GNOME/Cinnamon.", 3000)
                else:
                    self.statusbar.showMessage("Auto set wallpaper not supported on this desktop environment.", 5000)
        except Exception as e:
            self.statusbar.showMessage(f"Failed to set wallpaper: {e}", 5000)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_action.setIcon(self._create_svg_icon(self.fullscreen_svg))
        else:
            self.showFullScreen()
            self.fullscreen_action.setIcon(self._create_svg_icon(self.exit_fullscreen_svg))
            
    def cancel_crop(self):
        self.is_cropping = False
        self.rubber_band.hide()
        self.crop_button.hide()
        self.image_label.unsetCursor()
        self.statusbar.showMessage("Crop cancelled.", 2000)
        if self.is_in_crop_mode:
            self.crop_action.setChecked(False)

    def open_search(self):        
        self.search_image = ImageSearchApp()        
        self.search_image.show()
        self.search_image.activateWindow()
        
    def open_converter(self):        
        if self.converter_widget is None or not self.converter_widget.isVisible():
            self.converter_widget = ImageConverterWidget()        
        self.converter_widget.show()
        self.converter_widget.activateWindow()
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(any(url.toLocalFile().lower().endswith(ext) for ext in ALL_SUPPORTED_EXTENSIONS) for url in urls):
                event.acceptProposedAction()

    def dropEvent(self, event):
        self.stop_slideshow()
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if any(file_path.lower().endswith(ext) for ext in ALL_SUPPORTED_EXTENSIONS):
                self.open_file(file_path)
                break

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            # --- MODIFIKASI: Escape akan menghentikan slideshow fullscreen ---
            if self.slideshow_running:
                self.stop_slideshow()
            elif self.is_cropping:
                self.cancel_crop()
            elif self.is_in_crop_mode:
                self.crop_action.setChecked(False)
            elif self.isFullScreen():
                self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def is_pannable(self):
        return self.current_media_type == 'image' and \
               (self.scroll_area.horizontalScrollBar().isVisible() or \
               self.scroll_area.verticalScrollBar().isVisible())

    def image_mouse_press(self, event):
        if self.current_media_type != 'image' or self.display_image is None: return
        self.stop_slideshow()
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_in_crop_mode:
                self.is_cropping = True
                self.origin_point = event.position().toPoint()
                self.rubber_band.setGeometry(QRect(self.origin_point, QSize()))
                self.rubber_band.show()
                self.crop_button.hide()
            elif self.is_pannable():
                self.is_panning = True
                self.pan_last_pos = event.pos()
                self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)

    def image_mouse_move(self, event):
        if self.is_panning:
            delta = event.pos() - self.pan_last_pos
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            self.pan_last_pos = event.pos()
        elif self.is_cropping:
            self.rubber_band.setGeometry(QRect(self.origin_point, event.position().toPoint()).normalized())
        elif self.is_in_crop_mode:
            self.image_label.setCursor(Qt.CursorShape.CrossCursor)
        elif self.is_pannable():
            self.image_label.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.image_label.unsetCursor()
            
    def image_mouse_release(self, event):
        if self.is_panning:
            self.is_panning = False
            self.image_label.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.is_cropping:
            if self.origin_point == event.position().toPoint():
                self.cancel_crop()
                return

            self.is_cropping = False
            selection_rect = self.rubber_band.geometry()
            if not self.image_label.pixmap(): return
            pixmap_rect = self.image_label.pixmap().rect()
            
            pixmap_display_x = (self.image_label.width() - pixmap_rect.width()) / 2
            pixmap_display_y = (self.image_label.height() - pixmap_rect.height()) / 2

            relative_x = selection_rect.x() - pixmap_display_x
            relative_y = selection_rect.y() - pixmap_display_y
            
            scaled_selection = QRect(int(relative_x), int(relative_y), selection_rect.width(), selection_rect.height())
            scaled_selection = scaled_selection.intersected(pixmap_rect)
            
            if scaled_selection.width() > 5 and scaled_selection.height() > 5:
                img_h, img_w, _ = self.display_image.shape
                scale_x = img_w / pixmap_rect.width() if pixmap_rect.width() > 0 else 0
                scale_y = img_h / pixmap_rect.height() if pixmap_rect.height() > 0 else 0

                self.crop_x = int(scaled_selection.x() * scale_x)
                self.crop_y = int(scaled_selection.y() * scale_y)
                self.crop_w = int(scaled_selection.width() * scale_x)
                self.crop_h = int(scaled_selection.height() * scale_y)
                
                self.crop_button.show()
                pos_x = self.scroll_area.pos().x() + selection_rect.center().x() - self.crop_button.width() // 2
                pos_y = self.scroll_area.pos().y() + selection_rect.bottom() + 10
                self.crop_button.move(pos_x, pos_y)
                self.crop_button.raise_()
            else:
                self.rubber_band.hide()
                self.crop_button.hide()

    def perform_crop(self):
        if self.display_image is None or self.rubber_band.isHidden(): return
        self._push_to_undo_stack()
        try:
            self.crop_y = max(0, self.crop_y)
            self.crop_x = max(0, self.crop_x)
            
            cropped_img = self.display_image[self.crop_y:self.crop_y + self.crop_h, self.crop_x:self.crop_x + self.crop_w]
            self.display_image = cropped_img
            self.fit_to_window = True
            self._display_image()
            self.statusbar.showMessage("Image cropped successfully.", 3000)
        finally:
            self.rubber_band.hide()
            self.crop_button.hide()
            self.crop_action.setChecked(False)
            
    def toggle_crop_mode(self, checked):
        self.is_in_crop_mode = checked
        if checked:
            self.stop_slideshow()
            self.statusbar.showMessage("Crop mode enabled. Drag to select an area.", 3000)
            self.image_label.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.statusbar.showMessage("Crop mode disabled.", 2000)
            self.cancel_crop()

    def toggle_slideshow(self):
        if self.slideshow_running:
            self.stop_slideshow()
        else:
            self.start_slideshow()

    # --- REVISI: Logika memulai slideshow ---
    def start_slideshow(self):
        if len(self.current_folder_files) < 2:
            self.statusbar.showMessage("Not enough files in the folder for a slideshow.", 3000)
            return
            
        if self.is_in_crop_mode:
            self.crop_action.setChecked(False)
            
        self.slideshow_running = True
        
        # Simpan state jendela
        self.pre_slideshow_state = self.windowState()
        self.pre_slideshow_geometry = self.geometry()
        
        # Sembunyikan UI dan masuk ke fullscreen
        self.tool_bar.hide()
        self.statusbar.hide()
        self.filmstrip_scroll_area.hide()
        self.showFullScreen()
        
        self.slideshow_action.setIcon(self._create_svg_icon(self.pause_svg))
        self.slideshow_action.setText("Stop Slideshow")
        self.statusbar.showMessage("Slideshow started...", 2000)
        
        self.slideshow_timer.timeout.connect(self.advance_slideshow)
        self.slideshow_timer.start(3000)
        self._update_action_states(True)

    # --- REVISI: Logika menghentikan slideshow ---
    def stop_slideshow(self):
        if not self.slideshow_running:
            return

        self.slideshow_timer.stop()
        self.media_player.stop() # Hentikan video jika sedang berjalan
        try:
            self.slideshow_timer.timeout.disconnect(self.advance_slideshow)
        except TypeError:
            pass 
        self.slideshow_running = False
        
        # Kembalikan UI dan state jendela
        self.tool_bar.show()
        self.statusbar.show()
        if self.filmstrip_action.isChecked():
            self.filmstrip_scroll_area.show()
        
        # Keluar dari fullscreen dan kembalikan ke state sebelumnya
        self.setWindowState(self.pre_slideshow_state)
        self.setGeometry(self.pre_slideshow_geometry)

        self.slideshow_action.setIcon(self._create_svg_icon(self.play_svg))
        self.slideshow_action.setText("Start Slideshow")
        self.statusbar.showMessage("Slideshow stopped.", 2000)
        self._update_action_states(True)

    def advance_slideshow(self):
        if not self.current_folder_files:
            self.stop_slideshow()
            return
        
        next_index = self.current_file_index + 1
        
        # --- REVISI: Hentikan slideshow setelah satu putaran penuh ---
        if next_index >= len(self.current_folder_files):
            self.stop_slideshow()
            return

        self.current_file_index = next_index
        self.open_file(self.current_folder_files[self.current_file_index])
        
    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.maximize_action.setIcon(self.maximize_icon)
        else:
            self.showMaximized()
            self.maximize_action.setIcon(self.restore_icon)

    def show_context_menu(self, pos):
        if self.file_path is None: return
        
        context_menu = QMenu(self)

        collage_action = context_menu.addAction("Create Photo Collage...")
        collage_action.triggered.connect(self.open_collage_tool)
        collage_action = context_menu.addAction("Adjustment")
        collage_action.triggered.connect(self.open_brightness_contrass_gamma)
        context_menu.addSeparator()

        if self.current_media_type == 'image':
            # --- PENAMBAHAN: Menu Preset ---
            presets_menu = context_menu.addMenu("Presets")
            manage_presets_action = presets_menu.addAction("Manage Presets...")
            manage_presets_action.triggered.connect(self.open_manage_presets_dialog)
            presets_menu.addSeparator()
            
            # Populate preset list
            available_presets = self.preset_manager.get_presets()
            if not available_presets:
                no_preset_action = presets_menu.addAction("No presets found")
                no_preset_action.setEnabled(False)
            else:
                for name, data in sorted(available_presets.items()):
                    preset_action = presets_menu.addAction(name)
                    preset_action.triggered.connect(partial(self._apply_preset, data['settings']))
            
            effects_menu = context_menu.addMenu("Effects")
            
            # --- Menu Efek Warna & Artistik ---
            artistic_menu = effects_menu.addMenu("Artistic")
            artistic_menu.addAction("Grayscale", lambda: self.apply_effect(self.image_effects.apply_grayscale))
            artistic_menu.addAction("Sepia", lambda: self.apply_effect(self.image_effects.apply_sepia))
            artistic_menu.addAction("Invert Colors", lambda: self.apply_effect(self.image_effects.apply_invert))
            artistic_menu.addAction("Pencil Sketch", lambda: self.apply_effect(self.image_effects.apply_sketch))
            artistic_menu.addAction("Cartoon", lambda: self.apply_effect(self.image_effects.apply_cartoon))
            artistic_menu.addAction("Solarize", lambda: self.apply_effect(self.image_effects.apply_solarize)) 
            artistic_menu.addAction("Posterize", lambda: self.apply_effect(self.image_effects.apply_posterize))           
            artistic_menu.addAction("Pixelate", lambda: self.apply_effect(self.image_effects.apply_pixelate))
            artistic_menu.addAction("Thermal", lambda: self.apply_effect(self.image_effects.apply_thermal))

            
            # --- Menu Efek Filter & Penyesuaian ---
            filters_menu = effects_menu.addMenu("Filters & Adjustments")
            filters_menu.addAction("Blur", lambda: self.apply_effect(self.image_effects.apply_blur))
            filters_menu.addAction("Sharpen", lambda: self.apply_effect(self.image_effects.apply_sharpen))
            filters_menu.addAction("Emboss", lambda: self.apply_effect(self.image_effects.apply_emboss))
            filters_menu.addAction("Canny Edges", lambda: self.apply_effect(self.image_effects.apply_canny_edges))
            filters_menu.addAction("Vignette", lambda: self.apply_effect(self.image_effects.apply_vignette))

            # --- Menu Efek Tone Warna ---
            tone_menu = effects_menu.addMenu("Color Tone")
            tone_menu.addAction("Cool Tone", lambda: self.apply_effect(self.image_effects.apply_cool))
            tone_menu.addAction("Warm Tone", lambda: self.apply_effect(self.image_effects.apply_warm))
            tone_menu.addAction("Infrared (Simulation)", lambda: self.apply_effect(self.image_effects.apply_infrared))
                       
            context_menu.addSeparator()

            context_menu.addAction(self.save_as_action)
            context_menu.addAction(self.print_action)
            context_menu.addSeparator()
            context_menu.addAction(self.resize_action)
            context_menu.addAction(self.set_wallpaper_action)
            context_menu.addSeparator()
        
        context_menu.addAction(self.slideshow_action)
        context_menu.addAction(self.filmstrip_action)
        context_menu.addSeparator()
        context_menu.addAction(self.file_info_action)
        
        if self.current_media_type == 'image':
            context_menu.addAction(self.visual_search_action)
        
        context_menu.exec(self.mapToGlobal(pos))
        
    def show_file_info(self):
        if self.file_path and os.path.exists(self.file_path):
            size_bytes = os.path.getsize(self.file_path)
            filesize_str = f"{size_bytes/1024:.1f} KB" if size_bytes < 1024**2 else f"{size_bytes/1024**2:.1f} MB"
            
            info_text = (
                f"<b>Filename:</b> {os.path.basename(self.file_path)}<br>"
                f"<b>Path:</b> {os.path.dirname(self.file_path)}<br>"
            )
            
            if self.current_media_type == 'image' and self.cv_image is not None:
                h, w, _ = self.cv_image.shape
                info_text += f"<b>Dimensions:</b> {w} x {h} pixels<br>"

            info_text += f"<b>File Size:</b> {filesize_str} ({size_bytes:,} bytes)"
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("File Info")
            msg_box.setTextFormat(Qt.TextFormat.RichText)
            msg_box.setText(info_text)
            msg_box.setStyleSheet("QLabel { color: #000000; }")
            msg_box.exec()

    def apply_effect(self, effect_function):
        """Generic function to apply an image effect."""
        if self.display_image is None: return
        self._push_to_undo_stack()
        self.statusbar.showMessage(f"Applying {effect_function.__name__.replace('apply_', '')} effect...", 2000)
        # Terapkan efeknya
        self.display_image = effect_function(self.display_image)
        self.fit_to_window = False # Efek mungkin mengubah ukuran, jadi nonaktifkan fit
        self._display_image()
        self.statusbar.showMessage("Effect applied successfully.", 3000)    
            
    def open_collage_tool(self):
        """Opens the photo collage dialog."""
        dialog = CollageDialog(self)
        dialog.exec()
    
    def open_brightness_contrass_gamma(self):
        if self.display_image is None: return # Tambahkan pengecekan ini
    
        dialog = AdjustmentsDialog(self.display_image, self) # <-- PERUBAHAN DI SINI
        if dialog.exec():
            self._push_to_undo_stack()
            self.display_image = dialog.get_result_image()
            self._display_image()
            self.statusbar.showMessage("Adjustments applied.", 3000)

    # --- PENAMBAHAN: Fungsi untuk membuka dialog manajemen preset ---
    def open_manage_presets_dialog(self):
        dialog = ManagePresetsDialog(self.preset_manager, self)
        dialog.exec()
    
    # --- PENAMBAHAN: Fungsi untuk menerapkan preset yang dipilih ---
    def _apply_preset(self, settings):
        if self.display_image is None:
            return
        
        self._push_to_undo_stack()
        self.statusbar.showMessage("Applying preset...", 2000)
        
        try:
            self.display_image = apply_preset(self.display_image, settings)
            self._display_image()
            self.statusbar.showMessage("Preset applied successfully.", 3000)
        except Exception as e:
            self.statusbar.showMessage(f"Error applying preset: {e}", 5000)
            QMessageBox.critical(self, "Preset Error", f"An error occurred while applying the preset:\n{e}")
            # Rollback on error
            self.undo_image()


    def resize_image(self):
        if self.current_media_type != 'image' or self.display_image is None or not self.file_path: return
        
        original_size = (self.display_image.shape[1], self.display_image.shape[0])
        filesize = os.path.getsize(self.file_path)
        
        dialog = ResizeDialog(original_size, filesize, self)
        if dialog.exec():
            values = dialog.get_values()
            new_width, new_height = values["width"], values["height"]
            
            if new_width <= 0 or new_height <= 0:
                QMessageBox.warning(self, "Invalid Size", "Width and height must be positive values.")
                return

            try:
                resized_image = cv2.resize(self.display_image, (new_width, new_height), interpolation=cv2.INTER_AREA)
                default_filename = f"{os.path.splitext(os.path.basename(self.file_path))[0]}_resized.{values['format']}"
                filter_str = f"{values['format'].upper()} (*.{values['format']})"
                save_path, _ = QFileDialog.getSaveFileName(self, "Save Resized Image As...", os.path.join(self.last_directory, default_filename), filter_str)
                
                if save_path:
                    self.last_directory = os.path.dirname(save_path)
                    params = []
                    if values['format'] in ['jpg', 'jpeg']:
                        params = [cv2.IMWRITE_JPEG_QUALITY, values['quality']]
                    elif values['format'] == 'webp':
                        params = [cv2.IMWRITE_WEBP_QUALITY, values['quality']]
                    
                    cv2.imwrite(save_path, resized_image, params)
                    self.statusbar.showMessage(f"Resized image saved to {save_path}", 4000)
                    
            except Exception as e:
                QMessageBox.critical(self, "Resize Error", f"An error occurred while resizing or saving the image:\n{e}")

    def visual_search(self):
        if self.current_media_type == 'image' and self.file_path:
            self.statusbar.showMessage("Uploading image to Google Lens...", 5000)
            
            # URL endpoint Google Lens untuk upload gambar
            lens_url = "https://lens.google.com/upload"
            
            try:
                # Buka file gambar dalam mode binary 'rb'
                with open(self.file_path, 'rb') as image_file:
                    # Siapkan data untuk multipart/form-data POST request.
                    # 'encoded_image' adalah nama field yang diharapkan oleh Google Lens.
                    files = {'encoded_image': (os.path.basename(self.file_path), image_file)}
                    
                    # Kirim POST request. Library requests akan menangani redirect secara otomatis.
                    # Timeout ditambahkan untuk mencegah aplikasi hang jika koneksi lambat.
                    response = requests.post(lens_url, files=files, timeout=15)
                    
                    # Cek jika request gagal (misal: error 4xx atau 5xx)
                    response.raise_for_status() 
                    
                    # Dapatkan URL akhir setelah redirect, ini adalah URL halaman hasil pencarian
                    results_url = response.url
                    
                    # Buka URL hasil pencarian di browser default pengguna
                    webbrowser.open(results_url)
                    
                    self.statusbar.showMessage("Search results opened in browser.", 4000)

            except requests.exceptions.RequestException as e:
                # Tangani error jaringan (misal: tidak ada koneksi, timeout, dll)
                error_message = f"Failed to connect to Google Lens: {e}"
                QMessageBox.critical(self, "Network Error", error_message)
                self.statusbar.showMessage(error_message, 5000)
            except Exception as e:
                # Tangani error lainnya
                error_message = f"An unexpected error occurred: {e}"
                QMessageBox.critical(self, "Error", error_message)
                self.statusbar.showMessage(error_message, 5000)
            
    def toggle_filmstrip(self, checked):
        self.filmstrip_scroll_area.setVisible(checked)
        self.filmstrip_action.setChecked(checked)

    # --- MODIFIKASI: Cari semua file media yang didukung ---
    def _load_current_folder_files(self):
        if self.file_path:
            folder = os.path.dirname(self.file_path)
            all_files = []
            for ext in ALL_SUPPORTED_EXTENSIONS:
                all_files.extend(glob(os.path.join(folder, f"*{ext}")))
                all_files.extend(glob(os.path.join(folder, f"*{ext.upper()}")))

            # Hilangkan duplikat dan urutkan
            self.current_folder_files = sorted(list(set(all_files)), key=os.path.basename)

            try:
                self.current_file_index = self.current_folder_files.index(self.file_path)
            except ValueError:
                self.current_file_index = -1
        else:
            self.current_folder_files = []
            self.current_file_index = -1
        self._update_action_states(self.file_path is not None)

    def _display_image(self):
        if self.display_image is None:
            self.image_label.clear()
            return

        # --- AWAL PERUBAHAN ---
        h_orig, w_orig, *channels = self.display_image.shape
        num_channels = channels[0] if channels else 3 # Default ke 3 jika tidak ada channel info

        if num_channels == 4:
            # Handle gambar BGRA (dengan alpha)
            rgb_image = cv2.cvtColor(self.display_image, cv2.COLOR_BGRA2RGBA)
            bytes_per_line = num_channels * w_orig
            qt_image = QImage(rgb_image.data, w_orig, h_orig, bytes_per_line, QImage.Format.Format_RGBA8888)
        else:
            # Handle gambar BGR standar
            rgb_image = cv2.cvtColor(self.display_image, cv2.COLOR_BGR2RGB)
            bytes_per_line = 3 * w_orig
            qt_image = QImage(rgb_image.data, w_orig, h_orig, bytes_per_line, QImage.Format.Format_RGB888)
        # --- AKHIR PERUBAHAN ---

        pixmap = QPixmap.fromImage(qt_image)
        if self.fit_to_window:
            scroll_area_size = self.scroll_area.size()
            if w_orig > scroll_area_size.width() or h_orig > scroll_area_size.height():
                scaled_pixmap = pixmap.scaled(scroll_area_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            else:
                scaled_pixmap = pixmap
            if w_orig > 0: self.zoom_factor = scaled_pixmap.width() / w_orig
        else:
            display_w = int(w_orig * self.zoom_factor)
            display_h = int(h_orig * self.zoom_factor)
            scaled_pixmap = pixmap.scaled(display_w, display_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.size())
        self._update_status_bar()

    # --- REVISI: Perbarui status bar untuk gambar dan video ---
    def _update_status_bar(self):
        if self.file_path and os.path.exists(self.file_path):
            self.filename_label.setText(f" {os.path.basename(self.file_path)}")
            size_bytes = os.path.getsize(self.file_path)
            filesize_str = f"{size_bytes/1024:.1f} KB" if size_bytes < 1024**2 else f"{size_bytes/1024**2:.1f} MB"
            self.filesize_label.setText(f" {filesize_str} ")
            
            if self.current_media_type == 'image' and self.cv_image is not None:
                h, w, _ = self.display_image.shape
                self.dimensions_label.setText(f" {w} x {h} ")
                self.zoom_label.setText(f" {int(self.zoom_factor * 100)}% ")
                new_slider_value = int(self.zoom_factor * 100)
                if self.zoom_slider.value() != new_slider_value:
                    self.zoom_slider.setValue(new_slider_value)
            elif self.current_media_type == 'video':
                self.dimensions_label.setText(" Video ")
                self.zoom_label.setText(" ")
        else:
            self.filename_label.setText("")
            self.dimensions_label.setText(" ")
            self.filesize_label.setText(" ")
            self.zoom_label.setText(" ")

    def _push_to_undo_stack(self):
        if self.display_image is not None:
            self.undo_stack.append(self.display_image.copy())
            self.redo_stack.clear()
            self._update_action_states(True)

    def zoom_in(self):
        if self.current_media_type != 'image' or self.display_image is None: return
        self.fit_to_window = False
        self.zoom_factor = min(self.zoom_factor * 1.25, 8.0)
        self._display_image()

    def zoom_out(self):
        if self.current_media_type != 'image' or self.display_image is None: return
        self.fit_to_window = False
        self.zoom_factor = max(self.zoom_factor * 0.8, 0.1)
        self._display_image()

    def reset_zoom(self):
        if self.current_media_type != 'image' or self.display_image is None: return
        self.fit_to_window = True
        self._display_image()

    def slider_zoom(self, value):
        if self.current_media_type != 'image' or self.display_image is None: return
        self.fit_to_window = False
        self.zoom_factor = value / 100.0
        self._display_image()

    def rotate_left(self):
        if self.display_image is not None:
            self._push_to_undo_stack()
            self.display_image = cv2.rotate(self.display_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            self.fit_to_window = True
            self._display_image()

    def rotate_right(self):
        if self.display_image is not None:
            self._push_to_undo_stack()
            self.display_image = cv2.rotate(self.display_image, cv2.ROTATE_90_CLOCKWISE)
            self.fit_to_window = True
            self._display_image()

    def flip_image(self, flip_code):
        if self.display_image is not None:
            self._push_to_undo_stack()
            self.display_image = cv2.flip(self.display_image, flip_code)
            self._display_image()

    def save_image_as(self):
        if self.display_image is None: return
        default_path = os.path.join(self.last_directory, os.path.basename(self.file_path) if self.file_path else "")
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Image As...", default_path,"PNG (*.png);;JPG (*.jpg);;BMP (*.bmp)")
        if file_path:
            try:
                self.last_directory = os.path.dirname(file_path)
                cv2.imwrite(file_path, self.display_image)
                self.statusbar.showMessage(f"Image saved to {file_path}", 3000)
            except Exception as e:
                self.statusbar.showMessage(f"Failed to save image: {e}", 5000)

    def copy_image_to_clipboard(self):
        if self.current_media_type == 'image' and self.image_label.pixmap():
            QApplication.clipboard().setPixmap(self.image_label.pixmap())
            self.statusbar.showMessage("Image copied to clipboard", 3000)

    # --- REFAKTOR: Ganti nama fungsi navigasi ---
    def show_previous_file(self):
        if self.current_file_index > 0:
            self.current_file_index -= 1
            self.open_file(self.current_folder_files[self.current_file_index])

    def show_next_file(self):
        if self.current_file_index < len(self.current_folder_files) - 1:
            self.current_file_index += 1
            self.open_file(self.current_folder_files[self.current_file_index])

    def undo_image(self):
        if self.undo_stack:
            self.redo_stack.append(self.display_image.copy())
            self.display_image = self.undo_stack.pop()
            self._display_image()
            self._update_action_states(True)

    def redo_image(self):
        if self.redo_stack:
            self.undo_stack.append(self.display_image.copy())
            self.display_image = self.redo_stack.pop()
            self._display_image()
            self._update_action_states(True)

    def print_image(self):
        if self.current_media_type != 'image' or self.image_label.pixmap() is None: return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            painter = QPainter()
            painter.begin(printer)
            rect = painter.viewport()
            pixmap = self.image_label.pixmap()
            size = pixmap.size()
            size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pixmap.rect())
            painter.drawPixmap(0, 0, pixmap)
            painter.end()

    def save_as_pdf(self):
        if self.current_media_type != 'image' or self.image_label.pixmap() is None: return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save as PDF", "", "PDF Files (*.pdf)")
        if file_path:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            painter = QPainter()
            painter.begin(printer)
            rect = painter.viewport()
            pixmap = self.image_label.pixmap()
            size = pixmap.size()
            size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pixmap.rect())
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            self.statusbar.showMessage(f"Saved as PDF to {file_path}", 3000)

    def get_edge(self, pos):
        rect = self.rect()
        margin = self.resize_margin
        if pos.y() < margin:
            if pos.x() < margin: return Qt.CursorShape.SizeFDiagCursor
            if pos.x() > rect.right() - margin: return Qt.CursorShape.SizeBDiagCursor
            return Qt.CursorShape.SizeVerCursor
        if pos.y() > rect.bottom() - margin:
            if pos.x() < margin: return Qt.CursorShape.SizeBDiagCursor
            if pos.x() > rect.right() - margin: return Qt.CursorShape.SizeFDiagCursor
            return Qt.CursorShape.SizeVerCursor
        if pos.x() < margin: return Qt.CursorShape.SizeHorCursor
        if pos.x() > rect.right() - margin: return Qt.CursorShape.SizeHorCursor
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.resize_edge = self.get_edge(pos)
            if self.resize_edge:
                self.is_resizing = True
                self.old_pos = event.globalPosition().toPoint()
            elif self.tool_bar.geometry().contains(pos):
                self.old_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self.is_resizing and self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.old_pos = event.globalPosition().toPoint()
            geom = self.geometry()
            if self.resize_edge in (Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor):
                if pos.y() < self.resize_margin: geom.setTop(geom.top() + delta.y())
                else: geom.setBottom(geom.bottom() + delta.y())
            if self.resize_edge in (Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor):
                if pos.x() < self.resize_margin: geom.setLeft(geom.left() + delta.x())
                else: geom.setRight(geom.right() + delta.x())
            self.setGeometry(geom)
            event.accept()
        elif event.buttons() == Qt.MouseButton.LeftButton and self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            edge = self.get_edge(pos)
            if edge: self.setCursor(QCursor(edge))
            else: self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        self.is_resizing = False
        self.resize_edge = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() < self.tool_bar.height():
                self.toggle_maximize_restore()
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_media_type == 'image' and self.cv_image is not None and self.fit_to_window:
             self._display_image()
    
    def load_settings(self):
        geometry = self.settings.value("geometry", QByteArray())
        if geometry.size() > 0:
            self.restoreGeometry(geometry)
        else:
            self.center_window()
        self.last_directory = self.settings.value("last_directory", "")
        filmstrip_visible = self.settings.value("filmstrip_visible", True, type=bool)
        self.filmstrip_action.setChecked(filmstrip_visible)
        
    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("last_directory", self.last_directory)
        self.settings.setValue("filmstrip_visible", self.filmstrip_action.isChecked())
             
    def closeEvent(self, event):
        self.save_settings()
        self.stop_slideshow()
        if self.converter_widget and self.converter_widget.isVisible():
            self.converter_widget.close()        
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer()

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            viewer.open_file(file_path)
        else:
            print(f"Error: File not found at '{file_path}'")

    viewer.show()
    sys.exit(app.exec())