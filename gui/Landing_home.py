import tkinter as tk
from tkinter import ttk, font, filedialog
import sys
import os

# Add parent directory to path to import app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import PIL for image handling
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from app import ProjectManager


class LandingPage:
    def __init__(self, root):
        self.root = root

        self.root.title("Welcome to Vidhyut")
        self.root.geometry("1600x950")
        self.root.state('zoomed')

        # Initialize project manager
        self.project_manager = ProjectManager()

        # Color scheme
        self.header_bg = "#3f5f78"
        self.sidebar_bg = "#243241"
        self.content_bg = "#e8e8e8"
        self.card_bg = "#ffffff"
        self.button_color = "#2196F3"
        self.button_hover = "#1976D2"
        self.sidebar_hover = "#24384a"

        # Create UI
        self.create_sidebar()
        self.create_header()
        self.create_content()
        # End of __init__
     
    def create_sidebar(self):
        """Create the left sidebar with navigation links"""

        sidebar_frame = tk.Frame(
            self.root,
            bg=self.sidebar_bg,
            width=200
        )

        sidebar_frame.pack(
            side=tk.LEFT,
            fill=tk.Y
        )

        sidebar_frame.pack_propagate(False)

        # =========================
        # LOGO AREA
        # =========================

        logo_container = tk.Frame(
            sidebar_frame,
            bg=self.sidebar_bg
        )

        logo_container.pack(
            pady=(30, 40)
        )

        logo_loaded = False

        try:

            current_dir = os.path.dirname(
                os.path.abspath(__file__)
            )

            logo_path = os.path.join(
                current_dir,
                "assets",
                "Group 4.png"
            )

            if os.path.exists(logo_path):

                self.logo_photo = tk.PhotoImage(
                    file=logo_path
                )

                width = self.logo_photo.width()

                if width > 180:

                    factor = width // 180 + 1

                    self.logo_photo = self.logo_photo.subsample(
                        factor,
                        factor
                    )

                logo_label = tk.Label(
                    logo_container,
                    image=self.logo_photo,
                    bg=self.sidebar_bg
                )

                logo_label.pack()

                logo_loaded = True

        except Exception as e:

            print("Logo Error:", e)

        # =========================
        # FALLBACK TEXT LOGO
        # =========================

        if not logo_loaded:

            logo_label = tk.Label(
                logo_container,
                text="Vidhyut",
                font=("Arial", 22, "bold"),
                bg=self.sidebar_bg,
                fg="white"
            )

            logo_label.pack()

        # =========================
        # NAVIGATION LINKS
        # =========================

        self.create_nav_link(
            sidebar_frame,
            "Home",
            self.go_home
        )

        self.create_nav_link(
            sidebar_frame,
            "Learn",
            self.go_learn
        )

        separator = tk.Frame(
            sidebar_frame,
            bg="#4a5f7a",
            height=1
        )

        separator.pack(
            fill=tk.X,
            padx=20,
            pady=15
        )

        self.create_nav_link(
            sidebar_frame,
            "License",
            self.go_license
        )
        
    def create_nav_link(self, parent, text, command):
    
        link_frame = tk.Frame(
            parent,
            bg=self.sidebar_bg
        )

        link_frame.pack(fill=tk.X, pady=6)

        icon_photo = None

        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))

            icon_map = {
                "Home": "home.png",
                "Learn": "reading-book.png",
                "License": "certificate.png"
            }

            if text in icon_map:

                icon_path = os.path.join(
                    current_dir,
                    "assets",
                    icon_map[text]
                )

                if os.path.exists(icon_path):

                    icon_photo = tk.PhotoImage(file=icon_path)

                    if icon_photo.width() > 22:

                        factor = icon_photo.width() // 22 + 1

                        icon_photo = icon_photo.subsample(
                            factor,
                            factor
                        )

        except Exception as e:
            print("Icon Error:", e)

        link_button = tk.Button(
            link_frame,
            text=f"  {text}" if not icon_photo else text,
            image=icon_photo if icon_photo else None,
            compound=tk.LEFT if icon_photo else None,
            font=("Arial", 13),
            bg=self.sidebar_bg,
            fg="white",
            activebackground=self.sidebar_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            anchor="w",
            padx=30,
            pady=12,
            command=command
        )

        link_button.pack(fill=tk.X)

        if icon_photo:
            link_button.image = icon_photo

        link_button.bind(
            "<Enter>",
            lambda e: link_button.config(bg=self.sidebar_hover)
        )

        link_button.bind(
            "<Leave>",
            lambda e: link_button.config(bg=self.sidebar_bg)
        )
        
    def create_header(self):
    
        main_container = tk.Frame(
            self.root,
            bg=self.header_bg
        )

        main_container.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True
        )

        self.header_frame = tk.Frame(
            main_container,
            bg=self.header_bg,
            height=200
        )

        self.header_frame.pack(fill=tk.X)
        self.header_frame.pack_propagate(False)

        title_font_bold = font.Font(
            family="Arial",
            size=34,
            weight="bold"
        )

        title_label1 = tk.Label(
            self.header_frame,
            text="Vidhyut",
            font=title_font_bold,
            bg=self.header_bg,
            fg="white"
        )

        title_label1.pack(pady=(40, 0))

        title_font_normal = font.Font(
            family="Arial",
            size=24,
            weight="normal"
        )

        title_label2 = tk.Label(
            self.header_frame,
            text="Decoding Transformer Health",
            font=title_font_normal,
            bg=self.header_bg,
            fg="white"
        )

        title_label2.pack(pady=(5, 8))

        subtitle = tk.Label(
            self.header_frame,
            text="AI-Powered SFRA Analysis & Transformer Diagnostics Platform",
            font=("Arial", 14),
            bg=self.header_bg,
            fg="#dfe6ea"
        )

        subtitle.pack()

        self.main_container = main_container

    def create_content(self):

        outer_frame = tk.Frame(
            self.main_container,
            bg=self.content_bg
        )

        outer_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(
            outer_frame,
            bg=self.content_bg,
            highlightthickness=0
        )

        scrollbar = ttk.Scrollbar(
            outer_frame,
            orient="vertical",
            command=canvas.yview
        )

        scrollable_frame = tk.Frame(
            canvas,
            bg=self.content_bg
        )

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window(
            (0, 0),
            window=scrollable_frame,
            anchor="nw"
        )

        canvas.configure(
            yscrollcommand=scrollbar.set
        )

        canvas.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        # =========================
        # SMOOTH MOUSE SCROLL
        # =========================

        def _on_mousewheel(event):

            canvas.yview_scroll(
                int(-1 * (event.delta / 120)),
                "units"
            )

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        content_frame = scrollable_frame

        # =========================
        # MAIN BUTTON
        # =========================

        button_area = tk.Frame(
            content_frame,
            bg=self.content_bg
        )

        button_area.pack(pady=(80, 20))

        main_button = tk.Button(
            button_area,
            text="Go to Main Application",
            font=("Arial", 14, "bold"),
            bg=self.button_color,
            fg="white",
            activebackground=self.button_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=40,
            pady=14,
            command=self.go_to_main_application
        )

        main_button.pack()

        main_button.bind(
            "<Enter>",
            lambda e: main_button.config(bg=self.button_hover)
        )

        main_button.bind(
            "<Leave>",
            lambda e: main_button.config(bg=self.button_color)
        )

        # =========================
        # MODE DROPDOWN
        # =========================

        dropdown_frame = tk.Frame(
            content_frame,
            bg=self.content_bg
        )

        dropdown_frame.pack(pady=(15, 25))

        dropdown_label = tk.Label(
            dropdown_frame,
            text="Select Mode:",
            font=("Arial", 12),
            bg=self.content_bg,
            fg="#333333"
        )

        dropdown_label.pack(side=tk.LEFT, padx=(0, 10))

        style = ttk.Style()
        style.theme_use('clam')

        style.configure(
            'Custom.TCombobox',
            fieldbackground='white',
            background='white'
        )

        self.mode_var = tk.StringVar()

        mode_dropdown = ttk.Combobox(
            dropdown_frame,
            textvariable=self.mode_var,
            values=["Cloud", "Device"],
            width=22,
            state="readonly",
            font=("Arial", 11),
            style='Custom.TCombobox'
        )

        mode_dropdown.pack(side=tk.LEFT)

        mode_dropdown.set("Cloud")

        mode_dropdown.bind(
            "<<ComboboxSelected>>",
            self.on_mode_selected
        )

        # =========================
        # RECENT PROJECTS TITLE
        # =========================

        projects_title = tk.Label(
            content_frame,
            text="Recent Projects",
            font=("Arial", 22, "bold"),
            bg=self.content_bg,
            fg="#333333"
        )

        projects_title.pack(pady=(30, 20))

        projects_container = tk.Frame(
            content_frame,
            bg=self.content_bg
        )

        projects_container.pack(pady=10)

        projects = self.project_manager.get_recent_projects()

        for i, project in enumerate(projects):
            
            row = i//2
            col = i % 2
            
            self.create_project_card(
                projects_container,
                project,
                row,
                col
            )

        footer = tk.Label(
            content_frame,
            text="© 2026 Vidhyut AI Systems",
            font=("Arial", 10),
            bg=self.content_bg,
            fg="#777777"
        )

        footer.pack(pady=30)

    def create_project_card(self, parent, project, row, col):

        card_frame = tk.Frame(
            parent,
            bg=self.card_bg,
            relief=tk.SOLID,
            borderwidth=1,
            highlightbackground="#cccccc",
            highlightthickness=1,
            width=420,
            height=170
        )

        card_frame.grid(
            row=row,
            column=col,
            padx=20,
            pady=18,
            sticky="n"
        )

        card_frame.grid_propagate(False)

        inner_frame = tk.Frame(
            card_frame,
            bg=self.card_bg
        )

        inner_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=24,
            pady=20
        )

        name_label = tk.Label(
            inner_frame,
            text=project["name"],
            font=("Arial", 18, "bold"),
            bg=self.card_bg,
            fg="#000000",
            anchor="w"
        )

        name_label.pack(anchor="w")

        desc_label = tk.Label(
            inner_frame,
            text=project["description"],
            font=("Arial", 12),
            bg=self.card_bg,
            fg="#666666",
            wraplength=340,
            justify="left"
        )

        desc_label.pack(anchor="w", pady=(8, 14))

        bottom_frame = tk.Frame(
            inner_frame,
            bg=self.card_bg
        )

        bottom_frame.pack(
            fill=tk.X,
            side=tk.BOTTOM
        )

        status_label = tk.Label(
            bottom_frame,
            text=f"Status: {project['status']}",
            font=("Arial", 10),
            bg=self.card_bg,
            fg="#888888"
        )

        status_label.pack(side=tk.LEFT)

        view_button = tk.Button(
            bottom_frame,
            text="View Details",
            font=("Arial", 11),
            bg=self.button_color,
            fg="white",
            activebackground=self.button_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=7,
            command=lambda p=project: self.view_project_details(p)
        )

        view_button.pack(side=tk.RIGHT)

        view_button.bind(
            "<Enter>",
            lambda e: view_button.config(bg=self.button_hover)
        )

        view_button.bind(
            "<Leave>",
            lambda e: view_button.config(bg=self.button_color)
        )

        # =========================
        # CARD HOVER EFFECT
        # =========================

        def on_enter(e):

            card_frame.config(
                highlightbackground="#999999",
                highlightthickness=2
            )

        def on_leave(e):

            card_frame.config(
                highlightbackground="#cccccc",
                highlightthickness=1
            )

        card_frame.bind("<Enter>", on_enter)
        card_frame.bind("<Leave>", on_leave)
        
    
    
        # =========================================================
    # NAVIGATION FUNCTIONS
    # =========================================================

    def on_mode_selected(self, event):

        selected_mode = self.mode_var.get()

        if selected_mode == "Cloud":
            self.handle_cloud_mode()

        elif selected_mode == "Device":
            self.handle_device_mode()

    def handle_cloud_mode(self):

        print("Cloud mode selected")

        self.show_message(
            "Cloud Mode",
            "Cloud mode activated!\n\nConnecting to cloud services..."
        )

    def handle_device_mode(self):

        print("Device mode selected")

        file_path = filedialog.askopenfilename(
            title="Select a file from your device",
            filetypes=[
                ("All Files", "*.*"),
                ("Text Files", "*.txt"),
                ("CSV Files", "*.csv"),
                ("Excel Files", "*.xlsx *.xls"),
                ("PDF Files", "*.pdf"),
                ("Image Files", "*.png *.jpg *.jpeg *.gif")
            ]
        )

        if file_path:

            file_name = os.path.basename(file_path)

            self.show_message(
                "Device Mode",
                f"File selected:\n{file_name}\n\nPath: {file_path}"
            )

    def go_home(self):

        self.show_message(
            "Home",
            "You are already on the home page"
        )

    def go_learn(self):

        self.show_message(
            "Learn",
            "Opening learning resources..."
        )

    def go_license(self):

        self.show_message(
            "License",
            "Opening license information..."
        )
            
        # =========================================================
    # MAIN APPLICATION
    # =========================================================

    def go_to_main_application(self):

        mode = self.mode_var.get()

        print(f"Navigating to Main Application in {mode} mode...")

        try:

            import Main_page

            self.root.destroy()

            Main_page.main()

        except ImportError as e:

            print(f"Error importing Main_page.py: {e}")

            self.show_message(
                "Error",
                f"Could not load Main Application.\n\n{e}"
            )

        except Exception as e:

            print(f"Error launching Main Application: {e}")

            self.show_message(
                "Error",
                f"Error launching Main Application:\n\n{e}"
            )

    def view_project_details(self, project):

        self.show_message(
            "Project Details",
            f"Opening {project['name']}..."
        )
        
        # =========================================================
    # POPUP MESSAGE
    # =========================================================

    def show_message(self, title, message):

        msg_window = tk.Toplevel(self.root)

        msg_window.title(title)

        msg_window.geometry("420x180")

        msg_window.transient(self.root)

        msg_window.grab_set()

        msg_window.configure(bg="white")

        msg_label = tk.Label(
            msg_window,
            text=message,
            font=("Arial", 12),
            bg="white",
            pady=30,
            wraplength=350,
            justify="center"
        )

        msg_label.pack()

        ok_button = tk.Button(
            msg_window,
            text="OK",
            font=("Arial", 11),
            bg=self.button_color,
            fg="white",
            activebackground=self.button_hover,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=30,
            pady=8,
            command=msg_window.destroy
        )

        ok_button.pack(pady=10)

        ok_button.bind(
            "<Enter>",
            lambda e: ok_button.config(bg=self.button_hover)
        )

        ok_button.bind(
            "<Leave>",
            lambda e: ok_button.config(bg=self.button_color)
        )
        
    # =========================================================
# MAIN
# =========================================================

def main():

    root = tk.Tk()

    app = LandingPage(root)

    root.mainloop()


if __name__ == "__main__":

    main()