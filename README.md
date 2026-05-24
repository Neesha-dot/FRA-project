# Vidhyut — AI-Powered FRA Transformer Diagnostics

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python"/>
  <img src="https://img.shields.io/badge/ML-Scikit--Learn-orange?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Cloud-Firebase-yellow?style=for-the-badge&logo=firebase"/>
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge"/>
</p>

> An AI-powered desktop application for automated Frequency Response Analysis (FRA) diagnostics of power transformers — with ML fault classification, explainable AI graphs, and PDF report generation.

---

## About

**Vidhyut** (विद्युत — *electricity*) is a final year engineering project built for real-world transformer diagnostics. It solves three key problems:

- FRA data from different vendors (Omicron, Megger, Doble) cannot be easily compared
- Manual FRA interpretation requires deep expert knowledge
- No automated report generation tool exists for Indian field engineers

Tested on real transformer data from **MSETCL** (220kV) and **BHEL** (400/220kV).

---

## Key Features

-  Multi-format FRA parser — CSV, XML, and vendor-specific formats
-  ML fault classification with 0–100% severity score
-  7 analysis modules — Modal Frequencies, Energy Bands, Turbulence, HF Decay, Attenuation, Loss & Efficiency, Fault Classification
-  Explainable AI — Peak Activation Map shows *why* a fault was triggered
-  Auto PDF report generation with digital signature support
-  Firebase Firestore cloud integration for report storage and sharing

---

## Project Structure

```
FRA-project/
│
├── gui/                  # All UI screens and analysis modules
├── theme/                # Custom UI theme files
├── app.py                # Application entry point
├── gui_app.py            # Main GUI launcher
├── requirements.txt      # Python dependencies
└── recent.txt            # Recently opened files log
```

---

## Getting Started

**Prerequisites:** Python 3.10+, pip, Windows 10/11

```bash
# 1. Clone the repo
git clone https://github.com/Neesha-dot/FRA-project.git
cd FRA-project

# 2. Activate virtual environment (Windows)
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

---

## Supported Fault Types

| Fault | Frequency Region |
|---|---|
| Axial Winding Displacement | Low — 1 to 20 kHz |
| Radial Deformation | Mid — 20 to 400 kHz |
| Inter-turn Short Circuit | Mid–High — 20 kHz to 2 MHz |
| Core Movement / Grounding | Very Low — below 1 kHz |
| Bulk Winding Movement | Full spectrum |
| Insulation Degradation | High — above 400 kHz |

---

## Standards Referenced

IEC 60076-18 · IEEE C57.149

