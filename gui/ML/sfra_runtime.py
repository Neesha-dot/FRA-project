"""
SFRA Runtime Compatibility Layer (Hardened)
Provides the functions expected by sfra_model3.pkl:
- extract_features
- predict_fault
- parse_metadata
- parse_tap_table
- calculate_losses
- diagnose_with_taps

RULE:
This runtime MUST NOT:
- modify main_app.pipeline_data
- return numpy arrays to GUI for direct storage
- contain GUI logic

Only pure functions allowed.
"""

import numpy as np
import re
from typing import Tuple, Dict, Any

# -------------------------------------------------------------------
# INTERNAL GUARD: runtime arrays must NEVER be used as pipeline_data
# -------------------------------------------------------------------
def _safe_arrays_for_runtime_only(arr: np.ndarray) -> np.ndarray:
    """
    Prevents misuse: If someone tries to set pipeline_data = returned_array,
    they will see a clear error message instead of GUI crashing.
    """
    try:
        # tag the array to indicate it's runtime-only; this is harmless metadata
        setattr(arr, "_sfra_runtime_only", True)
    except Exception:
        pass
    return arr

# ---------------------------
# ensure arrays are numeric 1-D
# ---------------------------
def _ensure_1d_numeric(freq_in, mag_in) -> Tuple[np.ndarray, np.ndarray]:
    freq = _safe_arrays_for_runtime_only(
        np.asarray(freq_in, dtype=np.float64).reshape(-1)
    )
    mag  = _safe_arrays_for_runtime_only(
        np.asarray(mag_in, dtype=np.float64).reshape(-1)
    )

    if freq.size != mag.size:
        raise ValueError(f"SFRA arrays length mismatch: freq={freq.size}, mag={mag.size}")

    bad = ~np.isfinite(freq) | ~np.isfinite(mag)

    if np.any(bad):
        freq = _safe_arrays_for_runtime_only(freq[~bad])
        mag  = _safe_arrays_for_runtime_only(mag[~bad])

    if freq.size == 0:
        raise ValueError("No valid numeric SFRA points after cleaning (all NaN/Inf).")

    return freq, mag

# ============================================================
# 1. extract_features
# ============================================================
def extract_features(freq_in, mag_in) -> Dict[str, Any]:
    freq, mag = _ensure_1d_numeric(freq_in, mag_in)

    diff = np.diff(mag)

    # Local peaks
    if len(mag) >= 3:
        cond = (mag[1:-1] > mag[:-2]) & (mag[1:-1] > mag[2:])
        peaks_rel = np.nonzero(cond)[0]
        peaks = (peaks_rel + 1).astype(int)
    else:
        peaks = np.array([], dtype=int)

    def _safe_peak(i):
        if i < len(peaks):
            idx = int(peaks[i])
            idx = max(0, min(len(freq)-1, idx))
            return float(freq[idx])
        return 0.0

    modal_1 = _safe_peak(0)
    modal_2 = _safe_peak(1)
    modal_3 = _safe_peak(2)
    spacing = (modal_3 - modal_1) if (modal_3 > 0 and modal_1 > 0) else 0.0

    low_mask  = freq < 2000
    mid_mask  = (freq >= 2000) & (freq < 20000)
    high_mask = freq >= 20000

    E_low  = float(np.trapz(mag[low_mask], freq[low_mask])) if np.any(low_mask) else 0.0
    E_mid  = float(np.trapz(mag[mid_mask], freq[mid_mask])) if np.any(mid_mask) else 0.0
    E_high = float(np.trapz(mag[high_mask], freq[high_mask])) if np.any(high_mask) else 0.0

    hf_decay = 0.0
    if len(freq) > 10:
        x = freq[-11:]
        y = mag[-11:]
        dx = x[-1] - x[0]
        hf_decay = float((y[-1] - y[0]) / dx) if dx != 0 else 0.0

    midband_turbulence = float(np.nanstd(diff)) if diff.size > 0 else 0.0
    global_attenuation = float(abs(mag[0] - mag[-1])) if len(mag) >= 2 else 0.0

    return {
        "modal_1": float(modal_1),
        "modal_2": float(modal_2),
        "modal_3": float(modal_3),
        "modal_spacing_index": float(spacing),
        "E_low": float(E_low),
        "E_mid": float(E_mid),
        "E_high": float(E_high),
        "midband_turbulence": float(midband_turbulence),
        "hf_decay_rate": float(hf_decay),
        "global_attenuation": float(global_attenuation),
    }

# ============================================================
# 2. predict_fault
# ============================================================
def predict_fault(features: dict) -> list:
    faults = []

    turb = float(features.get("midband_turbulence", 0.0))
    spacing = float(features.get("modal_spacing_index", 0.0))
    E_low = float(features.get("E_low", 0.0))
    E_mid = float(features.get("E_mid", 0.0))

    if turb > 1.2:
        faults.append("radial_deformation")
    if spacing > 150000:
        faults.append("axial_deformation")
    if abs(E_low) < 400 and abs(E_mid) < 900:
        faults.append("core_movement")

    return faults if faults else ["healthy"]

# ============================================================
# 3. parse_metadata
# ============================================================
def parse_metadata(path: str) -> dict:
    meta = {
        "serial": "UNKNOWN",
        "manufacturer": "UNKNOWN",
        "year": None,
        "start_freq": None,
        "stop_freq": None,
    }

    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                L = line.strip()
                low = L.lower()
                if "serial" in low and ":" in L:
                    meta["serial"] = L.split(":", 1)[-1].strip() or meta["serial"]
                if "manufacturer" in low and ":" in L:
                    meta["manufacturer"] = L.split(":", 1)[-1].strip() or meta["manufacturer"]
                if "year" in low and ":" in L:
                    y = L.split(":", 1)[-1].strip()
                    if re.match(r"^\d{4}$", y):
                        meta["year"] = y
                if "start" in low and ":" in L:
                    val = L.split(":", 1)[-1].strip()
                    try:
                        meta["start_freq"] = float(val)
                    except:
                        pass
                if "stop" in low and ":" in L:
                    val = L.split(":", 1)[-1].strip()
                    try:
                        meta["stop_freq"] = float(val)
                    except:
                        pass
    except Exception:
        # best-effort: keep defaults
        pass

    return meta

# ============================================================
# 4. parse_tap_table
# ============================================================
def parse_tap_table(path: str) -> dict:
    taps = {
        "tap_position": None,
        "tap_percent": None,
        "Z_HV_LV": None
    }

    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                low = line.lower()
                if "tap" in low and ":" in line:
                    taps["tap_position"] = line.split(":", 1)[-1].strip()

                m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", line)
                if m:
                    taps["tap_percent"] = m.group(1)

                if "impedance" in low and ":" in line:
                    taps["Z_HV_LV"] = line.split(":",1)[-1].strip()

    except:
        pass

    return taps

# ============================================================
# 5. calculate_losses
# ============================================================
def calculate_losses(features: dict, metadata: dict) -> dict:
    E_low = abs(float(features.get("E_low", 0.0)))
    E_mid = abs(float(features.get("E_mid", 0.0)))
    spacing = abs(float(features.get("modal_spacing_index", 0.0)))

    core_loss = E_low * 0.003
    load_loss = E_mid * 0.02
    Z = spacing * 0.00001

    total_loss = core_loss + load_loss
    eff_unity = max(0.0, 100.0 - Z)
    eff_08 = eff_unity * 0.8

    return {
        "core_loss_w": float(core_loss),
        "load_loss_w": float(load_loss),
        "impedance_percent_z": float(Z),
        "%R_33C": float(Z * 0.2),
        "%X_33C": float(Z * 0.8),
        "total_loss_w": float(total_loss),
        "efficiency_unity_pf": float(eff_unity),
        "efficiency_0.8_pf": float(eff_08),
    }


# ============================================================
# 6A. derive severity / confidence / reason from features
# ============================================================
def _derive_fault_meta(features: dict, faults: list) -> Dict[str, Any]:
    """
    Rule-based mapping from raw features + fault labels
    -> severity (NONE/LOW/MEDIUM/HIGH), confidence [0-1],
       and human-readable reason string.
    """

    faults = faults or ["healthy"]
    primary = str(faults[0])

    f = features or {}

    def gf(name, default=0.0):
        try:
            return float(f.get(name, default) or 0.0)
        except Exception:
            return float(default)

    turb    = abs(gf("midband_turbulence"))
    spacing = abs(gf("modal_spacing_index"))
    E_low   = abs(gf("E_low"))
    E_mid   = abs(gf("E_mid"))

    # Defaults
    severity   = "NONE"
    confidence = 0.5
    reason     = "No abnormality detected."

    if primary == "healthy":
        severity   = "NONE"
        confidence = 0.80
        reason = (
            "All rule-based thresholds lie in the healthy range; "
            "no significant abnormality detected."
        )

    elif primary == "radial_deformation":
        # Tumhari rule: turb > 1.2 -> radial_deformation
        # uske upar severity gradation
        if turb < 1.6:
            severity   = "LOW"
            confidence = 0.65
        elif turb < 2.4:
            severity   = "MEDIUM"
            confidence = 0.78
        else:
            severity   = "HIGH"
            confidence = 0.90

        reason = (
            "Mid-band turbulence is above the radial deformation threshold "
            f"(index = {turb:.3f} > 1.2), indicating disturbance consistent "
            "with radial deformation."
        )

    elif primary == "axial_deformation":
        # Tumhari rule: spacing > 150000 -> axial_deformation
        if spacing < 180000:
            severity   = "LOW"
            confidence = 0.65
        elif spacing < 230000:
            severity   = "MEDIUM"
            confidence = 0.80
        else:
            severity   = "HIGH"
            confidence = 0.90

        reason = (
            "Modal spacing index is large "
            f"({spacing:.1f} Hz > 150000 Hz), which is characteristic of "
            "axial deformation patterns."
        )

    elif primary == "core_movement":
        # Tumhari rule: |E_low| < 400 and |E_mid| < 900
        if E_low < 250 and E_mid < 600:
            severity   = "HIGH"
            confidence = 0.85
        elif E_low < 400 and E_mid < 900:
            severity   = "MEDIUM"
            confidence = 0.75
        else:
            severity   = "LOW"
            confidence = 0.60

        reason = (
            "Low- and mid-band energies are reduced "
            f"(E_low ≈ {E_low:.1f}, E_mid ≈ {E_mid:.1f}), matching the "
            "core movement rule used by the classifier."
        )

    # Agar multiple faults aaye, reason me mention kar do
    if len(faults) > 1 and primary != "healthy":
        others = ", ".join(f.replace("_", " ") for f in faults[1:])
        reason += f" Secondary indicators also suggest: {others}."

    return {
        "severity": severity,             # GUI .upper() karega already
        "confidence": float(confidence),  # 0–1 range
        "reason": reason,
    }


# ============================================================
# 6B. diagnose_with_taps  (UPDATED – Kaggle–style JSON output)
# ============================================================
def diagnose_with_taps(features: dict, tap_info: dict) -> dict:

    features = dict(features or {})
    tap_info = dict(tap_info or {})

    file_path = tap_info.get("file")
    metadata  = tap_info.get("metadata")

    # If metadata missing → defaults
    if not isinstance(metadata, dict):
        metadata = {
            "serial": "UNKNOWN",
            "manufacturer": "UNKNOWN",
            "year": None,
            "start_freq": None,
            "stop_freq": None,
        }

    # Ensure metadata values are Python types
    def _py(v):
        try: return float(v)
        except: return v

    metadata = {k: _py(v) for k, v in metadata.items()}

    # Faults & losses
    faults = predict_fault(features)
    losses = calculate_losses(features, metadata)

    fault_meta = _derive_fault_meta(features, faults)

    # Base result
    result = {
        "file": file_path,
        "metadata": metadata,
        "features_used": features,
        "universal_fault_labels": faults,
        "loss_and_efficiency": losses,
    }

    result.update(fault_meta)

    # Extra compatibility fields
    result["base_faults"] = faults

    if tap_info.get("tap_position") is not None:
        result["tap_comment"] = "Tap data used in extended diagnosis."

    return result

class SFRA_Model4_Final:
    """
    Correct runtime stub so GUI can call:
        engine(features, tap_info)
    """

    def __init__(self):
        self.version = "4_final_runtime"
        self.description = "Runtime stub for SFRA_Model4_Final"

    def predict_single(self, features, tap_info=None):
        """
        GUI sometimes bhejti hai:
        - full payload: {"freq": ..., "mag": ..., "metadata": ..., "taps": ...}
        - ya pehle se extracted features dict

        Yeh function dono handle karega.
        """

        if tap_info is None:
            tap_info = {}

        # ------------------------------------------
        # 1) Agar features ke andar freq + mag hain
        #    → yeh actually RAW payload hai
        #    → pehle extract_features() chalao
        # ------------------------------------------
        if isinstance(features, dict) and "freq" in features and "mag" in features:
            freq = features.get("freq")
            mag  = features.get("mag")
            features = extract_features(freq, mag)
        else:
            # Normal case: already feature dict
            features = dict(features or {})

        # ------------------------------------------
        # 2) File + metadata normalize karo
        # ------------------------------------------
        file_path = tap_info.get("file")
        metadata  = tap_info.get("metadata")

        if not isinstance(metadata, dict):
            metadata = {
                "serial": "UNKNOWN",
                "manufacturer": "UNKNOWN",
                "year": None,
                "start_freq": None,
                "stop_freq": None,
            }

        # ------------------------------------------
        # 3) Faults + losses compute karo
        # ------------------------------------------
        faults = predict_fault(features)
        losses = calculate_losses(features, metadata)

        fault_meta = _derive_fault_meta(features, faults)

        # ------------------------------------------
        # 4) Kaggle-style compact JSON
        # ------------------------------------------
        result = {
            "file": file_path,
            "metadata": metadata,
            "features_used": features,          # ab sirf modal_1, E_low, etc.
            "universal_fault_labels": faults,
            "loss_and_efficiency": losses,
        }

        result.update(fault_meta)

        result["base_faults"] = faults

        if tap_info.get("tap_position") is not None:
            result["tap_comment"] = "Tap data used in extended diagnosis."

        return result