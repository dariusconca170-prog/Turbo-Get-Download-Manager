"""
TurboGet - Advanced Multi-threaded Download Manager
GUI, App Entry Point, and Native Messaging Web Server
"""

import asyncio
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from aiohttp import web
import aiohttp
from engine import DownloadEngine
from graph import SpeedGraph
from utils import format_bytes, is_valid_url, get_default_filename

class TurboGetGUI:
    """Advanced GUI for the download manager"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TurboGet - Advanced Download Manager")
        self.root.geometry("1000x700")
        self.root.configure(bg='#2b2b2b')

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()

        self.downloads: Dict[str, DownloadEngine] = {}
        self.active_download: Optional[str] = None
        self.start_time = 0

        # --- Web server state ---
        self.web_runner = None

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def configure_styles(self):
        """Configure custom styles for the application's theme"""
        self.style.configure('TFrame', background='#2b2b2b')
        self.style.configure('TLabel', background='#2b2b2b', foreground='#ffffff')
        self.style.configure('TButton', background='#4a4a4a', foreground='#ffffff', font=('Arial', 10))
        self.style.map('TButton', background=[('active', '#6a6a6a')])
        self.style.configure('Header.TLabel', font=('Arial', 12, 'bold'))
        self.style.configure('Accent.TButton', background='#007acc', foreground='#ffffff', font=('Arial', 10, 'bold'))
        self.style.map('Accent.TButton', background=[('active', '#005f9e')])
        self.style.configure('TProgressbar', thickness=20, background='#007acc', troughcolor='#4a4a4a')

    def build_ui(self):
        """Construct the main user interface"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # URL Input Section
        input_frame = ttk.LabelFrame(main_frame, text="Download URL", padding="10")
        input_frame.pack(fill=tk.X, pady=5)
        input_frame.columnconfigure(1, weight=1)
        ttk.Label(input_frame, text="URL:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.url_entry = ttk.Entry(input_frame, width=80)
        self.url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(input_frame, text="Save As:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.path_entry = ttk.Entry(input_frame, width=80)
        self.path_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_file).grid(row=1, column=2, padx=5)

        # Settings Section
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=5)
        ttk.Label(settings_frame, text="Threads:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.threads_var = tk.IntVar(value=16) # Increased default
        ttk.Spinbox(settings_frame, from_=1, to=64, textvariable=self.threads_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(settings_frame, text="Speed Limit (KB/s):").grid(row=0, column=2, sticky=tk.W, padx=15)
        self.speed_limit_var = tk.StringVar(value="Unlimited")
        ttk.Entry(settings_frame, textvariable=self.speed_limit_var, width=15).grid(row=0, column=3, sticky=tk.W, padx=5)

        # Control Buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        ttk.Button(control_frame, text="▶ Start Download", command=self.start_download, style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        self.pause_button = ttk.Button(control_frame, text="⏸ Pause", command=self.pause_download, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        self.resume_button = ttk.Button(control_frame, text="▶ Resume", command=self.resume_download, state=tk.DISABLED)
        self.resume_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(control_frame, text="⏹ Stop", command=self.stop_download, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Progress Section
        progress_frame = ttk.LabelFrame(main_frame, text="Download Progress", padding="10")
        progress_frame.pack(fill=tk.X, pady=5)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, mode='determinate', style='TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=5)
        self.progress_label = ttk.Label(progress_frame, text="Ready", style='Header.TLabel')
        self.progress_label.pack(anchor=tk.W)
        self.speed_label = ttk.Label(progress_frame, text="Speed: -- KB/s")
        self.speed_label.pack(anchor=tk.W)
        self.eta_label = ttk.Label(progress_frame, text="ETA: --")
        self.eta_label.pack(anchor=tk.W)

        graph_frame = ttk.LabelFrame(main_frame, text="Speed Monitor", padding="10")
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.speed_graph = SpeedGraph(graph_frame)
        self.speed_graph.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(main_frame, text="Status Log", padding="10")
        log_frame.pack(fill=tk.X, pady=5)
        self.log_text = tk.Text(log_frame, height=6, bg='#1e1e1e', fg='#00ff00', font=('Consolas', 9), relief=tk.FLAT)
        self.log_text.pack(fill=tk.X, expand=True, side=tk.LEFT)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text['yscrollcommand'] = scrollbar.set

    async def handle_add_download(self, request):
        """Web handler to receive a download URL from the native host."""
        try:
            data = await request.json()
            url = data.get("url")
            if url:
                self.root.after(0, self.on_url_detected, url)
                return web.Response(text="URL received")
        except Exception as e:
            self.root.after(0, self.log, f"Web server error: {e}")
            return web.Response(text=f"Error: {e}", status=500)
        return web.Response(text="Invalid request", status=400)

    async def start_web_server(self):
        """Initializes and starts the background web server on localhost."""
        app = web.Application()
        app.router.add_post('/add_download', self.handle_add_download)
        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        site = web.TCPSite(self.web_runner, '127.0.0.1', 9876) 
        await site.start()
        self.log("Browser integration server started on port 9876.")

    async def stop_web_server(self):
        """Stops the background web server gracefully."""
        if self.web_runner:
            await self.web_runner.cleanup()
            self.log("Browser integration server stopped.")

    def browse_file(self):
        filename = filedialog.asksaveasfilename(title="Save file as", defaultextension=".*")
        if filename:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, filename)

    def start_download(self):
        url = self.url_entry.get().strip()
        output_path = self.path_entry.get().strip()
        if not url or not is_valid_url(url):
            messagebox.showerror("Error", "Please enter a valid URL.")
            return
        if not output_path:
            messagebox.showerror("Error", "Please specify an output path.")
            return

        self.reset_ui()
        engine = DownloadEngine(url, output_path, self.threads_var.get())
        engine.progress_callback = self.on_progress
        engine.speed_callback = self.on_speed
        engine.status_callback = self.on_status
        speed_limit_text = self.speed_limit_var.get().strip()
        if speed_limit_text.isdigit():
            engine.set_speed_limit(float(speed_limit_text))
        
        self.downloads[url] = engine
        self.active_download = url
        self.update_button_states(is_running=True)

        self.log("Starting download...")
        self.start_time = time.time()
        threading.Thread(target=self.run_download, args=(engine,), daemon=True).start()
    
    def run_download(self, engine: DownloadEngine):
        try:
            asyncio.run(engine.download())
            if not engine.is_stopped:
                self.root.after(0, lambda: self.log("✓ Download completed successfully!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "Download completed!"))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"✗ Download failed: {e}"))
            self.root.after(0, lambda: messagebox.showerror("Error", f"Download failed: {e}"))
        finally:
            self.root.after(0, self.update_button_states, False)

    def pause_download(self):
        if self.active_download and self.active_download in self.downloads:
            self.downloads[self.active_download].pause()
            self.update_button_states(is_running=True, is_paused=True)

    def resume_download(self):
        if self.active_download and self.active_download in self.downloads:
            self.downloads[self.active_download].resume()
            self.update_button_states(is_running=True, is_paused=False)

    def stop_download(self):
        if self.active_download and self.active_download in self.downloads:
            self.downloads[self.active_download].stop()
            self.update_button_states(is_running=False)

    def on_progress(self, downloaded: int, total: int):
        if total > 0:
            progress = (downloaded / total) * 100
            self.progress_var.set(progress)
            self.root.after(0, lambda: self.progress_label.config(
                text=f"{format_bytes(downloaded)} / {format_bytes(total)} ({progress:.1f}%)"))

    def on_speed(self, current_speed: float, avg_speed: float):
        self.root.after(0, lambda: self.speed_label.config(text=f"Speed: {format_bytes(current_speed)}/s (avg: {format_bytes(avg_speed)}/s)"))
        if self.active_download and self.active_download in self.downloads:
            engine = self.downloads[self.active_download]
            remaining = engine.total_size - engine.downloaded_size
            if avg_speed > 0:
                eta_seconds = remaining / avg_speed
                self.root.after(0, lambda: self.eta_label.config(text=f"ETA: {str(timedelta(seconds=int(eta_seconds)))}"))
        self.root.after(0, self.speed_graph.update_plot, time.time() - self.start_time, current_speed / (1024 * 1024))

    def on_status(self, message: str):
        self.root.after(0, lambda: self.log(message))

    def on_url_detected(self, url: str):
        """Callback for web server. Fills the GUI with the detected URL."""
        self.log(f"Received URL from browser: {url}")
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, url)
        default_filename = get_default_filename(url)
        if default_filename:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, default_filename)
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))


    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def reset_ui(self):
        self.progress_var.set(0)
        self.progress_label.config(text="Initializing...")
        self.speed_label.config(text="Speed: --")
        self.eta_label.config(text="ETA: --")
        self.speed_graph.reset()
        self.log_text.delete('1.0', tk.END)

    def update_button_states(self, is_running: bool, is_paused: bool = False):
        self.pause_button.config(state=tk.NORMAL if is_running and not is_paused else tk.DISABLED)
        self.resume_button.config(state=tk.NORMAL if is_running and is_paused else tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL if is_running else tk.DISABLED)

    def run(self):
        """Run the application main loop and start background services."""
        self.log("TurboGet Advanced Download Manager initialized.")
        threading.Thread(target=lambda: asyncio.run(self.start_web_server()), daemon=True).start()
        self.root.mainloop()

    def on_closing(self):
        """Handle window closing event, ensuring graceful shutdown of services."""
        if self.active_download and self.downloads[self.active_download].is_running():
            if not messagebox.askokcancel("Quit", "A download is in progress. Are you sure you want to quit?"):
                return
        
        self.stop_download()
        if self.web_runner:
            asyncio.run(self.stop_web_server())
        
        self.root.destroy()

if __name__ == "__main__":
    app = TurboGetGUI()
    app.run()