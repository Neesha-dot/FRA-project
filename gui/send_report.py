import tkinter as tk
from tkinter import ttk, messagebox
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os
import threading


class SendReportModule:
    def __init__(self, workspace_frame, preview_frame, console_text):
        self.workspace_frame = workspace_frame
        self.preview_frame = preview_frame
        self.console_text = console_text
        self.db = None
        
        # ========== CONFIGURED EMAIL CREDENTIALS ==========
        # Gmail account for sending reports
        self.sender_email = "cognitivecore06@gmail.com"
        
        # Gmail App Password (16 characters from Google)
        self.sender_password = "ubryloicllcjmimz"  # App password without spaces
        # ==================================================

        self.initialize_firebase()
        self.setup_workspace()

    # ----------------------------------------------------------
    # FIREBASE INITIALIZATION
    # ----------------------------------------------------------
    def initialize_firebase(self):
        try:
            if not firebase_admin._apps:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                key_path = os.path.join(project_root, "fiirebase_key.json")

                if not os.path.exists(key_path):
                    self.log_to_console(f"ERROR: fiirebase_key.json not found at {key_path}")
                    messagebox.showerror("Firebase Error", f"fiirebase_key.json not found:\n{key_path}")
                    return

                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)
                self.log_to_console("Firebase initialized successfully")

            self.db = firestore.client()
            self.log_to_console("Firestore connected successfully")

        except Exception as e:
            self.log_to_console(f"Firebase initialization error: {str(e)}")
            messagebox.showerror("Firebase Error", str(e))

    # ----------------------------------------------------------
    # LOGGING
    # ----------------------------------------------------------
    def log_to_console(self, message):
        if self.console_text:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.console_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.console_text.see(tk.END)

    # ----------------------------------------------------------
    # CLEAR PREVIEW PANEL
    # ----------------------------------------------------------
    def clear_preview(self):
        for w in self.preview_frame.winfo_children():
            w.destroy()
        self.preview_frame.configure(bg="white")

    # ----------------------------------------------------------
    # SIDEBAR MENU
    # ----------------------------------------------------------
    def setup_workspace(self):
        for w in self.workspace_frame.winfo_children():
            w.destroy()

        bg = "#f5f5f5"
        hover = "#e8e8e8"
        self.workspace_frame.configure(bg=bg)

        tk.Label(
            self.workspace_frame, text="Workspace",
            font=("Segoe UI", 14, "bold"),
            bg=bg, anchor="w"
        ).pack(fill=tk.X, padx=12, pady=(15, 10))

        ttk.Separator(self.workspace_frame).pack(fill="x", padx=8, pady=5)

        buttons = [
            ("1. Book Diary", self.show_book_diary),
            ("2. Send Report", self.show_send_report),
            ("3. Emergency Contact", self.show_emergency_contact)
        ]

        for text, cmd in buttons:
            lbl = tk.Label(
                self.workspace_frame, text=text,
                font=("Segoe UI", 11),
                bg=bg, anchor="w",
                padx=15, pady=8,
                cursor="hand2"
            )
            lbl.pack(fill=tk.X)
            lbl.bind("<Button-1>", lambda e, c=cmd: c())
            lbl.bind("<Enter>", lambda e, L=lbl: L.config(bg=hover))
            lbl.bind("<Leave>", lambda e, L=lbl: L.config(bg=bg))

    # ----------------------------------------------------------
    # CLEAN HEADING
    # ----------------------------------------------------------
    def add_heading(self, text):
        tk.Label(
            self.preview_frame,
            text=text,
            font=("Segoe UI", 16, "bold"),
            bg="white"
        ).pack(anchor="w", padx=25, pady=(25, 15))

    # ----------------------------------------------------------
    # BOOK DIARY UI
    # ----------------------------------------------------------
    def show_book_diary(self):
        self.clear_preview()
        self.log_to_console("Opened Book Diary")
        self.add_heading("Book Diary")

        container = tk.Frame(self.preview_frame, bg="white")
        container.pack(fill=tk.BOTH, expand=True, padx=25, pady=10)

        form = tk.Frame(container, bg="white")
        form.pack(anchor="w")

        def make_field(label):
            row = tk.Frame(form, bg="white")
            row.pack(anchor="w", pady=8)

            tk.Label(row, text=label, font=("Segoe UI", 11), bg="white").pack(side="left")
            entry = tk.Entry(row, width=35, font=("Segoe UI", 11), bd=1, relief=tk.SOLID)
            entry.pack(side="left", padx=12)
            return entry

        name_entry = make_field("Name:")
        contact_entry = make_field("Contact Number:")
        email_entry = make_field("Email ID:")

        tk.Button(
            form, text="Save",
            bg="#4CAF50", fg="white",
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=12, pady=4,
            command=lambda: self.save_diary_entry(name_entry, contact_entry, email_entry)
        ).pack(anchor="w", pady=15)

        tk.Label(container, text="Saved Entries:", font=("Segoe UI", 12, "bold"), bg="white") \
            .pack(anchor="w", pady=(20, 8))

        # Entries container
        self.entries_frame = tk.Frame(container, bg="white")
        self.entries_frame.pack(fill=tk.X)

        # Initial loading message
        tk.Label(
            self.entries_frame,
            text="Loading entries...",
            font=("Segoe UI", 10),
            bg="white",
            fg="#666"
        ).pack(anchor="w", pady=5)

        # Load entries WITHOUT freezing UI
        threading.Thread(target=self.load_diary_entries_thread, daemon=True).start()

    # ----------------------------------------------------------
    # THREAD SAFE FIRESTORE FETCH
    # ----------------------------------------------------------
    def load_diary_entries_thread(self):
        try:
            docs = list(
                self.db.collection("diary_entries")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .stream()
            )
        except Exception:
            docs = []

        # Update UI AFTER data loads
        self.preview_frame.after(0, lambda: self.load_diary_entries(docs))

    # ----------------------------------------------------------
    # DISPLAY ENTRIES
    # ----------------------------------------------------------
    def load_diary_entries(self, docs):
        for w in self.entries_frame.winfo_children():
            w.destroy()

        if not docs:
            tk.Label(self.entries_frame, text="No entries found.", bg="white").pack()
            return

        for doc in docs:
            d = doc.to_dict()
            txt = f"{d['name']} — {d['email']} — {d['contact_number']}"

            tk.Label(
                self.entries_frame,
                text=txt,
                bg="white",
                font=("Segoe UI", 10),
                anchor="w"
            ).pack(fill="x", pady=3)

    # ----------------------------------------------------------
    # SAVE ENTRY (FIXED)
    # ----------------------------------------------------------
    def save_diary_entry(self, name_entry, contact_entry, email_entry):
        # Get values from Entry widgets
        name = name_entry.get().strip()
        contact = contact_entry.get().strip()
        email = email_entry.get().strip()

        if not (name and contact and email):
            messagebox.showwarning("Validation Error", "All fields required")
            return

        try:
            self.db.collection("diary_entries").document().set({
                "name": name,
                "contact_number": contact,
                "email": email,
                "timestamp": datetime.now()
            })
            
            # Log success to console only (no popup)
            self.log_to_console(f"Saved diary entry for {email}")

            # Clear form fields using the Entry widget objects
            name_entry.delete(0, tk.END)
            contact_entry.delete(0, tk.END)
            email_entry.delete(0, tk.END)

            # Refresh entries immediately without freezing UI
            threading.Thread(target=self.load_diary_entries_thread, daemon=True).start()

        except Exception as e:
            self.log_to_console(f"Error saving entry: {str(e)}")
            messagebox.showerror("Error", str(e))

    # ----------------------------------------------------------
    # SEND REPORT UI
    # ----------------------------------------------------------
    def show_send_report(self):
        self.clear_preview()
        self.log_to_console("Opened Send Report")
        self.add_heading("Send Report")

        container = tk.Frame(self.preview_frame, bg="white")
        container.pack(fill=tk.BOTH, expand=True, padx=25, pady=10)

        form = tk.Frame(container, bg="white")
        form.pack(anchor="w")

        row = tk.Frame(form, bg="white")
        row.pack(anchor="w", pady=8)

        tk.Label(row, text="Receiver Email ID:", font=("Segoe UI", 11), bg="white") \
            .pack(side="left")

        email_entry = tk.Entry(row, width=35, font=("Segoe UI", 11), bd=1, relief=tk.SOLID)
        email_entry.pack(side="left", padx=12)

        tk.Button(
            form, text="Send Report",
            bg="#4CAF50", fg="white",
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=12, pady=4,
            command=lambda: self.send_report(email_entry, container)
        ).pack(anchor="w", pady=15)

        # Message frame for displaying status
        self.message_frame = tk.Frame(container, bg="white")
        self.message_frame.pack(fill=tk.X, pady=(10, 0))

        # Show sent reports history
        tk.Label(container, text="Sent Reports History:", font=("Segoe UI", 12, "bold"), bg="white") \
            .pack(anchor="w", pady=(20, 8))

        self.reports_frame = tk.Frame(container, bg="white")
        self.reports_frame.pack(fill=tk.X)

        self.load_sent_reports()

    # ----------------------------------------------------------
    # LOAD SENT REPORTS HISTORY
    # ----------------------------------------------------------
    def load_sent_reports(self):
        for w in self.reports_frame.winfo_children():
            w.destroy()

        try:
            docs = self.db.collection("sent_reports").order_by(
                "timestamp", direction=firestore.Query.DESCENDING
            ).limit(10).stream()

            empty = True
            for doc in docs:
                empty = False
                d = doc.to_dict()
                timestamp = d['timestamp'].strftime("%Y-%m-%d %H:%M")
                txt = f"{d['receiver_email']} — {timestamp} — {d['status']}"

                tk.Label(
                    self.reports_frame,
                    text=txt,
                    bg="white",
                    font=("Segoe UI", 10),
                    anchor="w"
                ).pack(fill="x", pady=3)

            if empty:
                tk.Label(self.reports_frame, text="No reports sent yet.", bg="white").pack()

        except Exception as e:
            self.log_to_console(f"Error loading sent reports: {str(e)}")

    # ----------------------------------------------------------
    # DISPLAY MESSAGE IN PREVIEW PANEL
    # ----------------------------------------------------------
    def show_message(self, message, message_type="info"):
        """Display a message in the preview panel"""
        # Clear previous messages
        for w in self.message_frame.winfo_children():
            w.destroy()

        # Color based on message type
        if message_type == "error":
            bg_color = "#f8d7da"
            text_color = "#721c24"
            icon = "❌"
        elif message_type == "success":
            bg_color = "#d4edda"
            text_color = "#155724"
            icon = "✅"
        else:  # info
            bg_color = "#d1ecf1"
            text_color = "#0c5460"
            icon = "ℹ️"

        msg_container = tk.Frame(self.message_frame, bg=bg_color, bd=1, relief=tk.SOLID)
        msg_container.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            msg_container,
            text=f"{icon} {message}",
            font=("Segoe UI", 10),
            bg=bg_color,
            fg=text_color,
            wraplength=500,
            justify="left"
        ).pack(padx=10, pady=10)

    # ----------------------------------------------------------
    # FIND LATEST PDF IN OUTPUT FOLDER
    # ----------------------------------------------------------
    def find_latest_report_pdf(self):
        """
        Dynamically locate the latest generated PDF in the output folder.
        Returns the full path to the PDF or None if not found.
        """
        try:
            # Get project root (two levels up from this file)
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(current_file))
            output_dir = os.path.join(project_root, "output")
            
            # Check if output directory exists
            if not os.path.exists(output_dir):
                self.log_to_console(f"Output directory not found: {output_dir}")
                return None
            
            # Look for PDF files in output folder
            pdf_files = []
            for filename in os.listdir(output_dir):
                if filename.endswith('.pdf'):
                    full_path = os.path.join(output_dir, filename)
                    pdf_files.append(full_path)
            
            if not pdf_files:
                self.log_to_console("No PDF files found in output folder")
                return None
            
            # Get the most recently modified PDF
            latest_pdf = max(pdf_files, key=os.path.getmtime)
            self.log_to_console(f"Found PDF: {os.path.basename(latest_pdf)}")
            return latest_pdf
            
        except Exception as e:
            self.log_to_console(f"Error locating PDF: {str(e)}")
            return None

    # ----------------------------------------------------------
    # EMAIL SENDER (UPDATED)
    # ----------------------------------------------------------
    def send_report(self, email_entry, container):
        # Get value from Entry widget
        receiver = email_entry.get().strip()

        # Validation
        if not receiver:
            self.show_message("Please enter an email address.", "error")
            self.log_to_console("Error: Email field is empty")
            return

        # Check if email exists in diary
        self.log_to_console(f"Checking if {receiver} exists in Book Diary...")
        try:
            docs = list(self.db.collection("diary_entries").where("email", "==", receiver).stream())
            if not docs:
                self.show_message("This email is not registered in Book Diary.", "error")
                self.log_to_console(f"Email '{receiver}' not found in Book Diary")
                return
        except Exception as e:
            self.log_to_console(f"Database error: {str(e)}")
            self.show_message(f"Database error: {str(e)}", "error")
            return

        # Dynamically find PDF in output folder
        report_path = self.find_latest_report_pdf()
        
        if not report_path or not os.path.exists(report_path):
            self.show_message("No generated report found in /output folder.", "error")
            self.log_to_console("Report file missing")
            return

        # Show sending message
        self.show_message("Sending report... Please wait.", "info")
        
        # Send email in background thread
        self.log_to_console(f"Sending report to {receiver}...")
        threading.Thread(
            target=self.send_email_thread,
            args=(receiver, report_path),
            daemon=True
        ).start()

    # ----------------------------------------------------------
    # THREAD-SAFE EMAIL SENDING (UPDATED)
    # ----------------------------------------------------------
    def send_email_thread(self, receiver, file_path):
        success = self.send_email_with_attachment(receiver, file_path)

        # Update UI on main thread
        self.preview_frame.after(0, lambda: self.handle_email_result(success, receiver))

    def handle_email_result(self, success, receiver):
        if success:
            # Save to database
            try:
                self.db.collection("sent_reports").document().set({
                    "receiver_email": receiver,
                    "timestamp": datetime.now(),
                    "status": "sent"
                })
            except Exception as e:
                self.log_to_console(f"Database error: {str(e)}")

            # Show success message in preview panel
            self.show_message(f"Report sent successfully to {receiver}", "success")
            self.log_to_console(f"Report sent successfully to {receiver}")
            
            # Refresh history without refreshing entire preview panel
            self.load_sent_reports()
        else:
            self.show_message("Failed to send email. Check console for details.", "error")
            self.log_to_console("Failed to send email. Check console for details.")

    # ----------------------------------------------------------
    # EMAIL SENDING LOGIC (CONFIGURED FOR PROJECT APP)
    # ----------------------------------------------------------
    def send_email_with_attachment(self, receiver, file_path):
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = f"Project Medical System <{self.sender_email}>"
            msg["To"] = receiver
            msg["Subject"] = "Medical Report - Generated Report from Project"

            # Get recipient name from database
            recipient_name = "Recipient"
            try:
                docs = list(self.db.collection("diary_entries").where("email", "==", receiver).stream())
                if docs:
                    recipient_name = docs[0].to_dict().get("name", "Recipient")
            except:
                pass

            # Email body with personalization
            body = f"""Dear {recipient_name},

Please find attached your generated medical report.

This report has been automatically generated and sent from Project Medical Report System.

If you have any questions or concerns regarding this report, please feel free to contact us.

Best regards,
Project Medical Report System
Healthcare Team

---
This is an automated email from Project. Please do not reply to this message.
            """
            msg.attach(MIMEText(body, "plain"))

            # Attach PDF
            with open(file_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())

            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(file_path)}"
            )
            msg.attach(part)

            # Connect to Gmail SMTP
            self.log_to_console("Connecting to Gmail SMTP server...")
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            
            # Login with app password (already without spaces)
            self.log_to_console("Authenticating with Project credentials...")
            server.login(self.sender_email, self.sender_password)
            
            # Send email
            self.log_to_console("Sending email...")
            server.send_message(msg)
            server.quit()
            
            self.log_to_console("✓ Email sent successfully from Project!")
            return True

        except smtplib.SMTPAuthenticationError as e:
            self.log_to_console(f"❌ ERROR: Authentication failed - {str(e)}")
            self.log_to_console("Please verify Project email credentials:")
            self.log_to_console(f"1. Email: {self.sender_email}")
            self.log_to_console("2. App Password is correct (ubryloicllcjmimz)")
            self.log_to_console("3. 2-Factor Authentication is enabled on Gmail")
            return False
        except smtplib.SMTPException as e:
            self.log_to_console(f"SMTP Error: {str(e)}")
            return False
        except Exception as e:
            self.log_to_console(f"Error sending email: {str(e)}")
            return False

    # ----------------------------------------------------------
    # EMERGENCY CONTACT UI
    # ----------------------------------------------------------
    def show_emergency_contact(self):
        self.clear_preview()
        self.log_to_console("Opened Emergency Contact")
        self.add_heading("Emergency Contact")

        container = tk.Frame(self.preview_frame, bg="white")
        container.pack(fill=tk.BOTH, expand=True, padx=25, pady=10)

        form = tk.Frame(container, bg="white")
        form.pack(anchor="w")

        def make_field(label):
            row = tk.Frame(form, bg="white")
            row.pack(anchor="w", pady=8)

            tk.Label(row, text=label, bg="white", font=("Segoe UI", 11)).pack(side="left")
            entry = tk.Entry(row, width=35, font=("Segoe UI", 11), bd=1, relief=tk.SOLID)
            entry.pack(side="left", padx=12)
            return entry

        name_entry = make_field("Name:")
        contact_entry = make_field("Contact Number:")

        tk.Button(
            form, text="Add Contact",
            bg="#4CAF50", fg="white",
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=12, pady=4,
            command=lambda: self.add_emergency_contact(name_entry, contact_entry)
        ).pack(anchor="w", pady=15)

        tk.Label(container, text="Emergency Contacts:", font=("Segoe UI", 12, "bold"), bg="white") \
            .pack(anchor="w", pady=(20, 8))

        self.contacts_frame = tk.Frame(container, bg="white")
        self.contacts_frame.pack(fill=tk.X)

        self.load_emergency_contacts()

    def add_emergency_contact(self, name_entry, contact_entry):
        name = name_entry.get().strip()
        contact = contact_entry.get().strip()

        if not name or not contact:
            messagebox.showwarning("Error", "All fields required")
            return

        try:
            self.db.collection("emergency_contacts").document().set({
                "name": name,
                "contact_number": contact,
                "timestamp": datetime.now()
            })

            messagebox.showinfo("Success", "Contact added")
            self.log_to_console(f"Added emergency contact: {name}")
            
            # Clear fields
            name_entry.delete(0, tk.END)
            contact_entry.delete(0, tk.END)
            
            self.load_emergency_contacts()

        except Exception as e:
            self.log_to_console(f"Error adding contact: {str(e)}")
            messagebox.showerror("Error", str(e))

    def load_emergency_contacts(self):
        for w in self.contacts_frame.winfo_children():
            w.destroy()

        try:
            docs = self.db.collection("emergency_contacts").order_by(
                "timestamp", direction=firestore.Query.DESCENDING
            ).stream()

            empty = True
            for doc in docs:
                empty = False
                d = doc.to_dict()
                txt = f"{d['name']} — {d['contact_number']}"

                tk.Label(
                    self.contacts_frame, text=txt,
                    bg="white", font=("Segoe UI", 10), anchor="w"
                ).pack(fill="x", pady=3)

            if empty:
                tk.Label(self.contacts_frame, text="No contacts found.", bg="white").pack()

        except Exception as e:
            self.log_to_console(f"Error loading contacts: {str(e)}")
            tk.Label(self.contacts_frame, text="Error loading contacts.", fg="red", bg="white").pack()

