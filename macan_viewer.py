# image_viewer.py

import sys
import os
import cv2
import platform
import subprocess

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QScrollArea,
    QVBoxLayout, QFileDialog, QMenuBar, QMenu, QStatusBar, QToolBar,
    QSizePolicy
)
from PyQt6.QtGui import QPixmap, QImage, QAction, QIcon, QKeySequence
from PyQt6.QtCore import Qt, QSize

class ImageViewer(QMainWindow):
    """
    Aplikasi Image Viewer dengan PyQt6 dan OpenCV.
    Fitur: Buka, Simpan, Zoom, Rotasi, Flip, dan lainnya.
    """
    def __init__(self):
        super().__init__()

        self.image_path = None
        self.cv_image = None
        self.zoom_factor = 1.0

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Danx Image Viewer')
        self.setGeometry(100, 100, 1000, 800)

        # Atur stylesheet untuk tema gelap seperti di screenshot
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QMenuBar {
                background-color: #3c3c3c;
                color: #f0f0f0;
            }
            QMenuBar::item:selected {
                background-color: #555555;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #f0f0f0;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #555555;
            }
            QToolBar {
                background-color: #3c3c3c;
                border: none;
            }
            QStatusBar {
                background-color: #3c3c3c;
                color: #f0f0f0;
            }
            QStatusBar::item {
                border: none;
            }
            QLabel {
                color: #f0f0f0;
            }
        """)

        # Komponen Utama
        self.image_label = QLabel(self)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.image_label.setScaledContents(True)

        self.scroll_area = QScrollArea()
        self.scroll_area.setBackgroundRole(self.backgroundRole())
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        self.setCentralWidget(self.scroll_area)

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()

    def _create_actions(self):
        """Membuat semua actions untuk menu dan toolbar."""
        # Gunakan ikon standar dari tema, jika ada
        style = self.style()

        # File actions
        self.open_action = QAction(QIcon.fromTheme("document-open"), "&Buka Gambar...", self)
        self.open_action.triggered.connect(self.open_image)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        
        self.save_as_action = QAction(QIcon.fromTheme("document-save-as"), "Save &As...", self)
        self.save_as_action.triggered.connect(self.save_image_as)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)

        self.copy_action = QAction(QIcon.fromTheme("edit-copy"), "&Copy", self)
        self.copy_action.triggered.connect(self.copy_image_to_clipboard)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        
        self.open_explorer_action = QAction(QIcon.fromTheme("system-file-manager"), "Open in &File Explorer", self)
        self.open_explorer_action.triggered.connect(self.open_in_file_explorer)
        
        self.exit_action = QAction(QIcon.fromTheme("application-exit"), "&Exit", self)
        self.exit_action.triggered.connect(self.close)

        # Edit/View actions
        self.zoom_in_action = QAction(QIcon.fromTheme("zoom-in"), "Zoom &In", self)
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        
        self.zoom_out_action = QAction(QIcon.fromTheme("zoom-out"), "Zoom &Out", self)
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)

        self.rotate_left_action = QAction(QIcon.fromTheme("object-rotate-left"), "Rotate &Left", self)
        self.rotate_left_action.triggered.connect(self.rotate_left)
        
        self.rotate_right_action = QAction(QIcon.fromTheme("object-rotate-right"), "Rotate &Right", self)
        self.rotate_right_action.triggered.connect(self.rotate_right)
        
        # Non-aktifkan actions yang butuh gambar sampai gambar dibuka
        self.save_as_action.setEnabled(False)
        self.copy_action.setEnabled(False)
        self.open_explorer_action.setEnabled(False)
        self.zoom_in_action.setEnabled(False)
        self.zoom_out_action.setEnabled(False)
        self.rotate_left_action.setEnabled(False)
        self.rotate_right_action.setEnabled(False)


    def _create_menu_bar(self):
        """Membuat Menu Bar."""
        menu_bar = self.menuBar()
        
        # Menu File (digabung ke dalam Edit sesuai screenshot)
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.open_action) # Tambah open di sini
        edit_menu.addAction(self.save_as_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addSeparator()
        # "Set as" dan "Resize" bisa ditambahkan di sini jika ingin diimplementasikan
        # edit_menu.addAction("Set as")
        # edit_menu.addAction("Resize image")
        edit_menu.addAction(self.open_explorer_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.exit_action)


    def _create_tool_bar(self):
        """Membuat Tool Bar."""
        tool_bar = QToolBar("Main Toolbar")
        tool_bar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tool_bar)
        
        # Tambahkan action ke toolbar
        tool_bar.addAction(self.zoom_in_action)
        tool_bar.addAction(self.zoom_out_action)
        tool_bar.addSeparator()
        tool_bar.addAction(self.rotate_left_action)
        tool_bar.addAction(self.rotate_right_action)


    def _create_status_bar(self):
        """Membuat Status Bar di bagian bawah."""
        self.statusbar = self.statusBar()
        
        self.dimensions_label = QLabel("  ")
        self.filesize_label = QLabel("  ")
        self.zoom_label = QLabel(" 100% ")

        self.statusbar.addPermanentWidget(self.dimensions_label)
        self.statusbar.addPermanentWidget(self.filesize_label)
        self.statusbar.addPermanentWidget(self.zoom_label)
        
    def open_image(self):
        """Buka file dialog untuk memilih gambar."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Buka Gambar",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
        )
        if file_path:
            self.image_path = file_path
            self.cv_image = cv2.imread(self.image_path)
            
            if self.cv_image is None:
                self.statusbar.showMessage(f"Error: Gagal membuka file {os.path.basename(self.image_path)}", 5000)
                return

            self.zoom_factor = 1.0
            self._display_image()
            self._update_status_bar()
            self.setWindowTitle(f'{os.path.basename(self.image_path)} - Danx Image Viewer')

            # Aktifkan semua menu/toolbar yang relevan
            self.save_as_action.setEnabled(True)
            self.copy_action.setEnabled(True)
            self.open_explorer_action.setEnabled(True)
            self.zoom_in_action.setEnabled(True)
            self.zoom_out_action.setEnabled(True)
            self.rotate_left_action.setEnabled(True)
            self.rotate_right_action.setEnabled(True)

    def _display_image(self):
        """Konversi gambar OpenCV ke QPixmap dan tampilkan."""
        if self.cv_image is None:
            return

        # Terapkan zoom
        h, w, _ = self.cv_image.shape
        new_w = int(w * self.zoom_factor)
        new_h = int(h * self.zoom_factor)
        
        # OpenCV resize untuk kualitas yang lebih baik
        resized_img = cv2.resize(self.cv_image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Konversi BGR (OpenCV) ke RGB (PyQt)
        rgb_image = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
        h_resized, w_resized, ch = rgb_image.shape
        bytes_per_line = ch * w_resized
        
        qt_image = QImage(rgb_image.data, w_resized, h_resized, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())

    def _update_status_bar(self):
        """Update informasi di status bar."""
        if self.cv_image is not None and self.image_path:
            # Dimensi
            h, w, _ = self.cv_image.shape
            self.dimensions_label.setText(f" {w} x {h} ")
            
            # Ukuran file
            size_bytes = os.path.getsize(self.image_path)
            if size_bytes < 1024:
                filesize_str = f"{size_bytes} B"
            elif size_bytes < 1024**2:
                filesize_str = f"{size_bytes/1024:.1f} KB"
            else:
                filesize_str = f"{size_bytes/1024**2:.1f} MB"
            self.filesize_label.setText(f" {filesize_str} ")
            
            # Level zoom
            self.zoom_label.setText(f" {int(self.zoom_factor * 100)}% ")

    def zoom_in(self):
        self.zoom_factor *= 1.25
        self._display_image()
        self._update_status_bar()

    def zoom_out(self):
        self.zoom_factor *= 0.8
        self._display_image()
        self._update_status_bar()

    def rotate_left(self):
        if self.cv_image is not None:
            self.cv_image = cv2.rotate(self.cv_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            self._display_image()
            self._update_status_bar()
            
    def rotate_right(self):
        if self.cv_image is not None:
            self.cv_image = cv2.rotate(self.cv_image, cv2.ROTATE_90_CLOCKWISE)
            self._display_image()
            self._update_status_bar()

    def save_image_as(self):
        """Simpan gambar saat ini (setelah dirotasi/flip)."""
        if self.cv_image is None:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Gambar Sebagai...",
            "",
            "PNG Image (*.png);;JPG Image (*.jpg);;BMP Image (*.bmp)"
        )
        
        if file_path:
            try:
                cv2.imwrite(file_path, self.cv_image)
                self.statusbar.showMessage(f"Gambar berhasil disimpan di {file_path}", 3000)
            except Exception as e:
                self.statusbar.showMessage(f"Gagal menyimpan gambar: {e}", 5000)

    def copy_image_to_clipboard(self):
        """Salin gambar yang sedang tampil ke clipboard."""
        if self.image_label.pixmap():
            QApplication.clipboard().setPixmap(self.image_label.pixmap())
            self.statusbar.showMessage("Gambar disalin ke clipboard", 3000)

    def open_in_file_explorer(self):
        """Buka lokasi file di explorer/finder."""
        if not self.image_path:
            return
            
        path = os.path.dirname(self.image_path)
        system = platform.system()
        
        try:
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin": # macOS
                subprocess.run(["open", path])
            else: # Linux
                subprocess.run(["xdg-open", path])
        except Exception as e:
            self.statusbar.showMessage(f"Gagal membuka folder: {e}", 5000)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec())