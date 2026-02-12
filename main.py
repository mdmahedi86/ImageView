import sys
import os
import re
from PIL import Image, ImageSequence

from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
)
from PyQt6.QtGui import QPixmap, QIcon, QImage
from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal

from taskbar_icon import set_taskbar_icon
from temp_path import resource_path

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


icon_path = resource_path("icon.ico")
set_taskbar_icon(icon_path)


class FrameLoaderThread(QThread):
    """Thread to load animated frames in background without blocking UI"""
    frame_loaded = pyqtSignal(int, QPixmap, int)  # index, pixmap, duration
    
    def __init__(self, path):
        super().__init__()
        self.path = path
        self._running = True
        
    def run(self):
        """Load frames one by one instead of all at once"""
        try:
            img = Image.open(self.path)
            if not getattr(img, "is_animated", False):
                return
                
            for i, frame in enumerate(ImageSequence.Iterator(img)):
                if not self._running:
                    break
                    
                # Convert current frame only
                frame = frame.convert("RGBA")
                qimg = QImage(frame.tobytes(), frame.width, frame.height, 
                             QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimg)
                duration = frame.info.get('duration', 100)
                
                # Emit loaded frame
                self.frame_loaded.emit(i, pixmap, duration)
                
        except Exception as e:
            print(f"Error loading animation: {e}")
            
    def stop(self):
        self._running = False


class ImageViewer(QMainWindow):
    def __init__(self, start_file=None):
        super().__init__()
        self.setStyleSheet("background-color: black;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        self.setMinimumSize(640, 480)
        self.resize(1200, 800)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("background-color: black;")
        self.label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.label, 1)
        self.setCentralWidget(central)

        self.files = []
        self.index = 0

        # Animated state - lazy loading
        self.anim_loader = None
        self.anim_frames = {}  # Dict: index -> pixmap
        self.anim_durations = {}  # Dict: index -> duration
        self.anim_index = 0
        self.anim_frame_count = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._next_anim_frame)
        
        # Cache for next frame to preload just one ahead
        self.next_frame_to_preload = 1
        self.max_preloaded_frames = 2  # Only preload next 2 frames
        
        # Store current static pixmap for resize handling
        self.current_static_pixmap = None
        
        # Flag to track if window has been shown
        self._window_shown = False

        if start_file:
            self.load_images_from_folder(start_file)
            
    def showEvent(self, event):
        """Window is shown for the first time"""
        super().showEvent(event)
        if not self._window_shown:
            self._window_shown = True
            # Force a resize event to ensure proper image scaling
            QTimer.singleShot(10, self._delayed_show_image)

    def _delayed_show_image(self):
        """Delayed image show to ensure window has proper size"""
        if self.files:
            self.show_image()

    def load_images_from_folder(self, file_path):
        file_path = os.path.abspath(file_path)
        folder = os.path.dirname(file_path)
        all_files = sorted(os.listdir(folder), key=natural_sort_key)
        self.files = [os.path.join(folder, f) for f in all_files
                      if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'))]
        if file_path in self.files:
            self.index = self.files.index(file_path)
        # Don't show image immediately if window isn't shown yet
        if self._window_shown:
            self.show_image()

    def _clear_anim(self):
        """Stop and clear animation resources"""
        if self.anim_loader:
            self.anim_loader.stop()
            self.anim_loader.wait()
            self.anim_loader = None
            
        self.anim_timer.stop()
        self.anim_frames.clear()
        self.anim_durations.clear()
        self.anim_index = 0
        self.anim_frame_count = 0
        self.next_frame_to_preload = 1

    def show_image(self):
        self._clear_anim()
        self.current_static_pixmap = None

        if not self.files:
            self.label.clear()
            self.setWindowTitle("Image-View")
            return

        path = self.files[self.index]
        file_name = os.path.basename(path)
        self.setWindowTitle(file_name)

        # Check if file is potentially animated
        is_potentially_animated = path.lower().endswith(('.gif', '.webp'))
        
        if is_potentially_animated:
            # First try to load as static image for immediate display
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._set_scaled_pixmap(pixmap)
            
            # Then check if it's actually animated in background
            self._check_and_load_animation(path)
        else:
            # Static image
            pixmap = QPixmap(path)
            if pixmap.isNull():
                self.label.setText("Cannot load image:\n" + file_name)
                self.setWindowTitle("Error loading")
                return
            self.current_static_pixmap = pixmap
            self._set_scaled_pixmap(pixmap)

    def _check_and_load_animation(self, path):
        """Check if file is animated and start lazy loading"""
        def on_frame_loaded(index, pixmap, duration):
            """Callback when a frame is loaded in background"""
            if index == 0:
                # First frame loaded, display it immediately
                self.anim_frames[0] = pixmap
                self.anim_durations[0] = duration
                if self.anim_index == 0:  # Only if we haven't changed
                    self._set_scaled_pixmap(pixmap)
                    if self.anim_frame_count > 1:
                        self.anim_timer.start(duration)
            else:
                # Store other frames as they load
                self.anim_frames[index] = pixmap
                self.anim_durations[index] = duration
                
        try:
            # Quick check with PIL if file is animated
            img = Image.open(path)
            if not getattr(img, "is_animated", False):
                img.close()
                return
                
            self.anim_frame_count = img.n_frames
            img.close()
            
            if self.anim_frame_count > 1:
                # Start lazy loading in background
                self.anim_loader = FrameLoaderThread(path)
                self.anim_loader.frame_loaded.connect(on_frame_loaded)
                self.anim_loader.start()
            else:
                # Single frame, nothing more to do
                pass
                
        except Exception:
            # If anything fails, fall back to static display
            pass

    def _next_anim_frame(self):
        """Show next frame of animation, loading frames as needed"""
        if not self.anim_frame_count or self.anim_frame_count <= 1:
            return
            
        # Calculate next index
        next_index = (self.anim_index + 1) % self.anim_frame_count
        
        # Check if next frame is loaded
        if next_index in self.anim_frames:
            # Frame is loaded, show it
            self.anim_index = next_index
            self._set_scaled_pixmap(self.anim_frames[next_index])
            
            # Schedule next frame
            duration = self.anim_durations.get(next_index, 100)
            self.anim_timer.start(duration)
        else:
            # Frame not loaded yet, stop animation temporarily
            self.anim_timer.stop()
            
            # Try to restart from frame 0 if it exists
            if 0 in self.anim_frames:
                self.anim_index = 0
                self._set_scaled_pixmap(self.anim_frames[0])
                duration = self.anim_durations.get(0, 100)
                self.anim_timer.start(duration)

    def _set_scaled_pixmap(self, pixmap: QPixmap):
        """Scale and display pixmap"""
        if pixmap.isNull():
            return
            
        # Get label size, ensure it's valid
        target_size = self.label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            # Use window size as fallback
            target_size = self.size()
        
        # Ensure we have a reasonable minimum size
        if target_size.width() <= 0 or target_size.height() <= 0:
            target_size = QSize(100, 100)
        
        # Scale the pixmap
        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.label.setPixmap(scaled)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_PageDown, Qt.Key.Key_Space):
            if self.files:
                self.index = (self.index + 1) % len(self.files)
                self.show_image()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp):
            if self.files:
                self.index = (self.index - 1) % len(self.files)
                self.show_image()
        elif key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Handle window resize"""
        # Force immediate update of the current image
        if self.anim_frames and self.anim_index in self.anim_frames:
            # Resize current animated frame
            self._set_scaled_pixmap(self.anim_frames[self.anim_index])
        elif self.current_static_pixmap and not self.current_static_pixmap.isNull():
            # Resize current static image
            self._set_scaled_pixmap(self.current_static_pixmap)
        else:
            # Fallback: reload the image
            current_file = self.files[self.index] if self.files else None
            if current_file:
                self.show_image()
                
        super().resizeEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')) for url in urls):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path) and file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                self.load_images_from_folder(file_path)

    def closeEvent(self, event):
        """Clean up resources when closing"""
        self._clear_anim()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(icon_path))
    start_file = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = ImageViewer(start_file)

    viewer.showMaximized()
    viewer.activateWindow()
    viewer.raise_()
    viewer.setFocus()

    sys.exit(app.exec())