import os
import sys
import subprocess
from threading import Thread
from queue import Queue
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class ActionPopup(ctk.CTkToplevel):
    """Popup window for choosing an action for a clicked item."""

    def __init__(self, parent, folder_name, folder_path, callback_queue):
        super().__init__(parent)
        self.folder_path = folder_path
        self.callback_queue = callback_queue

        self.title("Select Action")
        self.geometry("350x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        label = ctk.CTkLabel(self, text=f"What do you want to do with:\n{folder_name}?", font=("Arial", 13, "bold"),
                             wraplength=300)
        label.pack(pady=15)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=5)

        is_dir = os.path.isdir(folder_path)
        self.btn_scan = ctk.CTkButton(btn_frame, text="Queue Scan", width=100, command=self.action_queue)
        if not is_dir:
            self.btn_scan.configure(state="disabled")
        self.btn_scan.pack(side="left", expand=True, padx=5)

        self.btn_open = ctk.CTkButton(btn_frame, text="Open in Explorer", width=100, command=self.action_open)
        self.btn_open.pack(side="left", expand=True, padx=5)

    def action_queue(self):
        self.destroy()
        self.callback_queue(self.folder_path)

    def action_open(self):
        self.destroy()
        subprocess.run(['explorer', '/select,', os.path.normpath(self.folder_path)])


class ScanTab:
    """Helper class to manage UI and data for an individual scan tab."""

    def __init__(self, tab_frame, path):
        self.frame = tab_frame
        self.path = path
        self.scan_data = {}
        self.visible_paths = []
        self.visible_names = []

        # Setup Matplotlib Figure for this tab specifically
        self.fig, self.ax = plt.subplots(figsize=(6, 5), facecolor='#2b2b2b')
        self.canvas = None


class DiskAnalyzerApp(ctk.CTk):
    def __init__(self, initial_path=None):
        super().__init__()

        self.title("Disk Space Analyzer (Multi-Tab & Queue)")
        self.geometry("1100 rounded_by_user")
        self.geometry("1150x700")

        # State management
        self.is_running = True
        self.active_scan_tab = None  # Holds the ScanTab object currently scanning
        self.cancel_requested = False
        self.scan_queue = Queue()
        self.tab_map = {}  # Maps tab name string -> ScanTab object

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- UI Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar Panel
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.btn_select = ctk.CTkButton(self.sidebar, text="Scan New Folder / Drive", command=self.select_directory)
        self.btn_select.pack(pady=20, padx=20)

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Ready", wraplength=200, justify="left")
        self.lbl_status.pack(pady=10, padx=20)

        self.btn_cancel = ctk.CTkButton(self.sidebar, text="Cancel Active Scan", fg_color="#C0392B",
                                        hover_color="#A93226", command=self.cancel_active_scan)
        self.btn_close_tab = ctk.CTkButton(self.sidebar, text="Close Current Tab", fg_color="#555555",
                                           hover_color="#444444", command=self.close_current_tab)
        self.btn_close_tab.pack(pady=10, padx=20)

        # Right Panel (Tabview instead of standard Frame)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Start the queue manager background loop
        self.process_queue()

        if initial_path and os.path.exists(initial_path):
            self.enqueue_path(initial_path)

    def select_directory(self):
        target_dir = filedialog.askdirectory()
        if target_dir:
            self.enqueue_path(target_dir)

    def enqueue_path(self, path):
        """Adds a path to the scan queue and updates the UI status."""
        self.scan_queue.put(path)
        self.update_queue_status()

    def update_queue_status(self):
        q_size = self.scan_queue.qsize()
        if self.active_scan_tab:
            status = f"Scanning:\n{self.active_scan_tab.path}\n\n"
            if q_size > 0:
                status += f"In queue: {q_size} folder(s) pending..."
            else:
                status += "Queue is empty."
        else:
            if q_size > 0:
                status = f"Starting next scan... ({q_size} in queue)"
            else:
                status = "Ready"
        self.lbl_status.configure(text=status)

    def cancel_active_scan(self):
        if self.active_scan_tab:
            self.cancel_requested = True
            self.lbl_status.configure(text="Cancelling active scan...\nPlease wait.")
            self.btn_cancel.configure(state="disabled")

    def close_current_tab(self):
        current_tab_name = self.tabview.get()
        if not current_tab_name:
            return

        # If trying to close the tab currently being scanned, cancel it first
        if self.active_scan_tab and self.tab_map.get(current_tab_name) == self.active_scan_tab:
            self.cancel_active_scan()

        if current_tab_name in self.tab_map:
            tab_obj = self.tab_map[current_tab_name]
            plt.close(tab_obj.fig)
            del self.tab_map[current_tab_name]

        self.tabview.delete(current_tab_name)

    def process_queue(self):
        """Checks periodically if a new scan can be initialized from the queue."""
        if not self.is_running:
            return

        if self.active_scan_tab is None and not self.scan_queue.empty():
            next_path = self.scan_queue.get()
            self.start_scan_thread(next_path)
        else:
            self.after(500, self.process_queue)

    def start_scan_thread(self, path):
        self.cancel_requested = False
        self.btn_cancel.pack(pady=10, padx=20)

        # Create a unique tab name based on folder name + incrementing if duplicate
        base_name = os.path.basename(path) if os.path.basename(path) else path
        tab_name = base_name
        counter = 1
        while tab_name in self.tabview._tab_dict:
            tab_name = f"{base_name} ({counter})"
            counter += 1

        self.tabview.add(tab_name)
        self.tabview.set(tab_name)

        tab_frame = self.tabview.tab(tab_name)
        new_tab_obj = ScanTab(tab_frame, path)
        self.tab_map[tab_name] = new_tab_obj
        self.active_scan_tab = new_tab_obj

        self.update_queue_status()
        Thread(target=self.scan_directory, args=(new_tab_obj,), daemon=True).start()

    def scan_directory(self, tab_obj):
        dir_sizes = {}
        try:
            for item in os.listdir(tab_obj.path):
                if not self.is_running or self.cancel_requested:
                    self.after(0, self.handle_scan_interrupted)
                    return

                item_path = os.path.join(tab_obj.path, item)
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
                self.after(0, lambda: self.lbl_status.configure(text=f"Scan error:\n{str(e)}"))
                self.after(0, self.cleanup_after_scan)
            return

        if not self.is_running or self.cancel_requested:
            self.after(0, self.handle_scan_interrupted)
            return

        tab_obj.scan_data = dir_sizes
        self.after(0, lambda: self.update_chart(tab_obj))

    def get_dir_size(self, path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            if not self.is_running or self.cancel_requested:
                return 0
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_size += os.path.getsize(fp)
                except (PermissionError, FileNotFoundError):
                    continue
        return total_size

    def handle_scan_interrupted(self):
        if self.is_running:
            self.lbl_status.configure(text="Scan was cancelled.")
            self.cleanup_after_scan()

    def cleanup_after_scan(self):
        self.active_scan_tab = None
        self.cancel_requested = False
        self.btn_cancel.pack_forget()
        self.btn_cancel.configure(state="normal")
        self.update_queue_status()
        # Resume listening to queue
        self.after(100, self.process_queue)

    def format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def update_chart(self, tab_obj):
        if not self.is_running:
            return

        tab_obj.ax.clear()

        if not tab_obj.scan_data:
            lbl = ctk.CTkLabel(tab_obj.frame, text="The folder is empty or protected.")
            lbl.pack(pady=40)
            self.cleanup_after_scan()
            return

        sorted_data = sorted(tab_obj.scan_data.items(), key=lambda x: x[1][1], reverse=True)[:10]
        legend_labels = [f"{item[0]} ({self.format_size(item[1][1])})" for item in sorted_data]
        sizes = [item[1][1] for item in sorted_data]

        tab_obj.visible_paths = [item[1][0] for item in sorted_data]
        tab_obj.visible_names = [item[0] for item in sorted_data]

        pie_result = tab_obj.ax.pie(
            sizes,
            autopct='%1.1f%%',
            startangle=140,
            textprops=dict(color="w", fontsize=9, weight="bold")
        )

        try:
            items = list(pie_result)
            wedges = items[0]
            autotexts = items[-1]
        except (TypeError, IndexError):
            wedges, autotexts = pie_result

        total_size = sum(sizes)
        for i, p in enumerate(sizes):
            if (p / total_size) * 100 < 2.5 and i < len(autotexts):
                autotexts[i].set_text("")

        for i, wedge in enumerate(wedges):
            wedge.set_picker(True)
            wedge.set_gid(i)

        tab_obj.ax.axis('equal')

        # Tie the click event listener specifically to this tab's canvas context
        tab_obj.fig.canvas.mpl_connect('pick_event', lambda event: self.on_pie_click(event, tab_obj))

        tab_obj.ax.legend(
            wedges, legend_labels, title="Folders / Files", title_fontsize=11,
            loc="center left", bbox_to_anchor=(1, 0, 0.5, 1),
            facecolor='#2b2b2b', edgecolor='none', labelcolor='white', fontsize=9
        )

        tab_obj.fig.tight_layout()

        tab_obj.canvas = FigureCanvasTkAgg(tab_obj.fig, master=tab_obj.frame)
        tab_obj.canvas.draw()
        tab_obj.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.cleanup_after_scan()

    def on_pie_click(self, event, tab_obj):
        # We block popups only if THIS specific tab is currently scanning
        if self.active_scan_tab == tab_obj:
            return

        idx = event.artist.get_gid()
        if idx is not None and idx < len(tab_obj.visible_names):
            folder_name = tab_obj.visible_names[idx]
            folder_path = tab_obj.visible_paths[idx]

            ActionPopup(self, folder_name, folder_path, self.enqueue_path)

    def on_closing(self):
        self.is_running = False
        self.cancel_requested = True
        for tab_obj in self.tab_map.values():
            plt.close(tab_obj.fig)
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    app = DiskAnalyzerApp(initial_path=path_arg)
    app.mainloop()