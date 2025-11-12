# image_viewer_v2.py

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
            QPushButton { /* Styling untuk tombol Crop */
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
        self.image_label.setScaledContents(True) # Ini akan membuat gambar skalakan ke ukuran label
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Agar gambar selalu di tengah

        self.scroll_area = QScrollArea()
        self.scroll_area.setBackgroundRole(self.backgroundRole())
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #1e1e1e; }") # Background gelap untuk area gambar
        
        # Tambahkan Crop Button
        self.crop_button = QPushButton("Crop Selection", self)
        self.crop_button.hide() # Sembunyikan secara default
        self.crop_button.clicked.connect(self.perform_crop)
        # Posisikan tombol crop, ini akan dihandle di resizeEvent

        self.setCentralWidget(self.scroll_area)

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()

        # Inisialisasi RubberBand
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.image_label)
        self.rubber_band.setStyleSheet("QRubberBand { border: 1px dashed white; background-color: rgba(255, 255, 255, 50); }")
        
        # Connect mouse events for cropping
        self.image_label.mousePressEvent = self.image_mouse_press
        self.image_label.mouseMoveEvent = self.image_mouse_move
        self.image_label.mouseReleaseEvent = self.image_mouse_release

    def _create_actions(self):
        """Membuat semua actions untuk menu dan toolbar."""
        # Gunakan ikon standar dari tema, jika ada, atau buat ikon kustom
        # PyQt6 theme icons might not always be available or look good.
        # For a truly custom look, you'd provide your own icon files.
        # Example: QIcon(":/icons/open.png") if you have a resource file.

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

        self.reset_zoom_action = QAction("Reset Zoom", self) # Custom action
        self.reset_zoom_action.triggered.connect(self.reset_zoom)
        self.reset_zoom_action.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_0))

        self.rotate_left_action = QAction(QIcon.fromTheme("object-rotate-left"), "Rotate &Left", self)
        self.rotate_left_action.triggered.connect(self.rotate_left)
        
        self.rotate_right_action = QAction(QIcon.fromTheme("object-rotate-right"), "Rotate &Right", self)
        self.rotate_right_action.triggered.connect(self.rotate_right)

        self.flip_horizontal_action = QAction("Flip Horizontal", self)
        self.flip_horizontal_action.triggered.connect(lambda: self.flip_image(0)) # 0 for horizontal

        self.flip_vertical_action = QAction("Flip Vertical", self)
        self.flip_vertical_action.triggered.connect(lambda: self.flip_image(1)) # 1 for vertical

        self.set_wallpaper_action = QAction(QIcon.fromTheme("applications-other"), "Set as &Wallpaper", self)
        self.set_wallpaper_action.triggered.connect(self.set_as_wallpaper)

        # Navigasi actions
        self.prev_action = QAction(QIcon.fromTheme("go-previous"), "Pre&vious Image", self)
        self.prev_action.triggered.connect(self.show_previous_image)
        self.prev_action.setShortcut(QKeySequence.StandardKey.Back)

        self.next_action = QAction(QIcon.fromTheme("go-next"), "&Next Image", self)
        self.next_action.triggered.connect(self.show_next_image)
        self.next_action.setShortcut(QKeySequence.StandardKey.Forward)

        # Non-aktifkan actions yang butuh gambar sampai gambar dibuka
        self._update_action_states(False) # Semua defaultnya False

    def _create_menu_bar(self):
        """Membuat Menu Bar."""
        menu_bar = self.menuBar()
        
        # Menu Edit
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.open_action)
        edit_menu.addAction(self.save_as_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.set_wallpaper_action) # Tambah set wallpaper
        edit_menu.addSeparator()
        # edit_menu.addAction("Set as") # Placeholder
        # edit_menu.addAction("Resize image") # Placeholder
        edit_menu.addAction(self.open_explorer_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.exit_action)

        # Menu View (untuk zoom, rotate, flip)
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
        # <<< PERUBAHAN 1: Simpan toolbar ke self.tool_bar >>>
        self.tool_bar = QToolBar("Main Toolbar")
        self.tool_bar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tool_bar)
        
        # Tombol Navigasi
        self.tool_bar.addAction(self.prev_action)
        self.tool_bar.addAction(self.next_action)
        self.tool_bar.addSeparator()

        # Tombol Zoom
        self.tool_bar.addAction(self.zoom_in_action)
        self.tool_bar.addAction(self.zoom_out_action)
        self.tool_bar.addSeparator()

        # Tombol Rotate & Flip
        self.tool_bar.addAction(self.rotate_left_action)
        self.tool_bar.addAction(self.rotate_right_action)
        self.tool_bar.addSeparator()
        self.tool_bar.addAction(self.flip_horizontal_action)
        self.tool_bar.addAction(self.flip_vertical_action)
        self.tool_bar.addSeparator()

        # Tombol Buka/Simpan
        self.tool_bar.addAction(self.open_action)
        self.tool_bar.addAction(self.save_as_action)

        # Spacer agar tombol di tengah/kanan jika diperlukan
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.tool_bar.addWidget(spacer)

        # Tombol Close Window di Frameless
        self.close_button = QPushButton("X", self)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #f0f0f0;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e81123;
            }
        """)
        self.close_button.clicked.connect(self.close)
        self.tool_bar.addWidget(self.close_button)


    def _create_status_bar(self):
        """Membuat Status Bar di bagian bawah."""
        self.statusbar = self.statusBar()
        
        self.dimensions_label = QLabel("  ")
        self.filesize_label = QLabel("  ")
        self.zoom_label = QLabel(" 100% ")

        self.statusbar.addPermanentWidget(self.dimensions_label)
        self.statusbar.addPermanentWidget(self.filesize_label)
        self.statusbar.addPermanentWidget(self.zoom_label)

    def _update_action_states(self, enabled):
        """Mengaktifkan/menonaktifkan actions berdasarkan apakah ada gambar yang dimuat."""
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
        """Buka file dialog untuk memilih gambar atau buka gambar dari path."""
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Buka Gambar",
                "",
                "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
            )
        
        if file_path:
            self.image_path = file_path
            self.cv_image = cv2.imread(self.image_path) # Simpan gambar asli

            if self.cv_image is None:
                self.statusbar.showMessage(f"Error: Gagal membuka file {os.path.basename(self.image_path)}", 5000)
                self._update_action_states(False)
                return

            self.display_image = self.cv_image.copy() # Gambar yang akan dimanipulasi
            self.zoom_factor = 1.0 # Reset zoom saat membuka gambar baru
            self._display_image()
            self._update_status_bar()
            self.setWindowTitle(f'{os.path.basename(self.image_path)} - Danx Image Viewer')

            # Update daftar gambar di folder
            self._load_current_folder_images()
            
            # Aktifkan semua menu/toolbar yang relevan
            self._update_action_states(True)

    def _load_current_folder_images(self):
        """Muat daftar gambar di folder yang sama."""
        if self.image_path:
            folder = os.path.dirname(self.image_path)
            # Filter hanya file gambar
            image_extensions = ('*.png', '*.jpg', '*.jpeg', '*.bmp', '*.webp')
            all_files = []
            for ext in image_extensions:
                all_files.extend(glob(os.path.join(folder, ext)))
            
            # Urutkan berdasarkan nama file
            self.current_folder_images = sorted(all_files, key=os.path.basename)
            
            try:
                self.current_image_index = self.current_folder_images.index(self.image_path)
            except ValueError:
                self.current_image_index = -1 # Gambar yang dibuka tidak ada di daftar (misal cuma 1)
        else:
            self.current_folder_images = []
            self.current_image_index = -1
        self._update_action_states(bool(self.cv_image)) # Update lagi untuk tombol navigasi

    def _display_image(self):
        """Konversi gambar OpenCV ke QPixmap dan tampilkan."""
        if self.display_image is None:
            self.image_label.clear()
            return

        # Skalakan gambar agar pas di scroll area (sesuai ukuran jendela)
        # Pertama, dapatkan ukuran area yang tersedia untuk gambar
        available_size = self.scroll_area.viewport().size()
        
        # Hitung faktor skala untuk menyesuaikan gambar ke area yang tersedia
        h_img, w_img, _ = self.display_image.shape
        if w_img == 0 or h_img == 0: return

        # Skala awal tanpa zoom, agar pas di jendela
        if self.zoom_factor == 1.0:
             scale_w = available_size.width() / w_img
             scale_h = available_size.height() / h_img
             fit_scale = min(scale_w, scale_h)
             
             # Jangan perbesar gambar jika sudah kecil, kecuali jendela sangat kecil
             if fit_scale > 1.0: # Jika gambar lebih kecil dari jendela, tampilkan asli
                 # Atau atur max scale agar tidak terlalu besar di awal
                 fit_scale = min(fit_scale, 1.5) # Batas awal biar gak kebesaran banget
                 
             new_w_display = int(w_img * fit_scale)
             new_h_display = int(h_img * fit_scale)

        else: # Jika zoom_factor sudah berubah
            new_w_display = int(w_img * self.zoom_factor)
            new_h_display = int(h_img * self.zoom_factor)


        # Apply zoom after initial fit if zoom_factor is not 1.0
        # resized_img = cv2.resize(self.display_image, (new_w_display, new_h_display), interpolation=cv2.INTER_AREA)
        # ^^^^^ Ini akan meresize display_image, tapi kita mau display_image tetap resolusi tinggi
        # kita hanya meresize pixmap untuk tampilan, bukan mengubah display_image itu sendiri

        # Konversi BGR (OpenCV) ke RGB (PyQt)
        rgb_image = cv2.cvtColor(self.display_image, cv2.COLOR_BGR2RGB)
        
        h_orig, w_orig, ch = rgb_image.shape
        bytes_per_line = ch * w_orig
        
        qt_image = QImage(rgb_image.data, w_orig, h_orig, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        
        # Skalakan QPixmap untuk tampilan sesuai zoom_factor
        display_w = int(w_orig * self.zoom_factor)
        display_h = int(h_orig * self.zoom_factor)

        # Skalakan pixmap untuk ditampilkan di label
        scaled_pixmap = pixmap.scaled(display_w, display_h, 
                                     Qt.AspectRatioMode.KeepAspectRatio, 
                                     Qt.TransformationMode.SmoothTransformation)
        
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.size()) # Penting untuk scroll area

    def _update_status_bar(self):
        """Update informasi di status bar."""
        if self.cv_image is not None and self.image_path:
            # Dimensi gambar asli
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
        else:
            self.dimensions_label.setText(" ")
            self.filesize_label.setText(" ")
            self.zoom_label.setText(" ")


    def zoom_in(self):
        if self.display_image is None: return
        self.zoom_factor = min(self.zoom_factor * 1.25, 5.0) # Maksimal 500%
        self._display_image()
        self._update_status_bar()

    def zoom_out(self):
        if self.display_image is None: return
        self.zoom_factor = max(self.zoom_factor * 0.8, 0.1) # Minimal 10%
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
            # Update gambar asli juga agar save_as menyimpan yang sudah dirotasi
            self.cv_image = self.display_image.copy() 
            self._display_image()
            self._update_status_bar()
            
    def rotate_right(self):
        if self.display_image is not None:
            self.display_image = cv2.rotate(self.display_image, cv2.ROTATE_90_CLOCKWISE)
            self.cv_image = self.display_image.copy()
            self._display_image()
            self._update_status_bar()

    def flip_image(self, flip_code):
        """Flip gambar. flip_code=0 (horizontal), 1 (vertical)"""
        if self.display_image is not None:
            self.display_image = cv2.flip(self.display_image, flip_code)
            self.cv_image = self.display_image.copy()
            self._display_image()
            self._update_status_bar()

    def save_image_as(self):
        """Simpan gambar saat ini (setelah dirotasi/flip/crop)."""
        if self.display_image is None:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Gambar Sebagai...",
            os.path.basename(self.image_path) if self.image_path else "",
            "PNG Image (*.png);;JPG Image (*.jpg);;BMP Image (*.bmp)"
        )
        
        if file_path:
            try:
                cv2.imwrite(file_path, self.display_image) # Simpan display_image
                self.statusbar.showMessage(f"Gambar berhasil disimpan di {file_path}", 3000)
                # Jika disimpan dengan nama berbeda, update image_path
                self.image_path = file_path
                self._load_current_folder_images()
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
                # Untuk Windows, buka file explorer dan sorot file
                subprocess.Popen(f'explorer /select,"{self.image_path}"')
            elif system == "Darwin": # macOS
                subprocess.run(["open", "-R", self.image_path]) # -R untuk reveal in Finder
            else: # Linux
                subprocess.run(["xdg-open", path])
        except Exception as e:
            self.statusbar.showMessage(f"Gagal membuka folder: {e}", 5000)

    def show_previous_image(self):
        """Tampilkan gambar sebelumnya di folder."""
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.open_image(self.current_folder_images[self.current_image_index])
            self.statusbar.showMessage("Gambar sebelumnya", 2000)
        else:
            self.statusbar.showMessage("Tidak ada gambar sebelumnya.", 2000)

    def show_next_image(self):
        """Tampilkan gambar berikutnya di folder."""
        if self.current_image_index < len(self.current_folder_images) - 1:
            self.current_image_index += 1
            self.open_image(self.current_folder_images[self.current_image_index])
            self.statusbar.showMessage("Gambar berikutnya", 2000)
        else:
            self.statusbar.showMessage("Tidak ada gambar berikutnya.", 2000)
            
    def set_as_wallpaper(self):
        """Atur gambar yang sedang tampil sebagai wallpaper."""
        if self.image_path is None:
            self.statusbar.showMessage("Tidak ada gambar yang dimuat untuk diatur sebagai wallpaper.", 3000)
            return

        current_os = platform.system()
        try:
            if current_os == "Windows":
                # Menggunakan ctypes untuk Windows
                import ctypes
                SPI_SETDESKWALLPAPER = 20
                ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, self.image_path, 3)
                self.statusbar.showMessage("Wallpaper berhasil diatur (Windows).", 3000)
            elif current_os == "Darwin": # macOS
                # Menggunakan osascript untuk macOS
                script = f'tell application "Finder" to set desktop picture to POSIX file "{self.image_path}"'
                subprocess.run(["osascript", "-e", script])
                self.statusbar.showMessage("Wallpaper berhasil diatur (macOS).", 3000)
            elif current_os == "Linux":
                # Untuk Linux, bergantung pada lingkungan desktop (GNOME, KDE, XFCE, dll.)
                # Contoh untuk GNOME (umum di Ubuntu, Fedora, dll.)
                # Cek apakah gsettings tersedia
                if subprocess.run(["which", "gsettings"], capture_output=True).returncode == 0:
                    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{self.image_path}"])
                    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-options", "zoom"]) # Atau 'stretched', 'scaled', 'center'
                    self.statusbar.showMessage("Wallpaper berhasil diatur (GNOME).", 3000)
                # Tambahkan logika untuk KDE/XFCE jika diperlukan
                else:
                    self.statusbar.showMessage("Tidak dapat mengatur wallpaper: Lingkungan desktop tidak didukung atau gsettings tidak ditemukan.", 5000)
            else:
                self.statusbar.showMessage(f"OS {current_os} tidak didukung untuk mengatur wallpaper.", 5000)
        except Exception as e:
            self.statusbar.showMessage(f"Gagal mengatur wallpaper: {e}", 5000)

    # --- Frameless Window Drag ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Periksa apakah event terjadi di menubar atau toolbar
            # Untuk frameless window, kita perlu mendeteksi di mana klik terjadi
            # Misalnya, jika y lebih kecil dari menubar + toolbar height
            if hasattr(self, 'tool_bar') and event.position().y() < self.menuBar().height() + self.tool_bar.height():
                self.old_pos = event.globalPosition().toPoint()
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        super().mouseReleaseEvent(event)

    # --- Cropping Logic ---
    def image_mouse_press(self, event):
        if self.display_image is None: return

        if event.button() == Qt.MouseButton.LeftButton:
            self.origin_point = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin_point, QSize()))
            self.rubber_band.show()
            self.is_cropping = True
            self.crop_button.hide() # Sembunyikan tombol crop saat mulai seleksi
        event.accept()

    def image_mouse_move(self, event):
        if self.is_cropping:
            self.rubber_band.setGeometry(QRect(self.origin_point, event.position().toPoint()).normalized())
        event.accept()

    def image_mouse_release(self, event):
        if self.is_cropping:
            self.is_cropping = False
            # Dapatkan area seleksi
            selection_rect = self.rubber_band.geometry()
            
            # Konversi koordinat dari QLabel ke gambar asli
            # Kita perlu memperhitungkan scaling gambar di QLabel
            if not self.image_label.pixmap(): return
            pixmap_rect = self.image_label.pixmap().rect()
            
            # Jika pixmap lebih kecil dari image_label, ada padding di QLabel
            # Kita perlu offset dan skala sesuai pixmap
            pixmap_display_x = (self.image_label.width() - pixmap_rect.width()) / 2
            pixmap_display_y = (self.image_label.height() - pixmap_rect.height()) / 2

            # Konversi koordinat seleksi relatif terhadap pixmap yang ditampilkan
            relative_selection_x = selection_rect.x() - pixmap_display_x
            relative_selection_y = selection_rect.y() - pixmap_display_y
            
            scaled_selection_rect = QRect(
                int(relative_selection_x),
                int(relative_selection_y),
                selection_rect.width(),
                selection_rect.height()
            )
            
            # Pastikan area seleksi valid dan berada di dalam pixmap
            scaled_selection_rect = scaled_selection_rect.intersected(pixmap_rect)
            
            if not scaled_selection_rect.isEmpty() and scaled_selection_rect.width() > 5 and scaled_selection_rect.height() > 5:
                # Sekarang skala kembali ke dimensi gambar asli (self.display_image)
                # Faktor skala = (lebar gambar asli) / (lebar pixmap yang ditampilkan)
                img_h, img_w, _ = self.display_image.shape
                
                scale_x = img_w / pixmap_rect.width()
                scale_y = img_h / pixmap_rect.height()

                self.crop_x = int(scaled_selection_rect.x() * scale_x)
                self.crop_y = int(scaled_selection_rect.y() * scale_y)
                self.crop_w = int(scaled_selection_rect.width() * scale_x)
                self.crop_h = int(scaled_selection_rect.height() * scale_y)
                
                # Pastikan tidak melebihi batas gambar asli
                self.crop_x = max(0, self.crop_x)
                self.crop_y = max(0, self.crop_y)
                self.crop_w = min(self.crop_w, img_w - self.crop_x)
                self.crop_h = min(self.crop_h, img_h - self.crop_y)

                # Tampilkan tombol Crop
                self.crop_button.show()
                # Posisikan tombol di dekat area seleksi atau di tengah bawah
                btn_width = self.crop_button.width()
                btn_height = self.crop_button.height()
                self.crop_button.move(
                    selection_rect.center().x() - btn_width // 2,
                    selection_rect.bottom() + 10 # 10 piksel di bawah seleksi
                )
                self.crop_button.raise_() # Pastikan tombol di atas semua

            else:
                self.rubber_band.hide()
                self.crop_button.hide()
        event.accept()

    def perform_crop(self):
        """Lakukan operasi crop pada gambar."""
        if self.display_image is None or self.rubber_band.isHidden():
            return

        try:
            cropped_img = self.display_image[self.crop_y : self.crop_y + self.crop_h,
                                             self.crop_x : self.crop_x + self.crop_w]
            self.display_image = cropped_img
            self.cv_image = self.display_image.copy() # Update gambar asli
            self.zoom_factor = 1.0 # Reset zoom setelah crop
            self._display_image()
            self._update_status_bar()
            self.statusbar.showMessage("Gambar berhasil di-crop.", 3000)
        except Exception as e:
            self.statusbar.showMessage(f"Gagal melakukan crop: {e}", 5000)
        finally:
            self.rubber_band.hide()
            self.crop_button.hide()

    def resizeEvent(self, event):
        """Handle event resize jendela."""
        super().resizeEvent(event)
        # Saat jendela diresize, gambar mungkin perlu diskalakan ulang
        # Panggil _display_image untuk menyesuaikan jika zoom_factor == 1.0
        if self.cv_image is not None and self.zoom_factor == 1.0:
            self._display_image()

        # <<< PERUBAHAN 2: Hapus pemindahan posisi tombol close secara manual >>>
        # Tombol close sudah diatur posisinya oleh layout toolbar,
        # jadi baris kode untuk memindahkannya di sini tidak lagi diperlukan.

        # Posisikan ulang tombol crop jika sedang terlihat
        if self.crop_button.isVisible() and self.rubber_band.isVisible():
            selection_rect = self.rubber_band.geometry()
            btn_width = self.crop_button.width()
            btn_height = self.crop_button.height()
            self.crop_button.move(
                selection_rect.center().x() - btn_width // 2,
                selection_rect.bottom() + 10
            )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec())