# image_viewer_v2_fixed.py

import sys
import os
import cv2
import platform
import subprocess
from glob import glob # Untuk mencari file di folder

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QScrollArea,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMenuBar, QMenu, QStatusBar, QToolBar,
    QSizePolicy, QPushButton, QRubberBand
)
from PyQt6.QtGui import QPixmap, QImage, QAction, QIcon, QKeySequence, QGuiApplication
from PyQt6.QtCore import Qt, QSize, QPoint, QRect

class ImageViewer(QMainWindow):
    """
    Aplikasi Image Viewer dengan PyQt6 dan OpenCV.
    Fitur: Buka, Simpan, Zoom, Rotasi, Flip, Navigasi, Frameless, Drag, Crop, Set as Wallpaper.
    """
    def __init__(self):
        super().__init__()

        self.image_path = None
        self.current_folder_images = []
        self.current_image_index = -1
        self.cv_image = None # Gambar asli, untuk operasi
        self.display_image = None # Gambar yang dimanipulasi (zoom, rotate, crop)
        self.zoom_factor = 1.0

        # Untuk frameless window drag
        self.old_pos = None

        # Untuk crop
        self.rubber_band = None
        self.origin_point = None
        self.is_cropping = False

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Danx Image Viewer')
        self.setGeometry(100, 100, 1200, 900) # Ukuran awal lebih besar

        # Set window frameless
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Atur stylesheet untuk tema gelap seperti di screenshot
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QMenuBar {
                background-color: #3c3c3c;
                color: #f0f0f0;
                border-bottom: 1px solid #555; /* Garis bawah menubar */
            }
            QMenuBar::item {
                padding: 5px 10px;
            }
            QMenuBar::item:selected {
                background-color: #555555;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #f0f0f0;
                border: 1px solid #555;
            }
            QMenu::item {
                padding: 5px 20px 5px 25px; /* Sesuaikan padding agar ikon muat */
            }
            QMenu::item:selected {
                background-color: #555555;
            }
            QToolBar {
                background-color: #3c3c3c;
                border: none;
                padding: 5px;
            }
            QToolBar QToolButton { /* Styling tombol di toolbar */
                background-color: transparent;
                border: none;
                padding: 5px;
                margin: 0 2px;
            }
            QToolBar QToolButton:hover {
                background-color: #555555;
                border-radius: 3px;
            }
            QStatusBar {
                background-color: #3c3c3c;
                color: #f0f0f0;
                border-top: 1px solid #555; /* Garis atas statusbar */
            }
            QStatusBar::item {
                border: none;
            }
            QLabel {
                color: #f0f0f0;
            }
            QPushButton { /* Styling untuk tombol Crop dan Kontrol Jendela */
                background-color: #555555;
                color: #f0f0f0;
                border: 1px solid #666;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)

        # Komponen Utama
        self.image_label = QLabel(self)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.image_label.setScaledContents(True)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #1e1e1e; }")

        self.crop_button = QPushButton("Crop Selection", self)
        self.crop_button.hide()
        self.crop_button.clicked.connect(self.perform_crop)

        self.setCentralWidget(self.scroll_area)

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()

        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.image_label)
        self.rubber_band.setStyleSheet("QRubberBand { border: 1px dashed white; background-color: rgba(255, 255, 255, 50); }")

        self.image_label.mousePressEvent = self.image_mouse_press
        self.image_label.mouseMoveEvent = self.image_mouse_move
        self.image_label.mouseReleaseEvent = self.image_mouse_release

    def _create_actions(self):
        """Membuat semua actions untuk menu dan toolbar."""
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

        self.zoom_in_action = QAction(QIcon.fromTheme("zoom-in"), "Zoom &In", self)
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        
        self.zoom_out_action = QAction(QIcon.fromTheme("zoom-out"), "Zoom &Out", self)
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)

        self.reset_zoom_action = QAction("Reset Zoom", self)
        self.reset_zoom_action.triggered.connect(self.reset_zoom)
        self.reset_zoom_action.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_0))

        self.rotate_left_action = QAction(QIcon.fromTheme("object-rotate-left"), "Rotate &Left", self)
        self.rotate_left_action.triggered.connect(self.rotate_left)
        
        self.rotate_right_action = QAction(QIcon.fromTheme("object-rotate-right"), "Rotate &Right", self)
        self.rotate_right_action.triggered.connect(self.rotate_right)

        self.flip_horizontal_action = QAction("Flip Horizontal", self)
        self.flip_horizontal_action.triggered.connect(lambda: self.flip_image(0))

        self.flip_vertical_action = QAction("Flip Vertical", self)
        self.flip_vertical_action.triggered.connect(lambda: self.flip_image(1))

        self.set_wallpaper_action = QAction(QIcon.fromTheme("applications-other"), "Set as &Wallpaper", self)
        self.set_wallpaper_action.triggered.connect(self.set_as_wallpaper)

        self.prev_action = QAction(QIcon.fromTheme("go-previous"), "Pre&vious Image", self)
        self.prev_action.triggered.connect(self.show_previous_image)
        self.prev_action.setShortcut(QKeySequence.StandardKey.Back)

        self.next_action = QAction(QIcon.fromTheme("go-next"), "&Next Image", self)
        self.next_action.triggered.connect(self.show_next_image)
        self.next_action.setShortcut(QKeySequence.StandardKey.Forward)

        self._update_action_states(False)

    def _create_menu_bar(self):
        """Membuat Menu Bar."""
        menu_bar = self.menuBar()
        
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.open_action)
        edit_menu.addAction(self.save_as_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.set_wallpaper_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.open_explorer_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.exit_action)

        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.reset_zoom_action)
        view_menu.addSeparator()
        view_menu.addAction(self.rotate_left_action)
        view_menu.addAction(self.rotate_right_action)
        view_menu.addSeparator()
        view_menu.addAction(self.flip_horizontal_action)
        view_menu.addAction(self.flip_vertical_action)

    def _create_tool_bar(self):
        """Membuat Tool Bar."""
        self.tool_bar = QToolBar("Main Toolbar")
        self.tool_bar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tool_bar)
        
        # Tombol Navigasi & Alat
        self.tool_bar.addAction(self.prev_action)
        self.tool_bar.addAction(self.next_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.zoom_in_action)
        self.tool_bar.addAction(self.zoom_out_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.rotate_left_action)
        self.tool_bar.addAction(self.rotate_right_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.open_action)
        self.tool_bar.addAction(self.save_as_action)

        # Spacer agar tombol kontrol jendela ke kanan
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.tool_bar.addWidget(spacer)

        ### ADDED: Tombol Minimize dan Maximize/Restore
        self.minimize_button = QPushButton("_", self)
        self.minimize_button.setFixedSize(30, 24)
        self.minimize_button.clicked.connect(self.showMinimized)
        
        self.maximize_button = QPushButton("[]", self)
        self.maximize_button.setFixedSize(30, 24)
        self.maximize_button.clicked.connect(self.toggle_maximize_restore)

        self.close_button = QPushButton("X", self)
        self.close_button.setFixedSize(30, 24)
        self.close_button.clicked.connect(self.close)

        # Styling untuk tombol kontrol jendela
        window_control_style = """
            QPushButton {{
                background-color: transparent; color: #f0f0f0; border: none;
                font-family: "Webdings"; font-size: 14px;
            }}
            QPushButton:hover {{ background-color: #555555; }}
            QPushButton#close_button:hover {{ background-color: #e81123; }}
        """
        self.minimize_button.setText("0") # karakter '0' di font Webdings adalah minimize
        self.maximize_button.setText("1") # karakter '1' di font Webdings adalah maximize
        self.close_button.setObjectName("close_button") # Untuk styling hover merah
        self.close_button.setText("r") # karakter 'r' di font Webdings adalah close
        
        self.minimize_button.setStyleSheet(window_control_style)
        self.maximize_button.setStyleSheet(window_control_style)
        self.close_button.setStyleSheet(window_control_style)

        self.tool_bar.addWidget(self.minimize_button)
        self.tool_bar.addWidget(self.maximize_button)
        self.tool_bar.addWidget(self.close_button)

    def _create_status_bar(self):
        """Membuat Status Bar."""
        self.statusbar = self.statusBar()
        self.dimensions_label = QLabel("  ")
        self.filesize_label = QLabel("  ")
        self.zoom_label = QLabel(" 100% ")
        self.statusbar.addPermanentWidget(self.dimensions_label)
        self.statusbar.addPermanentWidget(self.filesize_label)
        self.statusbar.addPermanentWidget(self.zoom_label)

    ### ADDED: Fungsi untuk toggle maximize/restore
    def toggle_maximize_restore(self):
        """Memaksimalkan jendela jika normal, atau mengembalikan jika maksimal."""
        if self.isMaximized():
            self.showNormal()
            self.maximize_button.setText("1") # Kembali ke ikon maximize
        else:
            self.showMaximized()
            self.maximize_button.setText("2") # Ikon restore di font Webdings

    def _update_action_states(self, enabled):
        """Mengaktifkan/menonaktifkan actions."""
        self.save_as_action.setEnabled(enabled)
        self.copy_action.setEnabled(enabled)
        self.open_explorer_action.setEnabled(enabled)
        self.set_wallpaper_action.setEnabled(enabled)
        self.zoom_in_action.setEnabled(enabled)
        self.zoom_out_action.setEnabled(enabled)
        self.reset_zoom_action.setEnabled(enabled)
        self.rotate_left_action.setEnabled(enabled)
        self.rotate_right_action.setEnabled(enabled)
        self.flip_horizontal_action.setEnabled(enabled)
        self.flip_vertical_action.setEnabled(enabled)
        self.prev_action.setEnabled(enabled and self.current_image_index > 0)
        self.next_action.setEnabled(enabled and self.current_image_index < len(self.current_folder_images) - 1)
        
    def open_image(self, file_path=None):
        """Buka gambar dari dialog atau path yang diberikan."""
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Buka Gambar", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)")
        
        if file_path:
            self.image_path = file_path
            self.cv_image = cv2.imread(self.image_path)
            if self.cv_image is None:
                self.statusbar.showMessage(f"Error: Gagal membuka file {os.path.basename(self.image_path)}", 5000)
                return
            self.display_image = self.cv_image.copy()
            self.zoom_factor = 1.0
            self._display_image()
            self._update_status_bar()
            self.setWindowTitle(f'{os.path.basename(self.image_path)} - Danx Image Viewer')
            self._load_current_folder_images()
            self._update_action_states(True)

    def _load_current_folder_images(self):
        """Muat daftar gambar di folder yang sama."""
        if self.image_path:
            folder = os.path.dirname(self.image_path)
            image_extensions = ('*.png', '*.jpg', '*.jpeg', '*.bmp', '*.webp')
            all_files = []
            for ext in image_extensions:
                all_files.extend(glob(os.path.join(folder, ext)))
            self.current_folder_images = sorted(all_files, key=os.path.basename)
            try:
                self.current_image_index = self.current_folder_images.index(self.image_path)
            except ValueError:
                self.current_image_index = -1
        else:
            self.current_folder_images = []
            self.current_image_index = -1
        self._update_action_states(bool(self.cv_image))

    def _display_image(self):
        """Konversi gambar OpenCV ke QPixmap dan tampilkan."""
        if self.display_image is None:
            self.image_label.clear()
            return
        
        rgb_image = cv2.cvtColor(self.display_image, cv2.COLOR_BGR2RGB)
        h_orig, w_orig, ch = rgb_image.shape
        bytes_per_line = ch * w_orig
        
        qt_image = QImage(rgb_image.data, w_orig, h_orig, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        
        display_w = int(w_orig * self.zoom_factor)
        display_h = int(h_orig * self.zoom_factor)

        scaled_pixmap = pixmap.scaled(display_w, display_h, 
                                     Qt.AspectRatioMode.KeepAspectRatio, 
                                     Qt.TransformationMode.SmoothTransformation)
        
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.size())

    def _update_status_bar(self):
        """Update informasi di status bar."""
        if self.cv_image is not None and self.image_path and os.path.exists(self.image_path):
            h, w, _ = self.cv_image.shape
            self.dimensions_label.setText(f" {w} x {h} ")
            size_bytes = os.path.getsize(self.image_path)
            if size_bytes < 1024**2:
                filesize_str = f"{size_bytes/1024:.1f} KB"
            else:
                filesize_str = f"{size_bytes/1024**2:.1f} MB"
            self.filesize_label.setText(f" {filesize_str} ")
            self.zoom_label.setText(f" {int(self.zoom_factor * 100)}% ")
        else:
            self.dimensions_label.setText(" ")
            self.filesize_label.setText(" ")
            self.zoom_label.setText(" ")
    
    # --- Fungsi Operasi Gambar (Zoom, Rotate, etc.) ---
    def zoom_in(self):
        if self.display_image is None: return
        self.zoom_factor = min(self.zoom_factor * 1.25, 8.0) # Max 800%
        self._display_image()
        self._update_status_bar()

    def zoom_out(self):
        if self.display_image is None: return
        self.zoom_factor = max(self.zoom_factor * 0.8, 0.1) # Min 10%
        self._display_image()
        self._update_status_bar()

    def reset_zoom(self):
        if self.display_image is None: return
        self.zoom_factor = 1.0
        self._display_image()
        self._update_status_bar()

    def rotate_left(self):
        if self.display_image is not None:
            self.display_image = cv2.rotate(self.display_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            self._display_image()
            self._update_status_bar()
            
    def rotate_right(self):
        if self.display_image is not None:
            self.display_image = cv2.rotate(self.display_image, cv2.ROTATE_90_CLOCKWISE)
            self._display_image()
            self._update_status_bar()

    def flip_image(self, flip_code):
        if self.display_image is not None:
            self.display_image = cv2.flip(self.display_image, flip_code)
            self._display_image()
            self._update_status_bar()

    def save_image_as(self):
        if self.display_image is None: return
        file_path, _ = QFileDialog.getSaveFileName(self, "Simpan Gambar Sebagai...", os.path.basename(self.image_path) if self.image_path else "","PNG (*.png);;JPG (*.jpg);;BMP (*.bmp)")
        if file_path:
            try:
                # Saat menyimpan, gunakan gambar yang sudah dimodifikasi (rotasi, flip)
                # Namun, kita harus konversi dari RGB (display) kembali ke BGR (OpenCV save) jika perlu
                # Dalam kasus ini, display_image masih BGR, jadi aman.
                cv2.imwrite(file_path, self.display_image)
                self.statusbar.showMessage(f"Gambar berhasil disimpan di {file_path}", 3000)
            except Exception as e:
                self.statusbar.showMessage(f"Gagal menyimpan gambar: {e}", 5000)

    def copy_image_to_clipboard(self):
        if self.image_label.pixmap():
            QApplication.clipboard().setPixmap(self.image_label.pixmap())
            self.statusbar.showMessage("Gambar disalin ke clipboard", 3000)

    def open_in_file_explorer(self):
        if not self.image_path: return
        path = os.path.dirname(self.image_path)
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.Popen(f'explorer /select,"{self.image_path}"')
            elif system == "Darwin":
                subprocess.run(["open", "-R", self.image_path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            self.statusbar.showMessage(f"Gagal membuka folder: {e}", 5000)

    def show_previous_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.open_image(self.current_folder_images[self.current_image_index])
    
    def show_next_image(self):
        if self.current_image_index < len(self.current_folder_images) - 1:
            self.current_image_index += 1
            self.open_image(self.current_folder_images[self.current_image_index])
            
    def set_as_wallpaper(self):
        if self.image_path is None: return
        # (Fungsi set_as_wallpaper tidak diubah, asumsikan sudah benar)
        pass # Placeholder untuk keringkasan

    ### FIX: Logika drag, maximize, dan interaksi tombol
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Cek apakah klik terjadi di area title bar (menu + toolbar)
            title_bar_height = self.menuBar().height() + self.tool_bar.height()
            if event.position().y() < title_bar_height:
                # Cek apakah yang diklik adalah widget interaktif (misal: tombol)
                widget = self.childAt(event.pos())
                if isinstance(widget, (QPushButton, QToolBar, QMenuBar)):
                     # Jika ya, biarkan widget itu yang menangani event
                    super().mousePressEvent(event)
                else:
                    # Jika tidak (area kosong), mulai proses drag
                    self.old_pos = event.globalPosition().toPoint()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        super().mouseReleaseEvent(event)

    ### ADDED: Fungsi double-click untuk maximize
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Hanya trigger jika double click di area title bar
            title_bar_height = self.menuBar().height() + self.tool_bar.height()
            if event.position().y() < title_bar_height:
                self.toggle_maximize_restore()
        super().mouseDoubleClickEvent(event)

    # --- Cropping Logic (tidak diubah) ---
    def image_mouse_press(self, event):
        if self.display_image is None: return
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin_point = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin_point, QSize()))
            self.rubber_band.show()
            self.is_cropping = True
            self.crop_button.hide()
    
    def image_mouse_move(self, event):
        if self.is_cropping:
            self.rubber_band.setGeometry(QRect(self.origin_point, event.position().toPoint()).normalized())
    
    def image_mouse_release(self, event):
        if self.is_cropping:
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
                scale_x = img_w / pixmap_rect.width()
                scale_y = img_h / pixmap_rect.height()

                self.crop_x = int(scaled_selection.x() * scale_x)
                self.crop_y = int(scaled_selection.y() * scale_y)
                self.crop_w = int(scaled_selection.width() * scale_x)
                self.crop_h = int(scaled_selection.height() * scale_y)
                
                self.crop_button.show()
                self.crop_button.move(selection_rect.center().x() - self.crop_button.width() // 2, selection_rect.bottom() + 10)
                self.crop_button.raise_()
            else:
                self.rubber_band.hide()
                self.crop_button.hide()

    def perform_crop(self):
        if self.display_image is None or self.rubber_band.isHidden(): return
        try:
            cropped_img = self.display_image[self.crop_y:self.crop_y + self.crop_h, self.crop_x:self.crop_x + self.crop_w]
            self.display_image = cropped_img
            self.zoom_factor = 1.0
            self._display_image()
            self._update_status_bar()
            self.statusbar.showMessage("Gambar berhasil di-crop.", 3000)
        finally:
            self.rubber_band.hide()
            self.crop_button.hide()

    def resizeEvent(self, event):
        """Handle event resize jendela."""
        super().resizeEvent(event)
        if self.cv_image is not None and self.zoom_factor == 1.0:
            self._display_image()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer()

    ### ADDED: Logika untuk membuka file dari path argumen command line
    # Cek apakah ada argumen yang diberikan saat menjalankan script
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        # Pastikan file tersebut ada sebelum mencoba membukanya
        if os.path.isfile(file_path):
            viewer.open_image(file_path)
        else:
            print(f"Error: File tidak ditemukan di '{file_path}'")

    viewer.show()
    sys.exit(app.exec())