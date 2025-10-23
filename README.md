# TurboGet - Advanced Download Manager

TurboGet is a multi-threaded download manager written in Python, featuring a Tkinter GUI and seamless browser integration inspired by IDM. It uses asynchronous I/O to maximize download speeds by splitting files into chunks and downloading them in parallel.

## Features

- **Multi-threaded Downloading:** Splits files into parts to download them simultaneously.
- **Download Resuming:** Can resume interrupted downloads.
- **IDM-Style Browser Integration:** Automatically captures download links from your browser (Chrome-based).
- **Live Speed Graph:** Visually monitor your download speed in real-time.
- **Speed Limiter:** Set a speed limit to manage your bandwidth.
- **Dark Themed GUI:** A modern, clean user interface built with Tkinter.

## Installation

**Prerequisites:**
- Python 3.8+
- Git

**1. Clone the Repository:**
```bash
git clone https://github.com/your-username/turbo_get_project.git
cd turbo_get_project
```

**2. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**3. Run the Installer:**
This script configures the browser integration. On Windows, it will modify the registry; on macOS/Linux, it will copy a file to the correct folder.
```bash
python install.py
```

**4. Install the Browser Extension:**
- Open your Chrome-based browser (Chrome, Brave, Edge) and navigate to `chrome://extensions`.
- Enable "Developer mode" in the top-right corner.
- Click "Load unpacked" and select the `turbo_get_extension` folder from this project.

**5. Restart your browser** for the changes to take effect.

## Usage

To run the application, execute the `main.py` script:
```bash
python turbo_get/main.py
```
Now, when you click a download link in your browser, the TurboGet application will automatically open and capture the download.