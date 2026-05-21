# analyse_graph2.py

import os
import tkinter as tk
from tkinter import messagebox

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_pdf import PdfPages


# -------------------------------------------------------------------
# small helpers
# -------------------------------------------------------------------
def _safe_float(d, key, default=0.0):
    try:
        v = d.get(key, default)
        return float(v if v is not None else default)
    except Exception:
        return float(default)


def _ensure_arrays(freq, mag):
    """Return numpy arrays (freq, mag) or empty ones on error."""
    try:
        f = np.asarray(freq, float).reshape(-1)
        m = np.asarray(mag,  float).reshape(-1)
    except Exception:
        f = np.array([])
        m = np.array([])
    return f, m


# -------------------------------------------------------------------
# core graph builder – used by BOTH views
# -------------------------------------------------------------------
def _build_all_graphs(
    main_app,
    graphs_holder,
    clear_panel,
    create_card,
    freq,
    mag,
    feats,
    faults,
    base_freq,
    base_mag,
    base_name,
    graphs_dir,
    pdata,
    report,
):
    """
    Draw all 6 graphs inside graphs_holder.
    Save PNGs into graphs_dir.
    Update pdata["graph_images"] and return (figures_list, graph_paths_dict).
    """

    clear_panel(graphs_holder)

    figures = []
    graph_paths = {}

    def _nearest_y(f_target):
        idx = np.argmin(np.abs(freq - f_target))
        return mag[idx]

    # modal values
    m1 = _safe_float(feats, "modal_1", 0.0)
    m2 = _safe_float(feats, "modal_2", 0.0)
    m3 = _safe_float(feats, "modal_3", 0.0)

    # ---------------------------------------------------------
    # Graph 1 – Fault Severity Gauge
    # ---------------------------------------------------------
    conf = 0.5
    try:
        conf = float(report.get("confidence", 0.5))
    except Exception:
        conf = 0.5
    conf = max(0.0, min(1.0, conf))
    angle = conf * np.pi  # 0..180 deg (radians)

    fig1 = Figure(figsize=(2.8, 2.8), dpi=100)
    ax1 = fig1.add_subplot(111, polar=True)

    ax1.set_theta_zero_location("N")
    ax1.set_theta_direction(-1)
    ax1.bar(angle, 1.0, width=np.deg2rad(5), color="red")
    ax1.set_yticklabels([])
    ax1.set_xticklabels([])
    ax1.set_ylim(0, 1.0)
    ax1.set_title(f"Fault Severity Gauge\nSeverity = {conf*100:.1f}%", fontsize=10)

    card1 = create_card(graphs_holder, "Fault Severity Gauge")
    canvas1 = FigureCanvasTkAgg(fig1, master=card1)
    canvas1.draw()
    canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    figures.append(fig1)

    png1 = os.path.join(graphs_dir, f"{base_name}_01_fault_severity.png")
    try:
        fig1.savefig(png1, dpi=150, bbox_inches="tight")
        graph_paths["fault_severity"] = png1
    except Exception as e:
        main_app.log_console(f"Failed to save fault severity PNG: {e}", "ERROR")

    # ---------------------------------------------------------
    # Graph 2 – Modal Frequencies + Spectrum Energy Bands
    # ---------------------------------------------------------
    fig2 = Figure(figsize=(6.0, 3.0), dpi=100)
    ax2 = fig2.add_subplot(111)

    ax2.plot(freq, mag, label="SFRA Curve")

    if m1 > 0:
        ax2.axvline(m1, color="green", linestyle="--", label=f"Modal 1: {m1:.1f}")
    if m2 > 0:
        ax2.axvline(m2, color="orange", linestyle="--", label=f"Modal 2: {m2:.1f}")
    if m3 > 0:
        ax2.axvline(m3, color="red", linestyle="--", label=f"Modal 3: {m3:.1f}")

    ax2.fill_between(freq, mag, where=freq < 2000, alpha=0.15, label="Low Band")
    ax2.fill_between(
        freq,
        mag,
        where=(freq >= 2000) & (freq < 20000),
        alpha=0.15,
        label="Mid Band",
    )
    ax2.fill_between(freq, mag, where=freq >= 20000, alpha=0.15, label="High Band")

    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Magnitude (dB)")
    ax2.set_title("Modal Frequencies + Spectrum Energy Bands")
    ax2.grid(True, linestyle=":", linewidth=0.5)
    ax2.legend(loc="best", fontsize=8)

    card2 = create_card(graphs_holder, "Modal Frequencies + Spectrum Energy Bands")
    canvas2 = FigureCanvasTkAgg(fig2, master=card2)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    figures.append(fig2)

    png2 = os.path.join(graphs_dir, f"{base_name}_02_modal_spectrum_bands.png")
    try:
        fig2.savefig(png2, dpi=150, bbox_inches="tight")
        graph_paths["modal_spectrum_bands"] = png2
    except Exception as e:
        main_app.log_console(f"Failed to save modal/spectrum PNG: {e}", "ERROR")

    # ---------------------------------------------------------
    # Graph 3 – Delta Comparison Curve — Damage Locator
    # ---------------------------------------------------------
    aligned_baseline = np.interp(freq, base_freq, base_mag)
    delta = aligned_baseline - mag

    fig3 = Figure(figsize=(6.0, 3.0), dpi=100)
    ax3 = fig3.add_subplot(111)

    ax3.plot(freq, delta, color="purple")
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_ylabel("Δ Magnitude (dB)")
    ax3.set_title("Delta Comparison Curve — Damage Locator")
    ax3.grid(True, linestyle=":", linewidth=0.5)

    card3 = create_card(graphs_holder, "Delta Comparison Curve — Damage Locator")
    canvas3 = FigureCanvasTkAgg(fig3, master=card3)
    canvas3.draw()
    canvas3.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    figures.append(fig3)

    png3 = os.path.join(graphs_dir, f"{base_name}_03_delta_damage_locator.png")
    try:
        fig3.savefig(png3, dpi=150, bbox_inches="tight")
        graph_paths["delta_damage_locator"] = png3
    except Exception as e:
        main_app.log_console(f"Failed to save delta PNG: {e}", "ERROR")

    # ---------------------------------------------------------
    # Graph 4 – Baseline vs Current SFRA Comparison
    # ---------------------------------------------------------
    aligned_baseline = np.interp(freq, base_freq, base_mag)
    delta_abs = np.abs(aligned_baseline - mag)

    fig4 = Figure(figsize=(6.0, 3.0), dpi=100)
    ax4 = fig4.add_subplot(111)

    ax4.plot(freq, mag, label="Current SFRA")
    ax4.plot(freq, aligned_baseline, label="Baseline SFRA")

    ax4.fill_between(
        freq,
        mag,
        aligned_baseline,
        where=delta_abs > 2.0,  # 2 dB deviation
        alpha=0.25,
        label="Deviation Zone",
    )

    ax4.set_xlabel("Frequency (Hz)")
    ax4.set_ylabel("Magnitude (dB)")
    ax4.set_title("Baseline vs Current SFRA Comparison")
    ax4.grid(True, linestyle=":", linewidth=0.5)
    ax4.legend(loc="best", fontsize=8)

    card4 = create_card(graphs_holder, "Baseline vs Current SFRA Comparison")
    canvas4 = FigureCanvasTkAgg(fig4, master=card4)
    canvas4.draw()
    canvas4.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    figures.append(fig4)

    png4 = os.path.join(graphs_dir, f"{base_name}_04_baseline_vs_current.png")
    try:
        fig4.savefig(png4, dpi=150, bbox_inches="tight")
        graph_paths["baseline_vs_current"] = png4
    except Exception as e:
        main_app.log_console(f"Failed to save baseline/current PNG: {e}", "ERROR")

    # ---------------------------------------------------------
    # Graph 5 – Peak Activation Map — Why ML Triggered Fault
    # ---------------------------------------------------------
    fig5 = Figure(figsize=(6.0, 3.2), dpi=100)
    ax5 = fig5.add_subplot(111)

    ax5.plot(freq, mag, label="SFRA Curve", color="black", linewidth=1.0)

    if m1 > 0:
        ax5.scatter([m1], [_nearest_y(m1)], color="green", s=40, label="Modal 1 Peak")
    if m2 > 0:
        ax5.scatter([m2], [_nearest_y(m2)], color="orange", s=40, label="Modal 2 Peak")
    if m3 > 0:
        ax5.scatter([m3], [_nearest_y(m3)], color="red", s=40, label="Modal 3 Peak")

    ax5.axvspan(0, 2000, alpha=0.08, label="Low Band")
    ax5.axvspan(2000, 20000, alpha=0.08, label="Mid Band")
    ax5.axvspan(20000, freq.max(), alpha=0.08, label="High Band")

    faults_list = faults or []
    y_text = 0.90
    for label_text, key, color in [
        ("Radial Triggered", "radial_deformation", "red"),
        ("Axial Triggered", "axial_deformation", "purple"),
        ("Core Movement Triggered", "core_movement", "blue"),
    ]:
        if key in faults_list:
            ax5.text(
                0.02,
                y_text,
                label_text,
                transform=ax5.transAxes,
                fontsize=9,
                color=color,
                bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
            )
            y_text -= 0.05

    ax5.set_xlabel("Frequency (Hz)")
    ax5.set_ylabel("Magnitude (dB)")
    ax5.set_title("Peak Activation Map — Why ML Triggered Fault")
    ax5.grid(True, linestyle=":", linewidth=0.5)
    ax5.legend(loc="lower right", fontsize=7)

    card5 = create_card(graphs_holder, "Peak Activation Map — Why ML Triggered Fault")
    canvas5 = FigureCanvasTkAgg(fig5, master=card5)
    canvas5.draw()
    canvas5.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    figures.append(fig5)

    png5 = os.path.join(graphs_dir, f"{base_name}_05_peak_activation.png")
    try:
        fig5.savefig(png5, dpi=150, bbox_inches="tight")
        graph_paths["peak_activation"] = png5
    except Exception as e:
        main_app.log_console(f"Failed to save peak activation PNG: {e}", "ERROR")

    # ---------------------------------------------------------
    # Graph 6 – Midband Turbulence Activation
    # ---------------------------------------------------------
    if freq.size > 1:
        diff_mag = np.diff(mag)
        turb = np.abs(diff_mag)
        f_turb = freq[1:]
    else:
        turb = np.zeros(0)
        f_turb = np.zeros(0)

    fig6 = Figure(figsize=(6.0, 2.0), dpi=100)
    ax6 = fig6.add_subplot(111)

    ax6.plot(f_turb, turb, color="red", label="Turbulence (|ΔMag|)")
    ax6.axhline(1.2, linestyle="--", color="orange", label="Radial Threshold (1.2)")

    ax6.set_xlabel("Frequency (Hz)")
    ax6.set_ylabel("|ΔMag|")
    ax6.set_title("Midband Turbulence Activation")
    ax6.grid(True, linestyle=":", linewidth=0.5)
    ax6.legend(loc="upper right", fontsize=7)

    card6 = create_card(graphs_holder, "Midband Turbulence Activation")
    canvas6 = FigureCanvasTkAgg(fig6, master=card6)
    canvas6.draw()
    canvas6.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    figures.append(fig6)

    png6 = os.path.join(graphs_dir, f"{base_name}_06_midband_turbulence.png")
    try:
        fig6.savefig(png6, dpi=150, bbox_inches="tight")
        graph_paths["midband_turbulence"] = png6
    except Exception as e:
        main_app.log_console(f"Failed to save turbulence PNG: {e}", "ERROR")

    # push into pipeline for Generate Report
    pdata["graph_images"] = graph_paths
    main_app.log_console(
        f"Graph plots rendered and PNGs saved to {graphs_dir}.",
        "SUCCESS",
    )

    return figures, graph_paths


# ===================================================================
# VIEW 1: GRAPH TOOLS OVERVIEW  (first button – NO PDF)
# ===================================================================
def show_graph_overview(main_app, preview_panel, helpers):
    """
    Tree item: 'GRAPH TOOLS'
    - Shows info + 'Start Graph Plotting' button.
    - No PDF export button.
    """

    clear_panel         = helpers["clear_panel"]
    create_card         = helpers["create_card"]
    add_section_caption = helpers["add_section_caption"]

    clear_panel(preview_panel)

    # ----- access pipeline ----------
    pdata = getattr(main_app, "pipeline_data", None)
    if not isinstance(pdata, dict):
        pdata = {}
        setattr(main_app, "pipeline_data", pdata)

    ml_out = pdata.get("ml_output")
    if not isinstance(ml_out, dict):
        ml_out = {}
        pdata["ml_output"] = ml_out

    report = ml_out.get("report")
    if not isinstance(report, dict):
        report = {}
        ml_out["report"] = report

    # we need sweep + report (analysis done)
    freq, mag = _ensure_arrays(pdata.get("freq", []), pdata.get("mag", []))
    if not report or freq.size == 0 or freq.size != mag.size:
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        card = create_card(root, "Graph Tools – SFRA Visual Diagnostics")
        tk.Label(
            card,
            text=(
                "Graph tools require an analysed sweep.\n\n"
                "Run 'Start Analysis' first, then re-open GRAPH TOOLS."
            ),
            font=("Segoe UI", 10),
            bg="white",
            fg="#555555",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        return

    feats  = report.get("features_used") or {}
    faults = report.get("universal_fault_labels") or ["healthy"]

    current_file = getattr(main_app, "homepage_current_file", "SFRA")
    base_name = os.path.splitext(os.path.basename(current_file))[0]

    documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
    os.makedirs(documents_dir, exist_ok=True)
    graphs_dir = os.path.join(documents_dir, "VidhyutGraphs")
    os.makedirs(graphs_dir, exist_ok=True)

    base_freq, base_mag = _ensure_arrays(
        pdata.get("baseline_freq", []),
        pdata.get("baseline_mag", []),
    )
    if base_freq.size == 0 or base_mag.size != base_freq.size:
        base_freq = freq.copy()
        base_mag  = mag.copy()

    root = tk.Frame(preview_panel, bg="white")
    root.pack(fill=tk.BOTH, expand=True)

    intro = create_card(root, "Graph Tools – SFRA Visual Diagnostics")
    add_section_caption(
        intro,
        "This tool generates multiple SFRA diagnostic graphs for the "
        "current analysed sweep."
    )
    add_section_caption(
        intro,
        "Click **Start Graph Plotting** to render all graphs in the preview panel."
    )

    controls = tk.Frame(intro, bg="white")
    controls.pack(anchor="w", pady=(6, 0))

    btn = tk.Button(
        controls,
        text="Start Graph Plotting",
        font=("Segoe UI", 10, "bold"),
        bg="#1976D2",
        fg="white",
        relief=tk.FLAT,
        padx=14,
        pady=6,
        cursor="hand2",
    )
    btn.pack()

    graphs_holder = tk.Frame(root, bg="white")
    graphs_holder.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def on_click():
        btn.config(state=tk.DISABLED, text="Plotting...")
        _build_all_graphs(
            main_app,
            graphs_holder,
            clear_panel,
            create_card,
            freq,
            mag,
            feats,
            faults,
            base_freq,
            base_mag,
            base_name,
            graphs_dir,
            pdata,
            report,
        )
        if btn.winfo_exists():
            btn.config(state=tk.NORMAL, text="Re-run Graph Plotting")

    btn.config(command=on_click)

    main_app.log_console("Graph Tools overview loaded.", "INFO")


# ===================================================================
# VIEW 2: EXPORT GRAPH (second button – PDF + PNG)
# ===================================================================
def show_graph_plots(main_app, preview_panel, helpers):
    """
    Tree item: 'Export Graph'

    - Auto renders all graphs when opened.
    - Has 'Export Graphs (PDF)' button.
    - PDF always saved under ~/Documents/<file>_SFRA_GRAPHS.pdf
    """

    clear_panel         = helpers["clear_panel"]
    create_card         = helpers["create_card"]
    add_section_caption = helpers["add_section_caption"]

    clear_panel(preview_panel)

    # ----- pipeline / report -----
    pdata = getattr(main_app, "pipeline_data", None)
    if not isinstance(pdata, dict):
        pdata = {}
        setattr(main_app, "pipeline_data", pdata)

    ml_out = pdata.get("ml_output")
    if not isinstance(ml_out, dict):
        ml_out = {}
        pdata["ml_output"] = ml_out

    report = ml_out.get("report")
    if not isinstance(report, dict):
        report = {}
        ml_out["report"] = report

    freq, mag = _ensure_arrays(pdata.get("freq", []), pdata.get("mag", []))

    if not report or freq.size == 0 or freq.size != mag.size:
        root = tk.Frame(preview_panel, bg="white")
        root.pack(fill=tk.BOTH, expand=True)

        card = create_card(root, "Export Graph – SFRA Visual Diagnostics")
        tk.Label(
            card,
            text=(
                "No analysed sweep found.\n\n"
                "Please run the analysis first, then open 'Export Graph'."
            ),
            font=("Segoe UI", 10),
            bg="white",
            fg="#555555",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        return

    feats  = report.get("features_used") or {}
    faults = report.get("universal_fault_labels") or ["healthy"]

    current_file = getattr(main_app, "homepage_current_file", "SFRA")
    base_name = os.path.splitext(os.path.basename(current_file))[0]

    documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
    os.makedirs(documents_dir, exist_ok=True)
    graphs_dir = os.path.join(documents_dir, "VidhyutGraphs")
    os.makedirs(graphs_dir, exist_ok=True)

    base_freq, base_mag = _ensure_arrays(
        pdata.get("baseline_freq", []),
        pdata.get("baseline_mag", []),
    )
    if base_freq.size == 0 or base_mag.size != base_freq.size:
        base_freq = freq.copy()
        base_mag  = mag.copy()

    root = tk.Frame(preview_panel, bg="white")
    root.pack(fill=tk.BOTH, expand=True)

    intro = create_card(root, "Export Graph – SFRA Visual Diagnostics")
    add_section_caption(
        intro,
        "This view renders all SFRA diagnostic graphs and lets you export "
        "them as a single PDF file."
    )

    graphs_holder = tk.Frame(root, bg="white")
    graphs_holder.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    # build graphs immediately
    figures, _graph_paths = _build_all_graphs(
        main_app,
        graphs_holder,
        clear_panel,
        create_card,
        freq,
        mag,
        feats,
        faults,
        base_freq,
        base_mag,
        base_name,
        graphs_dir,
        pdata,
        report,
    )

    # ---------- Export PDF footer ----------
    footer = tk.Frame(root, bg="white")
    footer.pack(fill=tk.X, pady=(4, 10))

    def export_pdf():
        if not figures:
            messagebox.showinfo("Export Graphs", "No graphs available to export.")
            return

        pdf_path = os.path.join(documents_dir, f"{base_name}_SFRA_GRAPHS.pdf")

        try:
            with PdfPages(pdf_path) as pdf:
                for fig in figures:
                    pdf.savefig(fig)

            main_app.log_console(f"Graphs exported to PDF: {pdf_path}", "SUCCESS")
            messagebox.showinfo("Export Graphs", f"Saved graphs PDF to:\n{pdf_path}")
        except Exception as e:
            main_app.log_console(f"Failed to export graphs: {e}", "ERROR")
            messagebox.showerror("Export Graphs", f"Failed to export graphs:\n{e}")

    export_btn = tk.Button(
        footer,
        text="Export Graphs (PDF)",
        font=("Segoe UI", 10, "bold"),
        bg="#388E3C",
        fg="white",
        padx=16,
        pady=6,
        relief=tk.FLAT,
        cursor="hand2",
        command=export_pdf,
    )
    export_btn.pack(anchor="e", padx=16)

    main_app.log_console("Export Graph view loaded (auto-render).", "INFO")


# ===================================================================
# ANIMATION VIEWER VIEW
# ===================================================================
def show_animation_viewer(main_app, preview_panel, helpers):
    clear_panel         = helpers["clear_panel"]
    create_card         = helpers["create_card"]
    add_section_caption = helpers["add_section_caption"]

    clear_panel(preview_panel)

    root = tk.Frame(preview_panel, bg="white")
    root.pack(fill=tk.BOTH, expand=True)

    card = create_card(root, "Animation Viewer")

    add_section_caption(
        card,
        "If the pipeline generated an SFRA animation (MP4), you can open it from here."
    )

    pdata = getattr(main_app, "pipeline_data", {}) or {}
    anim_path = (
        pdata.get("animation_path")
        or pdata.get("ml_output", {}).get("animation_path")
    )

    label_var = tk.StringVar()
    if anim_path and os.path.exists(anim_path):
        label_var.set(f"Animation file: {os.path.basename(anim_path)}")
    else:
        label_var.set("No animation file detected yet.")

    tk.Label(
        card,
        textvariable=label_var,
        font=("Segoe UI", 9),
        bg="white",
        fg="#555555",
        wraplength=420,
        justify="left",
    ).pack(anchor="w", pady=(4, 8))

    def open_anim():
        path = anim_path
        if not path or not os.path.exists(path):
            messagebox.showinfo("Animation Viewer", "No animation file found.")
            return
        try:
            os.startfile(path)  # Windows only
        except Exception as e:
            messagebox.showerror("Animation Viewer", f"Unable to open animation.\n{e}")

    if anim_path:
        btn = tk.Button(
            card,
            text="Open Animation",
            font=("Segoe UI", 10, "bold"),
            bg="#1976D2",
            fg="white",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=open_anim,
        )
        btn.pack(anchor="w", pady=(0, 4))