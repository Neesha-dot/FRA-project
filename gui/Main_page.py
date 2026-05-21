import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
import json
from analyse_graph import enable_analyse_graph
from generate_report import enable as enable_generate_report
from Monitor_performance import MonitorPerformanceUI

# Add parent directory to path to import app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import ProjectManager
from app import ProjectManager
from send_report import SendReportModule
from smart_suggestions import enable_smart_suggestions

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Welcome to vidhyut")
        self.root.geometry("1400x900")
        self.root.state('zoomed')  # Maximize window

        # Initialize state variables for file operations
        self.unsaved_changes = False
        self.project_data = {}
        self.current_file = None
        self.recent_projects = []

        # Initialize project manager
        self.project_manager = ProjectManager()

        # Color scheme - MS Word style
        self.menu_bg = "#f3f3f3"
        self.menu_hover = "#e5f3ff"
        self.menu_active_bg = "#cce4f7"
        self.content_bg = "#ffffff"
        self.accent_color = "#2196F3"

        # Track active menu
        self.active_menu = None

        # Load recent projects
        self.load_recent_projects()

        # Create custom menu bar (Word-style)
        self.create_word_style_menubar()

        # Create main content area
        self.create_content_area()

        # Setup keyboard shortcuts
        self.setup_shortcuts()

    def create_word_style_menubar(self):
        """Create a Microsoft Word-style menu bar"""
        # Menu bar container
        menubar_frame = tk.Frame(self.root, bg=self.menu_bg, height=30, relief=tk.FLAT)
        menubar_frame.pack(fill=tk.X, side=tk.TOP)
        menubar_frame.pack_propagate(False)

        # Menu items
        menu_items = ["File", "Edit", "Monitor Performance", "Help"]

        self.menu_labels = {}
        self.dropdown_menus = {}

        for item in menu_items:
            # Create label for each menu
            label = tk.Label(
                menubar_frame,
                text=item,
                font=("Segoe UI", 10),
                bg=self.menu_bg,
                fg="#333333",
                padx=15,
                pady=5,
                cursor="hand2"
            )
            label.pack(side=tk.LEFT)

            # Store label reference
            self.menu_labels[item] = label

            # Bind events
            label.bind("<Enter>", lambda e, lbl=label, name=item: self.on_menu_hover(lbl, name))
            label.bind("<Leave>", lambda e, lbl=label, name=item: self.on_menu_leave(lbl, name))
            label.bind("<Button-1>", lambda e, name=item: self.toggle_menu(name))

        # Container for dropdown menus (will be positioned absolutely)
        self.dropdown_container = tk.Frame(self.root, bg="white", relief=tk.RAISED, borderwidth=1)

    def on_menu_hover(self, label, name):
        """Handle mouse hover on menu item"""
        if self.active_menu != name:
            label.config(bg=self.menu_hover)

    def on_menu_leave(self, label, name):
        """Handle mouse leave from menu item"""
        if self.active_menu != name:
            label.config(bg=self.menu_bg)

    def toggle_menu(self, name):
        """Toggle dropdown menu"""
        # Close any open menu
        if self.active_menu == name:
            self.close_menu()
        else:
            self.close_menu()
            self.show_menu(name)

    def show_menu(self, name):
        """Show dropdown menu for selected item"""
        self.active_menu = name

        # Highlight active menu
        self.menu_labels[name].config(bg=self.menu_active_bg)

        # Position dropdown container using place (absolute positioning over content)
        self.dropdown_container.place(x=0, y=30)

        # Raise the dropdown container to ensure it appears on top
        self.dropdown_container.lift()

        # Create dropdown based on menu name
        if name == "File":
            self.create_file_menu()
        elif name == "Edit":
            self.create_edit_menu()
        elif name == "Monitor Performance":
            self.create_monitor_menu()
        elif name == "Help":
            self.create_help_menu()

        # Bind click outside to close
        self.root.bind("<Button-1>", self.check_outside_click)

    def close_menu(self):
        """Close any open dropdown menu"""
        if self.active_menu:
            self.menu_labels[self.active_menu].config(bg=self.menu_bg)
            self.active_menu = None

        # Clear dropdown container
        for widget in self.dropdown_container.winfo_children():
            widget.destroy()

        self.dropdown_container.place_forget()
        self.root.unbind("<Button-1>")

    def check_outside_click(self, event):
        """Check if click was outside menu"""
        widget = event.widget
        # If click is outside dropdown, close it
        if widget not in [self.dropdown_container] and not self.is_child_of(widget, self.dropdown_container):
            # Check if clicked on menubar
            clicked_on_menubar = False
            for label in self.menu_labels.values():
                if widget == label:
                    clicked_on_menubar = True
                    break

            if not clicked_on_menubar:
                self.close_menu()

    def is_child_of(self, widget, parent):
        """Check if widget is a child of parent"""
        while widget:
            if widget == parent:
                return True
            widget = widget.master
        return False

    def create_menu_item(self, parent, text, command, shortcut=None):
        """Create a menu item in dropdown"""
        item_frame = tk.Frame(parent, bg="white")
        item_frame.pack(fill=tk.X)

        # Text and shortcut container
        text_frame = tk.Frame(item_frame, bg="white")
        text_frame.pack(fill=tk.X)

        label = tk.Label(
            text_frame,
            text=text,
            font=("Segoe UI", 10),
            bg="white",
            fg="#333333",
            anchor="w",
            padx=20,
            pady=5
        )
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if shortcut:
            shortcut_label = tk.Label(
                text_frame,
                text=shortcut,
                font=("Segoe UI", 9),
                bg="white",
                fg="#888888",
                padx=20
            )
            shortcut_label.pack(side=tk.RIGHT)

        # Bind hover and click
        for widget in [item_frame, text_frame, label]:
            widget.bind("<Enter>", lambda e, f=item_frame: f.config(bg="#e5f3ff"))
            widget.bind("<Leave>", lambda e, f=item_frame: f.config(bg="white"))
            widget.bind("<Button-1>", lambda e, cmd=command: self.execute_menu_command(cmd))

        if shortcut:
            shortcut_label.bind("<Enter>", lambda e, f=item_frame: f.config(bg="#e5f3ff"))
            shortcut_label.bind("<Leave>", lambda e, f=item_frame: f.config(bg="white"))
            shortcut_label.bind("<Button-1>", lambda e, cmd=command: self.execute_menu_command(cmd))

    def create_separator(self, parent):
        """Create a separator line"""
        sep = tk.Frame(parent, bg="#e0e0e0", height=1)
        sep.pack(fill=tk.X, pady=3, padx=10)

    def execute_menu_command(self, command):
        """Execute menu command and close menu"""
        self.close_menu()
        if command:
            command()

    def create_file_menu(self):
        """Create File menu dropdown"""
        menu_frame = tk.Frame(self.dropdown_container, bg="white", relief=tk.RAISED, borderwidth=1)
        menu_frame.pack(anchor="w", padx=0, pady=0)
       
        self.create_menu_item(menu_frame, "New Project", self.new_project, "Ctrl+N")
        self.create_menu_item(menu_frame, "Open...", self.open_file, "Ctrl+O")
        self.create_menu_item(menu_frame, "Save", self.save_file, "Ctrl+S")
        self.create_menu_item(menu_frame, "Save As...", self.save_as_file, "Ctrl+Shift+S")
        self.create_separator(menu_frame)
        self.create_menu_item(menu_frame, "Import Data", self.import_data)
        self.create_menu_item(menu_frame, "Export Report", self.export_report)
        self.create_separator(menu_frame)
        self.create_menu_item(menu_frame, "Recent Projects", self.show_recent_projects)
        self.create_separator(menu_frame)
        self.create_menu_item(menu_frame, "Exit", self.exit_app, "Alt+F4")
   
    def create_edit_menu(self):
        """Create Edit menu dropdown"""
        menu_frame = tk.Frame(self.dropdown_container, bg="white", relief=tk.RAISED, borderwidth=1)
        menu_frame.pack(anchor="w", padx=0, pady=0)
       
        self.create_menu_item(menu_frame, "Undo", self.undo, "Ctrl+Z")
        self.create_menu_item(menu_frame, "Redo", self.redo, "Ctrl+Y")
        self.create_separator(menu_frame)
        self.create_menu_item(menu_frame, "Cut", self.cut, "Ctrl+X")
        self.create_menu_item(menu_frame, "Copy", self.copy, "Ctrl+C")
        self.create_menu_item(menu_frame, "Paste", self.paste, "Ctrl+V")
        self.create_separator(menu_frame)
        self.create_menu_item(menu_frame, "All", self.select_all, "Ctrl+A")
        self.create_menu_item(menu_frame, "Find", self.find, "Ctrl+F")
        self.create_separator(menu_frame)
        self.create_menu_item(menu_frame, "Preferences", self.preferences)
   
    def create_monitor_menu(self):
        """Monitor Performance dropdown – saare functions monitor_performance se."""
        menu_frame = tk.Frame(self.dropdown_container, bg="white", relief=tk.RAISED, borderwidth=1)
        menu_frame.pack(anchor="w", padx=0, pady=0)

        self.create_menu_item(
            menu_frame,
            "Dashboard",
            lambda: MonitorPerformanceUI.dashboard(self)
        )
        self.create_menu_item(
            menu_frame,
            "Real-time Monitoring",
            lambda: MonitorPerformanceUI.real_time(self)
        )
        self.create_separator(menu_frame)
        self.create_menu_item(
            menu_frame,
            "Load Analysis",
            lambda: MonitorPerformanceUI.load_analysis(self)
        )
        self.create_menu_item(
            menu_frame,
            "Temperature Monitoring",
            lambda: MonitorPerformanceUI.temperature(self)
        )
        self.create_separator(menu_frame)
        self.create_menu_item(
            menu_frame,
            "Historical Data",
            lambda: MonitorPerformanceUI.history(self)
        )
        self.create_menu_item(
            menu_frame,
            "Generate Report",
            lambda: MonitorPerformanceUI.reports(self)
        )
        self.create_separator(menu_frame)
        self.create_menu_item(
            menu_frame,
            "Alerts & Notifications",
            lambda: MonitorPerformanceUI.alerts(self)
        )


    def create_help_menu(self):
        """Create Help menu dropdown"""
        menu_frame = tk.Frame(self.dropdown_container, bg="white", relief=tk.RAISED, borderwidth=1)
        menu_frame.pack(anchor="w", padx=0, pady=0)
       
        self.create_menu_item(menu_frame, "Documentation", self.show_documentation)
        self.create_menu_item(menu_frame, "User Guide", self.user_guide)
        self.create_menu_item(menu_frame, "Video Tutorials", self.video_tutorials)
        self.create_separator(menu_frame)
        self.create_menu_item(menu_frame, "Check for Updates", self.check_updates)
        self.create_menu_item(menu_frame, "Report a Bug", self.report_bug)
        self.create_separator(menu_frame)
        self.create_menu_item(menu_frame, "About", self.about)

    def create_content_area(self):
        """Create the main content area"""
        # Main content frame
        content_frame = tk.Frame(self.root, bg=self.content_bg)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Second navbar with icon containers - styled like the image
        second_navbar = tk.Frame(content_frame, bg="#e8e8e8", height=70)
        second_navbar.pack(fill=tk.X, side=tk.TOP)
        second_navbar.pack_propagate(False)

        # Get the script's directory
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Try multiple possible paths for assets folder
        possible_asset_paths = [
            os.path.join(script_dir, "assets"),  # Same directory as script
            os.path.join(os.path.dirname(script_dir), "assets"),  # Parent directory
            os.path.join(script_dir, "..", "assets"),  # Explicit parent
        ]

        # Find the assets directory
        assets_dir = None
        for path in possible_asset_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                assets_dir = abs_path
                print(f"Found assets directory at: {assets_dir}")
                break

        if not assets_dir:
            print(f"Warning: Could not find assets directory. Searched:")
            for path in possible_asset_paths:
                print(f"  - {os.path.abspath(path)}")

        # Container definitions with explicit icon file paths
        containers = [
            ("Homepage", "home page.png"),
            ("Analysis & Graphs", "Analyze.png"),
            ("Generate Report", "Generate Report.png"),
            ("Analysis Report", "Analysis Report.png"),
            ("Smart Suggestions", "Smart Suggestions.png"),
            ("Send Report", "Send Report.png"),
            ("3D Viewer", "3D Viewer.png")
        ]

        # Create container frame - styled like toolbar in image
        containers_frame = tk.Frame(second_navbar, bg="#e8e8e8")
        containers_frame.pack(side=tk.LEFT, padx=5, pady=5)

        # Store icon references
        self.icon_images = []

        for i, (name, icon_filename) in enumerate(containers):
            # Create button frame with border (like in image)
            button_frame = tk.Frame(
                containers_frame,
                bg="#ffffff",
                relief=tk.RAISED,
                borderwidth=1,
                cursor="hand2"
            )
            button_frame.grid(row=0, column=i, padx=2, pady=2)

            # Inner padding frame
            inner_frame = tk.Frame(button_frame, bg="#ffffff", padx=8, pady=8)
            inner_frame.pack()

            # Try to load icon
            icon_loaded = False
            icon_label = None

            if assets_dir:
                icon_path = os.path.join(assets_dir, icon_filename)

                if os.path.exists(icon_path):
                    try:
                        from PIL import Image, ImageTk
                        # Load and resize icon to 32x32 (toolbar size)
                        icon_image = Image.open(icon_path)
                        icon_image = icon_image.resize((32, 32), Image.LANCZOS)

                        icon_photo = ImageTk.PhotoImage(icon_image)

                        icon_label = tk.Label(
                            inner_frame,
                            image=icon_photo,
                            bg="#ffffff",
                            bd=0,
                            highlightthickness=0
                        )
                        icon_label.image = icon_photo
                        self.icon_images.append(icon_photo)
                        icon_label.pack()
                        icon_loaded = True
                        print(f"✓ Loaded: {icon_filename}")
                    except Exception as e:
                        print(f"✗ Error loading {icon_filename}: {e}")
                else:
                    print(f"✗ File not found: {icon_path}")

            # Fallback to emoji if icon not loaded
            if not icon_loaded:
                emoji_map = {
                    "Homepage": "🏠",
                    "Analysis & Graph": "📊",
                    "Generate Report": "📝",
                    "Analysis Report": "📈",
                    "Smart Suggestion": "💡",
                    "Send Report": "📤",
                    "3D Viewer": "🎲"
                }

                icon_label = tk.Label(
                    inner_frame,
                    text=emoji_map.get(name, "📄"),
                    font=("Arial", 24),
                    bg="#ffffff",
                    bd=0,
                    highlightthickness=0
                )
                icon_label.pack()

            # Hover effects with tooltip
            def make_hover_enter(frame, inner, label, container_name):
                def handler(e):
                    frame.config(bg="#e0e0e0", relief=tk.SUNKEN)
                    inner.config(bg="#e0e0e0")
                    label.config(bg="#e0e0e0")

                    # Destroy existing tooltip if any
                    if hasattr(frame, 'tooltip') and frame.tooltip:
                        try:
                            frame.tooltip.destroy()
                        except:
                            pass

                    # Create tooltip
                    tooltip = tk.Toplevel()
                    tooltip.wm_overrideredirect(True)
                    tooltip.wm_geometry(f"+{e.x_root+10}+{e.y_root+10}")

                    tooltip_label = tk.Label(
                        tooltip,
                        text=container_name,
                        background="#ffffcc",
                        relief=tk.SOLID,
                        borderwidth=1,
                        font=("Arial", 9),
                        padx=5,
                        pady=2
                    )
                    tooltip_label.pack()

                    # Store tooltip reference
                    frame.tooltip = tooltip
                return handler

            def make_hover_leave(frame, inner, label):
                def handler(e):
                    frame.config(bg="#ffffff", relief=tk.RAISED)
                    inner.config(bg="#ffffff")
                    label.config(bg="#ffffff")

                    # Destroy tooltip if it exists
                    if hasattr(frame, 'tooltip') and frame.tooltip:
                        try:
                            frame.tooltip.destroy()
                            frame.tooltip = None
                        except:
                            pass
                return handler

            enter_handler = make_hover_enter(button_frame, inner_frame, icon_label, name)
            leave_handler = make_hover_leave(button_frame, inner_frame, icon_label)

            for widget in [button_frame, inner_frame, icon_label]:
                widget.bind("<Enter>", enter_handler)
                widget.bind("<Leave>", leave_handler)
                widget.bind("<Button-1>", lambda e, n=name: self.on_container_click(n))

        # ===== NEW STRUCTURED LAYOUT =====

        # Main workspace container (below second navbar)
        workspace_container = tk.Frame(content_frame, bg=self.content_bg)
        workspace_container.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        # Create PanedWindow for resizable layout
        # Main horizontal paned window (left sidebar | center+right | )
        main_paned = tk.PanedWindow(workspace_container, orient=tk.HORIZONTAL,
                                    sashwidth=5, sashrelief=tk.RAISED, bg="#cccccc")
        main_paned.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        # ===== 1. LEFT SIDEBAR - Workspace Panel =====
        left_sidebar_frame = tk.Frame(main_paned, bg="#f5f5f5", width=280, relief=tk.SUNKEN, borderwidth=1)
        main_paned.add(left_sidebar_frame)
        main_paned.paneconfigure(left_sidebar_frame, minsize=280, width=280, stretch="never")

        # Left sidebar header
        left_header = tk.Frame(left_sidebar_frame, bg="#2c3e50", height=35)
        left_header.pack(fill=tk.X, side=tk.TOP)
        left_header.pack_propagate(False)

        left_title = tk.Label(left_header, text="📁 Workspace", font=("Segoe UI", 11, "bold"),
                             bg="#2c3e50", fg="white", anchor="w", padx=10)
        left_title.pack(fill=tk.BOTH, expand=True)

        # Scrollable workspace content
        workspace_canvas = tk.Canvas(left_sidebar_frame, bg="#f5f5f5", highlightthickness=0)
        workspace_scrollbar = ttk.Scrollbar(left_sidebar_frame, orient="vertical", command=workspace_canvas.yview)
        workspace_scrollable = tk.Frame(workspace_canvas, bg="#f5f5f5")
        self.workspace_scrollable = workspace_scrollable

        workspace_scrollable.bind(
            "<Configure>",
            lambda e: workspace_canvas.configure(scrollregion=workspace_canvas.bbox("all"))
        )

        workspace_canvas.create_window((0, 0), window=workspace_scrollable, anchor="nw")
        workspace_canvas.configure(yscrollcommand=workspace_scrollbar.set)

        workspace_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        workspace_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # WORKSPACE CONTENT REMOVED - Empty scrollable area

        # Center + Right container
        center_right_paned = tk.PanedWindow(main_paned, orient=tk.HORIZONTAL,
                                            sashwidth=5, sashrelief=tk.RAISED, bg="#cccccc")
        main_paned.add(center_right_paned, minsize=400)

        # ===== 2. CENTER AREA - Preview Panel =====
        center_frame = tk.Frame(center_right_paned, bg="#ffffff", relief=tk.SUNKEN, borderwidth=1)
        center_right_paned.add(center_frame)
        center_right_paned.paneconfigure(center_frame, minsize=300, stretch="always")

        # Center header
        center_header = tk.Frame(center_frame, bg="#34495e", height=35)
        center_header.pack(fill=tk.X, side=tk.TOP)
        center_header.pack_propagate(False)

        center_title = tk.Label(center_header, text="📊 Preview Panel", font=("Segoe UI", 11, "bold"),
                               bg="#34495e", fg="white", anchor="w", padx=10)
        center_title.pack(fill=tk.BOTH, expand=True)

        # Center content area with scroll
        center_canvas = tk.Canvas(center_frame, bg="#ffffff", highlightthickness=0)
        center_scrollbar_y = ttk.Scrollbar(center_frame, orient="vertical", command=center_canvas.yview)
        center_scrollbar_x = ttk.Scrollbar(center_frame, orient="horizontal", command=center_canvas.xview)
        center_scrollable = tk.Frame(center_canvas, bg="#ffffff")
        self.center_scrollable = center_scrollable
        self.center_content_frame = center_scrollable

        center_scrollable.bind(
            "<Configure>",
            lambda e: center_canvas.configure(scrollregion=center_canvas.bbox("all"))
        )

        center_canvas.create_window((0, 0), window=center_scrollable, anchor="nw")
        center_canvas.configure(yscrollcommand=center_scrollbar_y.set, xscrollcommand=center_scrollbar_x.set)

        center_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        center_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        center_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # PREVIEW PANEL CONTENT REMOVED - Empty scrollable area

        # ===== 3. RIGHT SIDEBAR - Metadata Panel =====
        right_sidebar_frame = tk.Frame(center_right_paned, bg="#fafafa", width=280, relief=tk.SUNKEN, borderwidth=1)
        center_right_paned.add(right_sidebar_frame)
        center_right_paned.paneconfigure(right_sidebar_frame, minsize=280, width=280, stretch="never")

        # Right sidebar header
        right_header = tk.Frame(right_sidebar_frame, bg="#16a085", height=35)
        right_header.pack(fill=tk.X, side=tk.TOP)
        right_header.pack_propagate(False)

        right_title = tk.Label(right_header, text="ℹ️ Metadata", font=("Segoe UI", 11, "bold"),
                              bg="#16a085", fg="white", anchor="w", padx=10)
        right_title.pack(fill=tk.BOTH, expand=True)

        # Metadata content
        metadata_content = tk.Frame(right_sidebar_frame, bg="#fafafa")
        self.metadata_content = metadata_content

        metadata_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # METADATA CONTENT REMOVED - Empty content area

        # ===== 4. BOTTOM PANEL - Console =====
        bottom_console_frame = tk.Frame(workspace_container, bg="#1e1e1e", height=150, relief=tk.SUNKEN, borderwidth=2)
        bottom_console_frame.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_console_frame.pack_propagate(False)

        # Console header with controls
        console_header = tk.Frame(bottom_console_frame, bg="#2d2d2d", height=35)
        console_header.pack(fill=tk.X, side=tk.TOP)
        console_header.pack_propagate(False)

        console_title = tk.Label(console_header, text="💻 Console", font=("Segoe UI", 10, "bold"),
                                bg="#2d2d2d", fg="#ffffff", anchor="w", padx=10)
        console_title.pack(side=tk.LEFT, fill=tk.Y)

        # Right side controls container
        controls_frame = tk.Frame(console_header, bg="#2d2d2d")
        controls_frame.pack(side=tk.RIGHT, padx=5)

        # Console control buttons (styled like the image)
        button_style = {
            "font": ("Segoe UI", 9),
            "bg": "#3d3d3d",
            "fg": "#ffffff",
            "relief": tk.RAISED,
            "borderwidth": 1,
            "padx": 10,
            "pady": 3,
            "cursor": "hand2",
            "activebackground": "#505050",
            "activeforeground": "#ffffff"
        }

        # Load Last Session button
        load_session_btn = tk.Button(controls_frame, text="Load Last Session",
                                     command=self.load_last_session, **button_style)
        load_session_btn.pack(side=tk.RIGHT, padx=2)

        # Console Height control
        height_frame = tk.Frame(controls_frame, bg="#3d3d3d", relief=tk.RAISED, borderwidth=1)
        height_frame.pack(side=tk.RIGHT, padx=2)

        tk.Label(height_frame, text="Console Height", font=("Segoe UI", 8),
                bg="#3d3d3d", fg="#cccccc", padx=5, pady=2).pack(side=tk.TOP)

        height_control = tk.Frame(height_frame, bg="#3d3d3d")
        height_control.pack(side=tk.TOP, padx=5, pady=2)

        self.console_height_var = tk.StringVar(value="8")
        height_spinbox = tk.Spinbox(height_control, from_=5, to=20, width=5,
                                    textvariable=self.console_height_var,
                                    font=("Segoe UI", 9), bg="#2d2d2d", fg="#ffffff",
                                    buttonbackground="#505050", relief=tk.FLAT,
                                    command=lambda: self.adjust_console_height())
        height_spinbox.pack()

        # Font Size control
        font_frame = tk.Frame(controls_frame, bg="#3d3d3d", relief=tk.RAISED, borderwidth=1)
        font_frame.pack(side=tk.RIGHT, padx=2)

        tk.Label(font_frame, text="Font Size", font=("Segoe UI", 8),
                bg="#3d3d3d", fg="#cccccc", padx=5, pady=2).pack(side=tk.TOP)

        font_control = tk.Frame(font_frame, bg="#3d3d3d")
        font_control.pack(side=tk.TOP, padx=5, pady=2)

        self.font_size_var = tk.StringVar(value="10")
        font_spinbox = tk.Spinbox(font_control, from_=8, to=16, width=5,
                                  textvariable=self.font_size_var,
                                  font=("Segoe UI", 9), bg="#2d2d2d", fg="#ffffff",
                                  buttonbackground="#505050", relief=tk.FLAT,
                                  command=lambda: self.adjust_font_size())
        font_spinbox.pack()

        # Toggle Theme button
        toggle_theme_btn = tk.Button(controls_frame, text="Toggle Theme",
                                     command=self.toggle_console_theme, **button_style)
        toggle_theme_btn.pack(side=tk.RIGHT, padx=2)

        # Send Message button
        send_msg_btn = tk.Button(controls_frame, text="Send Message",
                                command=self.send_console_message, **button_style)
        send_msg_btn.pack(side=tk.RIGHT, padx=2)

        # Search bar
        search_frame = tk.Frame(controls_frame, bg="#3d3d3d", relief=tk.RAISED, borderwidth=1)
        search_frame.pack(side=tk.RIGHT, padx=2)

        tk.Label(search_frame, text="Search:", font=("Segoe UI", 8),
                bg="#3d3d3d", fg="#cccccc", padx=3).pack(side=tk.LEFT)

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=20,
                               font=("Segoe UI", 9), bg="#2d2d2d", fg="#ffffff",
                               relief=tk.FLAT, insertbackground="white")
        search_entry.pack(side=tk.LEFT, padx=3, pady=3)
        search_entry.bind("<Return>", lambda e: self.search_console())

        # Filter dropdown
        filter_frame = tk.Frame(controls_frame, bg="#3d3d3d", relief=tk.RAISED, borderwidth=1)
        filter_frame.pack(side=tk.RIGHT, padx=2)

        tk.Label(filter_frame, text="Filter:", font=("Segoe UI", 8),
                bg="#3d3d3d", fg="#cccccc", padx=3).pack(side=tk.LEFT)

        self.filter_var = tk.StringVar(value="All")
        filter_dropdown = ttk.Combobox(filter_frame, textvariable=self.filter_var,
                                      values=["All", "SUCCESS", "INFO", "WARNING", "ERROR"],
                                      width=10, font=("Segoe UI", 9), state="readonly")
        filter_dropdown.pack(side=tk.LEFT, padx=3, pady=3)
        filter_dropdown.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        # Export Logs button
        export_btn = tk.Button(controls_frame, text="Export Logs",
                              command=self.export_logs, **button_style)
        export_btn.pack(side=tk.RIGHT, padx=2)

        # Clear button
        clear_btn = tk.Button(controls_frame, text="Clear",
                             command=self.clear_console, **button_style)
        clear_btn.pack(side=tk.RIGHT, padx=2)

        # Console text area with scrollbar
        console_container = tk.Frame(bottom_console_frame, bg="#1e1e1e")
        console_container.pack(fill=tk.BOTH, expand=True)

        self.console_text = tk.Text(console_container, bg="#1e1e1e", fg="#00ff00",
                                   font=("Consolas", 10), wrap=tk.WORD,
                                   relief=tk.FLAT, insertbackground="white")
        console_scrollbar = ttk.Scrollbar(console_container, orient="vertical",
                                         command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=console_scrollbar.set)

        self.console_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        console_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure text tags for different log levels
        self.console_text.tag_config("SUCCESS", foreground="#00ff00")
        self.console_text.tag_config("INFO", foreground="#00bfff")
        self.console_text.tag_config("WARNING", foreground="#ffaa00")
        self.console_text.tag_config("ERROR", foreground="#ff0000")

        # Add initial console messages
        self.log_console("Application initialized successfully.", "SUCCESS")
        self.log_console("Ready to load projects.", "INFO")
        self.log_console("Type 'help' for available commands.", "INFO")

        # Store reference to bottom console frame for resizing
        self.bottom_console_frame = bottom_console_frame

    def on_workspace_item_click(self, item_name):
        """Handle workspace item click"""
        self.log_console(f"Selected: {item_name}")
        messagebox.showinfo("Workspace", f"Clicked on: {item_name}")

    def log_console(self, message, level="INFO"):
        """Add message to console with log level"""
        if hasattr(self, 'console_text'):
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Format message based on level
            log_entry = f"[{timestamp}] [{level}] {message}\n"

            self.console_text.insert(tk.END, log_entry, level)
            self.console_text.see(tk.END)  # Auto-scroll to bottom

    def clear_console(self):
        """Clear console output"""
        if hasattr(self, 'console_text'):
            self.console_text.delete(1.0, tk.END)
            self.log_console("Console cleared.", "INFO")

    def export_logs(self):
        """Export console logs to file"""
        file_path = filedialog.asksaveasfilename(
            title="Export Console Logs",
            defaultextension=".log",
            filetypes=[("Log Files", "*.log"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(self.console_text.get(1.0, tk.END))
                self.log_console(f"Logs exported to {os.path.basename(file_path)}", "SUCCESS")
            except Exception as e:
                self.log_console(f"Failed to export logs: {str(e)}", "ERROR")

    def apply_filter(self):
        """Apply filter to console messages"""
        filter_value = self.filter_var.get()
        self.log_console(f"Filter applied: {filter_value}", "INFO")
        # Implementation would filter console content based on level

    def search_console(self):
        """Search console content"""
        search_term = self.search_var.get()
        if search_term:
            self.log_console(f"Searching for: {search_term}", "INFO")
            # Implementation would highlight search results in console
        else:
            self.log_console("Please enter a search term", "WARNING")

    def send_console_message(self):
        """Send a custom message to console"""
        # This could open a dialog to enter custom message
        message = "Custom message sent"
        self.log_console(message, "INFO")

    def toggle_console_theme(self):
        """Toggle between dark and light console theme"""
        current_bg = self.console_text.cget("bg")
        if current_bg == "#1e1e1e":  # Dark theme
            self.console_text.config(bg="#ffffff", fg="#000000")
            self.log_console("Switched to light theme", "INFO")
        else:  # Light theme
            self.console_text.config(bg="#1e1e1e", fg="#00ff00")
            self.log_console("Switched to dark theme", "INFO")

    def adjust_font_size(self):
        """Adjust console font size"""
        try:
            size = int(self.font_size_var.get())
            self.console_text.config(font=("Consolas", size))
            self.log_console(f"Font size changed to {size}", "INFO")
        except:
            pass

    def adjust_console_height(self):
        """Adjust console height"""
        try:
            height = int(self.console_height_var.get())
            # Calculate pixels (approximate: height * 15 pixels per line)
            new_height = height * 15 + 35  # +35 for header
            self.bottom_console_frame.config(height=new_height)
            self.log_console(f"Console height adjusted to {height} lines", "INFO")
        except:
            pass

    def load_last_session(self):
        """Load last session logs"""
        self.log_console("Loading last session...", "INFO")
        # Sample previous session logs
        self.log_console("Successfully loaded file: project.json", "SUCCESS")
        self.log_console("File saved successfully: project.json", "SUCCESS")
        self.log_console("File terminated successfully.", "SUCCESS")
        self.log_console("CPU Usage: 8.0%, Memory Usage: 46.3%", "INFO")
        self.log_console("CPU Usage: 9.9%, Memory Usage: 46.4%", "INFO")
        self.log_console("Successfully loaded file: example.json", "SUCCESS")

    def on_container_click(self, name):
        """
        Patched handler (replaces old forwarding behavior).

        Behavior:
        - If name == "Homepage": create homepage UI (or fallback to enable_homepage)
        - If name indicates Analyze Graph: intercept and call enable_analyse_graph(self) and return
        - Otherwise: call original_handler which shows default popup
        """

        # Save a reference to the original behavior so we can call it for "others"
        def original_handler(n):
            messagebox.showinfo(n, f"You clicked on: {n}")

        # Homepage tab is handled here
        if name == "Homepage":
            # Attempt to call create_homepage_ui() if provided by Homepage module,
            # otherwise fall back to enable_homepage(app)
            try:
                from Homepage import create_homepage_ui
                # If create_homepage_ui expects the app instance, pass it; otherwise call without args
                try:
                    create_homepage_ui(self)
                except TypeError:
                    create_homepage_ui()
                return
            except Exception:
                # fallback to enable_homepage if create_homepage_ui not available
                try:
                    from Homepage import enable_homepage
                    enable_homepage(self)
                    return
                except Exception as e:
                    # if both fail, log and fallback to original handler
                    self.log_console(f"Failed to open Homepage: {e}", "ERROR")
                    original_handler(name)
                    return

        # Analyze Graph handled here (NOT forwarded!)
        # Accept multiple possible names used across the UI ("Analyze Graph", "Analysis & Graphs", etc.)
        analyze_names = {"Analyze Graph", "Analysis & Graphs", "Analysis & Graph", "Analyse Graph", "Analyse & Graphs"}
        if name in analyze_names:
            try:
                # We imported enable_analyse_graph at module top; call it with self
                enable_analyse_graph(self)
                return
            except Exception as e:
                # Log error and fallback to original handler
                self.log_console(f"Failed to open Analyze Graph: {e}", "ERROR")
                original_handler(name)
                return
        if name == "Generate Report":
            try:
                enable_generate_report(self)    # <-- CALL THE MODULE
                return
            except Exception as e:
                self.log_console(f"Failed to open Generate Report: {e}", "ERROR")
                return
        
        """Handle click on navbar container"""
        self.log_console(f"Toolbar action: {name}")
       
        # Handle Send Report specifically
        if name == "Send Report":
            self.load_send_report_module()
            return

        # For all others → call original
        original_handler(name)


    def load_send_report_module(self):
        """Load Send Report module into workspace and preview panels"""
        try:
            # Initialize the SendReportModule with correct frame references
            self.send_report_module = SendReportModule(
                workspace_frame=self.workspace_scrollable,  # Left panel scrollable area
                preview_frame=self.center_scrollable,       # Center panel scrollable area
                console_text=self.console_text              # Console text widget
            )
            self.log_console("Send Report module loaded successfully", "SUCCESS")
        except Exception as e:
            self.log_console(f"Failed to load Send Report module: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Failed to load Send Report module: {str(e)}")


    # FILE Menu Functions
    def new_project(self):
        messagebox.showinfo("New Project", "Creating a new project...")

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Open Project",
            filetypes=[("Project Files", "*.vdh"), ("All Files", "*.*")]
        )
        if file_path:
            messagebox.showinfo("Open File", f"Opening: {os.path.basename(file_path)}")

    def save_file(self):
        messagebox.showinfo("Save", "File saved successfully!")

    def save_as_file(self):
        file_path = filedialog.asksaveasfilename(
            title="Save As",
            defaultextension=".vdh",
            filetypes=[("Project Files", "*.vdh"), ("All Files", "*.*")]
        )
        if file_path:
            messagebox.showinfo("Save As", f"Saved as: {os.path.basename(file_path)}")

    def import_data(self):
        messagebox.showinfo("Import Data", "Import data functionality")

    def export_report(self):
        messagebox.showinfo("Export Report", "Export report functionality")

    def show_recent_projects(self):
        messagebox.showinfo("Recent Projects", "Showing recent projects...")

    def exit_app(self):
        if messagebox.askokcancel("Exit", "Do you want to exit?"):
            self.root.quit()

    # EDIT Menu Functions
    def undo(self):
        messagebox.showinfo("Undo", "Undo last action")

    def redo(self):
        messagebox.showinfo("Redo", "Redo last action")

    def cut(self):
        print("Cut")

    def copy(self):
        print("Copy")

    def paste(self):
        print("Paste")

    def select_all(self):
        print("All")

    def find(self):
        messagebox.showinfo("Find", "Find functionality")

    def preferences(self):
        messagebox.showinfo("Preferences", "Opening preferences...")

    # MONITOR PERFORMANCE Menu Functions
    def show_dashboard(self):
        messagebox.showinfo("Dashboard", "Opening performance dashboard...")

    def real_time_monitoring(self):
        messagebox.showinfo("Real-time Monitoring", "Starting real-time monitoring...")

    def transformer_health(self):
        messagebox.showinfo("Analysis", "Analyzing...")

    def load_analysis(self):
        messagebox.showinfo("Load Analysis", "Performing load analysis...")

    def temperature_monitoring(self):
        messagebox.showinfo("Temperature Monitoring", "Monitoring temperature...")

    def historical_data(self):
        messagebox.showinfo("Historical Data", "Loading historical data...")

    def generate_report(self):
        messagebox.showinfo("Generate Report", "Generating performance report...")

    def alerts_notifications(self):
        messagebox.showinfo("Alerts & Notifications", "Managing alerts...")

    # HELP Menu Functions
    def show_documentation(self):
        messagebox.showinfo("Documentation", "Opening documentation...")

    def user_guide(self):
        messagebox.showinfo("User Guide", "Opening user guide...")

    def video_tutorials(self):
        messagebox.showinfo("Video Tutorials", "Opening video tutorials...")

    def check_updates(self):
        messagebox.showinfo("Check for Updates", "Checking for updates...")

    def report_bug(self):
        messagebox.showinfo("Report a Bug", "Opening bug report form...")

    def about(self):
        about_text = """Application

Version 1.0.0




© 2024 Systems"""
        messagebox.showinfo("About", about_text)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts for file operations"""
        self.root.bind("<Control-n>", lambda e: self.new_project())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_as_file())
   
    # ==================== FILE MENU IMPLEMENTATIONS ====================
   
    def new_project(self):
        """Create a new project - FILE MENU"""
        if self.has_unsaved_changes():
            response = messagebox.askyesnocancel(
                "Unsaved Changes",
                "Do you want to save changes before creating a new project?"
            )
            if response is None:  # Cancel
                return
            elif response:  # Yes - save first
                self.save_file()
       
        # Clear current data
        self.current_file = None
        self.clear_workspace()
        self.unsaved_changes = False
        self.log_console("New project created successfully", "SUCCESS")
        messagebox.showinfo("New Project", "New project created successfully!")
   
    def open_file(self):
        """Open an existing project file - FILE MENU"""
        file_path = filedialog.askopenfilename(
            title="Open Project",
            filetypes=[
                ("Project Files", "*.proj"),
                ("JSON Files", "*.json"),
                ("All Files", "*.*")
            ]
        )
       
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
               
                self.current_file = file_path
                self.load_project_data(data)
                self.add_to_recent(file_path)
                self.unsaved_changes = False
                self.log_console(f"Opened: {os.path.basename(file_path)}", "SUCCESS")
                messagebox.showinfo("Success", f"Opened: {os.path.basename(file_path)}")
            except Exception as e:
                self.log_console(f"Failed to open file: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Failed to open file: {str(e)}")
   
    def save_file(self):
        """Save the current project - FILE MENU"""
        if self.current_file:
            self._save_to_file(self.current_file)
        else:
            self.save_as_file()
   
    def save_as_file(self):
        """Save project with a new name - FILE MENU"""
        file_path = filedialog.asksaveasfilename(
            title="Save Project As",
            defaultextension=".proj",
            filetypes=[
                ("Project Files", "*.proj"),
                ("JSON Files", "*.json"),
                ("All Files", "*.*")
            ]
        )
       
        if file_path:
            self._save_to_file(file_path)
            self.current_file = file_path
            self.add_to_recent(file_path)
   
    def _save_to_file(self, file_path):
        """Internal method to save data to file"""
        try:
            data = self.get_project_data()
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            self.unsaved_changes = False
            self.log_console(f"Saved: {os.path.basename(file_path)}", "SUCCESS")
            messagebox.showinfo("Success", f"Saved: {os.path.basename(file_path)}")
        except Exception as e:
            self.log_console(f"Failed to save file: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")
   
    def import_data(self):
        """Import data from external sources - FILE MENU"""
        file_path = filedialog.askopenfilename(
            title="Import Data",
            filetypes=[
                ("CSV Files", "*.csv"),
                ("Excel Files", "*.xlsx"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*")
            ]
        )
       
        if file_path:
            try:
                self.handle_data_import(file_path)
                self.log_console(f"Data imported from: {os.path.basename(file_path)}", "SUCCESS")
                messagebox.showinfo("Import", f"Data imported from: {os.path.basename(file_path)}")
            except Exception as e:
                self.log_console(f"Import failed: {str(e)}", "ERROR")
                messagebox.showerror("Import Error", f"Failed to import: {str(e)}")
   
    def export_report(self):
        """Export analysis report - FILE MENU"""
        file_path = filedialog.asksaveasfilename(
            title="Export Report",
            defaultextension=".pdf",
            filetypes=[
                ("PDF Files", "*.pdf"),
                ("HTML Files", "*.html"),
                ("Excel Files", "*.xlsx"),
                ("Text Files", "*.txt")
            ]
        )
       
        if file_path:
            try:
                self.generate_export_report(file_path)
                self.log_console(f"Report exported to: {os.path.basename(file_path)}", "SUCCESS")
                messagebox.showinfo("Export", f"Report exported to: {os.path.basename(file_path)}")
            except Exception as e:
                self.log_console(f"Export failed: {str(e)}", "ERROR")
                messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
   
    def show_recent_projects(self):
        """Show dialog with recent projects - FILE MENU"""
        if not self.recent_projects:
            messagebox.showinfo("Recent Projects", "No recent projects found.")
            return
       
        # Create recent projects dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Recent Projects")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
       
        # Title
        tk.Label(
            dialog,
            text="Recent Projects",
            font=("Arial", 14, "bold")
        ).pack(pady=15)
       
        # Listbox with scrollbar
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
       
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
       
        listbox = tk.Listbox(
            list_frame,
            font=("Arial", 10),
            yscrollcommand=scrollbar.set
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
       
        # Add recent projects to listbox
        for project in self.recent_projects:
            display_name = os.path.basename(project)
            listbox.insert(tk.END, f"{display_name}")
       
        # Double-click to open
        def on_double_click(event):
            selection = listbox.curselection()
            if selection:
                file_path = self.recent_projects[selection[0]]
                dialog.destroy()
                self.open_specific_file(file_path)
       
        listbox.bind('<Double-Button-1>', on_double_click)
       
        # Buttons
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=15)
       
        def open_selected():
            selection = listbox.curselection()
            if selection:
                file_path = self.recent_projects[selection[0]]
                dialog.destroy()
                self.open_specific_file(file_path)
            else:
                messagebox.showwarning("No Selection", "Please select a project to open.")
       
        def clear_recent():
            if messagebox.askyesno("Clear Recent", "Clear all recent projects?"):
                self.recent_projects.clear()
                self.save_recent_projects()
                dialog.destroy()
                messagebox.showinfo("Cleared", "Recent projects cleared.")
       
        tk.Button(
            button_frame,
            text="Open",
            command=open_selected,
            width=12
        ).pack(side=tk.LEFT, padx=5)
       
        tk.Button(
            button_frame,
            text="Clear List",
            command=clear_recent,
            width=12
        ).pack(side=tk.LEFT, padx=5)
       
        tk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy,
            width=12
        ).pack(side=tk.LEFT, padx=5)
   
    # Note: exit_app() already exists in your code above, so we don't redefine it
   
    # ==================== HELPER METHODS FOR FILE OPERATIONS ====================
   
    def has_unsaved_changes(self):
        """Check if there are unsaved changes"""
        return self.unsaved_changes
   
    def clear_workspace(self):
        """Clear all workspace data"""
        self.project_data = {}
        self.unsaved_changes = False
        self.current_file = None
       
        # Clear workspace scrollable area
        if hasattr(self, 'workspace_scrollable'):
            for widget in self.workspace_scrollable.winfo_children():
                widget.destroy()
       
        # Clear center content
        if hasattr(self, 'center_scrollable'):
            for widget in self.center_scrollable.winfo_children():
                widget.destroy()
            tk.Label(
                self.center_scrollable,
                text="New Project Created",
                font=("Segoe UI", 20),
                bg="#ffffff",
                fg="#333333"
            ).pack(pady=100)
       
        # Clear metadata
        if hasattr(self, 'metadata_content'):
            for widget in self.metadata_content.winfo_children():
                widget.destroy()
       
        self.log_console("Workspace cleared - New project ready", "SUCCESS")
   
    def load_project_data(self, data):
        """Load project data into workspace"""
        self.project_data = data
        self.unsaved_changes = False
       
        # Clear center content
        if hasattr(self, 'center_scrollable'):
            for widget in self.center_scrollable.winfo_children():
                widget.destroy()
           
            tk.Label(
                self.center_scrollable,
                text="Project Loaded Successfully",
                font=("Segoe UI", 20, "bold"),
                bg="#ffffff",
                fg="#333333"
            ).pack(pady=50)
           
            info_frame = tk.Frame(self.center_scrollable, bg="#ffffff")
            info_frame.pack(pady=20)
           
            tk.Label(
                info_frame,
                text=f"Project contains: {len(data)} items",
                font=("Segoe UI", 12),
                bg="#ffffff",
                fg="#666666"
            ).pack()
       
        self.log_console(f"Project loaded successfully with {len(data)} items", "SUCCESS")
   
    def get_project_data(self):
        """Get current project data for saving"""
        if not self.project_data:
            self.project_data = {
                "project_name": "My Project",
                "created_date": "2024-12-04",
                "data_points": 100,
                "status": "active"
            }
        return self.project_data
   
    def handle_data_import(self, file_path):
        """Handle data import from external file"""
        self.log_console(f"Importing data from: {os.path.basename(file_path)}", "INFO")
       
        if file_path.endswith('.csv'):
            self.log_console(f"CSV file imported: {os.path.basename(file_path)}", "SUCCESS")
        elif file_path.endswith('.xlsx'):
            self.log_console(f"Excel file imported: {os.path.basename(file_path)}", "SUCCESS")
        else:
            self.log_console(f"File imported: {os.path.basename(file_path)}", "SUCCESS")
       
        self.unsaved_changes = True
   
    def generate_export_report(self, file_path):
        """Generate and export report"""
        self.log_console(f"Exporting report to: {os.path.basename(file_path)}", "INFO")
       
        report_content = f"""
Performance Monitor Report
==========================


Project: {self.project_data.get('project_name', 'Untitled')}
Generated: 2024-12-04


Summary:
- Data Points: {self.project_data.get('data_points', 0)}
- Status: {self.project_data.get('status', 'Unknown')}
        """
       
        try:
            if file_path.endswith('.txt'):
                with open(file_path, 'w') as f:
                    f.write(report_content)
                self.log_console(f"Report exported successfully to {os.path.basename(file_path)}", "SUCCESS")
            elif file_path.endswith('.html'):
                with open(file_path, 'w') as f:
                    f.write(f"<html><body><pre>{report_content}</pre></body></html>")
                self.log_console(f"HTML report exported successfully", "SUCCESS")
            else:
                messagebox.showinfo("Export", "PDF/Excel export requires additional libraries")
        except Exception as e:
            self.log_console(f"Export failed: {str(e)}", "ERROR")
            raise Exception(f"Export failed: {str(e)}")
   
    def add_to_recent(self, file_path):
        """Add file to recent projects list"""
        if file_path in self.recent_projects:
            self.recent_projects.remove(file_path)
        self.recent_projects.insert(0, file_path)
        self.recent_projects = self.recent_projects[:10]
        self.save_recent_projects()
   
    def open_specific_file(self, file_path):
        """Open a specific file by path"""
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                self.current_file = file_path
                self.load_project_data(data)
                self.unsaved_changes = False
                self.log_console(f"Opened: {os.path.basename(file_path)}", "SUCCESS")
            except Exception as e:
                self.log_console(f"Failed to open file: {str(e)}", "ERROR")
                messagebox.showerror("Error", f"Failed to open file: {str(e)}")
        else:
            messagebox.showwarning("Not Found", "File no longer exists.")
            self.recent_projects.remove(file_path)
            self.save_recent_projects()
   
    def load_recent_projects(self):
        """Load recent projects from config file"""
        config_file = "recent_projects.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    self.recent_projects = json.load(f)
            except:
                self.recent_projects = []
        else:
            self.recent_projects = []
   
    def save_recent_projects(self):
        """Save recent projects to config file"""
        try:
            with open("recent_projects.json", 'w') as f:
                json.dump(self.recent_projects, f, indent=4)
        except Exception as e:
            print(f"Failed to save recent projects: {e}")
 
    def open_send_report(self):
    # Loads SendReportModule into the existing workspace + preview
        SendReportModule(
        workspace_frame=self.workspace_frame,
        preview_frame=self.preview_panel,
        console_log=self.console_log
        )

def main():
    root = tk.Tk()
    app = MainApplication(root)

    from Homepage import enable_homepage
    enable_homepage(app)

    # Enable Smart Suggestions module
    enable_smart_suggestions(app)

    root.mainloop()


if __name__ == "__main__":
    main()
