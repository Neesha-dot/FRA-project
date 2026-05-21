"""
Smart Suggestions Module - Clean List UI
Provides:
  1) AI - Smart Suggestion   (rule + ML + RAG knowledge mapping hook)
  2) AI - Chat Bot system    (local Phi-3-mini LLM + RAG, domain-locked)
  3) Import Suggestions      (legacy text/CSV import)
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json
from datetime import datetime

# Extra deps for RAG + local LLM
import numpy as np

try:
    from llama_cpp import Llama
except Exception:  # ImportError or others
    Llama = None


# =====================================================================
#  MAIN UI MODULE
# =====================================================================
def enable_smart_suggestions(app):

    main_app = app

    workspace_frame = main_app.workspace_scrollable
    preview_panel = main_app.center_scrollable
    metadata_panel = main_app.metadata_content

    # Store current suggestions / chat data
    main_app.suggestions_data = None
    main_app.imported_suggestions = []
    main_app.rag_suggestions = None

    # ---------------- PATHS & CONSTANTS ----------------
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    RAG_KB_PATH = os.path.join(BASE_DIR, "rag_knowledge_base.json")
    RAG_INDEX_DIR = os.path.join(BASE_DIR, "rag_index")
    RAG_EMB_FILE = os.path.join(RAG_INDEX_DIR, "rag_embeddings.npy")
    RAG_META_FILE = os.path.join(RAG_INDEX_DIR, "rag_chunks.json")

    # Local LLM (Phi-3-mini / 3.5-mini) path – YOU place model here
    LLM_DIR = os.path.join(BASE_DIR, "LLM_model")
    LLM_MODEL_PATH = os.path.join(LLM_DIR, "Phi-3-mini-4k-instruct-q4.gguf")

    # RAG behavior
    RAG_TOP_K = 6
    RAG_MIN_SIM = 0.45  # below this => out-of-domain

    # Lazy-loaded globals (inside closure)
    rag_embeddings = None       # np.ndarray [N, D]
    rag_chunks = None           # list[dict]
    rag_embedder = None         # SentenceTransformer model
    llm_model = None            # Llama instance

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
            preview_panel,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="white",
            relief=tk.FLAT,
            padx=15,
            pady=15,
        )
        t.insert(tk.END, content)
        t.config(state=tk.DISABLED)
        t.pack(fill=tk.BOTH, expand=True)

    # =================================================================
    #  PIPELINE DATA (already from Homepage module)
    # =================================================================
    def load_pipeline_data():
        """Load pipeline JSON data produced by Homepage -> Convert for Analysis."""
        try:
            if hasattr(main_app, "pipeline_data") and main_app.pipeline_data:
                return main_app.pipeline_data

            pipeline_path = "pipeline_data.json"
            if os.path.exists(pipeline_path):
                with open(pipeline_path, "r", encoding="utf-8") as f:
                    return json.load(f)

            return None
        except Exception as e:
            log(f"Error loading pipeline data: {str(e)}", "ERROR")
            return None

    # =================================================================
    #  BASIC FREQUENCY RESPONSE RULES (for Smart Suggestion)
    # =================================================================
    def analyze_frequency_response(freq, mag):
        """Analyze frequency response and generate simple rule-based suggestions."""
        suggestions = []

        # Convert to Python lists if numpy arrays
        if hasattr(freq, "tolist"):
            freq = freq.tolist()
        if hasattr(mag, "tolist"):
            mag = mag.tolist()

        if not freq or not mag:
            return suggestions

        # Low frequency analysis (< 2 kHz)
        low_freq_indices = [i for i, f in enumerate(freq) if f < 2000]
        if low_freq_indices:
            low_freq_mags = [mag[i] for i in low_freq_indices]
            avg_low_mag = sum(low_freq_mags) / len(low_freq_mags)

            if avg_low_mag < -20:
                suggestions.append(
                    {
                        "category": "Low Frequency Analysis",
                        "severity": "High",
                        "finding": "Low magnitude detected in low-frequency range (< 2 kHz).",
                        "recommendation": "Check for axial winding displacement or core grounding issues.",
                    }
                )

        # Mid frequency analysis (2 kHz - 20 kHz)
        mid_freq_indices = [i for i, f in enumerate(freq) if 2000 <= f < 20000]
        if mid_freq_indices:
            mid_freq_mags = [mag[i] for i in mid_freq_indices]

            if len(mid_freq_mags) > 3:
                mag_variation = max(mid_freq_mags) - min(mid_freq_mags)
                if mag_variation > 15:
                    suggestions.append(
                        {
                            "category": "Mid Frequency Analysis",
                            "severity": "Medium",
                            "finding": f"High magnitude variation ({mag_variation:.2f} dB) in mid-frequency range.",
                            "recommendation": "Inspect for loose connections or bulk winding movement.",
                        }
                    )

        # High frequency analysis (> 20 kHz)
        high_freq_indices = [i for i, f in enumerate(freq) if f >= 20000]
        if high_freq_indices:
            high_freq_mags = [mag[i] for i in high_freq_indices]

            if high_freq_mags:
                avg_high_mag = sum(high_freq_mags) / len(high_freq_mags)

                if avg_high_mag < -40:
                    suggestions.append(
                        {
                            "category": "High Frequency Analysis",
                            "severity": "Medium",
                            "finding": "Reduced response in high-frequency range (> 20 kHz).",
                            "recommendation": "Check for turn-to-turn insulation issues or moisture contamination.",
                        }
                    )

        # Overall magnitude check
        if mag:
            overall_avg = sum(mag) / len(mag)
            if overall_avg < -30:
                suggestions.append(
                    {
                        "category": "Overall Assessment",
                        "severity": "High",
                        "finding": "Overall low magnitude across frequency spectrum.",
                        "recommendation": "Perform detailed insulation resistance test and oil quality analysis.",
                    }
                )

        return suggestions

    # =================================================================
    #  RAG KNOWLEDGE BASE INDEX (for Chat Bot & future Smart Suggestion)
    # =================================================================
    def ensure_embedder():
        """Lazy-load sentence transformer for embeddings."""
        nonlocal rag_embedder
        if rag_embedder is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer

            log("Loading sentence-transformer model (all-MiniLM-L6-v2)...", "INFO")
            rag_embedder = SentenceTransformer("all-MiniLM-L6-v2")
            return True
        except ImportError:
            messagebox.showerror(
                "Embedding Model Missing",
                "SentenceTransformer not available.\n\n"
                "Please install:\n  pip install sentence-transformers",
            )
            log("sentence-transformers not installed.", "ERROR")
        except Exception as e:
            messagebox.showerror(
                "Embedding Error",
                f"Failed to load embedding model:\n{str(e)}",
            )
            log(f"Embedding model load error: {str(e)}", "ERROR")
        return False

    def build_rag_index():
        """Build embeddings from rag_knowledge_base.json and save to disk."""
        nonlocal rag_embeddings, rag_chunks

        if not os.path.exists(RAG_KB_PATH):
            messagebox.showerror(
                "RAG Knowledge Base Missing",
                f"rag_knowledge_base.json not found at:\n{RAG_KB_PATH}",
            )
            log("rag_knowledge_base.json missing.", "ERROR")
            return False

        if not ensure_embedder():
            return False

        try:
            with open(RAG_KB_PATH, "r", encoding="utf-8") as f:
                kb = json.load(f)
        except Exception as e:
            messagebox.showerror(
                "KB Load Error",
                f"Failed to read rag_knowledge_base.json:\n{str(e)}",
            )
            log(f"Error loading RAG KB: {str(e)}", "ERROR")
            return False

        texts = []
        metas = []

        fh_list = kb.get("fault_knowledge", [])
        for fault in fh_list:
            fault_label = fault.get("fault_label", "")
            display_name = fault.get("display_name", fault_label)
            fid = fault.get("id", fault_label)

            # core description
            desc = fault.get("description", "")
            if desc:
                texts.append(f"{display_name} ({fault_label}) - Overview: {desc}")
                metas.append(
                    {
                        "fault_id": fid,
                        "fault_label": fault_label,
                        "display_name": display_name,
                        "section": "description",
                        "text": desc,
                    }
                )

            # typical signatures
            for t in fault.get("typical_sfra_signatures", []):
                texts.append(f"{display_name} - SFRA signature: {t}")
                metas.append(
                    {
                        "fault_id": fid,
                        "fault_label": fault_label,
                        "display_name": display_name,
                        "section": "typical_sfra_signatures",
                        "text": t,
                    }
                )

            # supporting observables
            for t in fault.get("supporting_observables", []):
                texts.append(f"{display_name} - Field evidence: {t}")
                metas.append(
                    {
                        "fault_id": fid,
                        "fault_label": fault_label,
                        "display_name": display_name,
                        "section": "supporting_observables",
                        "text": t,
                    }
                )

            # common root causes
            for t in fault.get("common_root_causes", []):
                texts.append(f"{display_name} - Root cause: {t}")
                metas.append(
                    {
                        "fault_id": fid,
                        "fault_label": fault_label,
                        "display_name": display_name,
                        "section": "common_root_causes",
                        "text": t,
                    }
                )

            # severity levels
            for sev_code, sev_data in fault.get("severity_levels", {}).items():
                sev_name = sev_data.get("name", sev_code)
                summary = sev_data.get("summary", "")
                if summary:
                    texts.append(
                        f"{display_name} - Severity {sev_name} summary: {summary}"
                    )
                    metas.append(
                        {
                            "fault_id": fid,
                            "fault_label": fault_label,
                            "display_name": display_name,
                            "section": f"severity_{sev_code}_summary",
                            "severity": sev_code,
                            "severity_name": sev_name,
                            "text": summary,
                        }
                    )
                for ra in sev_data.get("recommended_actions", []):
                    texts.append(
                        f"{display_name} - Severity {sev_name} recommended action: {ra}"
                    )
                    metas.append(
                        {
                            "fault_id": fid,
                            "fault_label": fault_label,
                            "display_name": display_name,
                            "section": f"severity_{sev_code}_recommended_actions",
                            "severity": sev_code,
                            "severity_name": sev_name,
                            "text": ra,
                        }
                    )

            # tests
            for t in fault.get("recommended_tests", []):
                texts.append(f"{display_name} - Recommended test: {t}")
                metas.append(
                    {
                        "fault_id": fid,
                        "fault_label": fault_label,
                        "display_name": display_name,
                        "section": "recommended_tests",
                        "text": t,
                    }
                )

            # preventive actions
            for t in fault.get("preventive_actions", []):
                texts.append(f"{display_name} - Preventive action: {t}")
                metas.append(
                    {
                        "fault_id": fid,
                        "fault_label": fault_label,
                        "display_name": display_name,
                        "section": "preventive_actions",
                        "text": t,
                    }
                )

        if not texts:
            messagebox.showerror(
                "Empty KB",
                "No text chunks could be generated from rag_knowledge_base.json.",
            )
            log("RAG KB produced no chunks.", "ERROR")
            return False

        log(f"Building RAG index over {len(texts)} chunks...", "INFO")
        try:
            embeddings = rag_embedder.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            embeddings = np.asarray(embeddings, dtype=np.float32)

            os.makedirs(RAG_INDEX_DIR, exist_ok=True)
            np.save(RAG_EMB_FILE, embeddings)
            with open(RAG_META_FILE, "w", encoding="utf-8") as f:
                json.dump(metas, f, indent=2)

            rag_embeddings = embeddings
            rag_chunks = metas
            log("RAG index built and saved.", "SUCCESS")
            return True
        except Exception as e:
            messagebox.showerror(
                "RAG Index Error",
                f"Failed to build RAG index:\n{str(e)}",
            )
            log(f"Error building RAG index: {str(e)}", "ERROR")
            return False

    def ensure_rag_index_loaded():
        """Load previously built RAG index, or build it if missing."""
        nonlocal rag_embeddings, rag_chunks

        if rag_embeddings is not None and rag_chunks is not None:
            return True

        # Try loading existing index
        if os.path.exists(RAG_EMB_FILE) and os.path.exists(RAG_META_FILE):
            try:
                rag_embeddings = np.load(RAG_EMB_FILE)
                with open(RAG_META_FILE, "r", encoding="utf-8") as f:
                    rag_chunks = json.load(f)

                log(
                    f"Loaded RAG index: {rag_embeddings.shape[0]} chunks, dim={rag_embeddings.shape[1]}",
                    "INFO",
                )
                return True
            except Exception as e:
                log(f"Failed to load existing RAG index: {str(e)}", "ERROR")

        # Build a fresh index
        return build_rag_index()

    def rag_retrieve(question):
        """Return (top_chunks, best_similarity)."""
        if not ensure_rag_index_loaded():
            return [], 0.0
        if not ensure_embedder():
            return [], 0.0

        try:
            q_emb = rag_embedder.encode(
                [question],
                normalize_embeddings=True,
                show_progress_bar=False,
            )[0]
            q_emb = np.asarray(q_emb, dtype=np.float32)
        except Exception as e:
            log(f"Embedding error for query: {str(e)}", "ERROR")
            return [], 0.0

        sims = rag_embeddings @ q_emb  # cosine (embeddings normalized)
        if sims.size == 0:
            return [], 0.0

        idx_sorted = np.argsort(-sims)[:RAG_TOP_K]
        best = float(sims[idx_sorted[0]])

        chunks = []
        for idx in idx_sorted:
            meta = rag_chunks[int(idx)]
            meta_copy = dict(meta)
            meta_copy["score"] = float(sims[int(idx)])
            chunks.append(meta_copy)

        return chunks, best

    # =================================================================
    #  LOCAL LLM: PHI-3 MINI via llama-cpp
    # =================================================================
    def ensure_llm_loaded():
        """Lazy-load the Phi-3-mini / 3.5-mini local LLM."""
        nonlocal llm_model

        if llm_model is not None:
            return True

        if Llama is None:
            messagebox.showerror(
                "Local AI Model Missing",
                "llama-cpp-python is not installed.\n\n"
                "Install via:\n  pip install llama-cpp-python",
            )
            log("llama-cpp-python not installed.", "ERROR")
            return False

        if not os.path.exists(LLM_MODEL_PATH):
            messagebox.showerror(
                "Model File Not Found",
                "Local Phi-3-mini / Phi-3.5-mini GGUF model not found.\n\n"
                f"Expected path:\n  {LLM_MODEL_PATH}\n\n"
                "Place the .gguf file there and retry.",
            )
            log("LLM model file missing.", "ERROR")
            return False

        try:
            log("Loading local Phi-3-mini LLM (this may take a moment)...", "INFO")
            llm_model = Llama(
                model_path=LLM_MODEL_PATH,
                n_ctx=4096,
                n_threads=os.cpu_count() or 4,
                logits_all=False,
                embedding=False,
            )
            log("Local Phi-3-mini LLM loaded.", "SUCCESS")
            return True
        except Exception as e:
            messagebox.showerror(
                "Model Load Error",
                f"Failed to load local LLM:\n{str(e)}",
            )
            log(f"Error loading LLM: {str(e)}", "ERROR")
            return False

    def _clean_llm_output(raw_text: str) -> str:
        """Strip prompt-echo / instruction tails from model output."""
        if not raw_text:
            return raw_text

        txt = raw_text.strip()

        # If model produced a 'Solution' section, keep from there.
        for marker in ["#### Solution", "### Solution"]:
            idx = txt.lower().find(marker.lower())
            if idx != -1:
                txt = txt[idx:].strip()
                break

        # Cut off any trailing instruction block.
        for marker in ["### Instruction", "#### Instruction",
                       "you are vidhyut ai, a specialist assistant"]:
            idx = txt.lower().find(marker.lower())
            if idx != -1:
                txt = txt[:idx].strip()
                break

        return txt

    def generate_chat_response(question):
        """
        Use RAG + Phi-3-mini to answer a user question.
        Hard domain lock: if similarity too low, refuse.
        """
        # 1) Retrieve from RAG
        chunks, best_score = rag_retrieve(question)

        if best_score < RAG_MIN_SIM or not chunks:
            log(
                f"Chat question out-of-domain (best similarity={best_score:.3f}).",
                "WARNING",
            )
            return (
                "❌ This question appears to be outside the SFRA / transformer "
                "diagnostics knowledge base of VIDHYUT AI.\n\n"
                "Please ask about SFRA results, transformer faults, severity, "
                "next tests, precautions, or maintenance actions."
            )

        # 2) Load local LLM
        if not ensure_llm_loaded():
            return (
                "⚠️ Local AI model is not available.\n\n"
                "Check that llama-cpp-python is installed and the Phi-3-mini "
                "GGUF file is placed in the expected models folder."
            )

        # 3) Build context string
        ctx_lines = []
        for ch in chunks:
            label = ch.get("fault_label", "fault")
            disp = ch.get("display_name", label)
            section = ch.get("section", "info")
            txt = ch.get("text", "")
            score = ch.get("score", 0.0)
            ctx_lines.append(
                f"[{disp} | {section} | score={score:.3f}]\n{txt}".strip()
            )

        context = "\n\n".join(ctx_lines)

        # 4) Prompt for Phi-3
        prompt = f"""You are VIDHYUT AI, a specialist assistant for SFRA-based transformer diagnostics.

You MUST follow these rules:
- Answer ONLY using the information in the Context.
- If the question is outside SFRA / transformer diagnostics, you MUST say:
  "This question is outside the SFRA knowledge base of VIDHYUT AI."
- Do NOT invent new fault types or tests that are not implied by the context.
- Be concise and technical, suitable for protection / maintenance engineers.

Format your answer using short headings and bullet points with this structure:
- Main Issue
- Likely Fault / Condition
- Severity (qualitative)
- What Tests to Run Next
- Precautions / Operational Advice
- Who Should Review (e.g., utility maintenance, OEM, testing contractor)
- When to Retest / Follow-up

Context:
{context}

User Question:
{question}

Now provide the answer in the requested structured format:
"""

        try:
            result = llm_model(
                prompt,
                max_tokens=512,
                temperature=0.15,
                top_p=0.9,
                stop=["User Question:", "User question:"],
            )
            raw = result["choices"][0]["text"]
            text = _clean_llm_output(raw)
            return text or "⚠️ Local model returned an empty response."
        except Exception as e:
            log(f"LLM generation error: {str(e)}", "ERROR")
            return f"⚠️ Error while generating AI response:\n{str(e)}"

    # =================================================================
    #  SMART SUGGESTION (existing feature)
    # =================================================================
    def generate_rag_suggestions(pipeline_data):
        """Generate suggestions from pipeline data (rule-based for now)."""
        suggestions = []

        try:
            freq = pipeline_data.get("freq", [])
            mag = pipeline_data.get("mag", [])
            metadata = pipeline_data.get("metadata", {})
            taps = pipeline_data.get("taps", [])

            # Handle numpy arrays gracefully
            if hasattr(freq, "tolist"):
                freq = freq.tolist()
            if hasattr(mag, "tolist"):
                mag = mag.tolist()

            if len(freq) == 0 or len(mag) == 0:
                return [
                    {
                        "category": "Data Error",
                        "severity": "Critical",
                        "finding": "No frequency or magnitude data available.",
                        "recommendation": "Please load and convert SFRA data first using Homepage module.",
                    }
                ]

            # Analyze frequency response
            freq_suggestions = analyze_frequency_response(freq, mag)
            suggestions.extend(freq_suggestions)

            # Metadata-based suggestions
            if metadata:
                if not metadata.get("serial"):
                    suggestions.append(
                        {
                            "category": "Data Quality",
                            "severity": "Low",
                            "finding": "Serial number not found in metadata.",
                            "recommendation": "Add transformer serial number for better tracking and comparison.",
                        }
                    )

                if not metadata.get("manufacturer"):
                    suggestions.append(
                        {
                            "category": "Data Quality",
                            "severity": "Low",
                            "finding": "Manufacturer information missing.",
                            "recommendation": "Include manufacturer details for baseline comparison.",
                        }
                    )

            # Tap analysis
            if taps and len(taps) > 0:
                suggestions.append(
                    {
                        "category": "Tap Configuration",
                        "severity": "Info",
                        "finding": f"Detected {len(taps)} tap positions in data.",
                        "recommendation": "Ensure all measurements are from the same tap position for valid comparison.",
                    }
                )

            # Data points analysis
            if len(freq) < 100:
                suggestions.append(
                    {
                        "category": "Measurement Quality",
                        "severity": "Medium",
                        "finding": f"Limited data points detected ({len(freq)} points).",
                        "recommendation": "Consider using higher resolution settings for more detailed analysis.",
                    }
                )

            # Frequency range check
            min_freq = min(freq)
            max_freq = max(freq)

            if min_freq > 100:
                suggestions.append(
                    {
                        "category": "Frequency Coverage",
                        "severity": "Medium",
                        "finding": f"Minimum frequency is {min_freq:.2f} Hz.",
                        "recommendation": "Extend measurement to lower frequencies (< 20 Hz) for core issue detection.",
                    }
                )

            if max_freq < 500_000:
                suggestions.append(
                    {
                        "category": "Frequency Coverage",
                        "severity": "Low",
                        "finding": f"Maximum frequency is {max_freq:.2f} Hz.",
                        "recommendation": "Extend to higher frequencies (> 1 MHz) for detailed winding assessment.",
                    }
                )

        except Exception as e:
            log(f"Error generating RAG suggestions: {str(e)}", "ERROR")
            suggestions.append(
                {
                    "category": "Analysis Error",
                    "severity": "Critical",
                    "finding": f"Error during analysis: {str(e)}",
                    "recommendation": "Check data format and try reloading the file.",
                }
            )

        # Always return at least one card so UI never looks empty
        if not suggestions:
            suggestions.append(
                {
                    "category": "Overall Assessment",
                    "severity": "Info",
                    "finding": "No major anomalies detected by the rule engine for this SFRA trace.",
                    "recommendation": (
                        "Use VIDHYUT AI Chat Bot or detailed engineering review for "
                        "deeper interpretation, comparison with historical baselines, "
                        "and confirmation of healthy condition."
                    ),
                }
            )

        return suggestions

    # ---------------- INBUILT SUGGESTIONS (RAG-BASED) ----------------
    def show_inbuilt_suggestions():
        """Display AI - Smart Suggestion based on pipeline data."""
        log("Loading AI - Smart Suggestion...", "INFO")

        pipeline_data = load_pipeline_data()

        if not pipeline_data:
            messagebox.showwarning(
                "No Data",
                "No pipeline data found!\n\n"
                "Please load and convert SFRA data first:\n"
                "1. Go to Homepage\n"
                "2. Open File\n"
                "3. Click 'Convert for Analysis'",
            )
            log("No pipeline data available", "WARNING")
            return

        # Generate suggestions
        log("Analyzing pipeline data with AI rules...", "INFO")
        rag_suggestions = generate_rag_suggestions(pipeline_data)
        main_app.rag_suggestions = rag_suggestions

        # Display suggestions
        clear_panel(preview_panel)

        container = tk.Frame(preview_panel, bg="white")
        container.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

        # Header
        tk.Label(
            container,
            text="AI-Powered SFRA Analysis Suggestions",
            font=("Segoe UI", 16, "bold"),
            bg="white",
            fg="#123456",
        ).pack(anchor="w", pady=(0, 10))

        # Info banner
        info_frame = tk.Frame(container, bg="#e3f2fd", bd=1, relief=tk.SOLID)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(
            info_frame,
            text="🧠 Generated by rule engine based on your pipeline data",
            font=("Segoe UI", 10, "bold"),
            bg="#e3f2fd",
            fg="#1565c0",
        ).pack(anchor="w", padx=15, pady=8)

        tk.Label(
            info_frame,
            text=(
                f"Data Points Analyzed: {len(pipeline_data.get('freq', []))} | "
                f"Frequency Range: {min(pipeline_data.get('freq', [0])):.2f} - "
                f"{max(pipeline_data.get('freq', [0])):.2f} Hz"
            ),
            font=("Segoe UI", 9),
            bg="#e3f2fd",
            fg="#1976d2",
        ).pack(anchor="w", padx=15, pady=(0, 8))

        # Display suggestions by severity
        severity_colors = {
            "Critical": "#ffebee",
            "High": "#fff3e0",
            "Medium": "#fff9c4",
            "Low": "#f1f8e9",
            "Info": "#e8f5e9",
        }

        severity_icons = {
            "Critical": "🛑",
            "High": "⚠️",
            "Medium": "🟡",
            "Low": "🔵",
            "Info": "ℹ️",
        }

        for idx, suggestion in enumerate(rag_suggestions, 1):
            severity = suggestion.get("severity", "Info")
            category = suggestion.get("category", "General")
            finding = suggestion.get("finding", "")
            recommendation = suggestion.get("recommendation", "")

            card = tk.Frame(
                container,
                bg=severity_colors.get(severity, "#ffffff"),
                bd=1,
                relief=tk.SOLID,
            )
            card.pack(fill=tk.X, pady=8)

            header = tk.Frame(card, bg=severity_colors.get(severity, "#ffffff"))
            header.pack(fill=tk.X, padx=15, pady=(10, 5))

            tk.Label(
                header,
                text=f"{severity_icons.get(severity, '•')} {category}",
                font=("Segoe UI", 11, "bold"),
                bg=severity_colors.get(severity, "#ffffff"),
                fg="#333",
            ).pack(side="left")

            tk.Label(
                header,
                text=f"[{severity}]",
                font=("Segoe UI", 9, "bold"),
                bg=severity_colors.get(severity, "#ffffff"),
                fg="#666",
            ).pack(side="right")

            tk.Label(
                card,
                text=f"Finding: {finding}",
                font=("Segoe UI", 10),
                bg=severity_colors.get(severity, "#ffffff"),
                fg="#444",
                wraplength=700,
                justify="left",
            ).pack(anchor="w", padx=15, pady=(0, 5))

            tk.Label(
                card,
                text=f"Recommendation: {recommendation}",
                font=("Segoe UI", 10, "italic"),
                bg=severity_colors.get(severity, "#ffffff"),
                fg="#555",
                wraplength=700,
                justify="left",
            ).pack(anchor="w", padx=15, pady=(0, 10))

        log(f"Generated {len(rag_suggestions)} AI suggestions.", "SUCCESS")

        # Update metadata panel
        update_metadata_suggestions("rag", pipeline_data)

    # =================================================================
    #  IMPORT SUGGESTIONS (legacy)
    # =================================================================
    def import_suggestions():
        """Import plain-text suggestions from an external file."""
        log("Opening file dialog for suggestion import...", "INFO")

        filetypes = [
            ("Text Files", "*.txt"),
            ("CSV Files", "*.csv"),
            ("All Files", "*.*"),
        ]

        fp = filedialog.askopenfilename(
            title="Import Suggestions",
            filetypes=filetypes,
            initialdir=os.path.expanduser("~"),
        )

        if not fp:
            log("Import cancelled by user.", "WARNING")
            return

        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            imported_items = []
            lines = content.strip().split("\n")

            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    imported_items.append(line)

            if not imported_items:
                messagebox.showwarning(
                    "Empty File", "No suggestions found in the selected file."
                )
                return

            main_app.imported_suggestions = imported_items

            display_imported_suggestions(fp, imported_items)

            log(
                f"Imported {len(imported_items)} suggestions from {os.path.basename(fp)}",
                "SUCCESS",
            )

        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import suggestions:\n{str(e)}")
            log(f"Import error: {str(e)}", "ERROR")

    def display_imported_suggestions(filepath, items):
        """Display imported suggestions in preview panel."""
        clear_panel(preview_panel)

        container = tk.Frame(preview_panel, bg="white")
        container.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

        tk.Label(
            container,
            text="Imported Suggestions",
            font=("Segoe UI", 16, "bold"),
            bg="white",
        ).pack(anchor="w", pady=(0, 10))

        info_frame = tk.Frame(container, bg="#fffbf0", bd=1, relief=tk.SOLID)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(
            info_frame,
            text=f"📁 Source: {os.path.basename(filepath)}",
            font=("Segoe UI", 10),
            bg="#fffbf0",
            fg="#666",
        ).pack(anchor="w", padx=15, pady=8)

        tk.Label(
            info_frame,
            text=f"Total Suggestions: {len(items)}",
            font=("Segoe UI", 10),
            bg="#fffbf0",
            fg="#666",
        ).pack(anchor="w", padx=15, pady=(0, 8))

        for idx, suggestion in enumerate(items, 1):
            sugg_frame = tk.Frame(container, bg="white")
            sugg_frame.pack(fill=tk.X, pady=5)

            tk.Label(
                sugg_frame,
                text=f"{idx}.",
                font=("Segoe UI", 10, "bold"),
                bg="white",
                fg="#2c5aa0",
            ).pack(side="left", padx=(0, 10))

            tk.Label(
                sugg_frame,
                text=suggestion,
                font=("Segoe UI", 10),
                bg="white",
                fg="#333",
                wraplength=650,
                justify="left",
            ).pack(side="left", fill=tk.X, expand=True)

        update_metadata_suggestions("imported", filepath)

    # =================================================================
    #  METADATA PANEL
    # =================================================================
    def update_metadata_suggestions(mode, data=None):
        """Update metadata panel with suggestions / chat info."""
        clear_panel(metadata_panel)

        def add(name, val):
            tk.Label(
                metadata_panel,
                text=name,
                font=("Segoe UI", 9, "bold"),
                bg="#fafafa",
            ).pack(anchor="w", padx=10, pady=(5, 0))

            tk.Label(
                metadata_panel,
                text=val,
                bg="#fafafa",
                fg="#555",
                wraplength=220,
                justify="left",
            ).pack(anchor="w", padx=20, pady=(0, 5))

        if mode == "rag":
            add("Type", "AI - Smart Suggestion")
            add("Engine", "Rule-based SFRA analyzer")

            if main_app.rag_suggestions:
                add("Total Suggestions", str(len(main_app.rag_suggestions)))

                severity_count = {}
                for sugg in main_app.rag_suggestions:
                    sev = sugg.get("severity", "Info")
                    severity_count[sev] = severity_count.get(sev, 0) + 1

                add(
                    "By Severity",
                    "\n".join([f"{k}: {v}" for k, v in severity_count.items()]),
                )

            if data:
                add("Data Points", str(len(data.get("freq", []))))
                metadata = data.get("metadata", {})
                if metadata.get("serial"):
                    add("Serial Number", metadata["serial"])

            add("Generated On", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        elif mode == "imported":
            add("Type", "Imported Suggestions")

            if isinstance(data, str):
                add("Source File", os.path.basename(data))
                add("Location", os.path.dirname(data))

            add("Total Items", str(len(main_app.imported_suggestions)))
            add("Imported On", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        elif mode == "chat":
            add("Type", "AI - Chat Bot (Local LLM + RAG)")
            add("LLM Model", os.path.basename(LLM_MODEL_PATH))
            add("RAG KB", os.path.basename(RAG_KB_PATH))
            if rag_embeddings is not None:
                add("KB Chunks", str(rag_embeddings.shape[0]))
            add("Updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # =================================================================
    #  AI CHAT BOT SYSTEM (UI + logic)
    # =================================================================
    def open_ai_chat_bot():
        """Open the AI - Chat Bot system in the preview panel."""
        clear_panel(preview_panel)

        chat_root = tk.Frame(preview_panel, bg="white")
        chat_root.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

        # Header
        tk.Label(
            chat_root,
            text="AI - Chat Bot System",
            font=("Segoe UI", 16, "bold"),
            bg="white",
            fg="#123456",
        ).pack(anchor="w", pady=(0, 5))

        tk.Label(
            chat_root,
            text=(
                "Ask VIDHYUT AI about SFRA-based transformer diagnostics.\n"
                "⚠️ The bot is strictly limited to the internal SFRA knowledge base."
            ),
            font=("Segoe UI", 9),
            bg="white",
            fg="#555",
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # Chat log
        chat_frame = tk.Frame(chat_root, bg="#f7f7f7", bd=1, relief=tk.SOLID)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 10))

        chat_text = tk.Text(
            chat_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#222",
            relief=tk.FLAT,
            padx=10,
            pady=10,
        )
        chat_text.pack(fill=tk.BOTH, expand=True)

        chat_text.insert(
            tk.END,
            "VIDHYUT AI is ready.\n"
            "You can ask things like:\n"
            "• \"What does a high mid-band energy and strong HF damping indicate?\"\n"
            "• \"What tests should I run if inter-turn fault is suspected?\"\n\n",
        )
        chat_text.config(state=tk.DISABLED)

        # Input area
        input_frame = tk.Frame(chat_root, bg="white")
        input_frame.pack(fill=tk.X)

        input_box = tk.Text(
            input_frame,
            height=3,
            font=("Segoe UI", 10),
            bg="#fafafa",
            fg="#222",
            relief=tk.SOLID,
            wrap=tk.WORD,
        )
        input_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8), pady=(0, 2))

        send_btn = tk.Button(
            input_frame,
            text="Ask",
            font=("Segoe UI", 10, "bold"),
            bg="#1565c0",
            fg="white",
            activebackground="#0d47a1",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=4,
            cursor="hand2",
        )
        send_btn.pack(side=tk.RIGHT, pady=(0, 2))

        # Helper to append text
        def append(role, text):
            chat_text.config(state=tk.NORMAL)
            if role == "user":
                chat_text.insert(tk.END, f"\n👤 You:\n{text.strip()}\n")
            else:
                chat_text.insert(tk.END, f"\n🤖 VIDHYUT AI:\n{text.strip()}\n")
            chat_text.see(tk.END)
            chat_text.config(state=tk.DISABLED)

        # Send handler
        def on_send(event=None):
            question = input_box.get("1.0", tk.END).strip()
            if not question:
                return

            input_box.delete("1.0", tk.END)
            append("user", question)

            log(f"AI Chat question: {question}", "INFO")

            # Show thinking indicator + disable button
            send_btn.config(state=tk.DISABLED, text="Thinking...")
            chat_text.config(state=tk.NORMAL)
            chat_text.insert(tk.END, "\n🤖 VIDHYUT AI is thinking...\n")
            chat_text.see(tk.END)
            chat_text.config(state=tk.DISABLED)
            chat_root.update_idletasks()

            # Generate answer (blocking call for now)
            answer = generate_chat_response(question)
            append("bot", answer)

            # Restore button
            send_btn.config(state=tk.NORMAL, text="Ask")

            # Update metadata
            update_metadata_suggestions("chat")

        send_btn.config(command=on_send)
        input_box.bind("<Control-Return>", on_send)
        input_box.bind("<Shift-Return>", on_send)

        # Initial metadata
        update_metadata_suggestions("chat")

        log("AI Chat Bot UI loaded.", "SUCCESS")

    # =================================================================
    #  SMART SUGGESTIONS LANDING UI
    # =================================================================
    def create_smart_suggestions_ui():
        """Create the main Smart Suggestions UI."""
        clear_panel(workspace_frame)
        clear_panel(preview_panel)
        clear_panel(metadata_panel)

        # Workspace title
        tk.Label(
            workspace_frame,
            text="Smart Suggestions",
            font=("Segoe UI", 14, "bold"),
            bg="#f5f5f5",
        ).pack(anchor="w", padx=15, pady=(15, 20))

        # Operations list
        operations = [
            ("1. AI - Smart Suggestion", show_inbuilt_suggestions),
            ("2. AI - Chat Bot system", open_ai_chat_bot),
            ("3. Import Suggestions (Text/CSV)", import_suggestions),
        ]

        for text, cmd in operations:
            lbl = tk.Label(
                workspace_frame,
                text=text,
                font=("Segoe UI", 11),
                bg="#f5f5f5",
                anchor="w",
                padx=15,
                pady=8,
                cursor="hand2",
            )
            lbl.pack(fill=tk.X)
            lbl.bind("<Button-1>", lambda e, f=cmd: f())
            lbl.bind("<Enter>", lambda e, L=lbl: L.config(bg="#e8e8e8"))
            lbl.bind("<Leave>", lambda e, L=lbl: L.config(bg="#f5f5f5"))

        # ================= PREVIEW LANDING =================
        clear_panel(preview_panel)

        landing = tk.Frame(preview_panel, bg="white")
        landing.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        tk.Label(
            landing,
            text="AI - Smart Suggestions & Chat",
            font=("Segoe UI", 16, "bold"),
            bg="white",
            fg="#222",
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(
            landing,
            text=(
                "Use AI to interpret SFRA results and navigate transformer diagnostics:\n"
                "• AI - Smart Suggestion: one-click summary based on your pipeline data.\n"
                "• AI - Chat Bot system: ask VIDHYUT AI targeted questions using the SFRA knowledge base.\n"
                "• Import Suggestions: bring in your own checklists or notes from text / CSV files."
            ),
            font=("Segoe UI", 10),
            bg="white",
            fg="#555",
            justify="left",
        ).pack(anchor="w", pady=(0, 20))

        # Primary CTA button
        smart_btn = tk.Button(
            landing,
            text="⚡ Run AI - Smart Suggestion",
            font=("Segoe UI", 11, "bold"),
            bg="#1565c0",
            fg="white",
            activebackground="#0d47a1",
            activeforeground="white",
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor="hand2",
            command=show_inbuilt_suggestions,
        )
        smart_btn.pack(anchor="w", pady=(0, 10))

        # Secondary CTA – Chat Bot
        chat_btn = tk.Button(
            landing,
            text="💬 Open AI - Chat Bot system",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#1565c0",
            activebackground="#e3f2fd",
            activeforeground="#0d47a1",
            relief=tk.SOLID,
            bd=1,
            padx=18,
            pady=8,
            cursor="hand2",
            command=open_ai_chat_bot,
        )
        chat_btn.pack(anchor="w", pady=(5, 10))

        tk.Label(
            landing,
            text=(
                "Tip: Ensure you have loaded a file and clicked 'Convert for Analysis' "
                "in the Homepage module so the AI can see your SFRA pipeline."
            ),
            font=("Segoe UI", 9),
            bg="white",
            fg="#777",
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

        # Initial metadata
        tk.Label(
            metadata_panel,
            text="No suggestions loaded",
            font=("Segoe UI", 10),
            bg="#fafafa",
            fg="#999",
        ).pack(pady=20)

        log("Smart Suggestions module loaded", "INFO")

    # ---------------- MONKEY PATCH ----------------
    original_handler = main_app.on_container_click

    def patched(name):
        if name == "Smart Suggestions":
            create_smart_suggestions_ui()
        else:
            original_handler(name)

    main_app.on_container_click = patched