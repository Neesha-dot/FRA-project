"""
File Operations Module
Handles all file-related menu operations
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os




class FileOperations:
    def __init__(self, parent):
        """
        Initialize file operations handler
        Args:
            parent: Reference to Main_page instance
        """
        self.parent = parent
        self.current_file = None
        self.recent_projects = []
        self.load_recent_projects()
   
    def new_project(self):
        """Create a new project"""
        # Check if there are unsaved changes
        if self.parent.has_unsaved_changes():
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
        self.parent.clear_workspace()
        self.parent.unsaved_changes = False
        messagebox.showinfo("New Project", "New project created successfully!")
   
    def open_file(self):
        """Open an existing project file"""
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
                self.parent.load_project_data(data)
                self.add_to_recent(file_path)
                self.parent.unsaved_changes = False
                messagebox.showinfo("Success", f"Opened: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {str(e)}")
   
    def save_file(self):
        """Save the current project"""
        if self.current_file:
            self._save_to_file(self.current_file)
        else:
            self.save_as_file()
   
    def save_as_file(self):
        """Save project with a new name"""
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
            data = self.parent.get_project_data()
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            self.parent.unsaved_changes = False
            messagebox.showinfo("Success", f"Saved: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")
   
    def import_data(self):
        """Import data from external sources"""
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
                # Call parent's import handler
                self.parent.handle_data_import(file_path)
                messagebox.showinfo("Import", f"Data imported from: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import: {str(e)}")
   
    def export_report(self):
        """Export analysis report"""
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
                self.parent.generate_export_report(file_path)
                messagebox.showinfo("Export", f"Report exported to: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
   
    def show_recent_projects(self):
        """Show dialog with recent projects"""
        if not self.recent_projects:
            messagebox.showinfo("Recent Projects", "No recent projects found.")
            return
       
        # Create recent projects dialog
        dialog = tk.Toplevel(self.parent.root)
        dialog.title("Recent Projects")
        dialog.geometry("600x400")
        dialog.transient(self.parent.root)
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
   
    def open_specific_file(self, file_path):
        """Open a specific file by path"""
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                self.current_file = file_path
                self.parent.load_project_data(data)
                self.parent.unsaved_changes = False
                messagebox.showinfo("Success", f"Opened: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {str(e)}")
        else:
            messagebox.showwarning("Not Found", "File no longer exists.")
            self.recent_projects.remove(file_path)
            self.save_recent_projects()
   
    def add_to_recent(self, file_path):
        """Add file to recent projects list"""
        if file_path in self.recent_projects:
            self.recent_projects.remove(file_path)
        self.recent_projects.insert(0, file_path)
        self.recent_projects = self.recent_projects[:10]  # Keep last 10
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