import os
import sys
import ctypes

def set_taskbar_icon(icon_path: str, app_id: str = "mycompany.myproduct.subproduct.version", force_window: bool = False):
    """
    Sets the taskbar icon for Windows apps using the provided .ico file.
    Works with GUI frameworks and CLI apps (with optional hidden window).

    Args:
        icon_path (str): Path to the .ico file
        app_id (str): Custom AppUserModelID for taskbar grouping
        force_window (bool): If True, creates a hidden window for CLI apps
    """
    if not os.path.exists(icon_path):
        raise FileNotFoundError(f"Icon file not found: {icon_path}")

    if sys.platform != "win32":
        return  # Only relevant on Windows

    # Set AppUserModelID for taskbar icon grouping
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    if force_window:
        try:
            import win32gui
            import win32con
            import win32api

            hInstance = win32api.GetModuleHandle()
            className = "HiddenWindow"

            wndClass = win32gui.WNDCLASS()
            wndClass.lpfnWndProc = win32gui.DefWindowProc
            wndClass.hInstance = hInstance
            wndClass.lpszClassName = className
            wndClass.hIcon = win32gui.LoadImage(
                hInstance, icon_path, win32con.IMAGE_ICON, 0, 0,
                win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            )

            atom = win32gui.RegisterClass(wndClass)
            hwnd = win32gui.CreateWindowEx(
                0, atom, None, 0, 0, 0, 0, 0, 0, 0, hInstance, None
            )
        except ImportError:
            print("pywin32 is required for CLI taskbar icon support. Install with: pip install pywin32")

