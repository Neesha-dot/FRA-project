import tkinter as tk
from tkinter import ttk, messagebox
import time

try:
    import psutil
except ImportError:
    psutil = None


class MonitorPerformanceUI:
    # ---- common colours (no blue) ----
    BASE_BG = "#f1f5f9"     # light grey
    HEADER_BG = "#e5e7eb"   # header grey
    ACCENT = "#4b5563"      # dark grey accent
    ACCENT_MED = "#9ca3af"  # medium grey
    CARD_BG = "#ffffff"     # white cards
    MUTED_TEXT = "#374151"  # readable dark grey

    @classmethod
    def _base_window(cls, app, title, subtitle):
        """Create header + card container + footer. Return (win, card_frame, status_lbl, time_lbl)."""
        win = tk.Toplevel(app.root)
        win.title(title)

        # ---- size + center ----
        width, height = 800, 520
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.minsize(640, 480)

        win.config(bg=cls.BASE_BG)

        # ---------- Header ----------
        header = tk.Frame(win, bg=cls.HEADER_BG, height=110)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        left = tk.Frame(header, bg=cls.HEADER_BG)
        left.pack(side=tk.LEFT, padx=28, pady=18, fill=tk.Y)

        tk.Label(
            left, text=title, font=("Segoe UI", 22, "bold"),
            bg=cls.HEADER_BG, fg="#111827"
        ).pack(anchor="w")

        tk.Label(
            left, text=subtitle, font=("Segoe UI", 10),
            bg=cls.HEADER_BG, fg="#4b5563", wraplength=540, justify="left"
        ).pack(anchor="w", pady=(6, 0))

        right = tk.Frame(header, bg=cls.HEADER_BG)
        right.pack(side=tk.RIGHT, padx=24, pady=18)

        tk.Label(
            right, text="System Monitor",
            font=("Segoe UI", 9, "bold"),
            bg=cls.ACCENT, fg="#ffffff", padx=12, pady=6
        ).pack(anchor="e")

        # ---------- Body card ----------
        outer = tk.Frame(win, bg=cls.BASE_BG)
        outer.pack(fill=tk.BOTH, expand=True, padx=22, pady=(12, 18))

        card = tk.Frame(outer, bg=cls.CARD_BG)
        card.pack(fill=tk.BOTH, expand=True)

        # ---------- Footer ----------
        footer = tk.Frame(win, bg=cls.HEADER_BG, height=46)
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        footer.pack_propagate(False)

        status_frame = tk.Frame(footer, bg=cls.HEADER_BG)
        status_frame.pack(side=tk.LEFT, padx=18, pady=10)

        tk.Label(
            status_frame, text="●", font=("Segoe UI", 14),
            bg=cls.HEADER_BG, fg="#16a34a"
        ).pack(side=tk.LEFT, padx=(0, 6))

        status_lbl = tk.Label(
            status_frame, text="Real-time monitoring active",
            bg=cls.HEADER_BG, fg="#111827", font=("Segoe UI", 9, "bold")
        )
        status_lbl.pack(side=tk.LEFT)

        time_lbl = tk.Label(
            footer, text="Last update: --:--:--",
            bg=cls.HEADER_BG, fg="#4b5563", font=("Segoe UI", 9)
        )
        time_lbl.pack(side=tk.RIGHT, padx=18)

        # close handler
        win.is_open = True

        def on_close():
            win.is_open = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        # log
        try:
            app.log_console(f"Opened: {title}", "INFO")
        except Exception:
            pass

        return win, card, status_lbl, time_lbl
    # --------------------------------------------------
    # DASHBOARD  (summary: CPU, RAM, Disk, Network)
    # --------------------------------------------------
    @classmethod
    def dashboard(cls, app):
        win, card, _, time_lbl = cls._base_window(
            app,
            "Dashboard",
            "High-level overview of CPU, memory, disk and network usage (live from this system)."
        )

        # ===== scrollable content inside card =====
        scroll_container = tk.Frame(card, bg=cls.CARD_BG)
        scroll_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(
            scroll_container,
            bg=cls.CARD_BG,
            highlightthickness=0,
            bd=0
        )
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            scroll_container,
            orient="vertical",
            command=canvas.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        scroll_frame = tk.Frame(canvas, bg=cls.CARD_BG)
        window_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            # make inner frame same width as canvas
            canvas.itemconfig(window_id, width=event.width)

        scroll_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        # ====== actual dashboard content goes in scroll_frame ======
        header = tk.Frame(scroll_frame, bg=cls.CARD_BG)
        header.pack(fill=tk.X, padx=20, pady=(16, 8))
        tk.Label(
            header, text="System Overview",
            font=("Segoe UI", 14, "bold"),
            bg=cls.CARD_BG, fg=cls.ACCENT
        ).pack(side=tk.LEFT)

        sep = tk.Frame(scroll_frame, bg="#e5e7eb", height=1)
        sep.pack(fill=tk.X, padx=20, pady=(0, 10))

        grid = tk.Frame(scroll_frame, bg=cls.CARD_BG)
        grid.pack(fill=tk.X, padx=30, pady=10)

        def make_stat(row, title):
            box = tk.Frame(grid, bg="#f3f4f6", bd=1, relief=tk.FLAT)
            box.grid(row=row, column=0, sticky="ew", pady=6)
            grid.columnconfigure(0, weight=1)

            top = tk.Frame(box, bg="#f3f4f6")
            top.pack(fill=tk.X, padx=10, pady=(6, 2))
            tk.Label(
                top, text=title, font=("Segoe UI", 11, "bold"),
                bg="#f3f4f6", fg=cls.ACCENT
            ).pack(side=tk.LEFT)

            val = tk.Label(
                box, text="--", font=("Segoe UI", 12, "bold"),
                bg="#f3f4f6", fg=cls.MUTED_TEXT
            )
            val.pack(anchor="w", padx=10, pady=(0, 6))

            return val

        cpu_lbl   = make_stat(0, "CPU Usage")
        ram_lbl   = make_stat(1, "Memory (RAM)")
        disk_lbl  = make_stat(2, "Disk Usage (System Drive)")
        net_lbl   = make_stat(3, "Network Throughput (approx)")

        prev_net = psutil.net_io_counters() if psutil else None
        prev_time = time.time()

        def update():
            if not win.is_open:
                return

            if psutil is None:
                for lbl in (cpu_lbl, ram_lbl, disk_lbl, net_lbl):
                    lbl.config(text="psutil not installed (pip install psutil)")
            else:
                cpu = psutil.cpu_percent(interval=None)
                cpu_lbl.config(text=f"{cpu:.1f} %")

                mem = psutil.virtual_memory()
                used = mem.used / (1024 ** 3)
                total = mem.total / (1024 ** 3)
                ram_lbl.config(text=f"{used:.2f} / {total:.2f} GB  ({mem.percent:.1f} %)")

                disk = psutil.disk_usage("/")
                d_used = disk.used / (1024 ** 3)
                d_total = disk.total / (1024 ** 3)
                disk_lbl.config(text=f"{d_used:.1f} / {d_total:.1f} GB  ({disk.percent:.0f} %)")

                nonlocal prev_net, prev_time
                now_net = psutil.net_io_counters()
                now_time = time.time()
                if prev_net:
                    seconds = max(now_time - prev_time, 0.0001)
                    up = (now_net.bytes_sent - prev_net.bytes_sent) / seconds
                    down = (now_net.bytes_recv - prev_net.bytes_recv) / seconds
                    up_kb = up / 1024
                    down_kb = down / 1024
                    net_lbl.config(text=f"Up: {up_kb:.1f} KB/s   Down: {down_kb:.1f} KB/s")
                prev_net, prev_time = now_net, now_time

            time_lbl.config(text=f"Last update: {time.strftime('%H:%M:%S')}")
            win.after(1000, update)

        update()


    # --------------------------------------------------
    # REAL-TIME MONITORING (progress bars)
    # --------------------------------------------------
    @classmethod
    def real_time(cls, app):
        win, card, _, time_lbl = cls._base_window(
            app,
            "Real-time Monitoring",
            "Continuous view of CPU and RAM load using live progress bars."
        )

        frame = tk.Frame(card, bg=cls.CARD_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        tk.Label(
            frame, text="CPU Usage", font=("Segoe UI", 11, "bold"),
            bg=cls.CARD_BG, fg=cls.MUTED_TEXT
        ).pack(anchor="w")

        cpu_bar = ttk.Progressbar(frame, orient="horizontal", length=350,
                                  mode="determinate", maximum=100)
        cpu_bar.pack(anchor="w", pady=(4, 8))
        cpu_lbl = tk.Label(frame, text="-- %", font=("Segoe UI", 10, "bold"),
                           bg=cls.CARD_BG, fg=cls.ACCENT)
        cpu_lbl.pack(anchor="w", pady=(0, 16))

        tk.Label(
            frame, text="RAM Usage", font=("Segoe UI", 11, "bold"),
            bg=cls.CARD_BG, fg=cls.MUTED_TEXT
        ).pack(anchor="w")

        ram_bar = ttk.Progressbar(frame, orient="horizontal", length=350,
                                  mode="determinate", maximum=100)
        ram_bar.pack(anchor="w", pady=(4, 8))
        ram_lbl = tk.Label(frame, text="-- %", font=("Segoe UI", 10, "bold"),
                           bg=cls.CARD_BG, fg=cls.ACCENT)
        ram_lbl.pack(anchor="w")

        def update():
            if not win.is_open:
                return
            if psutil is None:
                cpu_lbl.config(text="psutil missing")
                ram_lbl.config(text="psutil missing")
            else:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()

                cpu_bar['value'] = cpu
                ram_bar['value'] = mem.percent

                cpu_lbl.config(text=f"{cpu:.1f} %")
                ram_lbl.config(text=f"{mem.percent:.1f} %")

            time_lbl.config(text=f"Last update: {time.strftime('%H:%M:%S')}")
            win.after(500, update)

        update()

    # --------------------------------------------------
    # LOAD ANALYSIS (mini history in this session)
    # --------------------------------------------------
    @classmethod
    def load_analysis(cls, app):
        win, card, _, time_lbl = cls._base_window(
            app,
            "Load Analysis",
            "Short history of CPU & RAM usage since this window opened."
        )

        frame = tk.Frame(card, bg=cls.CARD_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        tk.Label(
            frame, text="Recent Averages (last 60 samples)",
            font=("Segoe UI", 11, "bold"), bg=cls.CARD_BG, fg=cls.ACCENT
        ).pack(anchor="w")

        cpu_avg_lbl = tk.Label(frame, text="CPU Avg: -- %", bg=cls.CARD_BG,
                               fg=cls.MUTED_TEXT, font=("Segoe UI", 10))
        cpu_avg_lbl.pack(anchor="w", pady=(10, 4))

        ram_avg_lbl = tk.Label(frame, text="RAM Avg: -- %", bg=cls.CARD_BG,
                               fg=cls.MUTED_TEXT, font=("Segoe UI", 10))
        ram_avg_lbl.pack(anchor="w", pady=(2, 10))

        history_text = tk.Text(frame, height=15, bg="#f3f4f6",
                               fg=cls.MUTED_TEXT, font=("Segoe UI", 9))
        history_text.pack(fill=tk.BOTH, expand=True)

        cpu_history = []
        ram_history = []

        def update():
            if not win.is_open:
                return
            if psutil is not None:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent

                cpu_history.append(cpu)
                ram_history.append(mem)
                if len(cpu_history) > 60:
                    cpu_history.pop(0)
                    ram_history.pop(0)

                cpu_avg = sum(cpu_history) / len(cpu_history)
                ram_avg = sum(ram_history) / len(ram_history)

                cpu_avg_lbl.config(text=f"CPU Avg (approx): {cpu_avg:.1f} %")
                ram_avg_lbl.config(text=f"RAM Avg (approx): {ram_avg:.1f} %")

                history_text.insert(
                    tk.END,
                    f"{time.strftime('%H:%M:%S')}  CPU: {cpu:5.1f}%  RAM: {mem:5.1f}%\n"
                )
                history_text.see(tk.END)
            else:
                history_text.insert(tk.END, "psutil not installed.\n")

            time_lbl.config(text=f"Last update: {time.strftime('%H:%M:%S')}")
            win.after(1000, update)

        update()

    # --------------------------------------------------
    # TEMPERATURE MONITORING
    # --------------------------------------------------
    @classmethod
    def temperature(cls, app):
        win, card, _, time_lbl = cls._base_window(
            app,
            "Temperature Monitoring",
            "CPU/GPU temperature readings (where sensors are available)."
        )

        frame = tk.Frame(card, bg=cls.CARD_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        cpu_temp_lbl = tk.Label(frame, text="CPU Temp: --", bg=cls.CARD_BG,
                                fg=cls.MUTED_TEXT, font=("Segoe UI", 10))
        cpu_temp_lbl.pack(anchor="w", pady=4)

        gpu_temp_lbl = tk.Label(frame, text="GPU Temp: --", bg=cls.CARD_BG,
                                fg=cls.MUTED_TEXT, font=("Segoe UI", 10))
        gpu_temp_lbl.pack(anchor="w", pady=4)

        note_lbl = tk.Label(
            frame,
            text="* Some systems do not expose temperature sensors to psutil.",
            bg=cls.CARD_BG, fg=cls.MUTED_TEXT, font=("Segoe UI", 8)
        )
        note_lbl.pack(anchor="w", pady=(10, 0))

        def update():
            if not win.is_open:
                return
            if psutil is None or not hasattr(psutil, "sensors_temperatures"):
                cpu_temp_lbl.config(text="CPU Temp: N/A (no sensors/psutil)")
                gpu_temp_lbl.config(text="GPU Temp: N/A (no sensors/psutil)")
            else:
                temps = psutil.sensors_temperatures()
                cpu_str = "CPU Temp: N/A"
                gpu_str = "GPU Temp: N/A"
                for key, entries in temps.items():
                    for e in entries:
                        name = (e.label or key).lower()
                        if "cpu" in name or "core 0" in name:
                            cpu_str = f"CPU Temp: {e.current:.1f} °C"
                        if "gpu" in name or "graphics" in name:
                            gpu_str = f"GPU Temp: {e.current:.1f} °C"
                cpu_temp_lbl.config(text=cpu_str)
                gpu_temp_lbl.config(text=gpu_str)

            time_lbl.config(text=f"Last update: {time.strftime('%H:%M:%S')}")
            win.after(2000, update)

        update()

    # --------------------------------------------------
    # HISTORICAL DATA (simple session log)
    # --------------------------------------------------
    @classmethod
    def history(cls, app):
        win, card, _, time_lbl = cls._base_window(
            app,
            "Historical Data",
            "Live log of CPU, RAM, Disk and Network while this window is open."
        )

        text = tk.Text(card, bg="#f3f4f6", fg=cls.MUTED_TEXT, font=("Segoe UI", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        def update():
            if not win.is_open:
                return
            if psutil is not None:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage("/").percent
                net = psutil.net_io_counters()
                line = (
                    f"{time.strftime('%H:%M:%S')}  "
                    f"CPU {cpu:5.1f}%  RAM {mem:5.1f}%  DISK {disk:5.1f}%  "
                    f"TX {net.bytes_sent/1024/1024:6.2f}MB  RX {net.bytes_recv/1024/1024:6.2f}MB\n"
                )
            else:
                line = f"{time.strftime('%H:%M:%S')}  psutil not installed.\n"

            text.insert(tk.END, line)
            text.see(tk.END)

            time_lbl.config(text=f"Last update: {time.strftime('%H:%M:%S')}")
            win.after(1500, update)

        update()

    # --------------------------------------------------
    # GENERATE REPORT (snapshot)
    # --------------------------------------------------
    @classmethod
    def reports(cls, app):
        win, card, _, time_lbl = cls._base_window(
            app,
            "Generate Report",
            "Shows current snapshot of system usage (you can copy text as a mini report)."
        )

        text = tk.Text(card, bg="#f3f4f6", fg=cls.MUTED_TEXT, font=("Segoe UI", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        def refresh_snapshot():
            text.delete("1.0", tk.END)
            if psutil is None:
                text.insert(tk.END, "psutil not installed.\n")
            else:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage("/")
                net = psutil.net_io_counters()

                text.insert(tk.END, f"Report time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                text.insert(tk.END, f"CPU Usage: {cpu:.1f}%\n")
                text.insert(tk.END, f"RAM Usage: {mem.percent:.1f}%  ({mem.used/1024**3:.2f}/{mem.total/1024**3:.2f} GB)\n")
                text.insert(tk.END, f"Disk Usage (/): {disk.percent:.1f}%  ({disk.used/1024**3:.1f}/{disk.total/1024**3:.1f} GB)\n")
                text.insert(tk.END, f"Network Sent: {net.bytes_sent/1024**2:.2f} MB\n")
                text.insert(tk.END, f"Network Received: {net.bytes_recv/1024**2:.2f} MB\n")

            time_lbl.config(text=f"Last update: {time.strftime('%H:%M:%S')}")

        btn = tk.Button(card, text="Refresh Snapshot", bg=cls.ACCENT, fg="#ffffff",
                        font=("Segoe UI", 9, "bold"), pady=4, command=refresh_snapshot)
        btn.pack(side=tk.BOTTOM, pady=10)

        refresh_snapshot()

    # --------------------------------------------------
    # ALERTS & NOTIFICATIONS (thresholds)
    # --------------------------------------------------
    @classmethod
    def alerts(cls, app):
        win, card, _, time_lbl = cls._base_window(
            app,
            "Alerts & Notifications",
            "Simple live alerts for high CPU / RAM / Disk usage."
        )

        frame = tk.Frame(card, bg=cls.CARD_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        info = tk.Label(
            frame,
            text="Thresholds: CPU > 80%, RAM > 80%, Disk > 90%",
            bg=cls.CARD_BG, fg=cls.MUTED_TEXT, font=("Segoe UI", 9)
        )
        info.pack(anchor="w", pady=(0, 10))

        alert_box = tk.Text(frame, height=15, bg="#f3f4f6",
                            fg=cls.MUTED_TEXT, font=("Segoe UI", 9))
        alert_box.pack(fill=tk.BOTH, expand=True)

        def update():
            if not win.is_open:
                return
            if psutil is not None:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage("/").percent

                alerts = []
                if cpu > 80:
                    alerts.append(f"High CPU usage: {cpu:.1f}%")
                if mem > 80:
                    alerts.append(f"High RAM usage: {mem:.1f}%")
                if disk > 90:
                    alerts.append(f"High Disk usage: {disk:.1f}%")

                if alerts:
                    for a in alerts:
                        alert_box.insert(tk.END, f"{time.strftime('%H:%M:%S')}  {a}\n")
                        alert_box.see(tk.END)
            else:
                alert_box.insert(tk.END, "psutil not installed.\n")
                alert_box.see(tk.END)

            time_lbl.config(text=f"Last update: {time.strftime('%H:%M:%S')}")
            win.after(2000, update)

        update()


# ---------------- DEMO MAIN APP (menu) ---------------- #
class SimpleApp:
    def __init__(self, root):
        self.root = root
        root.title("Welcome to vidhyut")

        # root size + center
        width, height = 950, 600
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.config(bg=MonitorPerformanceUI.BASE_BG)

        menubar = tk.Menu(root)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        editmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=editmenu)

        monmenu = tk.Menu(menubar, tearoff=0)
        monmenu.add_command(label="Dashboard", command=lambda: MonitorPerformanceUI.dashboard(self))
        monmenu.add_command(label="Real-time Monitoring", command=lambda: MonitorPerformanceUI.real_time(self))
        monmenu.add_command(label="Load Analysis", command=lambda: MonitorPerformanceUI.load_analysis(self))
        monmenu.add_command(label="Temperature Monitoring", command=lambda: MonitorPerformanceUI.temperature(self))
        monmenu.add_separator()
        monmenu.add_command(label="Historical Data", command=lambda: MonitorPerformanceUI.history(self))
        monmenu.add_command(label="Generate Report", command=lambda: MonitorPerformanceUI.reports(self))
        monmenu.add_command(label="Alerts & Notifications", command=lambda: MonitorPerformanceUI.alerts(self))
        menubar.add_cascade(label="Monitor Performance", menu=monmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpmenu)

        root.config(menu=menubar)

        # console at bottom
        console_frame = tk.Frame(root, bg="#e5e7eb")
        console_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.console_text = tk.Text(console_frame, height=6, bg="#111827",
                                    fg="#e5e7eb", font=("Segoe UI", 9))
        self.console_text.pack(fill=tk.X, padx=6, pady=6)
        self.log_console("Application initialized successfully.", "SUCCESS")

    def log_console(self, message, level="INFO"):
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now}] [{level}] {message}\n"
        self.console_text.insert(tk.END, line)
        self.console_text.see(tk.END)

    def show_about(self):
        messagebox.showinfo("About", "Vidhyut – Real-time system monitoring demo.")


if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleApp(root)
    root.mainloop()