# turbo_get/utils.py
"""
Shared helper functions for formatting, validation, and file operations.
"""
from urllib.parse import urlparse
import os

def format_bytes(size: int) -> str:
    """Converts bytes into a human-readable format (KB, MB, GB)."""
    if not isinstance(size, (int, float)):
        return "0 B"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels) -1 :
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def is_valid_url(url: str) -> bool:
    """Performs a basic check to see if a string is a valid URL."""
    try:
        result = urlparse(url)
        # Check for scheme (http, https, ftp) and netloc (domain name)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def get_default_filename(url: str) -> str:
    """Extracts a filename from a URL path."""
    try:
        path = urlparse(url).path
        filename = os.path.basename(path)
        return filename if filename else "download.dat"
    except Exception:
        return "download.dat"