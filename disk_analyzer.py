import os
import sys
import subprocess
from threading import Thread
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class ActionPopup(ctk.CTkToplevel):
    """A small popup window letting the user choose an action for the clicked item."""
    def __init__(self, parent, folder_name, folder_path, callback_scan):
        super().__init__(parent)
        self.folder_path = folder_path
        self.callback_scan = callback_scan

        self.title("Select Action")
        self.geometry("350x150")
        self.resizable(False, False)
        self.transient(parent)  # Keep on top of main window
        self.grab_set()         # Make window modal

        # Center the popup over the parent window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        label = ctk.CTkLabel(self, text=f"What do you want to do with:\n{folder_name}?", font=("Arial", 13, "bold"),
                             wraplength=300)
        label.pack(pady=15)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=5)

        # Disable the scan button if the targeted item is a file instead of a folder
        is_dir = os.path.isdir(folder_path)
        self.btn_scan = ctk.CTkButton(btn_frame, text="Scan Folder", width=100, command=self.action_scan)
        if not is_dir:
            self.btn_scan.configure(state="disabled")
        self.btn_scan.pack(side="left", expand=True, padx=5)

        self.btn_open = ctk.CTkButton(btn_frame, text="Open in Explorer", width=100, command=self.action_open)
        self.btn_open.pack(side="left", expand=True, padx=5)

    def action_scan(self):
        self.destroy()
        self.callback_scan(self.folder_path)

    def action_open(self):
        self.destroy()
        subprocess.run(['explorer', '/select,', os.path.normpath(self.folder_path)])


class DiskSpaceAnalyzerApp(ctk.CTk):
    def __init__(self, initial_path=None):
        super().__init__()

        self.title("Disk Space Analyzer")
        self.geometry("1050x650")  # Made slightly wider to comfortably fit the legend list

        self.current_scan_data = {}
        self.is_running = True

        # Handle clean termination when clicking the 'X' button
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- UI Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Panel (Controls)
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.btn_select = ctk.CTkButton(self.sidebar, text="Select Folder / Drive", command=self.select_directory)
        self.btn_select.pack(pady=20, padx=20)

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Ready", wraplength=200, justify="left")
        self.lbl_status.pack(pady=10, padx=20)

        # Right Panel (Chart Frame)
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Use tight_layout immediately to maximize space utilization
        self.fig, self.ax = plt.subplots(figsize=(7, 6), facecolor='#2b2b2b')
        self.canvas = None

        # Check if the app was launched with a folder argument (e.g., from the right-click menu)
        if initial_path and os.path.exists(initial_path):
            self.start_scan_thread(initial_path)
        else:
            self.lbl_status.configure(text="Select a folder or drive to start the analysis.")

    def select_directory(self):
        target_dir = filedialog.askdirectory()
        if target_dir:
            self.start_scan_thread(target_dir)

    def start_scan_thread(self, path):
        self.lbl_status.configure(text=f"Scanning:\n{path}\nPlease wait...")
        Thread(target=self.scan_directory, args=(path,), daemon=True).start()

    def scan_directory(self, path):
        dir_sizes = {}
        try:
            # Scans only the top-level files/directories of the target path to keep the pie clean
            for item in os.listdir(path):
                if not self.is_running:
                    return

                item_path = os.path.join(path, item)
                try:
                    if os.path.isdir(item_path):
                        size = self.get_dir_size(item_path)
                    else:
                        size = os.path.getsize(item_path)

                    if size > 0:
                        dir_sizes[item] = (item_path, size)
                except PermissionError:
                    continue
        except Exception as e:
            if self.is_running:
                self.lbl_status.configure(text=f"Scan error:\n{str(e)}")
            return

        if not self.is_running:
            return

        self.current_scan_data = dir_sizes
        self.after(0, self.update_chart)

    def get_dir_size(self, path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            if not self.is_running:
                return 0

            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_size += os.path.getsize(fp)
                except (PermissionError, FileNotFoundError):
                    continue
        return total_size

    def format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def update_chart(self):
        if not self.is_running:
            return

        self.ax.clear()

        if not self.current_scan_data:
            self.lbl_status.configure(text="The folder is empty or could not be read.")
            return

        # Sort items by size descending and limit to the top 10 for clarity
        sorted_data = sorted(self.current_scan_data.items(), key=lambda x: x[1][1], reverse=True)[:10]

        legend_labels = [f"{item[0]} ({self.format_size(item[1][1])})" for item in sorted_data]
        sizes = [item[1][1] for item in sorted_data]

        self.current_visible_paths = [item[1][0] for item in sorted_data]
        self.current_visible_names = [item[0] for item in sorted_data]

        # Generate the pie chart without external labels to prevent text overlaps
        pie_result = self.ax.pie(
            sizes,
            autopct='%1.1f%%',
            startangle=140,
            textprops=dict(color="w", fontsize=9, weight="bold")
        )

        # BULLETPROOF UNPACKING HACK:
        # Handles Matplotlib's tuple returns alongside modern PieContainer objects interchangeably.
        try:
            items = list(pie_result)
            if len(items) == 2:
                wedges, autotexts = items
            else:
                wedges, texts, autotexts = items
        except TypeError:
            wedges, autotexts = pie_result

        # Suppress percentage texts on tiny wedges (< 2.5%) to prevent cramped layouts
        total_size = sum(sizes)
        for i, p in enumerate(sizes):
            percentage = (p / total_size) * 100
            if percentage < 2.5:
                if i < len(autotexts):
                    autotexts[i].set_text("")

        # Make the slices interactive
        for i, wedge in enumerate(wedges):
            wedge.set_picker(True)
            wedge.set_gid(i)

        self.ax.axis('equal')
        self.fig.canvas.mpl_connect('pick_event', self.on_pie_click)

        # ADD LEGEND PANEL (List layout on the right side)
        self.ax.legend(
            wedges,
            legend_labels,
            title="Folders / Files",
            title_fontsize=11,
            loc="center left",
            bbox_to_anchor=(1, 0, 0.5, 1),
            facecolor='#2b2b2b',
            edgecolor='none',
            labelcolor='white',
            fontsize=9
        )

        self.fig.tight_layout()

        if self.canvas:
            self.canvas.get_tk_widget().destroy()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.lbl_status.configure(
            text="Scan finished!\n\nClick on a pie slice to choose an action (Scan further or open in Explorer).")

    def on_pie_click(self, event):
        idx = event.artist.get_gid()
        if idx is not None:
            folder_name = self.current_visible_names[idx]
            folder_path = self.current_visible_paths[idx]

            ActionPopup(self, folder_name, folder_path, self.start_scan_thread)

    def on_closing(self):
        """Ensures a graceful and silent termination of background worker loops and memory arrays."""
        self.is_running = False
        plt.close(self.fig)
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    app = DiskSpaceAnalyzerApp(initial_path=path_arg)
    app.mainloop()