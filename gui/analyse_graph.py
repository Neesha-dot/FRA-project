"""
Analyze Graph Module
Loads a TreeView dashboard (workspace + preview + metadata)
Includes ML integration (loads pickled model that expects runtime helpers)
"""

import os
import sys
import json
import pickle
import inspect
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------
# IMPORT RUNTIME HELPERS (required by pickle)
# ---------------------------------------------------------------------
import ML.sfra_runtime

import analyse_graph2 as graph_tools

# expose runtime helper names expected by pickled model code
sys.modules['__main__'].extract_features   = ML.sfra_runtime.extract_features
sys.modules['__main__'].predict_fault      = ML.sfra_runtime.predict_fault
sys.modules['__main__'].parse_metadata     = ML.sfra_runtime.parse_metadata
sys.modules['__main__'].parse_tap_table    = ML.sfra_runtime.parse_tap_table
sys.modules['__main__'].calculate_losses   = ML.sfra_runtime.calculate_losses
sys.modules['__main__'].diagnose_with_taps = ML.sfra_runtime.diagnose_with_taps
sys.modules['__main__'].SFRA_Model4_Final  = ML.sfra_runtime.SFRA_Model4_Final

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "ML",
    "sfra_model4_v2.pkl"
)

# ----------------------------------------------------------
# JSON SAFE CONVERTER
# ----------------------------------------------------------
def make_json_safe(obj):
    import numpy as _np
    if isinstance(obj, (_np.generic,)):
        return obj.item()
    if isinstance(obj, _np.ndarray):
        return obj.tolist()
    if isinstance(obj, (list, tuple, set)):
        return [make_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()}
    return obj


# =====================================================================
#   MAIN ENABLE FUNCTION
# =====================================================================
def enable_analyse_graph(app):
    main_app = app

    def dbg(label, obj):
        try:
            main_app.log_console(
                f"[DEBUG] {label} -> type={type(obj)}, "
                f"is_dict={isinstance(obj, dict)}, is_ndarray={hasattr(obj, 'shape')}",
                "INFO"
            )
        except Exception:
            print("[DEBUG]", label, type(obj))

    # Panels expected on main_app
    workspace      = main_app.workspace_scrollable
    preview_panel  = main_app.center_scrollable
    metadata_panel = main_app.metadata_content

    _analysis_controls_holder = None

    # =================================================================
    # UI UTILITIES
    # =================================================================
    def clear_panel(panel):
        for w in panel.winfo_children():
            w.destroy()

    def show_preview_text_direct(container, text, height=14):
        """Create a simple text block inside given container (no clearing)."""
        f = tk.Frame(container, bg="white")
        f.pack(fill=tk.X, anchor="nw")
        t = tk.Text(
            f, wrap=tk.WORD, font=("Segoe UI", 11),
            bg="white", relief=tk.FLAT, padx=15, pady=15, height=height
        )
        t.insert(tk.END, text)
        t.config(state=tk.DISABLED)
        # 🔧 yahan fix: t.pack(fill(tk.X)) → t.pack(fill=tk.X)
        t.pack(fill=tk.X)
        return f

    def show_preview_text(text):
        clear_panel(preview_panel)
        show_preview_text_direct(preview_panel, text)
        nonlocal _analysis_controls_holder
        _analysis_controls_holder = tk.Frame(preview_panel, bg="white")
        _analysis_controls_holder.pack(fill=tk.X, pady=8)

    def update_preview(msg):
        show_preview_text(msg)

    def coerce_output_to_dict(output):
        if isinstance(output, dict):
            return output
        return {
            "raw_output": output,
            "features_used": {},
            "universal_fault_labels": [],
            "metadata": {},
            "loss_and_efficiency": {},
        }

    # =================================================================
    # SHARED CARD / WIDGET HELPERS
    # =================================================================
    def create_card(parent, title=None, pad_top=True):
        """Material-style card with optional section title."""
        top_pad = (12, 8) if pad_top else (0, 8)
        card = tk.Frame(
            parent,
            bg="white",
            highlightbackground="#E0E0E0",
            highlightthickness=1,
            bd=0,
        )
        card.pack(fill=tk.X, padx=16, pady=top_pad)

        inner = tk.Frame(card, bg="white")
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        if title:
            tk.Label(
                inner,
                text=title,
                font=("Segoe UI", 11, "bold"),
                bg="white",
                fg="#333333",
            ).pack(anchor="w", pady=(0, 4))

        return inner

    def add_section_caption(parent, text):
        tk.Label(
            parent,
            text=text,
            font=("Segoe UI", 9),
            bg="white",
            fg="#757575",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(0, 4))

    def draw_hbar(parent, label, value_text, pct, bar_color="#1976D2", accent="#E0E0E0"):
        """Reusable horizontal percentage bar."""
        wrap = tk.Frame(parent, bg="white")
        wrap.pack(fill=tk.X, pady=3)

        header = tk.Frame(wrap, bg="white")
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text=label,
            font=("Segoe UI", 9),
            bg="white",
            fg="#555555",
        ).pack(side=tk.LEFT, anchor="w")

        if value_text is not None:
            tk.Label(
                header,
                text=value_text,
                font=("Segoe UI", 9, "bold"),
                bg="white",
                fg="#111111",
            ).pack(side=tk.RIGHT, anchor="e")

        c = tk.Canvas(
            wrap,
            height=10,
            bg="white",
            highlightthickness=0,
            bd=0,
        )
        c.pack(fill=tk.X, expand=True, pady=(2, 0))

        w = 260
        pct = max(0.0, min(100.0, float(pct)))
        c.create_rectangle(0, 0, w, 10, fill=accent, outline=accent)
        fill_w = w * (pct / 100.0)
        c.create_rectangle(0, 0, fill_w, 10, fill=bar_color, outline=bar_color)

    def add_metric_tiles(parent, metrics, cols=2):
        """
        metrics = [(title, main_value, subtitle), ...]
        Builds small grey tiles like in Fault Classification.
        """
        grid = tk.Frame(parent, bg="white")
        grid.pack(fill=tk.X, pady=(4, 0))

        row = col = 0
        for title, main_value, subtitle in metrics:
            tile = tk.Frame(
                grid,
                bg="#F5F5F5",
                highlightbackground="#E0E0E0",
                highlightthickness=1,
            )
            tile.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            tk.Label(
                tile,
                text=title,
                font=("Segoe UI", 8, "bold"),
                bg="#F5F5F5",
                fg="#424242",
            ).pack(anchor="w", padx=6, pady=(4, 0))

            tk.Label(
                tile,
                text=main_value,
                font=("Segoe UI", 10),
                bg="#F5F5F5",
                fg="#000000",
            ).pack(anchor="w", padx=6)

            if subtitle:
                tk.Label(
                    tile,
                    text=subtitle,
                    font=("Segoe UI", 8),
                    bg="#F5F5F5",
                    fg="#757575",
                    wraplength=160,
                    justify="left",
                ).pack(anchor="w", padx=6, pady=(0, 4))

            col += 1
            if col >= cols:
                col = 0
                row += 1

    def add_process_steps(parent, steps):
        """
        steps = [(label, status, description), ...]
        status in {"pending", "running", "done"}
        """
        wrap = tk.Frame(parent, bg="white")
        wrap.pack(fill=tk.X, pady=(4, 0))

        for label, status, desc in steps:
            row = tk.Frame(wrap, bg="white")
            row.pack(fill=tk.X, pady=3)

            if status == "done":
                icon = "✅"
                color = "#4CAF50"
            elif status == "running":
                icon = "⏳"
                color = "#1976D2"
            else:
                icon = "•"
                color = "#B0BEC5"

            tk.Label(
                row,
                text=icon,
                font=("Segoe UI", 11),
                bg="white",
                fg=color,
                width=2,
            ).pack(side=tk.LEFT)

            text_frame = tk.Frame(row, bg="white")
            text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(
                text_frame,
                text=label,
                font=("Segoe UI", 9, "bold"),
                bg="white",
                fg="#333333",
            ).pack(anchor="w")

            if desc:
                tk.Label(
                    text_frame,
                    text=desc,
                    font=("Segoe UI", 8),
                    bg="white",
                    fg="#757575",
                    wraplength=380,
                    justify="left",
                ).pack(anchor="w")

    helpers = {
        "clear_panel": clear_panel,
        "create_card": create_card,
        "add_section_caption": add_section_caption,
        "draw_hbar": draw_hbar,
        "add_metric_tiles": add_metric_tiles,
    }

    # =================================================================
    # RIGHT-SIDE METADATA PANEL
    # =================================================================
    def update_metadata_panel(md, freq_array, mag_array):
        clear_panel(metadata_panel)
        wrap = tk.Frame(metadata_panel, bg="white")
        wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        file_path = getattr(main_app, "homepage_current_file", "Unknown File")
        file_name = os.path.basename(file_path) if file_path else "Unknown File"

        tk.Label(wrap, text="File Summary",
                 font=("Segoe UI", 12, "bold"), bg="white").pack(anchor="w")

        tk.Label(wrap, text=f"File: {file_name}",
                 font=("Segoe UI", 10), bg="white").pack(anchor="w", pady=(3, 0))

        if isinstance(md, dict):
            info = []
            if md.get("Company"):
                info.append(f"Company: {md['Company']}")
            if md.get("Location"):
                info.append(f"Location: {md['Location']}")

            if info:
                tk.Label(wrap, text=" | ".join(info),
                         font=("Segoe UI", 9), bg="white").pack(anchor="w", pady=(2, 4))

        # ---------------- Peaks ----------------
        def get_top_peaks(freq, mag, max_peaks=10):
            try:
                f = np.asarray(freq, float).reshape(-1)
                m = np.asarray(mag, float).reshape(-1)
            except Exception:
                return []
            if len(f) == 0 or len(f) != len(m):
                return []

            idx = []
            for i in range(1, len(f)-1):
                if m[i] >= m[i-1] and m[i] >= m[i+1]:
                    idx.append(i)

            if not idx:
                idx = list(range(len(f)))

            idx.sort(key=lambda i: m[i], reverse=True)
            idx = idx[:max_peaks]
            idx.sort(key=lambda i: f[i])

            return [(f[i], m[i]) for i in idx]

        try:
            peaks = get_top_peaks(freq_array, mag_array)
            if peaks:
                tk.Label(wrap, text="Top 10 Frequencies (Hz):",
                         font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w", pady=(8, 2))
                for f0, _m in peaks:
                    tk.Label(wrap, text=f"- {f0:.2f}",
                             font=("Segoe UI", 9), bg="white").pack(anchor="w")
        except Exception:
            pass

    # =================================================================
    # SHOW ML METADATA (Main Summary View)
    # =================================================================
    def show_ml_metadata():
        clear_panel(preview_panel)

        pdata = getattr(main_app, "pipeline_data", {})
        ml_out = pdata.get("ml_output", {})

        report = coerce_output_to_dict(ml_out.get("report"))
        if not isinstance(report, dict) or not report:
            show_preview_text("⚠ No ML report available.\nRun 'Start Analysis' first.")
            return

        file_path = report.get("file") or getattr(main_app, "homepage_current_file", None)
        file_name = os.path.basename(file_path) if file_path else "Unknown File"

        md     = report.get("metadata", {}) or {}
        feats  = report.get("features_used", {}) or {}
        losses = report.get("loss_and_efficiency", {}) or {}
        faults = report.get("universal_fault_labels", ["healthy"]) or ["healthy"]

        fault = faults[0] if faults else "healthy"
        fault_label = str(fault).replace("_", " ").title()

        # --- severity / confidence / reason ---
        severity_raw = str(report.get("severity", "none")).upper()
        try:
            conf = float(report.get("confidence", 0.5) * 100.0)
        except Exception:
            conf = 50.0
        conf = max(0.0, min(100.0, conf))
        reason = str(report.get("reason", "No abnormality detected."))

        sev_color_map = {
            "NONE":   "#4CAF50",
            "LOW":    "#8BC34A",
            "MEDIUM": "#FFC107",
            "HIGH":   "#F44336",
        }
        sev_color = sev_color_map.get(severity_raw, "#90A4AE")

        # --- metadata fallback/normalization (same as before) ---
        if not isinstance(md, dict):
            md = {}

        def _looks_default(mm: dict):
            if not mm:
                return True
            s = mm.get("serial") or mm.get("SerialNumber")
            m = mm.get("manufacturer") or mm.get("Manufacturer")
            if s in (None, "", "UNKNOWN") and m in (None, "", "UNKNOWN"):
                return True
            return False

        if _looks_default(md):
            header_meta = getattr(main_app, "homepage_header_metadata", {}) or {}
            if isinstance(header_meta, dict) and header_meta:
                md = header_meta

        if isinstance(md, dict) and md:
            md = dict(md)
            if "manufacturer" in md and "Manufacturer" not in md:
                md["Manufacturer"] = md["manufacturer"]
            if "serial" in md and "SerialNumber" not in md:
                md["SerialNumber"] = md["serial"]
            if "year" in md and "ManufactureYear" not in md:
                md["ManufactureYear"] = md["year"]
            if "start_freq" in md and "StartFrequency" not in md:
                md["StartFrequency"] = md["start_freq"]
            if "stop_freq" in md and "StopFrequency" not in md:
                md["StopFrequency"] = md["stop_freq"]

        raw_freq = pdata.get("freq", [])
        raw_mag  = pdata.get("mag", [])
        try:
            freq_array = np.asarray(raw_freq, float).reshape(-1)
        except Exception:
            freq_array = None
        try:
            mag_array = np.asarray(raw_mag, float).reshape(-1)
        except Exception:
            mag_array = None

        # --- features snapshot ---
        def f_feat(name, default=0.0):
            try:
                v = feats.get(name, default)
                return float(v if v is not None else default)
            except Exception:
                return float(default)

        E_low  = abs(f_feat("E_low"))
        E_mid  = abs(f_feat("E_mid"))
        E_high = abs(f_feat("E_high"))
        total_E = max(E_low + E_mid + E_high, 1e-6)

        pct_low  = (E_low  / total_E) * 100.0
        pct_mid  = (E_mid  / total_E) * 100.0
        pct_high = (E_high / total_E) * 100.0

        turb   = f_feat("midband_turbulence")
        hf_dec = f_feat("hf_decay_rate")
        g_att  = f_feat("global_attenuation")

        # --- losses snapshot ---
        def f_loss(name, default=0.0):
            try:
                v = losses.get(name, default)
                return float(v if v is not None else default)
            except Exception:
                return float(default)

        core_loss  = f_loss("core_loss_w")
        load_loss  = f_loss("load_loss_w")
        total_loss = f_loss("total_loss_w")
        eff_1      = f_loss("efficiency_unity_pf")
        eff_08     = f_loss("efficiency_0.8_pf")

        if total_loss == 0 and (abs(core_loss) + abs(load_loss)) > 0:
            total_loss = core_loss + load_loss

        # ================== ROOT LAYOUT ==================
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        # -------- Card 1: Diagnosis Overview --------
        card_top = tk.Frame(
            root,
            bg="white",
            highlightbackground="#E0E0E0",
            highlightthickness=1,
            bd=0,
        )
        card_top.pack(fill=tk.X, padx=16, pady=(12, 8))

        left = tk.Frame(card_top, bg="white")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=10)

        right = tk.Frame(card_top, bg="white")
        right.pack(side=tk.RIGHT, padx=12, pady=10)

        tk.Label(
            left,
            text="Analysis Result Overview",
            font=("Segoe UI", 13, "bold"),
            bg="white",
            fg="#212121",
        ).pack(anchor="w")

        tk.Label(
            left,
            text=f"File: {file_name}",
            font=("Segoe UI", 9),
            bg="white",
            fg="#555555",
        ).pack(anchor="w", pady=(2, 0))

        pill = tk.Frame(left, bg="white")
        pill.pack(anchor="w", pady=(8, 2))

        tk.Label(
            pill,
            text=fault_label,
            font=("Segoe UI", 11, "bold"),
            bg="white",
            fg="#111111",
        ).pack(side=tk.LEFT)

        tk.Label(
            pill,
            text=severity_raw.title(),
            font=("Segoe UI", 9, "bold"),
            bg=sev_color,
            fg="white",
            padx=8,
            pady=2,
        ).pack(side=tk.LEFT, padx=(10, 0))

        if reason:
            tk.Label(
                left,
                text=reason,
                font=("Segoe UI", 9),
                bg="white",
                fg="#555555",
                wraplength=380,
                justify="left",
            ).pack(anchor="w", pady=(6, 0))

        # confidence bar on right
        tk.Label(
            right,
            text="Model confidence",
            font=("Segoe UI", 9),
            bg="white",
            fg="#555555",
        ).pack(anchor="w")

        conf_canvas = tk.Canvas(
            right,
            height=12,
            width=160,
            bg="white",
            highlightthickness=0,
            bd=0,
        )
        conf_canvas.pack(anchor="w", pady=(2, 0))

        conf_canvas.create_rectangle(0, 0, 160, 12, fill="#E0E0E0", outline="#E0E0E0")
        w_conf = 160 * (conf / 100.0)
        conf_canvas.create_rectangle(0, 0, w_conf, 12, fill="#1976D2", outline="#1976D2")
        conf_canvas.create_text(
            160 - 4,
            6,
            text=f"{conf:4.1f}%",
            anchor="e",
            font=("Segoe UI", 8),
            fill="#111111",
        )

        tk.Label(
            right,
            text="This summarises the ML model output. Use other tabs for detailed features.",
            font=("Segoe UI", 8),
            bg="white",
            fg="#9E9E9E",
            wraplength=180,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        # -------- Card 2: Pipeline Flow (now 'completed') --------
        card_flow = create_card(root, "Analysis Flow Status")

        steps_done = [
            (
                "1. Feature Extraction",
                "done",
                "Modal frequencies, band energies, turbulence and HF indicators were derived from the raw sweep.",
            ),
            (
                "2. Energy Bands & Turbulence",
                "done",
                "Energy distribution across Low / Mid / High bands and mid-band roughness have been computed.",
            ),
            (
                "3. HF Decay & Attenuation",
                "done",
                "Global attenuation and HF decay trends are available in their dedicated views.",
            ),
            (
                "4. Loss & Efficiency (Model Space)",
                "done",
                "Core/load loss and efficiency estimates were produced from learned patterns.",
            ),
            (
                "5. Fault Classification",
                "done",
                "All features were fused into the final fault type, severity and confidence shown above.",
            ),
        ]
        add_process_steps(card_flow, steps_done)

        # -------- Card 3: Key Numeric Snapshots --------
        card_metrics = create_card(root, "Key Numeric Snapshots", pad_top=False)

        metrics = [
            ("E_low (0–2 kHz)", f"{E_low:.3f}", f"{pct_low:5.2f}% of total band energy"),
            ("E_mid (2–20 kHz)", f"{E_mid:.3f}", f"{pct_mid:5.2f}% of total band energy"),
            ("E_high (>20 kHz)", f"{E_high:.3f}", f"{pct_high:5.2f}% of total band energy"),
            ("Mid-band turbulence", f"{turb:.3f}", "Roughness of the 2–20 kHz window."),
            ("HF decay rate", f"{hf_dec:.6f}", "Trend of magnitude roll-off at high frequencies."),
            ("Global attenuation", f"{g_att:.3f} dB", "Magnitude drop across the full sweep."),
        ]
        add_metric_tiles(card_metrics, metrics, cols=3)

        # Loss & efficiency quick glance (if available)
        if any(abs(x) > 0 for x in (core_loss, load_loss, total_loss, eff_1, eff_08)):
            card_loss = create_card(root, "Loss & Efficiency Snapshot", pad_top=False)

            loss_metrics = [
                ("Core loss", f"{core_loss:,.2f} W", ""),
                ("Load loss", f"{load_loss:,.2f} W", ""),
                ("Total loss", f"{total_loss:,.2f} W", ""),
                ("Eff @1.0 pf", f"{eff_1:5.2f} %", ""),
                ("Eff @0.8 pf", f"{eff_08:5.2f} %", ""),
            ]
            add_metric_tiles(card_loss, loss_metrics, cols=3)

            tk.Label(
                card_loss,
                text="Full details are available in the 'Loss & Efficiency' view.",
                font=("Segoe UI", 8),
                bg="white",
                fg="#9E9E9E",
            ).pack(anchor="w", pady=(4, 0))

        # -------- Card 4: Metadata --------
        card_meta = create_card(root, "File Metadata", pad_top=False)

        if isinstance(md, dict) and md:
            for k, v in md.items():
                tk.Label(
                    card_meta,
                    text=f"{k}: {v}",
                    font=("Segoe UI", 9),
                    bg="white",
                    fg="#555555",
                    wraplength=420,
                    justify="left",
                ).pack(anchor="w")
        else:
            tk.Label(
                card_meta,
                text="Metadata not available.",
                font=("Segoe UI", 9),
                bg="white",
                fg="#555555",
            ).pack(anchor="w")

        # Update right-side metadata panel (peaks etc.)
        update_metadata_panel(md, freq_array, mag_array)

    
    # =================================================================
    #   ANALYSIS VIEWS (excluding Fault Classification)
    # =================================================================

    # -------------------------------------------------------
    # Modal Frequencies View
    # -------------------------------------------------------
    def show_modal_frequencies():
        pdata = getattr(main_app, "pipeline_data", None)
        dbg("show_modal_frequencies: pipeline_data", pdata)

        if not isinstance(pdata, dict):
            show_preview_text("⚠ No analysis data.\n\nRun 'Start Analysis' first.")
            return

        ml_out = pdata.get("ml_output", {})
        if not isinstance(ml_out, dict) or not ml_out.get("report"):
            show_preview_text("⚠ No ML report found.\nRun 'Start Analysis' first.")
            return

        report = coerce_output_to_dict(ml_out.get("report"))
        feats  = report.get("features_used", {}) or {}

        def _f(name, default=0.0):
            try:
                v = feats.get(name, default)
                return float(v if v is not None else default)
            except Exception:
                return float(default)

        modal_1 = _f("modal_1")
        modal_2 = _f("modal_2")
        modal_3 = _f("modal_3")
        spacing = abs(_f("modal_spacing_index"))

        clear_panel(preview_panel)
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        # Card 1 – modes summary
        inner_modes = create_card(root, "Modal Frequency Overview")

        metrics = [
            ("Mode 1", f"{modal_1:.3f} Hz", "First dominant resonance."),
            ("Mode 2", f"{modal_2:.3f} Hz", "Second dominant resonance."),
            ("Mode 3", f"{modal_3:.3f} Hz", "Third dominant resonance."),
        ]
        add_metric_tiles(inner_modes, metrics, cols=3)

        # Card 2 – spacing insight
        inner_spacing = create_card(root, "Spacing & Layout", pad_top=False)

        # Normalize spacing for bar (just for visual)
        spacing_display = min(max(spacing, 0.0), 50000.0)  # clamp
        pct_spacing = (spacing_display / 50000.0) * 100.0

        draw_hbar(
            inner_spacing,
            "Modal spacing index",
            f"{spacing:.3f} Hz",
            pct_spacing,
            bar_color="#3F51B5",
        )

        tk.Label(
            inner_spacing,
            text=(
                "Modal frequencies describe core + winding resonance behaviour. "
                "The spacing index captures how well-separated these resonances are "
                "in frequency, which influences how sensitive the response is to "
                "mechanical changes."
            ),
            font=("Segoe UI", 9),
            bg="white",
            fg="#555555",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        tk.Label(
            inner_spacing,
            text="Note: This view is descriptive only – no pass/fail judgement is made here.",
            font=("Segoe UI", 8, "italic"),
            bg="white",
            fg="#9E9E9E",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

    # -------------------------------------------------------
    # Energy Bands View
    # -------------------------------------------------------
    def show_energy_bands():
        pdata = getattr(main_app, "pipeline_data", None)
        dbg("show_energy_bands: pipeline_data", pdata)

        if not isinstance(pdata, dict):
            show_preview_text("⚠ No analysis data.\nRun 'Start Analysis' first.")
            return

        ml_out = pdata.get("ml_output", {})
        if not isinstance(ml_out, dict) or not ml_out.get("report"):
            show_preview_text("⚠ No ML report found.\nClick 'Start Analysis'.")
            return

        report = coerce_output_to_dict(ml_out.get("report"))
        feats  = report.get("features_used", {}) or {}

        def _f(name, default=0.0):
            try:
                v = feats.get(name, default)
                return float(v if v is not None else default)
            except Exception:
                return float(default)

        E_low  = _f("E_low")
        E_mid  = _f("E_mid")
        E_high = _f("E_high")

        turb   = _f("midband_turbulence")
        hf_dec = _f("hf_decay_rate")

        try:
            freq_array = np.asarray(pdata.get("freq", []), float).reshape(-1)
            mag_array  = np.asarray(pdata.get("mag",  []), float).reshape(-1)
        except Exception:
            freq_array = np.array([])
            mag_array  = np.array([])

        # Fallback integration if needed
        if (E_low == 0 and E_mid == 0 and E_high == 0) and \
           (freq_array.size > 0 and freq_array.size == mag_array.size):

            low_mask  = freq_array < 2000
            mid_mask  = (freq_array >= 2000) & (freq_array < 20000)
            high_mask = freq_array >= 20000

            if np.any(low_mask):
                E_low  = float(np.trapz(mag_array[low_mask],  freq_array[low_mask]))
            if np.any(mid_mask):
                E_mid  = float(np.trapz(mag_array[mid_mask],  freq_array[mid_mask]))
            if np.any(high_mask):
                E_high = float(np.trapz(mag_array[high_mask], freq_array[high_mask]))

        abs_low  = abs(E_low)
        abs_mid  = abs(E_mid)
        abs_high = abs(E_high)
        total_E  = abs_low + abs_mid + abs_high

        if total_E > 0:
            p_low  = abs_low  / total_E * 100
            p_mid  = abs_mid  / total_E * 100
            p_high = abs_high / total_E * 100
        else:
            p_low = p_mid = p_high = 0

        # pattern tag
        if p_mid >= max(p_low, p_high) and 40 <= p_mid <= 70:
            pattern = "MID band dominates – close to a typical reference profile."
        elif p_high > p_mid and p_high > 50:
            pattern = "HIGH band dominates – response weighted to higher frequencies."
        elif p_low > 30:
            pattern = "LOW band dominates – strong low-frequency behaviour."
        else:
            pattern = "Mixed distribution across bands."

        clear_panel(preview_panel)
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        # Card 1 – band distribution
        inner_dist = create_card(root, "Fault Signature Map (Energy Zones)")

        add_section_caption(
            inner_dist,
            "Relative energy captured in three SFRA bands. Bars show normalized "
            "share of the total integrated response magnitude.",
        )

        draw_hbar(
            inner_dist,
            "Low (0–2 kHz)",
            f"{E_low:.3f}",
            p_low,
            bar_color="#4CAF50",
        )
        draw_hbar(
            inner_dist,
            "Mid (2–20 kHz)",
            f"{E_mid:.3f}",
            p_mid,
            bar_color="#2196F3",
        )
        draw_hbar(
            inner_dist,
            "High (20 kHz – 1 MHz)",
            f"{E_high:.3f}",
            p_high,
            bar_color="#FF9800",
        )

        tk.Label(
            inner_dist,
            text=f"Dominant pattern: {pattern}",
            font=("Segoe UI", 9, "bold"),
            bg="white",
            fg="#424242",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        # Card 2 – indicators & sweep context
        inner_meta = create_card(root, "Band-related Indicators", pad_top=False)

        metrics = [
            ("Mid-band turbulence", f"{turb:.3f}", "Local roughness in 2–20 kHz window."),
            ("HF decay rate", f"{hf_dec:.6f}", "Slope of roll-off beyond 20 kHz."),
        ]

        if freq_array.size > 0:
            low_pts  = int(np.sum(freq_array < 2000))
            mid_pts  = int(np.sum((freq_array >= 2000) & (freq_array < 20000)))
            high_pts = int(np.sum(freq_array >= 20000))

            metrics.extend([
                ("Points in LOW", str(low_pts), "Number of samples below 2 kHz."),
                ("Points in MID", str(mid_pts), "Samples between 2–20 kHz."),
                ("Points in HIGH", str(high_pts), "Samples above 20 kHz."),
            ])

        add_metric_tiles(inner_meta, metrics, cols=2)


    # -------------------------------------------------------
    # Turbulence View
    # -------------------------------------------------------
    def show_turbulence():
        pdata = getattr(main_app, "pipeline_data", None)
        dbg("show_turbulence: pipeline_data", pdata)

        if not isinstance(pdata, dict):
            show_preview_text("⚠ No analysis data.\nRun 'Start Analysis'.")
            return

        ml_out = pdata.get("ml_output", {})
        if not isinstance(ml_out, dict) or not ml_out.get("report"):
            show_preview_text("⚠ No ML report.\nClick 'Start Analysis'.")
            return

        report = coerce_output_to_dict(ml_out.get("report"))
        feats  = report.get("features_used", {}) or {}

        def _f(n, d=0.0):
            try:
                v = feats.get(n, d)
                return float(v if v is not None else d)
            except Exception:
                return float(d)

        global_turb = _f("midband_turbulence")

        try:
            freq = np.asarray(pdata.get("freq", []), float).reshape(-1)
            mag  = np.asarray(pdata.get("mag",  []), float).reshape(-1)
        except Exception:
            freq = np.array([])
            mag  = np.array([])

        if freq.size == 0 or freq.size != mag.size:
            show_preview_text("🌪 Mid-band Turbulence\n\nSweep data unavailable.")
            return

        mid_mask = (freq >= 2000) & (freq < 20000)
        mid_idx  = np.nonzero(mid_mask)[0]

        if mid_idx.size < 10:
            show_preview_text("🌪 Mid-band Turbulence\n\nNot enough mid-band points.")
            return

        segments = np.array_split(mid_idx, 6)
        seg_info = []
        for sg in segments:
            if sg.size < 3:
                continue
            seg_freq = freq[sg]
            seg_mag  = mag[sg]
            diff     = np.diff(seg_mag)
            t_val    = float(np.nanstd(diff)) if diff.size > 0 else 0.0
            center_f = float(np.mean(seg_freq))
            seg_info.append((center_f, t_val))

        if not seg_info:
            show_preview_text("🌪 Mid-band Turbulence\n\nUnable to compute profile.")
            return

        max_t = max(t for _, t in seg_info) or 1.0

        if global_turb < 0.5:
            texture = "Smooth mid-band response surface."
        elif global_turb < 1.5:
            texture = "Moderately rippled mid-band response."
        else:
            texture = "Strongly rippled / disturbed mid-band response."

        clear_panel(preview_panel)
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        # Card 1 – global turbulence
        inner_global = create_card(root, "Mid-band Turbulence Overview")

        metrics = [
            ("Global turbulence index", f"{global_turb:.3f}", texture),
            ("Mid-band window", "2 – 20 kHz", "Region used to compute roughness."),
        ]
        add_metric_tiles(inner_global, metrics, cols=2)

        # Card 2 – segment roughness bars
        inner_seg = create_card(root, "Local Roughness by Segment", pad_top=False)

        add_section_caption(
            inner_seg,
            "Each bar represents local roughness in a slice of the 2–20 kHz band "
            "(higher bar = more variation in magnitude between points).",
        )

        for cf, tv in seg_info:
            pct = (tv / max_t) * 100.0
            label = f"~ {cf/1000.0:.1f} kHz"
            draw_hbar(
                inner_seg,
                label,
                f"{tv:.4f}",
                pct,
                bar_color="#009688",
            )

        tk.Label(
            inner_seg,
            text=f"Mid-band points: {mid_idx.size}  •  Total sweep points: {freq.size}",
            font=("Segoe UI", 8),
            bg="white",
            fg="#777777",
        ).pack(anchor="w", pady=(8, 0))


    # -------------------------------------------------------
    # HF Decay View
    # -------------------------------------------------------
    def show_hf_decay():
        pdata = getattr(main_app, "pipeline_data", None)
        dbg("show_hf_decay: pipeline_data", pdata)

        if not isinstance(pdata, dict):
            show_preview_text("⚠ No analysis data.")
            return

        ml_out = pdata.get("ml_output", {})
        if not isinstance(ml_out, dict) or not ml_out.get("report"):
            show_preview_text("⚠ No ML report.\nClick 'Start Analysis'.")
            return

        report = coerce_output_to_dict(ml_out.get("report"))
        feats  = report.get("features_used", {}) or {}

        def _f(n, d=0.0):
            try:
                v = feats.get(n, d)
                return float(v if v is not None else d)
            except Exception:
                return float(d)

        hf_rate_feature = _f("hf_decay_rate")

        try:
            freq = np.asarray(pdata.get("freq", []), float).reshape(-1)
            mag  = np.asarray(pdata.get("mag",  []), float).reshape(-1)
        except Exception:
            freq = np.array([])
            mag  = np.array([])

        if freq.size == 0 or freq.size != mag.size:
            show_preview_text("📉 High-frequency Decay\n\nSweep data unavailable.")
            return

        hf_mask = freq >= 20000
        hf_idx  = np.nonzero(hf_mask)[0]

        if hf_idx.size < 8:
            show_preview_text("📉 High-frequency Decay\n\nNot enough HF points.")
            return

        f_hf = freq[hf_idx]
        m_hf = mag[hf_idx]

        x = np.log10(f_hf)
        y = m_hf

        try:
            c_all = np.polyfit(x, y, 1)
            slope_dec = float(c_all[0])
        except Exception:
            slope_dec = 0.0

        mid = max(2, len(x) // 2)
        try:
            c_low  = np.polyfit(x[:mid],  y[:mid],  1)
            c_high = np.polyfit(x[mid:], y[mid:], 1)
            slope_low  = float(c_low[0])
            slope_high = float(c_high[0])
        except Exception:
            slope_low = slope_high = slope_dec

        if slope_dec > -10:
            style = "Very slow decay / almost flat HF response."
        elif slope_dec > -30:
            style = "Moderate HF decay."
        else:
            style = "Strong HF roll-off."

        f_start = float(f_hf[0])
        f_end   = float(f_hf[-1])

        clear_panel(preview_panel)
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        # Card 1 – global HF decay
        inner_main = create_card(root, "High-frequency Decay Profile")

        metrics = [
            ("Fitted slope (HF band)", f"{slope_dec:.3f} dB/dec", style),
            ("HF decay feature", f"{hf_rate_feature:.6f} dB/Hz", "Model-derived decay indicator."),
            ("HF span", f"{f_start:,.1f} → {f_end:,.1f} Hz", "Range used for decay fitting."),
        ]
        add_metric_tiles(inner_main, metrics, cols=2)

        # Card 2 – early vs late HF
        inner_seg = create_card(root, "Early vs Late HF Trend", pad_top=False)

        add_metric_tiles(
            inner_seg,
            [
                ("Overall HF slope", f"{slope_dec:.2f} dB/dec", "Aggregate trend over full HF region."),
                ("Early HF slope", f"{slope_low:.2f} dB/dec", "First half of HF band."),
                ("Late HF slope", f"{slope_high:.2f} dB/dec", "Second half of HF band."),
            ],
            cols=3,
        )

        tk.Label(
            inner_seg,
            text=f"HF points (≥20 kHz): {hf_idx.size}  •  Total sweep points: {freq.size}",
            font=("Segoe UI", 8),
            bg="white",
            fg="#777777",
        ).pack(anchor="w", pady=(8, 0))


    # -------------------------------------------------------
    # Attenuation View
    # -------------------------------------------------------
    def show_attenuation():
        pdata = getattr(main_app, "pipeline_data", None)
        dbg("show_attenuation: pipeline_data", pdata)

        if not isinstance(pdata, dict):
            show_preview_text("⚠ No analysis data.")
            return

        ml_out = pdata.get("ml_output", {})
        if not isinstance(ml_out, dict) or not ml_out.get("report"):
            show_preview_text("⚠ No ML report.\nRun 'Start Analysis'.")
            return

        report = coerce_output_to_dict(ml_out.get("report"))
        feats  = report.get("features_used", {}) or {}

        def _f(n, d=0.0):
            try:
                v = feats.get(n, d)
                return float(v if v is not None else d)
            except Exception:
                return float(d)

        global_att = _f("global_attenuation")

        try:
            freq = np.asarray(pdata.get("freq", []), float).reshape(-1)
            mag  = np.asarray(pdata.get("mag",  []), float).reshape(-1)
        except Exception:
            freq = np.array([])
            mag  = np.array([])

        clear_panel(preview_panel)
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        if freq.size < 3 or freq.size != mag.size:
            inner_simple = create_card(root, "Attenuation Overview")
            metrics = [
                ("Global attenuation", f"{global_att:.3f} dB", "Magnitude drop from start to end of sweep."),
            ]
            add_metric_tiles(inner_simple, metrics, cols=1)
            add_section_caption(
                inner_simple,
                "Sweep not sufficient for detailed attenuation profile.",
            )
            return

        m_start = mag[0]
        m_mid   = mag[len(mag) // 2]
        m_end   = mag[-1]

        att_mid = abs(m_start - m_mid)
        att_end = abs(m_start - m_end)

        n = freq.size
        seg_idx = [
            (0, n // 4),
            (n // 4, n // 2),
            (n // 2, 3 * n // 4),
            (3 * n // 4, n),
        ]

        seg_metrics = []
        for a, b in seg_idx:
            if b - a < 2:
                continue
            f0 = freq[a]
            f1 = freq[b - 1]
            m0 = mag[a]
            m1 = mag[b - 1]
            att = abs(m0 - m1)
            seg_metrics.append((f0, f1, att))

        max_seg = max((a for _, _, a in seg_metrics), default=1.0) or 1.0

        if att_end < 10:
            style = "Weak overall attenuation (fairly flat)."
        elif att_end < 40:
            style = "Moderate overall attenuation."
        else:
            style = "Strong overall attenuation across sweep."

        # Card 1 – global attenuation
        inner_global = create_card(root, "Global Attenuation")

        pct = max(0.0, min(100.0, (att_end / 60.0) * 100.0))
        draw_hbar(
            inner_global,
            "Start → End magnitude drop",
            f"{att_end:.3f} dB",
            pct,
            bar_color="#E91E63",
        )

        metrics = [
            ("ML global_attenuation", f"{global_att:.3f} dB", style),
            ("Sweep span", f"{freq[0]:,.1f} → {freq[-1]:,.1f} Hz", "Full frequency window."),
        ]
        add_metric_tiles(inner_global, metrics, cols=2)

        # Card 2 – reference points
        inner_points = create_card(root, "Reference Magnitudes", pad_top=False)

        metrics2 = [
            ("Start magnitude", f"{m_start:.3f}", ""),
            ("Mid-point magnitude", f"{m_mid:.3f}", f"Δ from start: {att_mid:.3f} dB"),
            ("End magnitude", f"{m_end:.3f}", f"Δ from start: {att_end:.3f} dB"),
        ]
        add_metric_tiles(inner_points, metrics2, cols=3)

        # Card 3 – segment-wise bars
        inner_seg = create_card(root, "Segment-wise Attenuation", pad_top=False)

        add_section_caption(
            inner_seg,
            "Local attenuation measured across four segments of the sweep.",
        )

        for f0, f1, att in seg_metrics:
            pct_seg = (att / max_seg) * 100.0
            label = f"{f0:,.1f} → {f1:,.1f} Hz"
            draw_hbar(
                inner_seg,
                label,
                f"{att:.3f} dB",
                pct_seg,
                bar_color="#9C27B0",
            )

        tk.Label(
            inner_seg,
            text=f"Total points: {n}",
            font=("Segoe UI", 8),
            bg="white",
            fg="#777777",
        ).pack(anchor="w", pady=(8, 0))


    # -------------------------------------------------------
    # Loss & Efficiency View
    # -------------------------------------------------------
    def show_loss_efficiency():
        pdata = getattr(main_app, "pipeline_data", None)
        dbg("show_loss_efficiency: pipeline_data", pdata)

        if not isinstance(pdata, dict):
            show_preview_text("⚠ No analysis data.")
            return

        ml_out = pdata.get("ml_output", {})
        if not isinstance(ml_out, dict) or not ml_out.get("report"):
            show_preview_text("⚠ No ML report.\nRun 'Start Analysis'.")
            return

        report  = coerce_output_to_dict(ml_out.get("report"))
        losses  = report.get("loss_and_efficiency", {}) or {}
        md_json = report.get("metadata", {}) or {}

        def _f_loss(n, d=0.0):
            try:
                v = losses.get(n, d)
                return float(v if v is not None else d)
            except Exception:
                return float(d)

        core_loss  = _f_loss("core_loss_w")
        load_loss  = _f_loss("load_loss_w")
        total_loss = _f_loss("total_loss_w")
        eff_1      = _f_loss("efficiency_unity_pf")
        eff_08     = _f_loss("efficiency_0.8_pf")
        Z_percent  = _f_loss("impedance_percent_z")
        R_33       = _f_loss("%R_33C")
        X_33       = _f_loss("%X_33C")

        if total_loss == 0 and (abs(core_loss) + abs(load_loss)) > 0:
            total_loss = core_loss + load_loss

        abs_core = abs(core_loss)
        abs_load = abs(load_loss)
        denom = abs_core + abs_load
        if denom > 0:
            pct_core = abs_core / denom * 100
            pct_load = abs_load / denom * 100
        else:
            pct_core = pct_load = 0

        if eff_1 >= 99:
            eff_tag = "High estimated efficiency."
        elif eff_1 >= 95:
            eff_tag = "Moderate-to-high estimated efficiency."
        else:
            eff_tag = "Reduced estimated efficiency."

        Z_note = "Approximate series impedance at rating (R & X at 33°C are components)."

        clear_panel(preview_panel)
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        # Card 1 – loss breakdown
        inner_loss = create_card(root, "Loss Breakdown")

        metrics = [
            ("Core loss (no-load)", f"{core_loss:,.2f} W", ""),
            ("Load loss (approx.)", f"{load_loss:,.2f} W", ""),
            ("Total estimated loss", f"{total_loss:,.2f} W", ""),
        ]
        add_metric_tiles(inner_loss, metrics, cols=3)

        draw_hbar(
            inner_loss,
            "Core share of total loss",
            f"{pct_core:5.2f} %",
            pct_core,
            bar_color="#FF9800",
        )
        draw_hbar(
            inner_loss,
            "Load share of total loss",
            f"{pct_load:5.2f} %",
            pct_load,
            bar_color="#03A9F4",
        )

        # Card 2 – efficiency gauges
        inner_eff = create_card(root, "Efficiency Snapshot", pad_top=False)

        draw_hbar(
            inner_eff,
            "@ 1.0 power factor",
            f"{eff_1:5.2f} %",
            eff_1,
            bar_color="#4CAF50",
        )
        draw_hbar(
            inner_eff,
            "@ 0.8 power factor",
            f"{eff_08:5.2f} %",
            eff_08,
            bar_color="#8BC34A",
        )

        tk.Label(
            inner_eff,
            text=eff_tag,
            font=("Segoe UI", 9),
            bg="white",
            fg="#555555",
        ).pack(anchor="w", pady=(6, 0))

        # Card 3 – impedance information
        inner_imp = create_card(root, "Impedance & Reactance (Model Space)", pad_top=False)

        metrics_imp = [
            ("|Z| at rating", f"{Z_percent:.6f} %", ""),
            ("%R @ 33°C", f"{R_33:.6f} %", ""),
            ("%X @ 33°C", f"{X_33:.6f} %", ""),
        ]
        add_metric_tiles(inner_imp, metrics_imp, cols=3)

        tk.Label(
            inner_imp,
            text=Z_note,
            font=("Segoe UI", 8),
            bg="white",
            fg="#777777",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        if isinstance(md_json, dict) and md_json:
            mva = md_json.get("MVA_Max") or md_json.get("mva") or md_json.get("MVA")
            try:
                if mva is not None:
                    mv = float(mva)
                    tk.Label(
                        inner_imp,
                        text=f"Rated apparent power: {mv:.3f} MVA",
                        font=("Segoe UI", 8),
                        bg="white",
                        fg="#555555",
                    ).pack(anchor="w", pady=(4, 0))
            except Exception:
                pass
    # =================================================================
    #   FULL ANALYSIS ENGINE
    # =================================================================

    def run_full_analysis():
        try:
            pdata0 = getattr(main_app, "pipeline_data", None)
            if not isinstance(pdata0, dict):
                messagebox.showwarning("No Data", "Convert a file first.")
                return

            raw_freq = pdata0.get("freq")
            raw_mag  = pdata0.get("mag")
            metadata = pdata0.get("metadata", {})
            taps_raw = pdata0.get("taps", {})

            if raw_freq is None or raw_mag is None:
                raise ValueError("Pipeline data missing freq/mag arrays.")

            freq = np.asarray(raw_freq, float).reshape(-1)
            mag  = np.asarray(raw_mag, float).reshape(-1)

            payload = {
                "freq": freq,
                "mag": mag,
                "metadata": metadata,
                "taps": taps_raw,
            }

            # --------------------------
            # Load ML model
            # --------------------------
            with open(MODEL_PATH, "rb") as f:
                ml = pickle.load(f)

            if isinstance(ml, dict) and "diagnosis_engine" in ml:
                engine = ml["diagnosis_engine"]
            elif hasattr(ml, "diagnosis_engine"):
                engine = ml.diagnosis_engine
            elif hasattr(ml, "predict_single"):
                engine = ml.predict_single
            else:
                raise RuntimeError("No valid diagnosis engine found in model.")

            sig = inspect.signature(engine)
            params = [
                p for p in sig.parameters.values()
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            ]
            n_required = len([p for p in params if p.default is p.empty])

            if isinstance(taps_raw, list) and taps_raw:
                tap_info = taps_raw[0]
            else:
                tap_info = taps_raw if isinstance(taps_raw, dict) else {}

            feats = ML.sfra_runtime.extract_features(freq, mag)

            # smart engine call
            if n_required <= 1:
                raw_output = engine(payload)
            elif n_required == 2:
                raw_output = engine(feats, tap_info)
            else:
                raw_output = engine(feats, tap_info, False)

            output = coerce_output_to_dict(raw_output)
            safe_output = make_json_safe(output)

            # --------------------------
            # Save JSON output
            # --------------------------
            out_dir = os.path.join(os.getcwd(), "outputs")
            os.makedirs(out_dir, exist_ok=True)
            base = os.path.splitext(
                os.path.basename(getattr(main_app, "homepage_current_file", "analysis"))
            )[0]

            json_path = None
            try:
                json_path = os.path.join(out_dir, f"{base}_FULL_REPORT.json")
                with open(json_path, "w") as jf:
                    json.dump(safe_output, jf, indent=4)
            except Exception:
                json_path = None

            # --------------------------
            # Store into pipeline_data
            # --------------------------
            pdata_final = getattr(main_app, "pipeline_data", {})
            if not isinstance(pdata_final, dict):
                pdata_final = {}

            main_app.pipeline_data = pdata_final
            main_app.pipeline_data.setdefault("ml_output", {})
            main_app.pipeline_data["ml_output"].update({
                "report": safe_output,
                "json_path": json_path
            })

            # no huge JSON print
            main_app.log_console("Diagnosis completed. See Analysis panel for details.", "INFO")

            # show analysis summary
            show_ml_metadata()

        except Exception as e:
            try:
                main_app.log_console(str(e), "ERROR")
                import traceback
                main_app.log_console("[TRACEBACK]\n" + traceback.format_exc(), "ERROR")
            except:
                pass

    
    # =================================================================
    #   ANALYSIS CONTROLS (START ANALYSIS BUTTON)
    # =================================================================

    def add_analysis_controls():
        holder = _analysis_controls_holder
        clear_panel(holder)

        frame = tk.Frame(holder, bg="white")
        frame.pack(pady=6)

        btn = tk.Button(
            frame, text="Start Analysis",
            font=("Segoe UI", 11, "bold"),
            bg="#1976D2", fg="white",
            padx=20, pady=8, relief=tk.FLAT, cursor="hand2"
        )
        btn.pack()

        loading_win = {"ref": None}

        # --------------------------
        # Loading spinner popup
        # --------------------------
        def show_loading_popup():
            if loading_win["ref"] is not None:
                return

            parent = preview_panel.winfo_toplevel()
            win = tk.Toplevel(parent)
            win.title("Running Analysis")
            win.configure(bg="white")
            win.geometry("260x130")
            win.resizable(False, False)

            tk.Label(win, text="Running Analysis...",
                     font=("Segoe UI", 11, "bold"), bg="white").pack(pady=(15, 5))

            spinner_label = tk.Label(
                win, text="", font=("Segoe UI", 20),
                bg="white", fg="#1976D2"
            )
            spinner_label.pack()

            tk.Label(win,
                     text="Please wait, this may take a moment.",
                     font=("Segoe UI", 9), bg="white").pack(pady=(0, 10))

            frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
            idx = 0

            def spin():
                nonlocal idx
                if loading_win["ref"] is None:
                    return
                spinner_label.config(text=frames[idx])
                idx = (idx + 1) % len(frames)
                win.after(120, spin)

            spin()
            win.transient(parent)
            win.grab_set()
            loading_win["ref"] = win

        def close_loading():
            win = loading_win["ref"]
            if win is not None:
                try: win.grab_release()
                except: pass
                try: win.destroy()
                except: pass
                loading_win["ref"] = None

        # --------------------------
        # FINAL EXECUTION
        # --------------------------
        def do_run():
            try:
                run_full_analysis()
            finally:
                close_loading()
                # button might have been destroyed if user switched views
                if btn.winfo_exists():
                    btn.config(state=tk.NORMAL, text="Start Analysis")

        def on_start():
            btn.config(state=tk.DISABLED, text="Running...")
            show_loading_popup()
            preview_panel.after(200, do_run)

        btn.config(command=on_start)


    # =================================================================
    #   ANALYSIS PREVIEW LOADER
    # =================================================================

    def load_analysis_preview():
        nonlocal _analysis_controls_holder

        clear_panel(preview_panel)
        pdata = getattr(main_app, "pipeline_data", {})

        # If already analysed → go straight to result dashboard
        if "ml_output" in pdata and "report" in pdata["ml_output"]:
            show_ml_metadata()
            return

        freq = pdata.get("freq", [])
        file = getattr(main_app, "homepage_current_file", "Unknown File")
        file_name = os.path.basename(file) if file else "Unknown File"

        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        # Card 1 – Analysis summary
        card_top = create_card(root, "Analysis Dashboard")

        tk.Label(
            card_top,
            text=f"File ready: {file_name}",
            font=("Segoe UI", 10, "bold"),
            bg="white",
            fg="#212121",
        ).pack(anchor="w", pady=(0, 2))

        tk.Label(
            card_top,
            text=f"Total SFRA points detected: {len(freq)}",
            font=("Segoe UI", 9),
            bg="white",
            fg="#555555",
        ).pack(anchor="w")

        add_section_caption(
            card_top,
            "Click **Start Analysis** to run the full ML-assisted diagnosis pipeline on this sweep.",
        )

        # Card 2 – What this analysis will do (process flow)
        card_flow = create_card(root, "Analysis Flow (Pipeline)", pad_top=False)

        steps = [
            (
                "1. Feature Extraction",
                "pending",
                "Compute modal frequencies, energy bands, turbulence, HF decay and attenuation from the SFRA sweep.",
            ),
            (
                "2. Energy Bands & Turbulence",
                "pending",
                "Summarise how the response energy is distributed across Low / Mid / High bands and how smooth or rippled the mid-band is.",
            ),
            (
                "3. HF Decay & Attenuation",
                "pending",
                "Measure how quickly high-frequency response rolls off and the overall magnitude drop from start to end of the sweep.",
            ),
            (
                "4. Loss & Efficiency (Model Space)",
                "pending",
                "Estimate core/load losses, approximate efficiency and model-space impedance from learned patterns.",
            ),
            (
                "5. Fault Classification",
                "pending",
                "Combine all derived features into a final fault label, severity and confidence score.",
            ),
        ]
        add_process_steps(card_flow, steps)

        tk.Label(
            card_flow,
            text="This view only describes the pipeline. Detailed results will appear after running analysis.",
            font=("Segoe UI", 8, "italic"),
            bg="white",
            fg="#9E9E9E",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        # Holder for Start Analysis button
        _analysis_controls_holder = tk.Frame(root, bg="white")
        _analysis_controls_holder.pack(fill=tk.X, pady=8)

        add_analysis_controls()
        main_app.log_console("Analyse Graph panel loaded (pre-analysis view).", "SUCCESS")

    # -------------------------------------------------------
    # Fault Classification View (REPLACED)
    # -------------------------------------------------------
    def show_fault_classification():
        """Render a modern card-based Fault Classification dashboard inside preview_panel."""
        clear_panel(preview_panel)

        pdata  = getattr(main_app, "pipeline_data", {}) or {}
        ml_out = pdata.get("ml_output", {}) or {}
        report = ml_out.get("report") or {}

        if not isinstance(report, dict) or not report:
            show_preview_text("⚠ No ML report available.\nRun 'Start Analysis' first.")
            return

        feats   = report.get("features_used", {}) or {}
        faults  = report.get("universal_fault_labels", ["healthy"]) or ["healthy"]
        meta    = report.get("metadata", {}) or {}
        losses  = report.get("loss_and_efficiency", {}) or {}

        fault = faults[0] if faults else "healthy"

        # -------------------- Core fields --------------------
        severity_raw = str(report.get("severity", "none")).upper()
        try:
            conf = float(report.get("confidence", 0.5) * 100.0)
        except Exception:
            conf = 50.0
        conf   = max(0.0, min(100.0, conf))
        reason = str(report.get("reason", "No abnormality detected."))

        fault_label = str(fault).replace("_", " ").title()

        # Severity -> color mapping
        sev_color_map = {
            "NONE":   "#4CAF50",
            "LOW":    "#8BC34A",
            "MEDIUM": "#FFC107",
            "HIGH":   "#F44336",
        }
        sev_color = sev_color_map.get(severity_raw, "#90A4AE")

        # -------------------- Energy band contributions --------------------
        def safe_float(v, default=0.0):
            try:
                return float(v)
            except Exception:
                return float(default)

        E_low  = abs(safe_float(feats.get("E_low", 0.0)))
        E_mid  = abs(safe_float(feats.get("E_mid", 0.0)))
        E_high = abs(safe_float(feats.get("E_high", 0.0)))
        total_E = max(E_low + E_mid + E_high, 1e-6)

        pct_low  = (E_low  / total_E) * 100.0
        pct_mid  = (E_mid  / total_E) * 100.0
        pct_high = (E_high / total_E) * 100.0

        # Key features (short list)
        key_features = {
            "Mid-band turbulence": safe_float(feats.get("midband_turbulence", 0.0)),
            "Modal spacing index": safe_float(feats.get("modal_spacing_index", 0.0)),
            "Global attenuation":  safe_float(feats.get("global_attenuation", 0.0)),
            "HF decay rate":       safe_float(feats.get("hf_decay_rate", 0.0)),
        }

        # Impact target for transformer diagram
        impact_target = (
            "CORE"       if str(fault) == "core_movement" else
            "HV WINDING" if str(fault) == "axial_deformation" else
            "LV WINDING" if str(fault) == "radial_deformation" else
            "NONE"
        )

        # ================== ROOT CONTAINER ==================
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        # Helper: section title
        def section_title(parent, text):
            tk.Label(
                parent,
                text=text,
                font=("Segoe UI", 11, "bold"),
                bg="white", fg="#333333"
            ).pack(anchor="w", pady=(4, 2))

        # Helper: horizontal bar
        def draw_bar(parent, label, pct, band_color="#1976D2", accent="#E0E0E0"):
            wrap = tk.Frame(parent, bg="white")
            wrap.pack(fill=tk.X, pady=2)

            tk.Label(
                wrap, text=label,
                font=("Segoe UI", 9),
                bg="white", fg="#555555"
            ).pack(anchor="w")

            c = tk.Canvas(
                wrap, height=12, bg="white",
                highlightthickness=0, bd=0
            )
            c.pack(fill=tk.X, expand=True, pady=(1, 0))

            # approximate width; canvas will stretch with frame
            w = 260
            c.create_rectangle(0, 0, w, 12, fill=accent, outline=accent)

            pct = max(0.0, min(100.0, pct))
            fill_w = w * (pct / 100.0)
            c.create_rectangle(0, 0, fill_w, 12, fill=band_color, outline=band_color)

            c.create_text(
                w - 20, 6,
                text=f"{pct:4.1f}%",
                anchor="e",
                font=("Segoe UI", 8),
                fill="#222222"
            )

        # ================== SECTION 1: Fault summary card ==================
        summary_card = tk.Frame(
            root, bg="white",
            highlightbackground="#E0E0E0", highlightthickness=1, bd=0
        )
        summary_card.pack(fill=tk.X, padx=16, pady=(12, 8))

        left = tk.Frame(summary_card, bg="white")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=10)

        right = tk.Frame(summary_card, bg="white")
        right.pack(side=tk.RIGHT, padx=12, pady=10)

        # Title
        tk.Label(
            left,
            text="Fault Classification",
            font=("Segoe UI", 13, "bold"),
            bg="white", fg="#212121"
        ).pack(anchor="w")

        # Fault label + severity pill
        pill = tk.Frame(left, bg="white")
        pill.pack(anchor="w", pady=(6, 2))

        tk.Label(
            pill,
            text=fault_label,
            font=("Segoe UI", 11, "bold"),
            bg="white", fg="#111111"
        ).pack(side=tk.LEFT)

        tk.Label(
            pill,
            text=severity_raw.title(),
            font=("Segoe UI", 9, "bold"),
            bg=sev_color, fg="white",
            padx=8, pady=2
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Reason
        if reason:
            tk.Label(
                left,
                text=reason,
                font=("Segoe UI", 9),
                bg="white", fg="#555555",
                wraplength=380,
                justify="left"
            ).pack(anchor="w", pady=(6, 0))

        # ================== SECTION 2: Energy band card ==================
        band_card = tk.Frame(
            root, bg="white",
            highlightbackground="#E0E0E0", highlightthickness=1, bd=0
        )
        band_card.pack(fill=tk.X, padx=16, pady=(0, 8))

        inner_band = tk.Frame(band_card, bg="white")
        inner_band.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        section_title(inner_band, "Fault Signature Map (Energy Zones)")

        draw_bar(inner_band, "Low (0–2 kHz)",         pct_low,  band_color="#4CAF50")
        draw_bar(inner_band, "Mid (2–20 kHz)",        pct_mid,  band_color="#2196F3")
        draw_bar(inner_band, "High (20 kHz – 1 MHz)", pct_high, band_color="#FF9800")

        # ================== SECTION 3: Feature impact tiles ==================
        feature_card = tk.Frame(
            root, bg="white",
            highlightbackground="#E0E0E0", highlightthickness=1, bd=0
        )
        feature_card.pack(fill=tk.X, padx=16, pady=(0, 8))

        inner_feat = tk.Frame(feature_card, bg="white")
        inner_feat.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        section_title(inner_feat, "Feature Impact Snapshot")

        feat_grid = tk.Frame(inner_feat, bg="white")
        feat_grid.pack(fill=tk.X)

        row = col = 0
        for label, val in key_features.items():
            tile = tk.Frame(
                feat_grid, bg="#F5F5F5",
                highlightbackground="#E0E0E0",
                highlightthickness=1
            )
            tile.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            tk.Label(
                tile, text=label,
                font=("Segoe UI", 8, "bold"),
                bg="#F5F5F5", fg="#424242"
            ).pack(anchor="w", padx=6, pady=(4, 0))

            tk.Label(
                tile, text=f"{val:.4f}",
                font=("Segoe UI", 10),
                bg="#F5F5F5", fg="#000000"
            ).pack(anchor="w", padx=6, pady=(0, 4))

            col += 1
            if col >= 2:
                col = 0
                row += 1

        # ================== SECTION 4: Transformer impact + Why ==================
        bottom = tk.Frame(root, bg="white")
        bottom.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        left_bottom  = tk.Frame(bottom, bg="white")
        right_bottom = tk.Frame(bottom, bg="white")
        left_bottom.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        right_bottom.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        # Transformer mini diagram
        diag_card = tk.Frame(
            left_bottom, bg="white",
            highlightbackground="#E0E0E0", highlightthickness=1, bd=0
        )
        diag_card.pack(fill=tk.BOTH, expand=True)

        inner_diag = tk.Frame(diag_card, bg="white")
        inner_diag.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        section_title(inner_diag, "Transformer Part Impact")

        diag_canvas = tk.Canvas(
            inner_diag,
            height=120, bg="white",
            highlightthickness=0, bd=0
        )
        diag_canvas.pack(fill=tk.X)

        width = 260
        cx_d = width // 2

        core_color = "#FFCDD2" if impact_target == "CORE"       else "#ECEFF1"
        hv_color   = "#FFCC80" if impact_target == "HV WINDING" else "#E0E0E0"
        lv_color   = "#80DEEA" if impact_target == "LV WINDING" else "#E0E0E0"

        diag_canvas.create_rectangle(cx_d-40, 20, cx_d+40, 50,
                                     fill=core_color, outline="#B0BEC5")
        diag_canvas.create_text(cx_d, 35, text="CORE", font=("Segoe UI", 9, "bold"))

        diag_canvas.create_rectangle(cx_d-70, 55, cx_d+70, 85,
                                     fill=lv_color, outline="#B0BEC5")
        diag_canvas.create_text(cx_d, 70, text="LV Winding", font=("Segoe UI", 9))

        diag_canvas.create_rectangle(cx_d-70, 90, cx_d+70, 120,
                                     fill=hv_color, outline="#B0BEC5")
        diag_canvas.create_text(cx_d, 105, text="HV Winding", font=("Segoe UI", 9))

        tk.Label(
            inner_diag,
            text="Highlighted section indicates which part is most likely affected based on ML features.",
            font=("Segoe UI", 8),
            bg="white", fg="#777777",
            wraplength=240, justify="left"
        ).pack(anchor="w", pady=(4, 0))

        # Why this diagnosis
        why_card = tk.Frame(
            right_bottom, bg="white",
            highlightbackground="#E0E0E0", highlightthickness=1, bd=0
        )
        why_card.pack(fill=tk.BOTH, expand=True)

        inner_why = tk.Frame(why_card, bg="white")
        inner_why.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        section_title(inner_why, "Why this diagnosis?")

        reasons = [
            f"Mid-band turbulence: {key_features['Mid-band turbulence']:.3f}",
            f"Modal spacing index: {key_features['Modal spacing index']:.1f}",
            "Relative energy in Low / Mid / High bands.",
            "High-frequency decay pattern (HF decay rate + global attenuation).",
        ]
        for rtxt in reasons:
            tk.Label(
                inner_why,
                text="• " + rtxt,
                font=("Segoe UI", 9),
                bg="white", fg="#555555",
                wraplength=240, justify="left"
            ).pack(anchor="w", pady=1)

        tk.Label(
            inner_why,
            text="Note: This view summarizes ML behaviour and is not a standalone pass/fail decision.",
            font=("Segoe UI", 8, "italic"),
            bg="white", fg="#9E9E9E",
            wraplength=240, justify="left"
        ).pack(anchor="w", pady=(6, 0))

    # =================================================================
    #   CREATE LEFT TREE UI  (ANALYSIS NAVIGATION)
    # =================================================================
    def create_analyse_ui():
        clear_panel(workspace)
        clear_panel(preview_panel)
        clear_panel(metadata_panel)

        tk.Label(
            workspace, text="Analysis Dashboard",
            font=("Segoe UI", 14, "bold"),
            bg="#f5f5f5"
        ).pack(anchor="w", padx=15, pady=(10, 20))

        style = ttk.Style()
        style.configure("Treeview",
                        background="#f5f5f5",
                        fieldbackground="#f5f5f5",
                        borderwidth=0,
                        highlightthickness=0,
                        rowheight=24,
                        font=("Segoe UI", 10))
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])

        tree = ttk.Treeview(workspace, show="tree")
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # MAIN TREE SECTIONS
        analysis_root = tree.insert("", "end", text="ANALYSIS", open=False)
        graph_root    = tree.insert("", "end", text="GRAPH TOOLS", open=False)

        # ANALYSIS SUB-VIEWS
        for item in [
        "Modal Frequencies",
        "Energy Bands",
        "Turbulence",
        "HF Decay",
        "Attenuation",
        "Loss & Efficiency",
        "Fault Classification",
        ]:
            tree.insert(analysis_root, "end", text=item)

        # GRAPH TOOL SUB-VIEWS  -> sirf do items
        tree.insert(graph_root, "end", text="Export Graphs")
        tree.insert(graph_root, "end", text="Animation Viewer")

        # =================================================================
        #   TREE CLICK HANDLER (ALL VIEWS WIRED)
        # =================================================================
        def on_tree_click(event):
            item_id = tree.focus()
            txt = tree.item(item_id, "text") if item_id else ""

            if not txt:
                return

            # ---------------- ROOT NODES ----------------
            if txt == "ANALYSIS":
                load_analysis_preview()
                return

            if txt == "GRAPH TOOLS":
                # Parent pe click = Analysis button + graphs (NO export button)
                try:
                    graph_tools.show_graph_overview(main_app, preview_panel, helpers)
                except AttributeError:
                    update_preview("Graph Tools view not available (show_graph_plots missing).")
                else:
                    main_app.log_console("Opened Graph Tools (Graph Plots view)", "INFO")
                return

            # ---------------- ANALYSIS SUB-VIEWS ----------------
            if txt == "Modal Frequencies":
                show_modal_frequencies()
                main_app.log_console("Opened Modal Frequencies view", "INFO")
                return

            if txt == "Energy Bands":
                show_energy_bands()
                main_app.log_console("Opened Energy Bands view", "INFO")
                return

            if txt == "Turbulence":
                show_turbulence()
                main_app.log_console("Opened Turbulence view", "INFO")
                return

            if txt == "HF Decay":
                show_hf_decay()
                main_app.log_console("Opened HF Decay view", "INFO")
                return

            if txt == "Attenuation":
                show_attenuation()
                main_app.log_console("Opened Attenuation view", "INFO")
                return

            if txt == "Loss & Efficiency":
                show_loss_efficiency()
                main_app.log_console("Opened Loss & Efficiency view", "INFO")
                return

            if txt == "Fault Classification":
                show_fault_classification()
                main_app.log_console("Opened Fault Classification view", "INFO")
                return

            # ---------------- GRAPH TOOLS SUB-VIEWS ----------------
            if txt == "Export Graphs":
                    # Child pe click = Export PDF button + graphs (NO analysis button)
                try:
                    graph_tools.show_graph_plots(main_app, preview_panel, helpers)
                except AttributeError:
                    # Fallback - atleast graphs toh dikha do
                    update_preview("Export Graphs view not ready yet.")
                    main_app.log_console("Opened Export Graphs view", "INFO")
                return

            if txt == "Animation Viewer":
                graph_tools.show_animation_viewer(main_app, preview_panel, helpers)
                main_app.log_console("Opened Animation Viewer view", "INFO")
                return

            # ---------------- FALLBACK ----------------
            update_preview(f"You selected: {txt}")
            main_app.log_console(f"Clicked: {txt}", "INFO")


        tree.bind("<<TreeviewSelect>>", on_tree_click)

        update_preview(
            "Analysis & Graphs Panel\n\n"
            "Use the left navigation tree to select an analysis module."
        )
        main_app.log_console("Analyse Graph panel loaded.", "SUCCESS")

    # Ensure holder exists before UI build
    _analysis_controls_holder = None

    # Build UI on entry
    create_analyse_ui()

# END OF enable_analyse_graph