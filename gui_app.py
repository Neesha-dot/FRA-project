import tkinter as tk
from tkinter import ttk, messagebox

class SimpleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("My Python GUI")
        self.root.geometry("400x300")
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title label
        title_label = ttk.Label(main_frame, text="Welcome to My GUI!", 
                                font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Name input
        name_label = ttk.Label(main_frame, text="Enter your name:")
        name_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.name_entry = ttk.Entry(main_frame, width=30)
        self.name_entry.grid(row=1, column=1, pady=5)
        
        # Dropdown menu
        dropdown_label = ttk.Label(main_frame, text="Choose an option:")
        dropdown_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        
        self.dropdown_var = tk.StringVar()
        dropdown = ttk.Combobox(main_frame, textvariable=self.dropdown_var, 
                                values=["Option 1", "Option 2", "Option 3"], 
                                width=27, state="readonly")
        dropdown.grid(row=2, column=1, pady=5)
        dropdown.set("Option 1")
        
        # Checkbox
        self.check_var = tk.BooleanVar()
        checkbox = ttk.Checkbutton(main_frame, text="I agree to the terms", 
                                    variable=self.check_var)
        checkbox.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        # Submit button
        submit_btn = ttk.Button(button_frame, text="Submit", 
                                command=self.submit_form)
        submit_btn.grid(row=0, column=0, padx=5)
        
        # Clear button
        clear_btn = ttk.Button(button_frame, text="Clear", 
                               command=self.clear_form)
        clear_btn.grid(row=0, column=1, padx=5)
        
        # Result label
        self.result_label = ttk.Label(main_frame, text="", 
                                      foreground="blue", wraplength=350)
        self.result_label.grid(row=5, column=0, columnspan=2, pady=10)
    
    def submit_form(self):
        name = self.name_entry.get()
        option = self.dropdown_var.get()
        agreed = self.check_var.get()
        
        if not name:
            messagebox.showwarning("Warning", "Please enter your name!")
            return
        
        if not agreed:
            messagebox.showwarning("Warning", "Please agree to the terms!")
            return
        
        result = f"Hello {name}! You selected: {option}"
        self.result_label.config(text=result)
        messagebox.showinfo("Success", "Form submitted successfully!")
    
    def clear_form(self):
        self.name_entry.delete(0, tk.END)
        self.dropdown_var.set("Option 1")
        self.check_var.set(False)
        self.result_label.config(text="")

def main():
    root = tk.Tk()
    app = SimpleGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
