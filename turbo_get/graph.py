# turbo_get/graph.py
"""
Manages the speed monitoring graph using Matplotlib.
"""

import tkinter as tk
from collections import deque
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class SpeedGraph:
    """A class to handle the plotting of download speed over time."""

    def __init__(self, master_frame: tk.Frame):
        self.figure = Figure(figsize=(8, 2.5), facecolor='#2b2b2b', dpi=100)
        self.ax = self.figure.add_subplot(111, facecolor='#1e1e1e')
        
        # Styling
        self.ax.tick_params(axis='x', colors='white')
        self.ax.tick_params(axis='y', colors='white')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.set_xlabel('Time (s)', color='white')
        self.ax.set_ylabel('Speed (MB/s)', color='white')
        
        self.figure.tight_layout() # Adjust plot to fit into figure area.

        self.canvas = FigureCanvasTkAgg(self.figure, master=master_frame)
        
        # Data storage
        self.time_data = deque(maxlen=60)  # Store last 60 seconds of data
        self.speed_data = deque(maxlen=60)

    def get_tk_widget(self) -> tk.Widget:
        """Returns the Tkinter widget for embedding in the GUI."""
        return self.canvas.get_tk_widget()

    def update_plot(self, time_point: float, speed_point: float):
        """Adds a new data point and redraws the graph."""
        self.time_data.append(time_point)
        self.speed_data.append(speed_point)

        self.ax.clear()
        
        if self.time_data and self.speed_data:
            self.ax.plot(list(self.time_data), list(self.speed_data), color='#00ff00', linewidth=2)
            self.ax.fill_between(list(self.time_data), list(self.speed_data), color='#00ff00', alpha=0.2)

        # Re-apply styling after clearing
        self.ax.set_xlabel('Time (s)', color='white')
        self.ax.set_ylabel('Speed (MB/s)', color='white')
        self.ax.grid(True, linestyle='--', alpha=0.2, color='white')
        
        # Set y-axis limit to be slightly higher than the max speed shown
        if self.speed_data:
            max_speed = max(self.speed_data)
            self.ax.set_ylim(0, max_speed * 1.2 + 1) # Add 1 MB/s buffer
        
        self.canvas.draw()

    def reset(self):
        """Clears all data and resets the graph to its initial state."""
        self.time_data.clear()
        self.speed_data.clear()
        self.ax.clear()
        
        # Re-apply initial styling
        self.ax.set_xlabel('Time (s)', color='white')
        self.ax.set_ylabel('Speed (MB/s)', color='white')
        self.ax.grid(True, linestyle='--', alpha=0.2, color='white')
        self.ax.set_ylim(0, 1)

        self.canvas.draw()