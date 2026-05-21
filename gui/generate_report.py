# generate_report.py  -- FULL (merged & cleaned)
"""
Generate Report module - defensive & refreshed-only metadata
- Integrates with Main_page.py frames:
    * app.workspace_scrollable
    * app.center_content_frame
    * app.metadata_content
- Metadata is built on load and ONLY rebuilt when user clicks "Refresh Metadata".
- No automatic rebuilds on typing, focusout, signature upload, calc, or JSON load/save.
- Added: per-section PDF generation + full PDF generation (ReportLab)
- Patched to load data from main_app.pipeline_data, to merge Homepage CSV header metadata,
  and autofill fields using a robust dotted-key StringVar registry.
- Mapping from CSV/header metadata to report fields is applied here (no Homepage.py changes).
"""
import os
import json
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
import uuid
import platform
import subprocess


# optional PIL usage
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

# ReportLab for PDF generation (install via pip if missing)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.units import mm
except Exception:
    canvas = None
    A4 = None
    ImageReader = None
    mm = None

# ---------- CONFIG ----------
# ---------- CONFIG ----------
LOGO_PATH = os.path.join("assets", "vidhyut_logo.png")

# ⚠️ LEGACY graph path – sirf fallback ke liye
GRAPH_PATH = os.path.join("output", "analysis_graph.png")

JSON_DEFAULT = os.path.join("output", "diagnostic_output.json")
PDF_OUTPUT_DIR = os.path.join("output")
PDF_FULL_FILENAME = os.path.join(PDF_OUTPUT_DIR, "vidhyut_full_transformer_report.pdf")

os.makedirs("output", exist_ok=True)
os.makedirs("assets", exist_ok=True)

# Report side ke liye pipeline_data["graph_images"] keys
GRAPH_KEYS_ORDER = [
    "modal_spectrum_bands",
    "baseline_vs_current",
    "peak_activation",
    "delta_damage_locator",
    "fault_severity",
    "midband_turbulence",
]



# ---------- SAFE JSON LOAD ----------
def safe_load_json(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ---------- ATTACH MODULE ----------
def _inject_frames(app):
    """Ensure required frames exist on app (create hidden fallbacks)."""
    if not hasattr(app, "workspace_scrollable"):
        tmp = tk.Frame(app.root, bg="#f5f5f5")
        tmp.pack_forget()
        app.workspace_scrollable = tmp

    if not hasattr(app, "center_content_frame"):
        if hasattr(app, "center_scrollable"):
            app.center_content_frame = app.center_scrollable
        else:
            tmp = tk.Frame(app.root, bg="white")
            tmp.pack_forget()
            app.center_content_frame = tmp

    if not hasattr(app, "metadata_content"):
        tmp = tk.Frame(app.root, bg="#fafafa")
        tmp.pack_forget()
        app.metadata_content = tmp


def attach_generate_report(app):
    """Patch app.on_container_click so toolbar 'Generate Report' opens UI."""
    if not hasattr(app, "_original_on_container_click"):
        app._original_on_container_click = getattr(app, "on_container_click", None)

    def patched(name):
        # debug log
        try:
            if hasattr(app, "log_console"):
                app.log_console(f"Toolbar action (patched): {name}", "INFO")
        except Exception:
            pass

        if name == "Generate Report":
            try:
                controller = getattr(app, "_gr_controller", None)
                if controller is None:
                    controller = GRController(app)
                    app._gr_controller = controller
                # Ensure controller loads latest pipeline data and shows UI
                try:
                    controller.load_from_pipeline()
                except Exception:
                    # safe: if load_from_pipeline fails, continue to show UI (will be empty/default)
                    pass
                controller.load_ui()
            except Exception as e:
                try:
                    messagebox.showerror("Generate Report error", str(e))
                except Exception:
                    pass
                if hasattr(app, "log_console"):
                    app.log_console(f"Generate Report error: {e}", "ERROR")
            return

        # delegate
        orig = getattr(app, "_original_on_container_click", None)
        if callable(orig):
            try:
                return orig(name)
            except Exception as e:
                if hasattr(app, "log_console"):
                    app.log_console(f"Error in original on_container_click: {e}", "ERROR")
        return None

    app.on_container_click = patched


def enable(app_instance):
    _inject_frames(app_instance)
    attach_generate_report(app_instance)


# --------------------------------------
#             CONTROLLER
# --------------------------------------
class GRController:
    def __init__(self, app):
        self.app = app
        self.json_data = safe_load_json(JSON_DEFAULT)
    
        # canonical model
        self.model = {}

        # merge default JSON if present (keep for backward compatibility)
        try:
            if isinstance(self.json_data, dict) and self.json_data:
                self._merge_json(self.json_data)
        except Exception:
            pass

        # frame refs
        self.left_frame = None
        self.center_frame_inner = None
        self.right_frame = None

        # dotted key -> StringVar
        self.field_vars = {}

        # internal metadata scroll widgets
        self._meta_canvas = None
        self._meta_inner = None
        self._meta_vbar = None

        # preview labels placeholders
        self._sig_preview_label = None
        self._auth_sig_label = None

        # menu labels (for left panel)
        self._menu_labels = []
        self._menu_selected_index = None

        # keep track of generated test report numbers
        self._last_report_no = None


    # -------------------------
    # Graph image resolver (pipeline_data["graph_images"])
    # -------------------------
    def _resolve_graph_image(self, preferred_key: str = "modal_spectrum_bands"):
        """
        pipeline_data["graph_images"] se koi graph PNG pick karta hai.

        Priority:
          1) preferred_key (default: 'modal_spectrum_bands')
          2) GRAPH_KEYS_ORDER me jo pehle mil jaye
          3) legacy GRAPH_PATH agar file exist karti ho
          4) None
        """
        try:
            pdata = getattr(self.app, "pipeline_data", {}) or {}
            gdict = pdata.get("graph_images") or {}
        except Exception:
            gdict = {}

        if isinstance(gdict, dict) and gdict:
            # 1) Preferred
            if preferred_key:
                p = gdict.get(preferred_key)
                if isinstance(p, str) and os.path.exists(p):
                    return p

            # 2) Baki keys order wise
            for key in GRAPH_KEYS_ORDER:
                if key == preferred_key:
                    continue
                p = gdict.get(key)
                if isinstance(p, str) and os.path.exists(p):
                    return p

        # 3) Legacy fallback
        if os.path.exists(GRAPH_PATH):
            return GRAPH_PATH

        return None


    def _ensure_list(self, x):
      if isinstance(x, list):
        return x
      if isinstance(x, str):
        try:
            return json.loads(x)
        except:
            return []
      return []

    # -------------------------
    # JSON merging helpers
    # -------------------------
    def _merge_json(self, js):
        if not js:
            return
        meta = js.get("meta") or js.get("metadata") or {}
        for k in ("serial_number", "manufacturer", "year", "start_frequency", "stop_frequency", "red_lead", "black_lead"):
            if k in meta:
                self.model.setdefault("meta", {})[k] = str(meta[k])
        if "customer" in js:
            self.model["customer"] = js.get("customer", "")
        if "po_number" in js or "poNumber" in js:
            self.model["po_number"] = js.get("po_number") or js.get("poNumber") or self.model.get("po_number", "")
        if "curve_stats" in js:
            self.model.setdefault("curve_stats", {}).update(js.get("curve_stats", {}))
        if "features_used" in js:
            self.model.setdefault("features_used", {}).update(js.get("features_used", {}))
            for k in ("min_mag", "max_mag", "phase_mean", "points"):
                if k in self.model.get("features_used", {}) and k not in self.model.get("curve_stats", {}):
                    self.model.setdefault("curve_stats", {})[k] = self.model["features_used"][k]
        if "transformer_performance" in js:
            self.model.setdefault("transformer_performance", {}).update(js.get("transformer_performance", {}))
        if "tested_by" in js:
            self.model.setdefault("tested_by", {}).update(js.get("tested_by", {}))

    # -------------------------
    # Pipeline loader & autofill (NEW)
    # -------------------------
    def load_from_pipeline(self):
        """
        Load data from app.pipeline_data (set by Homepage -> Convert or Analyse module)
        into self.model, then autofill available StringVars.
        Call this before showing UI to auto-populate fields.
        This function now also merges Homepage CSV header metadata (main_app.homepage_header_metadata)
        into the model so all CSV header keys are available and mapped into UI fields.
        """
        pdata = getattr(self.app, "pipeline_data", {}) or {}
        
        # SFRA arrays
        if "freq" in pdata:
         self.model["freq"] = self._ensure_list(pdata.get("freq"))

        if "mag" in pdata:
         self.model["mag"] = self._ensure_list(pdata.get("mag"))

        if "phase" in pdata:
         self.model["phase"] = self._ensure_list(pdata.get("phase"))


        # pipeline metadata (may be empty)
        pipeline_meta = pdata.get("metadata", {}) or {}
        graphs = pdata.get("graph_images") or {}
        if isinstance(graphs, dict):
            self.model["graph_images"] = graphs

        top10 = pdata.get("top10_points") or []
        if isinstance(top10, list):
            self.model["top10_points"] = top10

        # ---------- MERGE CSV/HEADER METADATA FROM HOMEPAGE ----------
        csv_meta = getattr(self.app, "homepage_header_metadata", {}) or {}

        combined_meta = {}
        combined_meta.update(csv_meta)          # all CSV/header keys first
        combined_meta.update(pipeline_meta)     # then pipeline (ML) metadata overrides if present
        self.model["metadata"] = combined_meta

        # Direct mapping from CSV/header keys to report model expected keys:
        customer_val = combined_meta.get("Company") or combined_meta.get("Manufacturer") or combined_meta.get("company") or combined_meta.get("manufacturer")
        if customer_val:
            self.model["customer"] = str(customer_val)

        po_val = combined_meta.get("BayID") or combined_meta.get("BayId") or combined_meta.get("bayid")
        if po_val:
            self.model["po_number"] = str(po_val)

        serial = combined_meta.get("SerialNumber") or combined_meta.get("serialnumber") or combined_meta.get("Serial") or combined_meta.get("serial")
        if serial:
            self.model.setdefault("meta", {})["serial_number"] = str(serial)

        manu = combined_meta.get("Manufacturer") or combined_meta.get("manufacturer")
        if manu:
            self.model.setdefault("meta", {})["manufacturer"] = str(manu)

        year = combined_meta.get("ManufactureYear") or combined_meta.get("manufactureyear") or combined_meta.get("Year") or combined_meta.get("year")
        if year:
            self.model.setdefault("meta", {})["year"] = str(year)

        rating = combined_meta.get("MVA_Max") or combined_meta.get("MVA_MAX") or combined_meta.get("Mva_Max")
        if rating:
            self.model["rating"] = str(rating)

        phase = combined_meta.get("PhaseCount") or combined_meta.get("Phase") or combined_meta.get("phasecount")
        if phase:
            self.model["phase"] = str(phase)

        freq_val = combined_meta.get("StartFrequency") or combined_meta.get("StartFreq") or combined_meta.get("Start_Frequency")
        if freq_val:
            self.model["frequency"] = str(freq_val)

        connection = combined_meta.get("WindingCount") or combined_meta.get("Winding_Count")
        if connection:
            self.model["connection"] = str(connection)

        hv = combined_meta.get("HV")
        if hv:
            self.model.setdefault("meta", {})["rated_voltage_hv"] = str(hv)

        lv1 = combined_meta.get("LV1") or combined_meta.get("LV_1") or combined_meta.get("LV")
        if lv1:
            self.model.setdefault("meta", {})["rated_voltage_lv"] = str(lv1)

        oltc = combined_meta.get("LTCPosition") or combined_meta.get("LTC_Position") or combined_meta.get("LTC")
        if oltc:
            self.model.setdefault("meta", {})["oltc"] = str(oltc)

        operator = combined_meta.get("Operator") or combined_meta.get("operator")
        if operator:
            self.model.setdefault("tested_by", {})["name"] = str(operator)

        sf = combined_meta.get("StartFrequency") or combined_meta.get("StartFreq") or combined_meta.get("Start_Frequency")
        if sf:
            try:
                self.model.setdefault("meta", {})["start_frequency"] = str(sf)
            except Exception:
                pass
        stf = combined_meta.get("StopFrequency") or combined_meta.get("StopFreq") or combined_meta.get("Stop_Frequency")
        if stf:
            try:
                self.model.setdefault("meta", {})["stop_frequency"] = str(stf)
            except Exception:
                pass

        # taps: preserve existing pipeline taps if any
        if "taps" in pdata:
            self.model["taps"] = pdata.get("taps", []) or []
        else:
            self.model.setdefault("taps", [])

        # ml report (diagnostic)
        ml_out = pdata.get("ml_output", {}) or {}
        if "report" in ml_out:
            self.model["ml_report"] = ml_out.get("report", {}) or {}
            rep = self.model["ml_report"]
            if isinstance(rep, dict):
                if "metadata" in rep:
                    if "metadata" not in self.model or not self.model["metadata"]:
                        self.model["metadata"] = rep.get("metadata", {}) or {}
                if "features_used" in rep:
                    self.model.setdefault("features_used", {}).update(rep.get("features_used", {}))
                if "curve_stats" in rep:
                    self.model.setdefault("curve_stats", {}).update(rep.get("curve_stats", {}))
                if "loss_and_efficiency" in rep or "losses" in rep:
                    self.model.setdefault("transformer_performance", {})
                    self.model["transformer_performance"].setdefault("loss_estimates", {})
                    los = rep.get("loss_and_efficiency", rep.get("losses", {})) or {}
                    if isinstance(los, dict):
                        if "core_loss_w" in los:
                            self.model["transformer_performance"]["loss_estimates"]["core_loss_watts"] = los.get("core_loss_w")
                        if "load_loss_w" in los:
                            self.model["transformer_performance"]["loss_estimates"]["load_loss_watts"] = los.get("load_loss_w")
                        if "efficiency_unity_pf" in los:
                            self.model["transformer_performance"]["eff_unity"] = los.get("efficiency_unity_pf")
                        if "efficiency_0.8_pf" in los:
                            self.model["transformer_performance"]["eff_08pf"] = los.get("efficiency_0.8_pf")

        # If there is a JSON file previously loaded, merge it but don't overwrite pipeline keys
        if isinstance(self.json_data, dict) and self.json_data:
            jd = dict(self.json_data)
            if "meta" in jd and not self.model.get("meta"):
                self.model["meta"] = jd.get("meta", {})
            if "tested_by" in jd and not self.model.get("tested_by"):
                self.model["tested_by"] = jd.get("tested_by", {})
            if "curve_stats" in jd and not self.model.get("curve_stats"):
                self.model["curve_stats"] = jd.get("curve_stats", {})
            if "features_used" in jd and not self.model.get("features_used"):
                self.model["features_used"] = jd.get("features_used", {})

        # Now autofill any existing UI fields (or prepare field_vars for upcoming UI)
        self.autofill_fields_from_json_model()
         
         
    def autofill_fields_from_json_model(self):
        """
        Create / set StringVars for any flat key present in model so UI widgets
        can bind to them when created. This doesn't rebuild metadata pane.
        """
        flat = self.flatten_dict(self.model)
        for key, val in flat.items():
            try:
                if key not in self.field_vars:
                    # prepare a StringVar so UI creation will bind to it
                    self.field_vars[key] = tk.StringVar(value=str(val) if val is not None else "")
                    self.field_vars[key].trace_add("write", lambda *a, k=key: self._on_var_change(k))
                else:
                    self.field_vars[key].set(str(val) if val is not None else "")
            except Exception:
                pass

    def flatten_dict(self, d, parent=""):
        """
        Flatten nested dictionaries into dotted keys:
        {'meta': {'serial': 'A'}} -> {'meta.serial': 'A'}
        """
        out = {}
        if not isinstance(d, dict):
            return out
        for k, v in d.items():
            name = f"{parent}.{k}" if parent else k
            if isinstance(v, dict):
                out.update(self.flatten_dict(v, name))
            else:
                out[name] = v
        return out

    # -------------------------
    # UI helpers
    # -------------------------
    def clear_frame(self, frame):
        for w in list(frame.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

    def load_ui(self):
        _inject_frames(self.app)

        self.left_frame = self.app.workspace_scrollable
        self.center_frame_inner = getattr(self.app, "center_content_frame", None)
        self.right_frame = getattr(self.app, "metadata_content", None)

        if self.center_frame_inner is None:
            tmp = tk.Frame(self.app.root, bg="white")
            tmp.pack_forget()
            self.center_frame_inner = tmp

        if self.right_frame is None:
            tmp = tk.Frame(self.app.root, bg="#fafafa")
            tmp.pack_forget()
            self.right_frame = tmp

        try:
            self._build_left(self.left_frame)
            self.show_section1()
            # build metadata once on load
            self._build_right(self.right_frame)
            # ensure model fields are synced (if field_vars exist they'll be used)
            self.sync_model_to_fields()
            if hasattr(self.app, "log_console"):
                self.app.log_console("Generate Report UI loaded.", "SUCCESS")
        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Generate Report load_ui error: {e}", "ERROR")

    # Alias for external callers expecting show()
    def show(self):
        return self.load_ui()

    # -------------------------
    # LEFT pane
    # -------------------------
    def _build_left(self, parent):
        try:
            self.clear_frame(parent)
            # small spacer
            tk.Frame(parent, height=8, bg="#f5f5f5").pack(fill="x")

            # header
            gr_header = tk.Frame(parent, bg="#f5f5f5")
            gr_header.pack(fill="x", pady=(6, 2))
            tk.Label(gr_header, text="Generate Report", font=("Segoe UI", 14, "bold"), bg="#f5f5f5", anchor="w", padx=12).pack(fill="x")

            # container for menu items (left column)
            btn_area = tk.Frame(parent, bg="#f5f5f5")
            btn_area.pack(fill="both", expand=True, padx=6, pady=6)

            # menu definitions (text, callback)
            options = [
                ("1. Transformer Test Report", self.show_section1),
                ("2. Measurement of Voltage Ratio", self.show_section2),
                ("3. Graph", self.show_section3),
                ("4. Regulation & Efficiency Calculation", self.show_section4),
                ("5. Transformer Tested Signature", self.show_section5),
            ]

            # create label-based menu
            self._menu_labels = []
            for idx, (text, cmd) in enumerate(options):
                lbl = tk.Label(btn_area, text=text, anchor="w", padx=12, pady=10, bg="#f5f5f5",
                               font=("Segoe UI", 11))
                lbl.pack(fill="x", pady=4)
                lbl._gr_cmd = cmd
                lbl._gr_index = idx
                lbl.bind("<Button-1>", lambda e, l=lbl: self._on_menu_click(l))
                lbl.bind("<Enter>", lambda e, l=lbl: self._on_menu_enter(l))
                lbl.bind("<Leave>", lambda e, l=lbl: self._on_menu_leave(l))
                self._menu_labels.append(lbl)

            # spacer
            tk.Frame(btn_area, height=6, bg="#f5f5f5").pack(fill="x", pady=(4, 4))

            # Add the "Generate Full Report (PDF)" label to match style of left menu
            lbl_full = tk.Label(btn_area, text="📄 Generate Full Report (PDF)", anchor="w", padx=12, pady=10, bg="#f5f5f5", font=("Segoe UI", 11))
            lbl_full.pack(fill="x", pady=6)
            lbl_full._gr_cmd = self.generate_full_pdf_and_preview
            lbl_full._gr_index = len(self._menu_labels)  # last index
            lbl_full.bind("<Button-1>", lambda e, l=lbl_full: self._on_menu_click(l))
            lbl_full.bind("<Enter>", lambda e, l=lbl_full: self._on_menu_enter(l))
            lbl_full.bind("<Leave>", lambda e, l=lbl_full: self._on_menu_leave(l))

            # store it but do not include in selection cycling with other section labels
            self._menu_full_label = lbl_full

            # style variables for selected/hover
            self._menu_hover_bg = "#f0f0f0"
            self._menu_selected_bg = "#e0e0e0"
            self._menu_normal_bg = "#f5f5f5"

            # auto-select first item
            if self._menu_labels:
                self._select_menu_label(self._menu_labels[0])

            parent.update_idletasks()
            if hasattr(self.app, "log_console"):
                self.app.log_console("Generate Report - left panel built (label-menu).", "INFO")
        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Error building left panel: {e}", "ERROR")

    # menu interaction helpers
    def _on_menu_click(self, label_widget):
        try:
            # call assigned command and mark selected
            if hasattr(label_widget, "_gr_cmd") and callable(label_widget._gr_cmd):
                label_widget._gr_cmd()
            if getattr(label_widget, "_gr_index", None) is not None and getattr(label_widget, "_gr_index", None) < len(self._menu_labels):
                self._select_menu_label(label_widget)
            else:
                # if it's full-report label, style it briefly
                try:
                    label_widget.configure(bg=self._menu_selected_bg)
                    self.app.root.after(200, lambda: label_widget.configure(bg=self._menu_normal_bg))
                except Exception:
                    pass
            # log section title if present
            try:
                t = label_widget.cget("text")
                self._log_section(t)
            except Exception:
                pass
        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Menu click handler error: {e}", "ERROR")

    def _on_menu_enter(self, label_widget):
        try:
            idx = getattr(label_widget, "_gr_index", None)
            if idx is None:
                return
            if self._menu_selected_index == idx:
                return
            label_widget.configure(bg=self._menu_hover_bg)
        except Exception:
            pass

    def _on_menu_leave(self, label_widget):
        try:
            idx = getattr(label_widget, "_gr_index", None)
            if idx is None:
                return
            if self._menu_selected_index == idx:
                label_widget.configure(bg=self._menu_selected_bg)
            else:
                label_widget.configure(bg=self._menu_normal_bg)
        except Exception:
            pass

    def _select_menu_label(self, label_widget):
        try:
            for lbl in self._menu_labels:
                lbl_idx = getattr(lbl, "_gr_index", None)
                if lbl is label_widget:
                    lbl.configure(bg=self._menu_selected_bg)
                    self._menu_selected_index = lbl_idx
                else:
                    lbl.configure(bg=self._menu_normal_bg)
        except Exception:
            pass

    # -------------------------
    # CENTER helpers
    # -------------------------
    def _make_label_entry(self, parent, label_text, var_key, default=""):
        frm = tk.Frame(parent, bg="white")
        frm.pack(fill="x", pady=6, padx=12)
        lbl = tk.Label(frm, text=label_text + ":", width=28, anchor="w", bg="white")
        lbl.pack(side="left")
        if var_key not in self.field_vars:
            init = self._get_model_value(var_key) or default
            self.field_vars[var_key] = tk.StringVar(value=str(init))
            self.field_vars[var_key].trace_add("write", lambda *a, k=var_key: self._on_var_change(k))
        ent = ttk.Entry(frm, textvariable=self.field_vars[var_key])
        ent.pack(side="left", fill="x", expand=True)
        return ent

    def _get_model_value(self, dotted):
        parts = dotted.split(".")
        node = self.model
        try:
            for p in parts:
                node = node[p]
            return node
        except Exception:
            return ""

    def _set_model_value(self, dotted, val):
        parts = dotted.split(".")
        node = self.model
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = val

    def _on_var_change(self, dotted):
        """Update model from a field var. Do NOT rebuild metadata here."""
        var = self.field_vars.get(dotted)
        if var is None:
            return
        try:
            self._set_model_value(dotted, var.get())
        except Exception:
            pass

    def _log_section(self, title):
        if hasattr(self.app, "log_console"):
            self.app.log_console(f"{title} opened.", "INFO")

    # -------------------------
    # SECTIONS (center)
    # -------------------------
    def show_section1(self):
        """Transformer Test Report"""
        if self.center_frame_inner is None:
            return
        try:
            self.clear_frame(self.center_frame_inner)
            container = tk.Frame(self.center_frame_inner, bg="white")
            container.pack(fill="both", expand=True, padx=12, pady=8)

            tk.Label(container, text="Transformer Test Report", font=("Segoe UI", 18, "bold"), bg="white").pack(anchor="w", pady=(0, 8))

            grid_frame = tk.Frame(container, bg="white")
            grid_frame.pack(fill="both", expand=True)
            left_col = tk.Frame(grid_frame, bg="white")
            right_col = tk.Frame(grid_frame, bg="white")
            left_col.pack(side="left", fill="both", expand=True, padx=(0, 6))
            right_col.pack(side="left", fill="both", expand=True, padx=(6, 0))

            fields = [
                ("Customer", "customer"),
                ("Customer Reference P.O.No", "po_number"),
                ("Serial No", "meta.serial_number"),
                ("Make", "meta.manufacturer"),
                ("Previously Repaired By", "previously_repaired_by"),
                ("Rating", "rating"),
                ("Cooling", "cooling"),
                ("Phase", "phase"),
                ("Vector Group", "vector_group"),
                ("Frequency", "frequency"),
                ("Connection", "connection"),
                ("Ref. Standard", "ref_standard"),
                ("Rated Voltage HV", "meta.rated_voltage_hv"),
                ("Rated Voltage LV", "meta.rated_voltage_lv"),
                ("Full Load Line Current HV", "full_load_hv"),
                ("Full Load Line Current LV", "full_load_lv"),
                ("OLTC", "meta.oltc"),
                ("Voltage Variation", "voltage_variation"),
            ]

            half = (len(fields) + 1) // 2
            for label_text, key in fields[:half]:
                self._make_label_entry(left_col, label_text, key, default=self._get_model_value(key) or "")
            for label_text, key in fields[half:]:
                self._make_label_entry(right_col, label_text, key, default=self._get_model_value(key) or "")

            # Tested by + signature upload
            sig_frame = tk.Frame(container, bg="white")
            sig_frame.pack(fill="x", pady=10, padx=12)
            tk.Label(sig_frame, text="Tested By (Name):", width=20, anchor="w", bg="white").pack(side="left")
            if "tested_by.name" not in self.field_vars:
                self.field_vars["tested_by.name"] = tk.StringVar(value=self.model.get("tested_by", {}).get("name", ""))
                self.field_vars["tested_by.name"].trace_add("write", lambda *a: self._on_var_change("tested_by.name"))
            ttk.Entry(sig_frame, textvariable=self.field_vars["tested_by.name"]).pack(side="left", fill="x", expand=True, padx=6)
            tk.Label(sig_frame, text="Designation:", width=12, anchor="w", bg="white").pack(side="left", padx=(8, 0))
            if "tested_by.designation" not in self.field_vars:
                self.field_vars["tested_by.designation"] = tk.StringVar(value=self.model.get("tested_by", {}).get("designation", ""))
                self.field_vars["tested_by.designation"].trace_add("write", lambda *a: self._on_var_change("tested_by.designation"))
            ttk.Entry(sig_frame, textvariable=self.field_vars["tested_by.designation"], width=28).pack(side="left", padx=(4, 0))

            def upload_sig():
                p = filedialog.askopenfilename(title="Select signature image", filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
                if not p:
                    return
                # update model but do NOT rebuild metadata automatically
                self._set_model_value("tested_by.signature", p)
                messagebox.showinfo("Signature", "Signature uploaded.")

            ttk.Button(container, text="Upload Digital Signature", command=upload_sig).pack(anchor="w", padx=12, pady=(8, 12))

            # ----- ADD per-section Generate PDF button for Section 1 -----
            btn_area = tk.Frame(container, bg="white")
            btn_area.pack(fill="x", pady=(4, 8), padx=12)
            ttk.Button(btn_area, text="📄 Generate Report (This Section)", command=lambda: self.generate_section_pdf_and_preview(1)).pack(anchor="w")

            self._log_section("Transformer Test Report")
        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Error show_section1: {e}", "ERROR")

    def show_section2(self):
        """Measurement of Voltage Ratio / Frequency Response summary"""
        if self.center_frame_inner is None:
            return

        try:
            self.clear_frame(self.center_frame_inner)

            frame = tk.Frame(self.center_frame_inner, bg="white")
            frame.pack(fill="both", expand=True, padx=12, pady=8)

            tk.Label(
                frame,
                text="Measurement of Voltage Ratio",
                font=("Segoe UI", 16, "bold"),
                bg="white"
            ).pack(anchor="w", pady=(0, 4))

            tk.Label(
                frame,
                text="Top-10 Frequency Response Points (from CSV) + Full SFRA Table",
                font=("Segoe UI", 10),
                bg="white",
                fg="#555555",
            ).pack(anchor="w", pady=(0, 8))

            # ------------ TOP-10 TABLE ------------
            top_frame = tk.Frame(frame, bg="white")
            top_frame.pack(fill="x", pady=(0, 10))

            tk.Label(
                top_frame,
                text="Top-10 Frequency Points (highest magnitude)",
                font=("Segoe UI", 12, "bold"),
                bg="white",
            ).pack(anchor="w", pady=(0, 4))

            cols_top = ("Rank", "Index", "Frequency (Hz)", "Magnitude (dB)")
            top_tree = ttk.Treeview(top_frame, columns=cols_top, show="headings", height=10)
            for c in cols_top:
                top_tree.heading(c, text=c)
                top_tree.column(c, anchor="center", width=140)
            top_tree.pack(fill="x", expand=False)

            top10 = self.model.get("top10_points", []) or []
            if top10:
                for row in top10:
                    top_tree.insert(
                        "",
                        "end",
                        values=(
                            row.get("rank"),
                            row.get("index"),
                            row.get("freq"),
                            row.get("mag"),
                        ),
                    )
            else:
                top_tree.insert("", "end", values=("—", "—", "No top-10 data", "—"))

            # ------------ FULL SFRA TABLE ------------
            tk.Label(
                frame,
                text="Full Frequency Response Data",
                font=("Segoe UI", 12, "bold"),
                bg="white",
            ).pack(anchor="w", pady=(12, 4))

            cols = ("Index", "Frequency (Hz)", "Magnitude (dB)", "Phase (Deg)")
            tree = ttk.Treeview(frame, columns=cols, show="headings", height=14)

            for c in cols:
                tree.heading(c, text=c)
                tree.column(c, width=150, anchor="center")

            tree.pack(fill="both", expand=True)

            freqs = self.model.get("freq", [])
            mags = self.model.get("mag", [])
            phase = self.model.get("phase", [])

            if freqs is not None and len(freqs) > 0:
                for i, f in enumerate(freqs):
                    m = mags[i] if i < len(mags) else ""
                    p = phase[i] if i < len(phase) else ""
                    tree.insert("", "end", values=(i + 1, f, m, p))
            else:
                tree.insert("", "end", values=("No Data", "", "", ""))

            # PDF button (same as pehle)
            btn_area = tk.Frame(frame, bg="white")
            btn_area.pack(fill="x", pady=(8, 12), padx=6)

            ttk.Button(
                btn_area,
                text="📄 Generate Report (This Section)",
                command=lambda: self.generate_section_pdf_and_preview(2)
            ).pack(anchor="w")

            self._log_section("Measurement of Voltage Ratio / Frequency Response")

        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Error show_section2: {e}", "ERROR")

    def show_section3(self):
        """Graph (SFRA + ML diagnostic plots)"""
        if self.center_frame_inner is None:
            return
        try:
            self.clear_frame(self.center_frame_inner)

            frame = tk.Frame(self.center_frame_inner, bg="white")
            frame.pack(fill="both", expand=True, padx=12, pady=8)

            tk.Label(
                frame,
                text="Graph (Sweep Frequency Response)",
                font=("Segoe UI", 16, "bold"),
                bg="white"
            ).pack(anchor="w", pady=(0, 8))

            cs = self.model.get("curve_stats", {}) or {}
            stats_text = (
                f"Min mag: {cs.get('min_mag','n/a')}  "
                f"Max mag: {cs.get('max_mag','n/a')}  "
                f"Phase mean: {cs.get('phase_mean','n/a')}"
            )
            tk.Label(frame, text=stats_text, bg="white").pack(anchor="w", pady=6)

            graphs = self.model.get("graph_images", {}) or {}

            # ----- Agar pipeline graphs mile, sab dikhao -----
            if graphs and Image and ImageTk:
                title_map = {
                    "modal_spectrum_bands": "Modal Frequencies + Spectrum Energy Bands",
                    "baseline_vs_current": "Baseline vs Current SFRA Comparison",
                    "peak_activation": "Peak Activation Map — Feature Importance",
                    "delta_damage_locator": "Delta Comparison Curve — Damage Locator",
                    "fault_severity": "Fault Severity Gauge",
                    "midband_turbulence": "Mid-band Turbulence & HF Decay",
                }

                # Preferred display order (top of file me GRAPH_KEYS_ORDER already defined hai)
                ordered_keys = GRAPH_KEYS_ORDER or list(graphs.keys())

                for key in ordered_keys:
                    path = graphs.get(key)
                    if not path or not os.path.exists(path):
                        continue

                    block = tk.Frame(frame, bg="white")
                    block.pack(fill="both", expand=True, pady=(10, 6))

                    title = title_map.get(
                        key,
                        key.replace("_", " ").title()
                    )
                    tk.Label(
                        block,
                        text=title,
                        font=("Segoe UI", 14, "bold"),
                        bg="white"
                    ).pack(anchor="w", pady=(0, 4))

                    try:
                        img = Image.open(path)
                        img.thumbnail((780, 360))
                        tkimg = ImageTk.PhotoImage(img)
                        lbl = tk.Label(block, image=tkimg, bg="white")
                        lbl.image = tkimg
                        lbl.pack()

                        tk.Label(
                            block,
                            text=f"Source: {os.path.basename(path)}",
                            bg="white",
                            fg="#777777",
                            font=("Segoe UI", 8),
                        ).pack(anchor="w", pady=(2, 0))
                    except Exception as e:
                        tk.Label(
                            block,
                            text=f"Failed to render graph {os.path.basename(path)} ({e})",
                            bg="white",
                            fg="red",
                        ).pack(anchor="w")

            else:
                # ----- Fallback: purana single GRAPH_PATH logic -----
                graph_img_path = self._resolve_graph_image(preferred_key="modal_spectrum_bands")
                if Image and ImageTk and graph_img_path and os.path.exists(graph_img_path):
                    try:
                        img = Image.open(graph_img_path)
                        img.thumbnail((780, 360))
                        tkimg = ImageTk.PhotoImage(img)
                        lbl = tk.Label(frame, image=tkimg, bg="white")
                        lbl.image = tkimg
                        lbl.pack(pady=12)

                        tk.Label(
                            frame,
                            text=f"Source: {os.path.basename(graph_img_path)}",
                            bg="white",
                            fg="#777777",
                            font=("Segoe UI", 8),
                        ).pack(anchor="w", pady=(0, 4))
                    except Exception as e:
                        tk.Label(
                            frame,
                            text=f"Graph found but failed to render: {e}",
                            bg="white",
                        ).pack(anchor="w")
                else:
                    tk.Label(
                        frame,
                        text="No pipeline graph image found in pipeline_data['graph_images'] "
                             f"or at legacy {GRAPH_PATH}",
                        bg="white",
                    ).pack(anchor="w")

            # per-section PDF button (same as pehle)
            btn_area = tk.Frame(frame, bg="white")
            btn_area.pack(fill="x", pady=(8, 12), padx=6)
            ttk.Button(
                btn_area,
                text="📄 Generate Report (This Section)",
                command=lambda: self.generate_section_pdf_and_preview(3)
            ).pack(anchor="w")

            self._log_section("Graph (SFRA + ML plots)")
        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Error show_section3: {e}", "ERROR")

    def show_section4(self):
        """Regulation & Efficiency calculations"""
        if self.center_frame_inner is None:
            return
        try:
            self.clear_frame(self.center_frame_inner)
            frame = tk.Frame(self.center_frame_inner, bg="white")
            frame.pack(fill="both", expand=True, padx=12, pady=8)
            tk.Label(frame, text="Load Loss, Regulation & Efficiency Calculation", font=("Segoe UI", 16, "bold"), bg="white").pack(anchor="w", pady=(0, 8))

            form = tk.Frame(frame, bg="white")
            form.pack(fill="x", pady=6, padx=6)

            perf_fields = [
                ("Core Loss (W)", "transformer_performance.loss_estimates.core_loss_watts"),
                ("Load Loss (W)", "transformer_performance.loss_estimates.load_loss_watts"),
                ("Impedance %Z", "transformer_performance.impedance_pct"),
                ("% R at 33°C", "transformer_performance.r_at_33"),
                ("% X at 33°C", "transformer_performance.r_at_33"),  # note: duplicated label kept
                ("Total Loss (W)", "transformer_performance.total_loss_watts"),
                ("Efficiency @ unity (%)", "transformer_performance.eff_unity"),
                ("Efficiency @ 0.8 pf (%)", "transformer_performance.eff_08pf"),
            ]

            for label_text, dotted in perf_fields:
                row = tk.Frame(form, bg="white")
                row.pack(fill="x", pady=6)
                tk.Label(row, text=label_text + ":", width=24, anchor="w", bg="white").pack(side="left", padx=(4, 0))
                if dotted not in self.field_vars:
                    cur = self._get_model_value(dotted)
                    self.field_vars[dotted] = tk.StringVar(value=str(cur if cur is not None else ""))
                    self.field_vars[dotted].trace_add("write", lambda *a, k=dotted: self._on_var_change(k))
                ttk.Entry(row, textvariable=self.field_vars[dotted]).pack(side="left", fill="x", expand=True, padx=(8, 10))

            def calc_eff():
                try:
                    core = float(self.field_vars.get("transformer_performance.loss_estimates.core_loss_watts", tk.StringVar("0")).get() or 0)
                    load = float(self.field_vars.get("transformer_performance.loss_estimates.load_loss_watts", tk.StringVar("0")).get() or 0)
                    rating_mva = float(self.model.get("transformer_performance", {}).get("rating_mva", 80.0))
                    output_w = rating_mva * 1e6
                    eff = 0.0
                    if (output_w + core + load) > 0:
                        eff = (output_w / (output_w + core + load)) * 100.0
                    self._set_model_value("transformer_performance.eff_unity", f"{eff:.3f}")
                    if "transformer_performance.eff_unity" in self.field_vars:
                        self.field_vars["transformer_performance.eff_unity"].set(f"{eff:.3f}")
                    messagebox.showinfo("Calculated", f"Estimated Efficiency: {eff:.3f}% (approx)")
                except Exception as e:
                    messagebox.showerror("Calc error", str(e))
                    if hasattr(self.app, "log_console"):
                        self.app.log_console(f"Calc error: {e}", "ERROR")

            ttk.Button(frame, text="Calculate Efficiency (approx)", command=calc_eff).pack(anchor="w", padx=12, pady=(8, 12))

            # per-section generate PDF (section 4)
            btn_area = tk.Frame(frame, bg="white")
            btn_area.pack(fill="x", pady=(8, 12), padx=6)
            ttk.Button(btn_area, text="📄 Generate Report (This Section)", command=lambda: self.generate_section_pdf_and_preview(4)).pack(anchor="w")

            self._log_section("Regulation & Efficiency Calculation")
        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Error show_section4: {e}", "ERROR")

    def show_section5(self):
        """Transformer Tested Signature"""
        if self.center_frame_inner is None:
            return
        try:
            self.clear_frame(self.center_frame_inner)
            frame = tk.Frame(self.center_frame_inner, bg="white")
            frame.pack(fill="both", expand=True, padx=12, pady=8)
            tk.Label(frame, text="Transformer Tested Signature", font=("Segoe UI", 16, "bold"), bg="white").pack(anchor="w", pady=(0, 8))

            sig_area = tk.Frame(frame, bg="white")
            sig_area.pack(fill="both", expand=True, padx=6)

            left_col = tk.Frame(sig_area, bg="white")
            right_col = tk.Frame(sig_area, bg="white")
            left_col.pack(side="left", fill="both", expand=True, padx=(0, 6))
            right_col.pack(side="left", fill="both", expand=True, padx=(6, 0))

            # ---------------- LEFT COLUMN ----------------
            tk.Label(left_col, text="Tested By:", font=("Segoe UI", 11, "bold"),
                     bg="white").pack(anchor="w", pady=(4, 6))

            r1 = tk.Frame(left_col, bg="white")
            r1.pack(fill="x", pady=4)
            tk.Label(r1, text="Name:", width=16, anchor="w", bg="white").pack(side="left")

            if "tested_by.name" not in self.field_vars:
                self.field_vars["tested_by.name"] = tk.StringVar(
                    value=self.model.get("tested_by", {}).get("name", "")
                )
                self.field_vars["tested_by.name"].trace_add(
                    "write", lambda *a: self._on_var_change("tested_by.name")
                )

            ttk.Entry(r1, textvariable=self.field_vars["tested_by.name"]).pack(
                side="left", fill="x", expand=True
            )

            r2 = tk.Frame(left_col, bg="white")
            r2.pack(fill="x", pady=4)
            tk.Label(r2, text="Designation:", width=16, anchor="w",
                     bg="white").pack(side="left")

            if "tested_by.designation" not in self.field_vars:
                self.field_vars["tested_by.designation"] = tk.StringVar(
                    value=self.model.get("tested_by", {}).get("designation", "")
                )
                self.field_vars["tested_by.designation"].trace_add(
                    "write", lambda *a: self._on_var_change("tested_by.designation")
                )

            ttk.Entry(r2, textvariable=self.field_vars["tested_by.designation"]).pack(
                side="left", fill="x", expand=True
            )

            # Signature preview (LEFT)
            preview_frame = tk.Frame(left_col, bg="white")
            preview_frame.pack(fill="both", pady=8)

            self._sig_preview_label = tk.Label(
                preview_frame, bg="#f8f8f8", relief="groove",
                width=40, height=20, text="(No signature uploaded)"
            )
            self._sig_preview_label.pack(fill="both", expand=True, padx=4, pady=4)

            def upload_test_sig():
                p = filedialog.askopenfilename(
                    title="Select signature image",
                    filetypes=[("Images", "*.png;*.jpg;*.jpeg")]
                )
                if not p:
                    return

                self._set_model_value("tested_by.signature", p)

                if Image and ImageTk:
                    self._load_sig_preview(p)

                messagebox.showinfo("Signature", "Signature uploaded.")

            ttk.Button(left_col, text="Upload Signature",
                       command=upload_test_sig).pack(anchor="w", pady=(4, 0))

            # ---------------- RIGHT COLUMN ----------------
            tk.Label(right_col, text="For (Authority) / Witnesses",
                     font=("Segoe UI", 11, "bold"), bg="white").pack(anchor="w", pady=(4, 6))

            auth_frame = tk.Frame(right_col, bg="white")
            auth_frame.pack(fill="x", pady=6)

            tk.Label(auth_frame, text="Authority Name:", width=16, anchor="w",
                     bg="white").pack(side="left")

            if "authority.name" not in self.field_vars:
                self.field_vars["authority.name"] = tk.StringVar(
                    value=self.model.get("tested_by", {}).get("authority_name", "")
                )
                self.field_vars["authority.name"].trace_add(
                    "write", lambda *a: self._on_var_change("authority.name")
                )

            ttk.Entry(auth_frame, textvariable=self.field_vars["authority.name"]).pack(
                side="left", fill="x", expand=True
            )

            # Authority signature (RIGHT)
            auth_sig_frame = tk.Frame(right_col, bg="white")
            auth_sig_frame.pack(fill="both", pady=6)

            self._auth_sig_label = tk.Label(
                auth_sig_frame, bg="#f8f8f8", relief="groove",
                width=40, height=20, text="(No signature)"
            )
            self._auth_sig_label.pack(fill="both", expand=True, padx=4, pady=4)

            def load_auth_sig():
                p = filedialog.askopenfilename(
                    title="Select authority signature image",
                    filetypes=[("Images", "*.png;*.jpg;*.jpeg")]
                )
                if not p:
                    return

                self._set_model_value("tested_by.authority_signature", p)

                if Image and ImageTk:
                    self._load_auth_preview(p)

                messagebox.showinfo("Authority signature", "Uploaded.")

            ttk.Button(right_col, text="Upload Authority Signature",
                       command=load_auth_sig).pack(anchor="w", pady=(4, 0))

            # ---------------- WITNESSES ----------------
            witnesses_frame = tk.Frame(frame, bg="white")
            witnesses_frame.pack(fill="x", pady=(12, 0))

            tk.Label(witnesses_frame, text="Witnesses:",
                     font=("Segoe UI", 11, "bold"), bg="white").pack(anchor="w")

            for i in range(1, 3):
                wrow = tk.Frame(witnesses_frame, bg="white")
                wrow.pack(fill="x", pady=4)

                tk.Label(wrow, text=f"{i}.", width=3, anchor="w",
                         bg="white").pack(side="left")

                name_key = f"tested_by.witness_{i}_name"
                desig_key = f"tested_by.witness_{i}_designation"

                if name_key not in self.field_vars:
                    self.field_vars[name_key] = tk.StringVar(
                        value=self.model.get("tested_by", {}).get(name_key, "")
                    )
                    self.field_vars[name_key].trace_add(
                        "write", lambda *a, k=name_key: self._on_var_change(k))

                if desig_key not in self.field_vars:
                    self.field_vars[desig_key] = tk.StringVar(
                        value=self.model.get("tested_by", {}).get(desig_key, "")
                    )
                    self.field_vars[desig_key].trace_add(
                        "write", lambda *a, k=desig_key: self._on_var_change(k))

                ttk.Entry(wrow, textvariable=self.field_vars[name_key],
                          width=30).pack(side="left", padx=(6, 6))

                ttk.Entry(wrow, textvariable=self.field_vars[desig_key],
                          width=30).pack(side="left", padx=(6, 6))

            # per-section Generate button for section 5 (signatures)
            btn_area = tk.Frame(frame, bg="white")
            btn_area.pack(fill="x", pady=(8, 12), padx=6)
            ttk.Button(btn_area, text="📄 Generate Report (This Section)", command=lambda: self.generate_section_pdf_and_preview(5)).pack(anchor="w")

            # load existing previews
            sigp = self.model.get("tested_by", {}).get("signature", "")
            if sigp and os.path.exists(sigp) and Image and ImageTk:
                self._load_sig_preview(sigp)

            authp = self.model.get("tested_by", {}).get("authority_signature", "")
            if authp and os.path.exists(authp) and Image and ImageTk:
                self._load_auth_preview(authp)

        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Error show_section5: {e}", "ERROR")

    # --------------------------------------------------------------------
    # PATCHED — dynamic signature preview, NO overlapping
    # --------------------------------------------------------------------
    def _load_sig_preview(self, path):
        try:
            if not Image or not ImageTk:
                return

            def render():
                fw = self._sig_preview_label.winfo_width()
                fh = self._sig_preview_label.winfo_height()

                if fw < 100: fw = 400
                if fh < 80: fh = 250

                img = Image.open(path)
                img.thumbnail((fw - 20, fh - 20), Image.LANCZOS)

                p = ImageTk.PhotoImage(img)
                self._sig_preview_label.configure(image=p, text="")
                self._sig_preview_label.image = p

            self._sig_preview_label.after(10, render)

        except:
            try:
                self._sig_preview_label.configure(text="(signature preview failed)")
            except Exception:
                pass

    def _load_auth_preview(self, path):
        try:
            if not Image or not ImageTk:
                return

            def render():
                fw = self._auth_sig_label.winfo_width()
                fh = self._auth_sig_label.winfo_height()

                if fw < 100: fw = 400
                if fh < 80: fh = 250

                img = Image.open(path)
                img.thumbnail((fw - 20, fh - 20), Image.LANCZOS)

                p = ImageTk.PhotoImage(img)
                self._auth_sig_label.configure(image=p, text="")
                self._auth_sig_label.image = p

            self._auth_sig_label.after(10, render)

        except:
            try:
                self._auth_sig_label.configure(text="(preview failed)")
            except Exception:
                pass

    # -------------------------
    # RIGHT metadata area - scroll only when needed
    # -------------------------
    def _build_right(self, parent):
        """
        Build the metadata cards. This is called on load_ui and ONLY when
        refresh_metadata() is called (Refresh button).
        """
        if parent is None:
            return
        try:
            # clear
            for w in parent.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass

            # create canvas + vbar but keep vbar hidden initially
            canvas = tk.Canvas(parent, bg="#fafafa", highlightthickness=0)
            vbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=vbar.set)

            # pack canvas first; we will pack/unpack vbar depending on content size
            canvas.pack(side="left", fill="both", expand=True)
            # don't pack vbar now — will pack only if needed

            inner = tk.Frame(canvas, bg="#fafafa")
            canvas.create_window((0, 0), window=inner, anchor="nw")

            def on_inner_config(e=None):
                # update scrollregion
                try:
                    canvas.configure(scrollregion=canvas.bbox("all") or (0, 0, 0, 0))
                except Exception:
                    pass
                # decide if scrollbar needed
                try:
                    parent_h = parent.winfo_height() or 1
                    inner_h = inner.winfo_reqheight() or 0
                    # show vbar only when inner content is taller
                    if inner_h > parent_h - 8:
                        if not vbar.winfo_ismapped():
                            vbar.pack(side="right", fill="y", padx=(0, 4))
                    else:
                        if vbar.winfo_ismapped():
                            vbar.pack_forget()
                except Exception:
                    pass

            inner.bind("<Configure>", on_inner_config)

            # mousewheel bound to canvas only (works when pointer is over canvas)
            def _on_mousewheel(event):
                try:
                    if event.delta:
                        # Windows/mac
                        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    elif getattr(event, "num", None) == 4:
                        canvas.yview_scroll(-1, "units")
                    elif getattr(event, "num", None) == 5:
                        canvas.yview_scroll(1, "units")
                except Exception:
                    pass

            # bind both wheel forms
            canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
            canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
            # linux wheel (Button-4/5)
            canvas.bind("<Button-4>", _on_mousewheel)
            canvas.bind("<Button-5>", _on_mousewheel)

            # save refs
            self._meta_canvas = canvas
            self._meta_inner = inner
            self._meta_vbar = vbar

            # build cards inside inner
            cards = tk.Frame(inner, bg="#fafafa")
            cards.pack(fill="both", expand=True, pady=8, padx=6)

            def make_card(title):
                c = tk.Frame(cards, bg="white", relief="groove", bd=1)
                c.pack(fill="x", padx=6, pady=8)
                tk.Label(c, text=title, bg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
                return c

            # Transformer Meta card
            card_meta = make_card("Transformer Meta")
            meta_rows = [
                ("Serial No", "meta.serial_number"),
                ("Manufacturer", "meta.manufacturer"),
                ("Year", "meta.year"),
                ("Start Freq", "meta.start_frequency"),
                ("Stop Freq", "meta.stop_frequency"),
                ("Red Lead", "meta.red_lead"),
                ("Black Lead", "meta.black_lead"),
            ]
            for label, dotted in meta_rows:
                frm = tk.Frame(card_meta, bg="white")
                frm.pack(fill="x", padx=8, pady=2)
                tk.Label(frm, text=label + ":", bg="white", width=12, anchor="w").pack(side="left")
                if dotted not in self.field_vars:
                    self.field_vars[dotted] = tk.StringVar(value=str(self._get_model_value(dotted) or ""))
                    # keep trace but _on_var_change no longer rebuilds metadata
                    self.field_vars[dotted].trace_add("write", lambda *a, k=dotted: self._on_var_change(k))
                ent = ttk.Entry(frm, textvariable=self.field_vars[dotted])
                ent.pack(side="left", fill="x", expand=True)

            # Curve stats
            card_cs = make_card("Curve Stats")
            cs = self.model.get("curve_stats", {}) or {}
            cs_rows = [
                ("Min Mag", cs.get("min_mag", "n/a")),
                ("Max Mag", cs.get("max_mag", "n/a")),
                ("Phase Mean", cs.get("phase_mean", "n/a")),
                ("Points", cs.get("points", "n/a")),
            ]
            for label, val in cs_rows:
                f = tk.Frame(card_cs, bg="white")
                f.pack(fill="x", padx=8, pady=2)
                tk.Label(f, text=label + ":", bg="white", width=12, anchor="w").pack(side="left")
                tk.Label(f, text=str(val), bg="white").pack(side="left", fill="x", expand=True)

            # Performance card
            card_perf = make_card("Performance")
            perf_rows = [
                ("Voltage Regulation", "transformer_performance.voltage_regulation"),
                ("Efficiency (%)", "transformer_performance.eff_unity"),
                ("Core Loss (W)", "transformer_performance.loss_estimates.core_loss_watts"),
                ("Load Loss (W)", "transformer_performance.loss_estimates.load_loss_watts"),
            ]
            for label, dotted in perf_rows:
                frm = tk.Frame(card_perf, bg="white")
                frm.pack(fill="x", padx=8, pady=2)
                tk.Label(frm, text=label + ":", bg="white", width=16, anchor="w").pack(side="left")
                if dotted not in self.field_vars:
                    self.field_vars[dotted] = tk.StringVar(value=str(self._get_model_value(dotted) or ""))
                    self.field_vars[dotted].trace_add("write", lambda *a, k=dotted: self._on_var_change(k))
                ent = ttk.Entry(frm, textvariable=self.field_vars[dotted])
                ent.pack(side="left", fill="x", expand=True)

            # Feature stats (optional)
            feat = self.model.get("features_used", {}) or {}
            if feat:
                card_feat = make_card("Feature Stats (ML)")
                shown = list(feat.items())[:12]
                for k, v in shown:
                    frm = tk.Frame(card_feat, bg="white")
                    frm.pack(fill="x", padx=8, pady=2)
                    tk.Label(frm, text=f"{k}:", bg="white", width=18, anchor="w").pack(side="left")
                    tk.Label(frm, text=str(v), bg="white").pack(side="left", fill="x", expand=True)

            # --- CSV / Header Metadata (ALL KEYS) card ---
            card_header = make_card("CSV / Header Metadata")
            header_meta = self.model.get("metadata", {}) or {}
            if header_meta:
                for k, v in sorted(header_meta.items()):
                    f = tk.Frame(card_header, bg="white")
                    f.pack(fill="x", padx=8, pady=2)
                    tk.Label(f, text=f"{k}:", bg="white", width=18, anchor="w").pack(side="left")
                    tk.Label(f, text=str(v), bg="white").pack(side="left", fill="x", expand=True)
            else:
                f = tk.Frame(card_header, bg="white")
                f.pack(fill="x", padx=8, pady=2)
                tk.Label(f, text="(No CSV/header metadata available)", bg="white").pack(side="left")

            # --- REFRESH BUTTON (ONLY HERE, bottom of metadata inner) ---
            refresh_row = tk.Frame(inner, bg="#fafafa")
            refresh_row.pack(fill="x", padx=6, pady=(6, 12))
            ttk.Button(refresh_row, text="🔄 Refresh Metadata", command=self.refresh_metadata).pack(anchor="e", padx=6)

            # request layout update and decide scrollbar visibility
            parent.update_idletasks()
            on_inner_config()

            if hasattr(self.app, "log_console"):
                self.app.log_console("Metadata pane (Generate Report) built.", "INFO")
        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Error building metadata pane: {e}", "ERROR")

    def refresh_metadata(self):
        """
        Called by the Refresh Metadata button.
        Sync all field vars into the model and rebuild the metadata pane.
        """
        try:
            # sync fields -> model
            for k, var in list(self.field_vars.items()):
                try:
                    self._set_model_value(k, var.get())
                except Exception:
                    pass
            # merge any JSON loaded data (already in self.model via _merge_json)
            # now rebuild metadata (explicit)
            self._build_right(self.right_frame)
            if hasattr(self.app, "log_console"):
                self.app.log_console("Metadata refreshed by user.", "INFO")
            messagebox.showinfo("Metadata", "Metadata refreshed.")
        except Exception as e:
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Error refreshing metadata: {e}", "ERROR")
            messagebox.showerror("Refresh error", str(e))

    def _ensure_metadata_width(self):
        """Ensure metadata internal canvas matches container width."""
        # intentionally safe no-op to avoid recursive layout loops.
        return

    # -------------------------
    # Model <-> vars helpers
    # -------------------------
    def sync_model_to_fields(self):
        primary = [
            "customer",
            "po_number",
            "meta.serial_number",
            "meta.manufacturer",
            "meta.year",
            "meta.start_frequency",
            "meta.stop_frequency",
            "meta.red_lead",
            "meta.black_lead",
        ]
        for key in primary:
            if key not in self.field_vars:
                val = self._get_model_value(key) or ""
                self.field_vars[key] = tk.StringVar(value=str(val))
                self.field_vars[key].trace_add("write", lambda *a, k=key: self._on_var_change(k))
            else:
                try:
                    self.field_vars[key].set(str(self._get_model_value(key) or ""))
                except Exception:
                    pass

    def sync_model_from_fields(self):
        for k, var in self.field_vars.items():
            try:
                self._set_model_value(k, var.get())
            except Exception:
                pass

    # -------------------------
    # JSON load/save/preview
    # -------------------------
    def load_json(self):
        p = filedialog.askopenfilename(title="Select diagnostic JSON", filetypes=[("JSON", "*.json")])
        if not p:
            return
        try:
            data = safe_load_json(p)
            self.json_data = data
            self._merge_json(data)
            for k in list(self.field_vars.keys()):
                try:
                    # update field vars — but do NOT rebuild metadata automatically
                    self.field_vars[k].set(str(self._get_model_value(k) or ""))
                except Exception:
                    pass
            self.sync_model_to_fields()
            messagebox.showinfo("Loaded", "JSON loaded and fields auto-filled. Click 'Refresh Metadata' to update metadata panel.")
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Loaded JSON {os.path.basename(p)}", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Load JSON", str(e))
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Load JSON error: {e}", "ERROR")

    def save_json(self):
        p = filedialog.asksaveasfilename(title="Save diagnostic JSON", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not p:
            return
        self.sync_model_from_fields()
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.model, f, indent=2)
            messagebox.showinfo("Saved", f"Saved to {p}")
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Saved JSON {os.path.basename(p)}", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Save JSON", str(e))
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Save JSON error: {e}", "ERROR")

    def preview_report(self):
        collected = self.collect_all()
        win = tk.Toplevel(self.app.root)
        win.title("Report Preview")
        win.geometry("900x700")
        txt = ScrolledText(win)
        txt.pack(fill="both", expand=True)
        txt.insert("end", "=== Vidhyut Transformer Report Preview ===\n\n")
        txt.insert("end", json.dumps(collected, indent=2))

        graph_img_path = self._resolve_graph_image(preferred_key="modal_spectrum_bands")
        if Image and ImageTk and graph_img_path and os.path.exists(graph_img_path):
            try:
                img = Image.open(graph_img_path)
                img.thumbnail((700, 360))
                tkimg = ImageTk.PhotoImage(img)
                lbl = tk.Label(win, image=tkimg)
                lbl.image = tkimg
                lbl.pack(pady=8)
            except Exception:
                pass

    def collect_all(self):
        # ensure model is updated from fields
        self.sync_model_from_fields()
        out = {
            "customer": self.model.get("customer", ""),
            "po_number": self.model.get("po_number", ""),
            "meta": self.model.get("meta", {}),
            "curve_stats": self.model.get("curve_stats", {}),
            "features_used": self.model.get("features_used", {}),
            "transformer_performance": self.model.get("transformer_performance", {}),
            "tested_by": self.model.get("tested_by", {}),
            "metadata": self.model.get("metadata", {}),
        }
        return out

    # -------------------------
    # PDF generation helpers (ReportLab)
    # -------------------------
    def _ensure_reportlab_installed(self):
        if canvas is None or A4 is None or mm is None:
            raise RuntimeError("ReportLab not available. Install with: pip install reportlab")

    def _generate_test_report_no(self):
        # Create a short unique report no (timestamp + short uuid)
        t = datetime.now().strftime("%Y%m%d%H%M%S")
        short = uuid.uuid4().hex[:6].upper()
        return f"VID-{t}-{short}"

    def _draw_header(self, c, page_width, page_height, report_no, title_text):
        # Draw VIDHYUT centered and report meta on top
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(page_width / 2.0, page_height - 40, "VIDHYUT")

        # small subtitle / date / report number
        c.setFont("Helvetica", 10)
        c.drawRightString(page_width - 40, page_height - 28, "Date: " + datetime.now().strftime("%d-%b-%Y"))
        c.drawRightString(page_width - 40, page_height - 42, f"Test Report No: {report_no}")

        # draw section title slightly lower
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, page_height - 70, title_text)
        # horizontal rule
        c.line(40, page_height - 74, page_width - 40, page_height - 74)

    def _draw_fields_table(self, c, page_width, start_y, rows, col_widths=None, left_margin=40, row_height=18):
        """
        Draws key/value pairs as two-column table starting at start_y (y coordinate).
        rows = list of (label, value)
        Returns y coordinate after drawing.
        """
        x = left_margin
        y = start_y
        if col_widths is None:
            col_widths = (150, page_width - left_margin - 40 - 150)
        label_w, val_w = col_widths
        c.setFont("Helvetica", 10)
        for (label, val) in rows:
            if y < 80:
                c.showPage()
                y = A4[1] - 80
            # label
            c.drawString(x, y, f"{label}:")
            if val is None:
                val = ""
            v = str(val)
            approx_chars = int(val_w / 6)
            lines = [v[i:i+approx_chars] for i in range(0, len(v), approx_chars)] if len(v) > approx_chars else [v]
            c.drawString(x + label_w + 6, y, lines[0] if lines else "")
            if len(lines) > 1:
                # draw subsequent lines
                ly = y - row_height
                for l in lines[1:]:
                    if ly < 80:
                        c.showPage()
                        ly = A4[1] - 80
                    c.drawString(x + label_w + 6, ly, l)
                    ly -= row_height
                y = ly + row_height
            y -= row_height
        return y

    def _embed_image(self, c, img_path, x, y, max_w, max_h):
        """
        Draw image at (x, y) where y is top coordinate. Scales to fit within max_w x max_h preserving aspect.
        """
        if not img_path or not os.path.exists(img_path):
            return
        try:
            img = Image.open(img_path) if Image else None
            if img is not None:
                w, h = img.size
                ratio = min(max_w / w, max_h / h, 1.0)
                draw_w = w * ratio
                draw_h = h * ratio
                # reportlab y coordinates: drawImage expects lower-left corner
                c.drawImage(ImageReader(img), x, y - draw_h, width=draw_w, height=draw_h)
        except Exception:
            # fallback: try direct drawImage from path
            try:
                c.drawImage(img_path, x, y - max_h, width=max_w, height=max_h)
            except Exception:
                pass

    def generate_section_pdf(self, section_index, out_path=None):
        """
        section_index: 1..5 mapping to the five sections (same order as menu)
        returns path to saved PDF.
        """
        self._ensure_reportlab_installed()
        # ensure model synced
        self.sync_model_from_fields()

        if out_path is None:
            os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
            out_path = os.path.join(PDF_OUTPUT_DIR, f"vidhyut_section_{section_index}_{int(time.time())}.pdf")

        report_no = self._generate_test_report_no()
        self._last_report_no = report_no

        page_width, page_height = A4

        c = canvas.Canvas(out_path, pagesize=A4)

        title_map = {
            1: "Transformer Test Report",
            2: "Measurement of Voltage Ratio",
            3: "Graph (Sweep Frequency Response)",
            4: "Regulation & Efficiency Calculation",
            5: "Transformer Tested Signature",
        }
        title_text = title_map.get(section_index, f"Section {section_index}")

        # header
        self._draw_header(c, page_width, page_height, report_no, title_text)

        y = page_height - 100

        if section_index == 1:
            # transformer test report fields: use same ordering as UI
            fields = [
                ("Customer", self.model.get("customer", "")),
                ("Customer Reference P.O.No", self.model.get("po_number", "")),
                ("Serial No", self._get_model_value("meta.serial_number") or ""),
                ("Make", self._get_model_value("meta.manufacturer") or ""),
                ("Previously Repaired By", self.model.get("previously_repaired_by", "")),
                ("Rating", self.model.get("rating", "")),
                ("Cooling", self.model.get("cooling", "")),
                ("Phase", self.model.get("phase", "")),
                ("Vector Group", self.model.get("vector_group", "")),
                ("Frequency", self.model.get("frequency", "")),
                ("Connection", self.model.get("connection", "")),
                ("Ref. Standard", self.model.get("ref_standard", "")),
                ("Rated Voltage HV", self.model.get("meta", {}).get("rated_voltage_hv", "")),
                ("Rated Voltage LV", self.model.get("meta", {}).get("rated_voltage_lv", "")),
                ("Full Load Line Current HV", self.model.get("full_load_hv", "")),
                ("Full Load Line Current LV", self.model.get("full_load_lv", "")),
                ("OLTC", self.model.get("meta", {}).get("oltc", "")),
                ("Voltage Variation", self.model.get("voltage_variation", "")),
            ]
            y = self._draw_fields_table(c, page_width, y, fields, left_margin=40)

            # Tested by details + signature if available
            tested = self.model.get("tested_by", {}) or {}
            y -= 10
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, "Tested By:")
            y -= 18
            details = [
                ("Name", tested.get("name", "")),
                ("Designation", tested.get("designation", "")),
            ]
            y = self._draw_fields_table(c, page_width, y, details, left_margin=60)
            # signatures
            sigp = tested.get("signature", "")
            if sigp and os.path.exists(sigp):
                # embed signature bottom-left
                self._embed_image(c, sigp, 60, y, max_w=160, max_h=80)
            # authority signature if any
            authp = tested.get("authority_signature", "")
            if authp and os.path.exists(authp):
                self._embed_image(c, authp, page_width - 220, y, max_w=160, max_h=80)

        elif section_index == 2:
            freqs = self.model.get("freq", [])
            mags = self.model.get("mag", [])
            phase = self.model.get("phase", [])

            c.setFont("Helvetica-Bold", 10)
            c.drawString(40, y, "Index")
            c.drawString(120, y, "Frequency (Hz)")
            c.drawString(260, y, "Magnitude (dB)")
            c.drawString(400, y, "Phase (Deg)")
            y -= 18

            c.setFont("Helvetica", 10)

            for i, f in enumerate(freqs):
              if y < 80:
                c.showPage()
                self._draw_header(c, page_width, page_height, report_no, title_text)
                y = page_height - 100

                mag = mags[i] if i < len(mags) else ""
                ph = phase[i] if i < len(phase) else ""

                c.drawString(40, y, str(i + 1))
                c.drawString(120, y, str(f))
                c.drawString(260, y, str(mag))
                c.drawString(400, y, str(ph))

                y -= 16



        elif section_index == 3:
            # Graphs: include stats and embed ALL pipeline graph images
            cs = self.model.get("curve_stats", {}) or {}
            stats_text = (
                f"Min mag: {cs.get('min_mag','n/a')}  "
                f"Max mag: {cs.get('max_mag','n/a')}  "
                f"Phase mean: {cs.get('phase_mean','n/a')}"
            )
            c.setFont("Helvetica", 10)
            c.drawString(40, y, stats_text)
            y -= 24

            graphs = self.model.get("graph_images", {}) or {}

            if graphs:
                title_map = {
                    "modal_spectrum_bands": "Modal Frequencies + Spectrum Energy Bands",
                    "baseline_vs_current": "Baseline vs Current SFRA Comparison",
                    "peak_activation": "Peak Activation Map — Feature Importance",
                    "delta_damage_locator": "Delta Comparison Curve — Damage Locator",
                    "fault_severity": "Fault Severity Gauge",
                    "midband_turbulence": "Mid-band Turbulence & HF Decay",
                }
                ordered_keys = GRAPH_KEYS_ORDER or list(graphs.keys())

                for key in ordered_keys:
                    path = graphs.get(key)
                    if not path or not os.path.exists(path):
                        continue

                    if y < 160:
                        c.showPage()
                        self._draw_header(c, page_width, page_height, report_no, title_text)
                        y = page_height - 100

                    title = title_map.get(
                        key,
                        key.replace("_", " ").title()
                    )
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(40, y, title)
                    y -= 18

                    self._embed_image(
                        c,
                        path,
                        x=60,
                        y=y,
                        max_w=page_width - 120,
                        max_h=260,
                    )
                    y -= 280
            else:
                # fallback: legacy single graph
                graph_img_path = self._resolve_graph_image(preferred_key="modal_spectrum_bands")
                if graph_img_path:
                    self._embed_image(
                        c,
                        graph_img_path,
                        60,
                        y,
                        max_w=page_width - 120,
                        max_h=300,
                    )
                    y -= 320
                else:
                    c.setFont("Helvetica", 10)
                    c.drawString(
                        40,
                        y,
                        "No pipeline graph image found in pipeline_data['graph_images'] "
                        f"or at legacy {GRAPH_PATH}",
                    )
                    y -= 20

        elif section_index == 4:
            # Regulation & Efficiency: draw perf fields
            perf_rows = [
                ("Core Loss (W)", self._get_model_value("transformer_performance.loss_estimates.core_loss_watts") or ""),
                ("Load Loss (W)", self._get_model_value("transformer_performance.loss_estimates.load_loss_watts") or ""),
                ("Impedance %Z", self._get_model_value("transformer_performance.impedance_pct") or ""),
                ("% R at 33°C", self._get_model_value("transformer_performance.r_at_33") or ""),
                ("Total Loss (W)", self._get_model_value("transformer_performance.total_loss_watts") or ""),
                ("Efficiency @ unity (%)", self._get_model_value("transformer_performance.eff_unity") or ""),
                ("Efficiency @ 0.8 pf (%)", self._get_model_value("transformer_performance.eff_08pf") or ""),
            ]
            y = self._draw_fields_table(c, page_width, y, perf_rows, left_margin=40)

        elif section_index == 5:
            # Tested signature section: include names & both signatures
            tested = self.model.get("tested_by", {}) or {}

            # --- SAFE READ for Authority Name ---
            auth_var = self.field_vars.get("authority.name")
            if hasattr(auth_var, "get"):
                authority_name = auth_var.get()
            else:
                authority_name = auth_var or tested.get("authority_name", "") or ""

            rows = [
                ("Name", tested.get("name", "")),
                ("Designation", tested.get("designation", "")),
                ("Authority Name", authority_name),
            ]

            y = self._draw_fields_table(c, page_width, y, rows, left_margin=40)

            # embed signatures
            y -= 10
            sigp = tested.get("signature", "")
            authp = tested.get("authority_signature", "")

            # position images side by side if both exist
            if sigp and os.path.exists(sigp) and authp and os.path.exists(authp):
                max_w = (page_width - 140) / 2.0
                max_h = 120
                self._embed_image(c, sigp, 60, y, max_w=max_w, max_h=max_h)
                self._embed_image(c, page_width - 60 - max_w, y, max_w=max_w, max_h=max_h)
                y -= (max_h + 10)
            else:
                if sigp and os.path.exists(sigp):
                    self._embed_image(c, sigp, 60, y, max_w=200, max_h=120)
                    y -= 140
                if authp and os.path.exists(authp):
                    self._embed_image(c, authp, 60, y, max_w=200, max_h=120)
                    y -= 140

        # finalize
        c.showPage()
        c.save()
        return out_path

    # Helper to open a file using OS default app for preview
    def _open_file_preview(self, path):
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", path])
            else:
                # assume linux with xdg-open
                subprocess.call(["xdg-open", path])
        except Exception:
            # cannot auto open; show path to user
            messagebox.showinfo("PDF saved", f"PDF saved to: {path}")

    # Wrapper: generate section PDF and preview (called by per-section buttons)
    def generate_section_pdf_and_preview(self, section_index):
        try:
            self._ensure_reportlab_installed()
        except Exception as e:
            messagebox.showerror("PDF error", str(e))
            return
        try:
            out = self.generate_section_pdf(section_index)
            # try to open
            try:
                self._open_file_preview(out)
            except Exception:
                messagebox.showinfo("PDF saved", f"Section PDF saved to: {out}")
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Generated section {section_index} PDF: {out}", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Generate PDF", str(e))
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Generate section PDF error: {e}", "ERROR")

    # Full PDF combiner
    def generate_full_pdf(self, out_path=None):
        try:
            self._ensure_reportlab_installed()
        except Exception:
            raise

        # ensure model updated
        self.sync_model_from_fields()

        if out_path is None:
            os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
            out_path = os.path.join(PDF_OUTPUT_DIR, f"vidhyut_full_transformer_report_{int(time.time())}.pdf")

        report_no = self._generate_test_report_no()
        self._last_report_no = report_no

        page_width, page_height = A4
        c = canvas.Canvas(out_path, pagesize=A4)

        # sequence through sections 1..5 and draw their content
        for si in range(1, 6):
            title_map = {
                1: "Transformer Test Report",
                2: "Measurement of Voltage Ratio",
                3: "Graph (Sweep Frequency Response)",
                4: "Regulation & Efficiency Calculation",
                5: "Transformer Tested Signature",
            }
            title_text = title_map.get(si, f"Section {si}")
            self._draw_header(c, page_width, page_height, report_no, title_text)
            y = page_height - 100

            # delegate to generate_section_pdf-like logic but draw inline to same canvas
            if si == 1:
                fields = [
                    ("Customer", self.model.get("customer", "")),
                    ("Customer Reference P.O.No", self.model.get("po_number", "")),
                    ("Serial No", self._get_model_value("meta.serial_number") or ""),
                    ("Make", self._get_model_value("meta.manufacturer") or ""),
                    ("Previously Repaired By", self.model.get("previously_repaired_by", "")),
                    ("Rating", self.model.get("rating", "")),
                    ("Cooling", self.model.get("cooling", "")),
                    ("Phase", self.model.get("phase", "")),
                    ("Vector Group", self.model.get("vector_group", "")),
                    ("Frequency", self.model.get("frequency", "")),
                    ("Connection", self.model.get("connection", "")),
                    ("Ref. Standard", self.model.get("ref_standard", "")),
                    ("Rated Voltage HV", self.model.get("meta", {}).get("rated_voltage_hv", "")),
                    ("Rated Voltage LV", self.model.get("meta", {}).get("rated_voltage_lv", "")),
                    ("Full Load Line Current HV", self.model.get("full_load_hv", "")),
                    ("Full Load Line Current LV", self.model.get("full_load_lv", "")),
                    ("OLTC", self.model.get("meta", {}).get("oltc", "")),
                    ("Voltage Variation", self.model.get("voltage_variation", "")),
                ]
                y = self._draw_fields_table(c, page_width, y, fields, left_margin=40)
                tested = self.model.get("tested_by", {}) or {}
                y -= 10
                c.setFont("Helvetica-Bold", 12)
                c.drawString(40, y, "Tested By:")
                y -= 18
                details = [
                    ("Name", tested.get("name", "")),
                    ("Designation", tested.get("designation", "")),
                ]
                y = self._draw_fields_table(c, page_width, y, details, left_margin=60)
                sigp = tested.get("signature", "")
                if sigp and os.path.exists(sigp):
                    self._embed_image(c, sigp, 60, y, max_w=160, max_h=80)
                authp = tested.get("authority_signature", "")
                if authp and os.path.exists(authp):
                    self._embed_image(c, authp, page_width - 220, y, max_w=160, max_h=80)

            elif si == 2:
                freqs = self.model.get("freq", [])
                mags  = self.model.get("mag", [])
                phase = self.model.get("phase", [])

                c.setFont("Helvetica-Bold", 10)
                c.drawString(40, y, "Index")
                c.drawString(120, y, "Frequency (Hz)")
                c.drawString(260, y, "Magnitude (dB)")
                c.drawString(400, y, "Phase (Deg)")
                y -= 18
  
                c.setFont("Helvetica", 10)
                for i, f in enumerate(freqs):
                  if y < 80:
                     c.showPage()
                     self._draw_header(c, page_width, page_height, report_no, title_text)
                     y = page_height - 100

                     mag = mags[i] if i < len(mags) else ""
                     ph  = phase[i] if i < len(phase) else ""

                     c.drawString(40, y, str(i+1))
                     c.drawString(120, y, str(f))
                     c.drawString(260, y, str(mag))
                     c.drawString(400, y, str(ph))

                     y -= 16


            elif si == 3:
                cs = self.model.get("curve_stats", {}) or {}
                stats_text = (
                    f"Min mag: {cs.get('min_mag','n/a')}  "
                    f"Max mag: {cs.get('max_mag','n/a')}  "
                    f"Phase mean: {cs.get('phase_mean','n/a')}"
                )
                c.setFont("Helvetica", 10)
                c.drawString(40, y, stats_text)
                y -= 24

                graphs = self.model.get("graph_images", {}) or {}

                if graphs:
                    title_map = {
                        "modal_spectrum_bands": "Modal Frequencies + Spectrum Energy Bands",
                        "baseline_vs_current": "Baseline vs Current SFRA Comparison",
                        "peak_activation": "Peak Activation Map — Feature Importance",
                        "delta_damage_locator": "Delta Comparison Curve — Damage Locator",
                        "fault_severity": "Fault Severity Gauge",
                        "midband_turbulence": "Mid-band Turbulence & HF Decay",
                    }
                    ordered_keys = GRAPH_KEYS_ORDER or list(graphs.keys())

                    for key in ordered_keys:
                        path = graphs.get(key)
                        if not path or not os.path.exists(path):
                            continue

                        if y < 160:
                            c.showPage()
                            self._draw_header(c, page_width, page_height, report_no, title_text)
                            y = page_height - 100

                        title = title_map.get(
                            key,
                            key.replace("_", " ").title()
                        )
                        c.setFont("Helvetica-Bold", 12)
                        c.drawString(40, y, title)
                        y -= 18

                        self._embed_image(
                            c,
                            path,
                            x=60,
                            y=y,
                            max_w=page_width - 120,
                            max_h=260,
                        )
                        y -= 280
                else:
                    graph_img_path = self._resolve_graph_image(preferred_key="modal_spectrum_bands")
                    if graph_img_path:
                        self._embed_image(
                            c,
                            graph_img_path,
                            60,
                            y,
                            max_w=page_width - 120,
                            max_h=300,
                        )
                        y -= 320
                    else:
                        c.setFont("Helvetica", 10)
                        c.drawString(
                            40,
                            y,
                            "No pipeline graph image found in pipeline_data['graph_images'] "
                            f"or at legacy {GRAPH_PATH}",
                        )
                        y -= 20

            elif si == 4:
                perf_rows = [
                    ("Core Loss (W)", self._get_model_value("transformer_performance.loss_estimates.core_loss_watts") or ""),
                    ("Load Loss (W)", self._get_model_value("transformer_performance.loss_estimates.load_loss_watts") or ""),
                    ("Impedance %Z", self._get_model_value("transformer_performance.impedance_pct") or ""),
                    ("% R at 33°C", self._get_model_value("transformer_performance.r_at_33") or ""),
                    ("Total Loss (W)", self._get_model_value("transformer_performance.total_loss_watts") or ""),
                    ("Efficiency @ unity (%)", self._get_model_value("transformer_performance.eff_unity") or ""),
                    ("Efficiency @ 0.8 pf (%)", self._get_model_value("transformer_performance.eff_08pf") or ""),
                ]
                y = self._draw_fields_table(c, page_width, y, perf_rows, left_margin=40)

            elif si == 5:
                tested = self.model.get("tested_by", {}) or {}
                auth_name = self.field_vars.get("authority.name", None)
                authority_name = auth_name.get() if hasattr(auth_name, "get") else (tested.get("authority_name", "") or "")
                rows = [
                    ("Name", tested.get("name", "")),
                    ("Designation", tested.get("designation", "")),
                    ("Authority", authority_name),
                ]
                y = self._draw_fields_table(c, page_width, y, rows, left_margin=40)
                y -= 10
                sigp = tested.get("signature", "")
                authp = tested.get("authority_signature", "")
                if sigp and os.path.exists(sigp) and authp and os.path.exists(authp):
                    max_w = (page_width - 140) / 2.0
                    max_h = 120
                    self._embed_image(c, sigp, 60, y, max_w=max_w, max_h=max_h)
                    self._embed_image(c, authp, page_width - 60 - max_w, y, max_w=max_w, max_h=max_h)
                    y -= (max_h + 10)
                else:
                    if sigp and os.path.exists(sigp):
                        self._embed_image(c, sigp, 60, y, max_w=200, max_h=120)
                        y -= 140
                    if authp and os.path.exists(authp):
                        self._embed_image(c, authp, 60, y, max_w=200, max_h=120)
                        y -= 140

            # finish section page
            c.showPage()

        c.save()
        return out_path

    def generate_full_pdf_and_preview(self):
        try:
            self._ensure_reportlab_installed()
        except Exception as e:
            messagebox.showerror("PDF error", str(e))
            return
        try:
            out = self.generate_full_pdf()
            try:
                self._open_file_preview(out)
            except Exception:
                messagebox.showinfo("PDF saved", f"Full PDF saved to: {out}")
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Generated full PDF: {out}", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Generate PDF", str(e))
            if hasattr(self.app, "log_console"):
                self.app.log_console(f"Generate full PDF error: {e}", "ERROR")


# End of file
