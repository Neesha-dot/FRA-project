import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
from datetime import datetime
import re
import numpy as np
import xml.etree.ElementTree as ET
import csv
import pickle
import json

# ---------------------------------------------------------------------
# ML MODEL + Runtime Helpers
# ---------------------------------------------------------------------
import ML.sfra_runtime as rt

# Patch required runtime functions for pickle
import sys
sys.modules['__main__'].extract_features   = rt.extract_features
sys.modules['__main__'].predict_fault      = rt.predict_fault
sys.modules['__main__'].parse_metadata     = rt.parse_metadata
sys.modules['__main__'].parse_tap_table    = rt.parse_tap_table
sys.modules['__main__'].calculate_losses   = rt.calculate_losses
sys.modules['__main__'].diagnose_with_taps = rt.diagnose_with_taps

# =====================================================================
#  CLEAN NUMERIC TOKEN EXTRACTOR (utility)
# =====================================================================
def _clean_numeric_token(cell):
    """
    Extract the most plausible numeric token from any FRA CSV/text cell.
    Returns: float or None
    """
    if cell is None:
        return None
    s = str(cell).strip()
    if s == "":
        return None

    # exact number
    m_full = re.fullmatch(r"[+-]?\d+(\.\d+)?", s)
    if m_full:
        try:
            return float(s)
        except:
            return None

    # trailing suffix pattern (e.g., "244549-4" or "244549 -4")
    m_suffix = re.match(r"^([+-]?\d+(\.\d+)?)[\s\-]+[0-9]+$", s)
    if m_suffix:
        try:
            return float(m_suffix.group(1))
        except:
            pass

    # first numeric substring
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", s)
    if m:
        try:
            return float(m.group(1))
        except:
            return None

    return None

# =====================================================================
#  UNIVERSAL CSV LOADER (works with various FRA CSV variants)
# =====================================================================
def robust_universal_csv_loader(fp):
    """
    Loads many FRA CSV/text formats and extracts:
        freq[] = first numeric token per row
        mag[]  = second numeric token per row
    Returns numpy arrays (freq, mag).
    Raises ValueError if none found.
    """
    freq = []
    mag = []

    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.get_dialect("excel")
        reader = csv.reader(f, dialect)

        for row in reader:
            if not row:
                continue
            # attempt to extract numeric tokens conservatively from cells
            tokens = []
            for cell in row:
                v = _clean_numeric_token(cell)
                if v is not None:
                    tokens.append(v)

            # If the row didn't give useful tokens, try extracting from the full row text
            if len(tokens) < 2:
                row_text = ",".join([str(c) for c in row])
                nums = re.findall(r"([+-]?\d+(?:\.\d+)?)", row_text)
                if len(nums) >= 2:
                    try:
                        tokens = [float(nums[0]), float(nums[1])]
                    except:
                        tokens = []

            if len(tokens) >= 2:
                freq.append(float(tokens[0]))
                mag.append(float(tokens[1]))
            else:
                # skip rows that don't yield two numbers
                continue

    if len(freq) == 0:
        raise ValueError("No valid numeric FRA rows found in CSV.")

    return np.array(freq, dtype=float), np.array(mag, dtype=float)

# =====================================================================
#  EXPORT ML-READY UNIFIED CSV
# =====================================================================
def export_unified_csv(freq, mag, original_fp):
    """
    Saves standardized ML-ready FRA CSV in user Documents/Converted_FRA:
        Frequency,Magnitude
    Returns full path of saved file.
    """
    out_dir = os.path.join(os.path.expanduser("~"), "Documents", "Converted_FRA")
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(original_fp))[0]
    out_path = os.path.join(out_dir, f"{base}_converted.csv")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("Frequency,Magnitude\n")
        for fval, mval in zip(freq, mag):
            f.write(f"{fval},{mval}\n")

    return out_path

# =====================================================================
#  BINARY FILE DETECTION + PLACEHOLDERS
# =====================================================================
def is_binary_file(fp):
    """Heuristic: return True if file contains null bytes or many >127 bytes."""
    try:
        with open(fp, "rb") as f:
            chunk = f.read(2048)
            if not chunk:
                return False
            if b"\x00" in chunk:
                return True
            high = sum(1 for b in chunk if b > 127)
            return high > (len(chunk) * 0.1)
    except Exception:
        return False

def load_sfra_binary(fp):
    """Placeholder for real binary .sfra parsing - needs sample for implementation."""
    raise ValueError(".sfra appears binary. Provide a sample .sfra for a proper decoder implementation.")

def load_pfratest_binary(fp):
    """Placeholder for .pfraTest binary parsing."""
    raise ValueError(".pfraTest appears binary. Provide a sample file for a proper decoder implementation.")

def load_bak_binary(fp):
    """Placeholder for .bak binary parsing."""
    raise ValueError(".bak appears binary. Provide a sample file for a proper decoder implementation.")

# =====================================================================
#  UNIVERSAL TEXT / XML PARSER (works for FRA v2.0 multi-column too)
# =====================================================================
def parse_any_format(raw_text):
    """
    UNIVERSAL PARSER — accepts multi-column FRA rows (FRA v2.0).
    Uses:
        freq = first numeric token in the row
        mag  = second numeric token in the row
    Returns: freq (np.array), mag (np.array), metadata (dict), taps (list)
    """
    freq = []
    mag = []
    metadata = {}
    taps = []

    if raw_text is None:
        raw_text = ""
    text = raw_text.replace("\r", "\n")

    # Parse CSV/text rows: line-by-line numeric extraction
    for line in text.split("\n"):
        nums = re.findall(r"([+-]?\d+(?:\.\d+)?)", line)
        if len(nums) >= 2:
            try:
                fval = float(nums[0])
                mval = float(nums[1])
                freq.append(fval)
                mag.append(mval)
                continue
            except:
                pass

    # XML fallback: look for <point f=".." m=".."/>
    try:
        if "<" in text and "</" in text:
            try:
                root = ET.fromstring(text)
                for node in root.findall(".//point"):
                    fattr = node.attrib.get("f")
                    mattr = node.attrib.get("m")
                    if fattr is not None and mattr is not None:
                        try:
                            freq.append(float(fattr))
                            mag.append(float(mattr))
                        except:
                            pass
            except:
                pass
    except:
        pass

    # metadata (best-effort)
    fields = {
        "serial": r"[Ss]erial[:=\s]+([A-Za-z0-9\-\/]+)",
        "manufacturer": r"[Mm]anufacturer[:=\s]+([A-Za-z0-9 \-]+)",
        "year": r"[Yy]ear[:=\s]+([0-9]{4})",
        "start_freq": r"[Ss]tart[_ ]?[Ff]req[:=\s]+([0-9.]+)",
        "stop_freq": r"[Ss]top[_ ]?[Ff]req[:=\s]+([0-9.]+)"
    }
    for key, pat in fields.items():
        m = re.search(pat, text)
        metadata[key] = m.group(1) if m else None

    # taps detection (best-effort)
    tap_lines = re.findall(
        r"[Tt]ap[:\s]+([0-9]+).*?[Ss]et[:\s]+([0-9]+).*?[Uu][:=\s]+([0-9.]+).*?[Vv][:=\s]+([0-9.]+).*?[Ww][:=\s]+([0-9.]+)",
        text
    )
    for t in tap_lines:
        try:
            taps.append({
                "tap_no": int(t[0]),
                "set_tap": int(t[1]),
                "u": float(t[2]),
                "v": float(t[3]),
                "w": float(t[4])
            })
        except:
            pass

    if len(freq) == 0:
        raise ValueError("No usable SFRA numeric data detected.")

    # dedupe and sort by frequency
    arr = sorted(list(set(zip(freq, mag))), key=lambda x: x[0])
    freq = np.array([p[0] for p in arr], dtype=float)
    mag = np.array([p[1] for p in arr], dtype=float)

    return freq, mag, metadata, taps
# =====================================================================
#  MAIN UI MODULE
# =====================================================================
def enable_homepage(app):
    main_app = app

    workspace_frame = main_app.workspace_scrollable
    preview_panel = main_app.center_scrollable
    metadata_panel = main_app.metadata_content

    main_app.homepage_current_file = None
    main_app.homepage_file_data = None
    main_app.homepage_header_metadata = {}
    main_app.pipeline_data = None

    # library UI state
    main_app.library_expanded = False
    main_app.library_frame = None
    main_app.tree_expanded = False
    main_app.selected_transformer = tk.StringVar(value="")
    main_app.selected_winding = tk.StringVar(value="HV")
   
    # NEW: Additional required fields
    main_app.selected_manufacturer = tk.StringVar(value="")
    main_app.serial_number = tk.StringVar(value="")
    main_app.year_of_manufacturing = tk.StringVar(value="")
    main_app.voltage_rating = tk.StringVar(value="")
   
    # ML model storage
    main_app.loaded_ml_model = None
    main_app.loaded_model_config = None
    main_app.current_transformer_model = None

    # ---------------- UTILITIES ----------------
    def log(msg, level="INFO"):
        if hasattr(main_app, "log_console"):
            main_app.log_console(msg, level)

    def clear_panel(panel):
        for w in panel.winfo_children():
            w.destroy()

    def update_preview(content):
        clear_panel(preview_panel)
        t = tk.Text(
            preview_panel, wrap=tk.WORD, font=("Segoe UI", 10),
            bg="white", relief=tk.FLAT, padx=12, pady=12
        )
        t.insert(tk.END, content)
        t.config(state=tk.DISABLED)
        t.pack(fill=tk.BOTH, expand=True)

    # ---------------- HEADER METADATA PARSER ----------------
    def parse_header_metadata(text):
        meta = {}
        for line in (text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            cols = [c.strip() for c in line.split(",")]
            # If numeric data begins -> stop parsing header
            if len(cols) >= 2 and re.match(r"^[+-]?\d+(\.\d+)?$", cols[0] or "") and re.match(r"^[+-]?\d+(\.\d+)?$", cols[1] or ""):
                break
            if len(cols) == 2 and re.match(r"^[A-Za-z0-9_]+$", cols[0]):
                key, val = cols
                meta[key] = val
        return meta

    # ---------------- VALIDATION FUNCTION ----------------
    def validate_library_details():
        """
        Returns True if all required Library details are filled, False otherwise.
        """
        transformer = main_app.selected_transformer.get().strip()
        manufacturer = main_app.selected_manufacturer.get().strip()
        serial = main_app.serial_number.get().strip()
        year = main_app.year_of_manufacturing.get().strip()
        voltage = main_app.voltage_rating.get().strip()
       
        if not transformer:
            return False
        if not manufacturer:
            return False
        if not serial:
            return False
        if not year:
            return False
        if not voltage:
            return False
       
        return True

    # ---------------- SAVE (overwrite original) ----------------
    def save_file():
        """
        Overwrite the original file (simplified Save behavior).
        """
        if not main_app.homepage_current_file:
            messagebox.showwarning("No File", "Please open a file first.")
            return

        if not isinstance(main_app.homepage_file_data, str):
            messagebox.showerror("Save Error", "Current file appears to be binary or not loaded as text. Use Save As to export a text copy.")
            return

        try:
            with open(main_app.homepage_current_file, "w", encoding="utf-8") as f:
                f.write(main_app.homepage_file_data)
            messagebox.showinfo("Saved", f"File overwritten:\n{main_app.homepage_current_file}")
            log(f"File overwritten: {main_app.homepage_current_file}", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            log(str(e), "ERROR")

    # ---------------- SAVE AS ----------------
    def save_as_file():
        if main_app.homepage_file_data is None:
            messagebox.showwarning("No Data", "No file is loaded to save.")
            return

        fp = filedialog.asksaveasfilename(
            title="Save As",
            defaultextension=".txt",
            filetypes=[
                ("Text File", "*.txt"),
                ("CSV File", "*.csv"),
                ("All Files", "*.*")
            ],
            initialdir=os.path.expanduser("~")
        )
        if not fp:
            return

        if not isinstance(main_app.homepage_file_data, str):
            messagebox.showerror("Save As Error", "Current file appears binary. Please use export functions for binary formats.")
            return

        try:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(main_app.homepage_file_data)
            messagebox.showinfo("Saved", f"File saved:\n{fp}")
            log(f"File saved as: {fp}", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Save As Error", str(e))
            log(str(e), "ERROR")

    # ---------------- FILE OPEN WITH VALIDATION ----------------
    # ---------------- FILE OPEN WITH VALIDATION ----------------
    def open_file():
        # VALIDATION: Check if all Library details are filled
        if not validate_library_details():
            messagebox.showwarning(
                "Library Details Required",
                "Please select a transformer from the Library and fill the required details before opening a file.\n\n"
                "Required fields:\n"
                "• Transformer selection\n"
                "• Manufacturer\n"
                "• Serial Number\n"
                "• Year of Manufacturing\n"
                "• Voltage Rating"
            )
            return
       
        log("Opening file dialog...", "INFO")
        filetypes = [
            ("All Supported Files", "*.pdf *.doc *.docx *.txt *.csv *.xml *.sfra *.pfraTest *.bak"),
            ("CSV Files", "*.csv"),
            ("Text Files", "*.txt"),
            ("XML Files", "*.xml"),
            ("SFRA Files", "*.sfra"),
            ("PFRA Test Files", "*.pfraTest"),
            ("BAK Files", "*.bak"),
            ("All Files", "*.*")
        ]
        fp = filedialog.askopenfilename(title="Open File", filetypes=filetypes, initialdir=os.path.expanduser("~"))
        if not fp:
            return

        main_app.homepage_current_file = fp
        ext = os.path.splitext(fp)[1].lower()

        try:
            # Try reading as text first
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read()
            except Exception:
                # fallback to binary then attempt to decode to text (best-effort)
                with open(fp, "rb") as f:
                    data = f.read().decode("utf-8", errors="ignore")

            main_app.homepage_file_data = data

            # parse header metadata (best-effort)
            try:
                main_app.homepage_header_metadata = parse_header_metadata(data)
            except:
                main_app.homepage_header_metadata = {}

            # Update right-side metadata panel
            update_metadata(fp)
           
            # Display file info and metadata in preview panel
            display_file_preview_with_metadata(fp, data)
           
            log(f"Opened file: {fp}", "INFO")

        except Exception as e:
            messagebox.showerror("Error", str(e))
            log(str(e), "ERROR")

    # ---------------- NEW: DISPLAY FILE PREVIEW WITH METADATA ----------------
    def display_file_preview_with_metadata(fp, data):
        """
        Display file metadata and content preview in the center preview panel
        """
        clear_panel(preview_panel)
       
        container = tk.Frame(preview_panel, bg="white")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
       
        # Header
        tk.Label(
            container,
            text="File Loaded Successfully",
            font=("Segoe UI", 16, "bold"),
            bg="white",
            fg="#4CAF50"
        ).pack(anchor="w", pady=(0, 10))
       
        # File Info Section
        info_frame = tk.Frame(container, bg="#f0f8ff", relief=tk.RIDGE, bd=1)
        info_frame.pack(fill=tk.X, pady=(0, 20))
       
        def add_info(label, value, frame):
            row = tk.Frame(frame, bg="#f0f8ff")
            row.pack(fill=tk.X, padx=15, pady=5)
            tk.Label(
                row,
                text=f"{label}:",
                font=("Segoe UI", 10, "bold"),
                bg="#f0f8ff",
                width=20,
                anchor="w"
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=value,
                font=("Segoe UI", 10),
                bg="#f0f8ff",
                anchor="w"
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
       
        tk.Label(
            info_frame,
            text="📄 File Information",
            font=("Segoe UI", 12, "bold"),
            bg="#f0f8ff",
            fg="#0066cc"
        ).pack(anchor="w", padx=15, pady=(10, 10))
       
        add_info("Filename", os.path.basename(fp), info_frame)
        add_info("Size", f"{os.path.getsize(fp):,} bytes", info_frame)
        add_info("Extension", os.path.splitext(fp)[1], info_frame)
        add_info("Location", os.path.dirname(fp), info_frame)
       
        tk.Frame(info_frame, height=5, bg="#f0f8ff").pack()
       
        # Header Metadata Section (if available)
        header_meta = getattr(main_app, "homepage_header_metadata", {}) or {}
        if header_meta:
            meta_frame = tk.Frame(container, bg="#fff8e1", relief=tk.RIDGE, bd=1)
            meta_frame.pack(fill=tk.X, pady=(0, 20))
           
            tk.Label(
                meta_frame,
                text="📊 SFRA Header Metadata",
                font=("Segoe UI", 12, "bold"),
                bg="#fff8e1",
                fg="#e65100"
            ).pack(anchor="w", padx=15, pady=(10, 10))
           
            for key, value in header_meta.items():
                add_info(key, value or "N/A", meta_frame)
           
            tk.Frame(meta_frame, height=5, bg="#fff8e1").pack()
       
        # Library Configuration Section
        lib_frame = tk.Frame(container, bg="#e8f5e9", relief=tk.RIDGE, bd=1)
        lib_frame.pack(fill=tk.X, pady=(0, 20))
       
        tk.Label(
            lib_frame,
            text="⚙️ Current Library Configuration",
            font=("Segoe UI", 12, "bold"),
            bg="#e8f5e9",
            fg="#2e7d32"
        ).pack(anchor="w", padx=15, pady=(10, 10))
       
        add_info("Transformer", main_app.selected_transformer.get(), lib_frame)
        add_info("Winding", main_app.selected_winding.get(), lib_frame)
        add_info("Manufacturer", main_app.selected_manufacturer.get(), lib_frame)
        add_info("Serial Number", main_app.serial_number.get(), lib_frame)
        add_info("Year", main_app.year_of_manufacturing.get(), lib_frame)
        add_info("Voltage Rating", f"{main_app.voltage_rating.get()} kV", lib_frame)
       
        tk.Frame(lib_frame, height=5, bg="#e8f5e9").pack()
       
        # Separator
        tk.Frame(container, height=2, bg="#e0e0e0").pack(fill=tk.X, pady=15)
       
        # File Content Preview
        tk.Label(
            container,
            text="📝 File Content Preview (First 500 characters)",
            font=("Segoe UI", 11, "bold"),
            bg="white"
        ).pack(anchor="w", pady=(0, 10))
       
        preview_text = tk.Text(
            container,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#fafafa",
            relief=tk.SUNKEN,
            bd=1,
            height=15
        )
        preview_text.pack(fill=tk.BOTH, expand=True)
       
        # Insert truncated content
        preview_content = data[:500] if len(data) > 500 else data
        if len(data) > 500:
            preview_content += "\n\n... (content truncated) ..."
       
        preview_text.insert(tk.END, preview_content)
        preview_text.config(state=tk.DISABLED)
       
        # Action Buttons
        button_frame = tk.Frame(container, bg="white")
        button_frame.pack(fill=tk.X, pady=(15, 0))
       
        def create_action_button(text, command, bg_color):
            btn = tk.Button(
                button_frame,
                text=text,
                font=("Segoe UI", 10, "bold"),
                bg=bg_color,
                fg="white",
                relief=tk.FLAT,
                padx=20,
                pady=8,
                cursor="hand2",
                command=command
            )
            btn.pack(side=tk.LEFT, padx=(0, 10))
            return btn
    # ---------------- METADATA PANEL ----------------
    def update_metadata(fp):
        clear_panel(metadata_panel)
        if not fp:
            tk.Label(metadata_panel, text="No file selected").pack()
            return

        def add(name, val):
            tk.Label(metadata_panel, text=name, font=("Segoe UI", 9, "bold"), bg="#fafafa").pack(anchor="w", padx=10)
            tk.Label(metadata_panel, text=val, bg="#fafafa", fg="#555").pack(anchor="w", padx=20, pady=(0, 5))

        add("Filename", os.path.basename(fp))
        add("Size", f"{os.path.getsize(fp)} bytes")
        add("Location", os.path.dirname(fp))

        header_meta = getattr(main_app, "homepage_header_metadata", {}) or {}
        if header_meta:
            tk.Label(metadata_panel, text="SFRA Header Metadata", font=("Segoe UI", 10, "bold"), bg="#fafafa", fg="#333").pack(anchor="w", padx=10, pady=(10, 5))
            for k, v in header_meta.items():
                add(k, v)

    # ---------------- LIBRARY (INLINE TREE) ----------------
    def toggle_library():
        main_app.library_expanded = not main_app.library_expanded
        if main_app.library_expanded:
            create_library_section()
        else:
            if main_app.library_frame:
                main_app.library_frame.destroy()
                main_app.library_frame = None
                main_app.tree_expanded = False
                update_preview("Welcome! Use the menu to get started.")

    def toggle_tree():
        main_app.tree_expanded = not main_app.tree_expanded
        if main_app.tree_expanded:
            main_app.tree_toggle_label.config(text="➖ Transformers")
            main_app.transformer_options_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        else:
            main_app.tree_toggle_label.config(text="➕ Transformers")
            main_app.transformer_options_frame.pack_forget()

    def on_transformer_select():
        transformer = main_app.selected_transformer.get()
        if not transformer:
            return

        log(f"Transformer selected: {transformer}", "INFO")

        try:
            base_name = (
                transformer.replace(" kV", "")
                           .replace(" MVA", "")
                           .replace("/", "_")
                           .replace(" for ", "_")
            )

            model_name = f"BHEL_{base_name}_ICT_II"

            project_root = os.path.dirname(os.path.abspath(__file__))
            models_dir = os.path.join(project_root, "models")

            model_path  = os.path.join(models_dir, f"{model_name}_model.pkl")
            config_path = os.path.join(models_dir, f"{model_name}_baseline.json")

            if os.path.exists(model_path):
                with open(model_path, "rb") as f:
                    main_app.loaded_ml_model = pickle.load(f)
                log(f"✓ ML Model loaded: {os.path.basename(model_path)}", "SUCCESS")
            else:
                main_app.loaded_ml_model = None
                log(f"⚠ Model not found: {model_path}", "WARNING")

            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    main_app.loaded_model_config = json.load(f)
                log(f"✓ Config loaded: {os.path.basename(config_path)}", "SUCCESS")
            else:
                main_app.loaded_model_config = None
                log(f"⚠ Config not found: {config_path}", "WARNING")

            main_app.current_transformer_model = {
                "transformer": transformer,
                "model_name": model_name,
                "model": main_app.loaded_ml_model,
                "config": main_app.loaded_model_config,
                "model_path": model_path if os.path.exists(model_path) else None,
                "config_path": config_path if os.path.exists(config_path) else None,
            }

            csv_baseline_path = os.path.join(models_dir, f"{model_name}_baseline.csv")

            if os.path.exists(csv_baseline_path):
                main_app.current_baseline_csv = csv_baseline_path
                log(f"✓ Baseline CSV loaded: {csv_baseline_path}", "SUCCESS")
            else:
                main_app.current_baseline_csv = None
                log("❌ No baseline CSV found for this transformer.", "ERROR")

            if main_app.loaded_ml_model and main_app.loaded_model_config:
                log(f"🎯 Transformer '{transformer}' ready with ML model", "SUCCESS")
            elif main_app.loaded_ml_model or main_app.loaded_model_config:
                log(f"⚠ Partial load for '{transformer}' - check models folder", "WARNING")
            else:
                log(f"❌ No ML resources found for '{transformer}'", "ERROR")

        except Exception as e:
            log(f"❌ Error loading model/config: {str(e)}", "ERROR")
            main_app.loaded_ml_model = None
            main_app.loaded_model_config = None
            main_app.current_transformer_model = None
            main_app.current_baseline_csv = None

        update_preview_with_widgets()


    def on_set_button():
        transformer = main_app.selected_transformer.get()
        winding = main_app.selected_winding.get()
        manufacturer = main_app.selected_manufacturer.get()
        serial = main_app.serial_number.get()
        year = main_app.year_of_manufacturing.get()
        voltage = main_app.voltage_rating.get()
       
        if not transformer:
            messagebox.showwarning("No Selection", "Please select a transformer first.")
            return
       
        if not manufacturer or not serial or not year or not voltage:
            messagebox.showwarning("Missing Details", "Please fill all required fields:\n• Manufacturer\n• Serial Number\n• Year of Manufacturing\n• Voltage Rating")
            return
           
        update_preview(
            f"✔ Library Configuration Set!\n\n"
            f"Transformer: {transformer}\n"
            f"Winding: {winding}\n"
            f"Manufacturer: {manufacturer}\n"
            f"Serial Number: {serial}\n"
            f"Year: {year}\n"
            f"Voltage Rating: {voltage} kV\n\n"
            "Configuration saved successfully."
        )
        log(f"Library set: {transformer} - {winding} - {manufacturer}", "SUCCESS")
        messagebox.showinfo("Success", f"Configuration set:\n\n{transformer}\nWinding: {winding}\nManufacturer: {manufacturer}\nSerial: {serial}\nYear: {year}\nVoltage: {voltage} kV")

    def create_library_section():
        if main_app.library_frame:
            main_app.library_frame.destroy()

        main_app.library_frame = tk.Frame(workspace_frame, bg="#f5f5f5")
        main_app.library_frame.pack(fill=tk.X, padx=15, pady=10)

        # Tree header (expandable/collapsible)
        tree_header_frame = tk.Frame(main_app.library_frame, bg="#f5f5f5")
        tree_header_frame.pack(fill=tk.X, pady=(0, 5))

        main_app.tree_toggle_label = tk.Label(tree_header_frame, text="➕ Transformers", font=("Segoe UI", 10, "bold"), bg="#f5f5f5", cursor="hand2", fg="#0066cc")
        main_app.tree_toggle_label.pack(anchor="w", padx=5)
        main_app.tree_toggle_label.bind("<Button-1>", lambda e: toggle_tree())
        main_app.tree_toggle_label.bind("<Enter>", lambda e: main_app.tree_toggle_label.config(fg="#0052a3"))
        main_app.tree_toggle_label.bind("<Leave>", lambda e: main_app.tree_toggle_label.config(fg="#0066cc"))

        main_app.transformer_options_frame = tk.Frame(main_app.library_frame, bg="#f5f5f5")

        transformers = [
            "400/220 kV for 315 MVA"
        ]

        for transformer in transformers:
            rb = tk.Radiobutton(
                main_app.transformer_options_frame,
                text=transformer,
                variable=main_app.selected_transformer,
                value=transformer,
                font=("Segoe UI", 10),
                bg="#f5f5f5",
                command=on_transformer_select,
                cursor="hand2"
            )
            rb.pack(anchor="w", padx=30, pady=3)

    # ---------------- PREVIEW WIDGETS (WITH NEW FIELDS) ----------------
    def update_preview_with_widgets():
        clear_panel(preview_panel)

        container = tk.Frame(preview_panel, bg="white")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        transformer = main_app.selected_transformer.get()

        if not transformer:
            tk.Label(container, text="Please select a transformer from the library.", font=("Segoe UI", 11), bg="white", fg="#666").pack(pady=50)
            return

        tk.Label(container, text="Configure Library Settings", font=("Segoe UI", 14, "bold"), bg="white").pack(anchor="w", pady=(0, 20))
        tk.Label(container, text="Selected Transformer:", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w", pady=(0, 5))
        tk.Label(container, text=transformer, font=("Segoe UI", 11), bg="white", fg="#0066cc").pack(anchor="w", pady=(0, 20))

        separator = tk.Frame(container, height=2, bg="#e0e0e0")
        separator.pack(fill=tk.X, pady=15)

        # Winding Type
        tk.Label(container, text="Winding Type:", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w", pady=(10, 10))
        winding_frame = tk.Frame(container, bg="white")
        winding_frame.pack(anchor="w", pady=(0, 20))
        winding_dropdown = ttk.Combobox(
            winding_frame,
            textvariable=main_app.selected_winding,
            values=["HV", "LV"],
            state="readonly",
            width=20,
            font=("Segoe UI", 11)
        )
        winding_dropdown.pack(side=tk.LEFT)

        separator2 = tk.Frame(container, height=2, bg="#e0e0e0")
        separator2.pack(fill=tk.X, pady=15)

        # NEW FIELD: Manufacturer
        tk.Label(container, text="Manufacturer: *", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w", pady=(10, 10))
        manufacturer_frame = tk.Frame(container, bg="white")
        manufacturer_frame.pack(anchor="w", pady=(0, 20))
        manufacturer_dropdown = ttk.Combobox(
            manufacturer_frame,
            textvariable=main_app.selected_manufacturer,
            values=["ABB", "Siemens", "GE", "CG Power", "Toshiba", "Hyundai", "BHEL", "Hitachi", "Other"],
            state="readonly",
            width=20,
            font=("Segoe UI", 11)
        )
        manufacturer_dropdown.pack(side=tk.LEFT)

        # NEW FIELD: Serial Number
        tk.Label(container, text="Serial Number: *", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w", pady=(10, 10))
        serial_entry = tk.Entry(container, textvariable=main_app.serial_number, font=("Segoe UI", 11), width=25)
        serial_entry.pack(anchor="w", pady=(0, 20))

        # NEW FIELD: Year of Manufacturing
        tk.Label(container, text="Year of Manufacturing (YYYY): *", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w", pady=(10, 10))
        year_entry = tk.Entry(container, textvariable=main_app.year_of_manufacturing, font=("Segoe UI", 11), width=25)
        year_entry.pack(anchor="w", pady=(0, 20))

        # NEW FIELD: Voltage Rating
        tk.Label(container, text="Voltage Rating (kV): *", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w", pady=(10, 10))
        voltage_entry = tk.Entry(container, textvariable=main_app.voltage_rating, font=("Segoe UI", 11), width=25)
        voltage_entry.pack(anchor="w", pady=(0, 20))

        separator3 = tk.Frame(container, height=2, bg="#e0e0e0")
        separator3.pack(fill=tk.X, pady=15)

        set_btn = tk.Button(
            container,
            text="Set Configuration",
            font=("Segoe UI", 11, "bold"),
            bg="#4CAF50",
            fg="white",
            relief=tk.FLAT,
            padx=30,
            pady=12,
            cursor="hand2",
            command=on_set_button
        )
        set_btn.pack(anchor="w", pady=10)
        set_btn.bind("<Enter>", lambda e: set_btn.config(bg="#45a049"))
        set_btn.bind("<Leave>", lambda e: set_btn.config(bg="#4CAF50"))

        tk.Label(container, text="* Required fields - Fill all before opening files", font=("Segoe UI", 9), bg="white", fg="#d32f2f").pack(anchor="w", pady=(20, 0))

    # ---------------- CONVERT FOR ANALYSIS ----------------
    # ------------- INSERTED ML PIPELINE FUNCTION PLACED ABOVE -------------
    def run_ml_pipeline(freq, mag, metadata, taps):
        """
        Uses the ML model + baseline that were loaded when the transformer
        was selected in the Library.

        Fixes the issue where the pipeline was ALWAYS using
        BHEL_400_220_315_ICT_II model regardless of selection.
        """

        # --------------------------------------------------------------
        # VERIFY SELECTED TRANSFORMER MODEL
        # --------------------------------------------------------------
        if not main_app.current_transformer_model:
            print("❌ No transformer model loaded. Select transformer first.")
            return {
                "baseline_freq": None,
                "baseline_mag": None,
                "baseline_label": None,
                "diagnosis": None,
                "graph_bundle": None
            }

        model_info = main_app.current_transformer_model

        model_path  = model_info.get("model_path")
        json_path   = model_info.get("config_path")

        # CSV fallback: convert "_model.pkl" → ".csv"
        csv_path = None
        if model_path and model_path.endswith("_model.pkl"):
            csv_path = model_path.replace("_model.pkl", ".csv")

        ml_output = {
            "baseline_freq": None,
            "baseline_mag": None,
            "baseline_label": None,
            "diagnosis": None,
            "graph_bundle": None,
        }

        # --------------------------------------------------------------
        # 1) LOAD ML MODEL (pickle)
        # --------------------------------------------------------------
        model = None
        if model_path and os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    model = pickle.load(f)
                print(f"✓ Loaded Model: {os.path.basename(model_path)}")
            except Exception as e:
                print("❌ ML model load failed:", e)
        else:
            print(f"⚠ Model file missing: {model_path}")

        # --------------------------------------------------------------
        # 2) LOAD BASELINE (JSON → CSV fallback)
        # --------------------------------------------------------------
        baseline_freq = None
        baseline_mag  = None

        

        csv_path = main_app.current_baseline_csv   # <-- USE CSV SELECTED IN on_transformer_select()

        if csv_path and os.path.exists(csv_path):
            try:
                from analyse_graph2 import load_baseline_csv
                baseline_freq, baseline_mag = load_baseline_csv(csv_path)
                ml_output["baseline_label"] = "Baseline CSV"
                print(f"✓ Baseline CSV Loaded: {os.path.basename(csv_path)}")
            except Exception as e:
                print(f"❌ Failed to load baseline CSV: {e}")
                return ml_output
        else:
            print("❌ No baseline CSV found for selected transformer!")
            return ml_output

        # --------------------------------------------------------------
        # 3) ALIGN FOR GRAPH TOOLS
        # --------------------------------------------------------------
        try:
            from analyse_graph2 import align_and_interpolate
            common_f, mag_base_aligned, mag_meas_aligned = align_and_interpolate(
            baseline_freq, baseline_mag, freq, mag, n_points=1000
            )

            ml_output["graph_bundle"] = {
                "freq": common_f.tolist(),
                "mag_base": mag_base_aligned.tolist(),
                "mag_meas": mag_meas_aligned.tolist()
            }

        except Exception as e:
            print("Alignment failed:", e)

        # --------------------------------------------------------------
        # 4) SAVE BASELINE FOR GUI
        # --------------------------------------------------------------
        ml_output["baseline_freq"] = baseline_freq.tolist()
        ml_output["baseline_mag"]  = baseline_mag.tolist()

        main_app.pipeline_data["baseline_freq"] = baseline_freq.tolist()
        main_app.pipeline_data["baseline_mag"]  = baseline_mag.tolist()
        main_app.pipeline_data["baseline_label"] = ml_output.get("baseline_label")

        # --------------------------------------------------------------
        # 5) DIAGNOSIS
        # --------------------------------------------------------------
        

    def convert_for_analysis():
        """
        Conversion pipeline with auto-export
        """
        if not main_app.homepage_current_file:
            messagebox.showwarning("No File", "Please open a file first.")
            return

        fp = main_app.homepage_current_file
        ext = os.path.splitext(fp)[1].lower()

        try:
            freq = []
            mag = []
            metadata = {}
            taps = []

            # CSV path
            if ext == ".csv":
                try:
                    if is_binary_file(fp):
                        raise ValueError("CSV appears binary; attempting fallback parser.")
                    freq, mag = robust_universal_csv_loader(fp)
                except Exception:
                    freq, mag, metadata, taps = parse_any_format(main_app.homepage_file_data)

            # SFRA
            elif ext == ".sfra":
                if is_binary_file(fp):
                    freq, mag = load_sfra_binary(fp)
                else:
                    freq, mag, metadata, taps = parse_any_format(main_app.homepage_file_data)

            # PFRA test variants
            elif ext in [".pfratest", ".pfra", ".fra"]:
                if is_binary_file(fp):
                    freq, mag = load_pfratest_binary(fp)
                else:
                    freq, mag, metadata, taps = parse_any_format(main_app.homepage_file_data)

            # BAK
            elif ext == ".bak":
                if is_binary_file(fp):
                    freq, mag = load_bak_binary(fp)
                else:
                    freq, mag, metadata, taps = parse_any_format(main_app.homepage_file_data)

            # OTHER
            else:
                try:
                    freq, mag, metadata, taps = parse_any_format(main_app.homepage_file_data)
                except Exception:
                    freq, mag = robust_universal_csv_loader(fp)

            # finalize arrays
            freq = np.array(freq, dtype=float).reshape(-1)
            mag = np.array(mag, dtype=float).reshape(-1)

            if len(freq) != len(mag):
                raise ValueError(f"SFRA data mismatch:\nfreq points = {len(freq)}\nmag points  = {len(mag)}\n\nMalformed SFRA data detected. Ensure a clean FRA file.")

            # top-10 points
            top10_points = []
            try:
                if len(freq) > 0:
                    idx = np.argsort(mag)[::-1][:10]
                    for rank, i in enumerate(idx, start=1):
                        top10_points.append({"rank": int(rank), "index": int(i), "freq": float(freq[i]), "mag": float(mag[i])})
            except:
                top10_points = []

            # save pipeline data for ML
            main_app.pipeline_data = {"freq": freq, "mag": mag, "metadata": metadata, "taps": taps}

            # ---------- ML PIPELINE CALL ADDED ----------
            try:
                ml_out = run_ml_pipeline(freq, mag, metadata, taps)
                main_app.pipeline_data["ml_output"] = ml_out
                log("ML pipeline executed.", "SUCCESS")
            except Exception as ex:
                main_app.pipeline_data["ml_output"] = {}
                log(f"ML pipeline failed: {ex}", "ERROR")
            # --------------------------------------------

            # auto-export unified CSV
            try:
                out_csv = export_unified_csv(freq, mag, fp)
                log(f"Unified CSV exported: {out_csv}", "SUCCESS")
                export_msg = f"\nUnified CSV exported:\n{out_csv}"
            except Exception as ex:
                export_msg = f"\nExport failed: {ex}"
                log(export_msg, "ERROR")

            # update preview
            update_preview(
                "✔ Conversion Successful!\n\n"
                f"Points Detected: {len(freq)}\n"
                f"Metadata Extracted: {len([v for v in metadata.values() if v])}\n"
                f"Taps Detected: {len(taps)}\n"
                f"{export_msg}\n\n"
                "ML-ready pipeline generated."
            )
            log("Pipeline generated!", "SUCCESS")

        except Exception as e:
            messagebox.showerror("Conversion Error", str(e))
            log(str(e), "ERROR")

    # ---------------- HOMEPAGE UI ----------------
    def create_homepage_ui():
        clear_panel(workspace_frame)
        clear_panel(preview_panel)
        clear_panel(metadata_panel)

        tk.Label(workspace_frame, text="Homepage", font=("Segoe UI", 14, "bold"), bg="#f5f5f5").pack(anchor="w", padx=15, pady=(15, 20))

        operations = [
            ("1. Library", toggle_library),
            ("2. Open File", open_file),
            ("3. Save", save_file),
            ("4. Save As", save_as_file),
            ("5. Convert for Analysis", convert_for_analysis)
        ]

        for text, cmd in operations:
            lbl = tk.Label(workspace_frame, text=text, font=("Segoe UI", 11), bg="#f5f5f5", anchor="w", padx=15, pady=8, cursor="hand2")
            lbl.pack(fill=tk.X)
            lbl.bind("<Button-1>", lambda e, f=cmd: f())
            lbl.bind("<Enter>", lambda e, L=lbl: L.config(bg="#e8e8e8"))
            lbl.bind("<Leave>", lambda e, L=lbl: L.config(bg="#f5f5f5"))

        update_preview("Welcome! Use the menu to get started.")
        update_metadata(None)

    # ---------------- MONKEY PATCH ----------------
    original_handler = main_app.on_container_click

    def patched(name):
        if name == "Homepage":
            create_homepage_ui()
        else:
            original_handler(name)

    main_app.on_container_click = patched

# End of Homepage.py 