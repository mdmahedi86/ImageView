import sys
import ctypes

# Windows dark title bar helper for PyQt5 / PyQt6
# Usage: call enable_dark_title_bar(winId) after the window is shown

DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def enable_dark_title_bar(win_id):
    """
    Enables dark title bar on Windows 10/11 for a Qt window.

    Parameters
    ----------
    win_id : int
        window.winId() from a PyQt widget
    """

    if sys.platform != "win32":
        return

    try:
        hwnd = int(win_id)
        value = ctypes.c_int(1)

        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(value),
            ctypes.sizeof(value)
        )

    except Exception:
        pass


# Optional convenience function

def apply_dark_title_bar(window):
    """
    Call this after window.show()

    Example:
        apply_dark_title_bar(self)
    """

    window_id = window.winId()
    enable_dark_title_bar(window_id)




# how to use:

# from dark_titlebar import apply_dark_title_bar

# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()

#     def showEvent(self, event):
#         super().showEvent(event)
#         apply_dark_title_bar(self)



#----- Or after showing the window:

# window.show()
# apply_dark_title_bar(window)