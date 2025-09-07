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
## Changelog v5.0.0

Changelog Macan Quick View:

- Fit to Screen Button: A new "Fit to Screen" button with a unique icon has been added to the toolbar, allowing you to instantly resize the image to fit the window.
- Fullscreen Icon: The icon for the fullscreen button has been updated to be distinct from the new "Fit to Screen" icon.
- Restore Icon Fix: The maximize button's icon will now correctly change to a "restore" icon when the window is maximized and switch back when the size is restored.

Changelog Macan Image Viewer:

ManagePresetsDialog has been completely redesigned. It now features:
A live image preview on the right side.
A list of presets on the left. When you click a preset, the preview updates instantly.
A "Strength" slider to control the intensity of the selected preset, blending it with the original image.
The dialog now functions as an "apply" tool. Clicking OK will apply the currently previewed effect to the image in the main viewer.
---
## 📸 Screenshot
<img width="1080" height="2202" alt="macan_image_viewer_v4 5 0" src="https://github.com/user-attachments/assets/ed8bc604-bd20-4012-b07f-7093e4a994ac" />



---

## ℹ️ Information Before Installation
The application uses PyQt6, Pillow, and OpenCV. Ensure Python version is 3.8 or higher.
The Set as Wallpaper feature is only available on Windows.
The Print and Save as PDF features require Qt Print Support.
The Batch and Converter features may consume higher CPU resources when processing multiple files.

## 📜 License
This project is licensed under the MIT License. Free to use, modify and redevelop as long as credit is given.
