# Vidhyut — AI-Powered FRA Transformer Diagnostics

An AI-powered desktop application for automated Frequency Response Analysis (FRA) diagnostics of power transformers — with ML fault classification, explainable AI graphs, and PDF report generation.


About
Vidhyut (विद्युत — electricity) is a final year engineering project built for real-world transformer diagnostics. It solves three key problems:

FRA data from different vendors (Omicron, Megger, Doble) cannot be easily compared
Manual FRA interpretation requires deep expert knowledge
No automated report generation tool exists for Indian field engineers

Tested on real transformer data from MSETCL (220kV) and BHEL (400/220kV).

Key Features

🔌 Multi-format FRA parser — CSV, XML, and vendor-specific formats
🤖 ML fault classification with 0–100% severity score
📊 7 analysis modules — Modal Frequencies, Energy Bands, Turbulence, HF Decay, Attenuation, Loss & Efficiency, Fault Classification
📈 Explainable AI — Peak Activation Map shows why a fault was triggered
📄 Auto PDF report generation with digital signature support
☁️ Firebase Firestore cloud integration for report storage and sharing
🧠 RAG-based smart suggestions using local knowledge base


Project Structure
FRA-project/
│
├── gui/
│   ├── ML/
│   │   ├── predict_fault.py        # ML inference — fault classification
│   │   ├── parse_metadata.py       # FRA file metadata parser
│   │   ├── sfra_runtime.py         # Runtime SFRA signal processing
│   │   ├── sfra_model3.pkl         # Trained ML model v3
│   │   ├── sfra_model4.pkl         # Trained ML model v4
│   │   └── sfra_model4_v2.pkl      # Trained ML model v4.2
│   │
│   ├── models/
│   │   ├── BHEL_400_220_315_ICT_II_baseline.csv   # Baseline FRA data
│   │   ├── BHEL_400_220_315_ICT_II_baseline.json  # Baseline config
│   │   └── BHEL_400_220_315_ICT_II_model.pkl      # Transformer-specific model
│   │
│   ├── rag_index/
│   │   ├── rag_chunks.json         # RAG knowledge base chunks
│   │   └── rag_embeddings.npy      # Precomputed embeddings
│   │
│   ├── assets/                     # Icons and UI assets
│   ├── LLM_model/                  # LLM integration module
│   ├── analyse_graph.py            # Graph analysis module
│   ├── analyse_graph2.py           # Extended graph analysis
│   ├── file_operations.py          # File import/export handler
│   ├── generate_report.py          # PDF report generator
│   ├── Homepage.py                 # Homepage screen
│   ├── Landing_home.py             # Landing/splash entry screen
│   ├── Login.py                    # Login screen
│   ├── Main_page.py                # Main application window
│   ├── Monitor_performance.py      # Performance monitoring module
│   ├── send_report.py              # Email report dispatch
│   ├── smart_suggestions.py        # RAG-based smart suggestions
│   ├── splash_screen.py            # Splash screen on launch
│   └── rag_knowledge_base.json     # Domain knowledge base
│
├── assets/                         # Global assets
├── theme/                          # Custom UI theme
├── app.py                          # Application entry point
├── gui_app.py                      # GUI launcher
├── requirements.txt                # Python dependencies
└── recent.txt                      # Recently opened files

Getting Started
Prerequisites: Python 3.10+, pip, Windows 10/11

# 1. Clone the repo
git clone https://github.com/Neesha-dot/FRA-project.git
cd FRA-project

# 2. Activate virtual environment (Windows)
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python .\gui\Main_page.py

Supported Fault Types
FaultFrequency RegionAxial Winding DisplacementLow — 1 to 20 kHzRadial DeformationMid — 20 to 400 kHzInter-turn Short CircuitMid–High — 20 kHz to 2 MHzCore Movement / GroundingVery Low — below 1 kHzBulk Winding MovementFull spectrumInsulation DegradationHigh — above 400 kHz

Analysis Modules
ModuleDescriptionModal FrequenciesResonance peak identificationEnergy BandsLow / Mid / High band energy distributionTurbulenceMid-band irregularity — radial fault indicatorHF DecayHigh-frequency signal attenuation trackingAttenuationOverall signal loss across spectrumLoss & EfficiencyCore loss, load loss, efficiency calculationFault ClassificationML model — fault type + severity score



