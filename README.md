## 🐅 Macan Image Viewer
Modern, Powerful, and Shrine-Inspired Image Viewer
Macan Image Viewer is a PySide6 and OpenCV-based desktop application for viewing, managing, and processing images.

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
## Changelog v6.0.0
New Features
Viewer Zoom Control: Implemented intuitive mouse-wheel (scroll) zoom functionality directly on the image viewer for enhanced navigation efficiency.
File Deletion: Integrated a "Move to Trash" feature.
Added a "Delete" icon and action to the main toolbar.
Mapped the Delete key as a system-standard keyboard shortcut for this operation.
Toolbar Branding: Added a prominent application title label to the main toolbar for improved UI clarity and branding.
Enhancements & Changes
UI/UX Modernization: The primary "Next" and "Previous" file navigation controls have been relocated from the main toolbar to an on-image overlay. This provides a cleaner, more immersive viewing experience and aligns the UI with the Macan Gallery interface.
Iconography: Updated the new navigation overlay buttons and the toolbar "Delete" button icons to a high-contrast white color, ensuring optimal visibility against the dark theme.
Fixes
UI Readability: Resolved a theme conflict where the "Delete Confirmation" dialog text was rendered white-on-white. The dialog is now forced to a system-standard light theme to ensure text is always legible.
---
## 📸 Screenshot
<img width="804" height="688" alt="Screenshot 2025-11-14 070625" src="https://github.com/user-attachments/assets/9cddb118-e887-487a-b16d-6e8e91e03fdf" />
<img width="1365" height="685" alt="Screenshot 2025-11-14 070721" src="https://github.com/user-attachments/assets/1ae059df-7350-41a6-b1f7-6415a12ed733" />

---

## ℹ️ Information Before Installation
The application uses PySide6, Pillow, and OpenCV. Ensure Python version is 3.8 or higher.
The Set as Wallpaper feature is only available on Windows.
The Print and Save as PDF features require Qt Print Support.
The Batch and Converter features may consume higher CPU resources when processing multiple files.

## 📜 License
This project is licensed under the MIT License. Free to use, modify and redevelop as long as credit is given.
