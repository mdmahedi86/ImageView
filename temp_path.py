import os, sys

def resource_path(relative_path):
    """
    Returns absolute path to resource, works for PyInstaller or local development.
    Raises FileNotFoundError if the resource does not exist.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    full_path = os.path.join(base_path, relative_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Resource not found: {full_path}")
    return full_path
