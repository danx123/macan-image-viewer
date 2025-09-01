## 🐅 Macan Image Viewer
Modern, Powerful, and Shrine-Inspired Image Viewer
Macan Image Viewer is a PyQt6 and OpenCV-based desktop application for viewing, managing, and processing images.

Designed with a modern UI, comprehensive feature support, and lightweight performance for everyday and professional use.

---

## ✨ Key Features
📂 Full Image Viewer: Open various image formats (PNG, JPG, WEBP, BMP, GIF, etc.)
🔍 Navigation & Zoom: Zoom in/out, fit-to-window, and pan control
📐 Quick Edit: Rotate, flip, and crop with rubber band selection
🖼️ Wallpaper & Print: Set images as wallpaper (Windows) or print directly
🎞️ Filmstrip & Slideshow: Preview folder collections, plus automatic slideshows
🎚️ Image Converter: Batch convert to various formats (JPEG, PNG, WEBP, BMP, GIF) with resolution and quality control
⚡ Resize Dialog: Resize images by pixels or percentage, complete with quality and format options
🗂️ Save State: The app remembers the last settings with QSettings
🖥️ Drag & Drop Support: Drag images directly into the app to open them
📝 Export PDF: Save images as PDFs

---
## 📝 Changelog v2.7.0
- Immersive Slideshow Mode: When you start the slideshow, the application now enters a clean, borderless fullscreen mode, hiding the toolbar and status bar for an uninterrupted viewing experience. The slideshow automatically returns to the normal window view when it completes its loop or when you press the Esc key.
- Expanded Format Support: The viewer now supports a wider range of files. In addition to standard images, I've added support for common video formats like MP4, AVI, and MKV.
- Automatic Video Playback: While navigating through a folder using the "Next" and "Previous" buttons, if the application encounters a video file, it will automatically switch to the video player and begin playback.

---
## 📸 Screenshot
<img width="1102" height="654" alt="Screenshot 2025-08-31 233037" src="https://github.com/user-attachments/assets/c35b4c17-d908-4a79-94b2-9398c5a0101a" />

<img width="1103" height="654" alt="Screenshot 2025-08-31 232949" src="https://github.com/user-attachments/assets/47ae6a96-61af-4b1e-bd37-1a1bd1f22a42" />

<img width="1102" height="654" alt="Screenshot 2025-08-31 233125" src="https://github.com/user-attachments/assets/fff50170-db5a-4b1c-b6ab-6ba509bb2dba" />

<img width="1101" height="648" alt="Screenshot 2025-08-31 232929" src="https://github.com/user-attachments/assets/cd11ead1-2244-4b11-a9c2-88d7702f785f" />

---

## ℹ️ Information Before Installation
The application uses PyQt6, Pillow, and OpenCV. Ensure Python version is 3.8 or higher.
The Set as Wallpaper feature is only available on Windows.
The Print and Save as PDF features require Qt Print Support.
The Batch and Converter features may consume higher CPU resources when processing multiple files.

## 📜 License
This project is licensed under the MIT License. Free to use, modify and redevelop as long as credit is given.
