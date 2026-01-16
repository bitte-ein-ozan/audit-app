import streamlit as st
import pandas as pd
import os
import io
from dotenv import load_dotenv
from modules.utils import extract_text_from_pdf, extract_pages_from_pdf, load_excel_data, excel_to_csv_string
from modules.auditor import InvoiceAuditor
from modules.parser import InvoiceParser
from modules.pdf_generator import generate_audit_pdf
import plotly.express as px

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Breer Audit Cockpit",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# MODERN CSS INJECTION
st.markdown("""
<style>
    /* Global Background */
    .stApp {
        background-color: #F8F9FB;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    
    /* Header Area styling to align Logo and Text */
    .header-container {
        display: flex;
        align-items: center;
        padding-bottom: 2rem;
        border-bottom: 1px solid #E0E0E0;
        margin-bottom: 2rem;
    }
    
    .header-title {
        color: #1E3D59; /* Breer Blue */
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        padding-left: 15px;
        line-height: 1.2;
    }
    
    .header-subtitle {
        color: #666;
        font-size: 1.1rem;
        font-weight: 400;
        margin-top: 5px;
        padding-left: 15px;
    }

    /* Card Styling for Sections */
    .card-container {
        background-color: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 2rem;
    }

    /* Metrics Styling */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #E0E0E0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }

    /* Button Styling */
    .stButton>button {
        background: linear-gradient(135deg, #1E3D59 0%, #162E44 100%);
        color: white;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(30, 61, 89, 0.3);
    }

    /* Custom File Uploader Label */
    .stFileUploader label {
        font-weight: bold;
        color: #1E3D59;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
from pathlib import Path
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# -----------------------------------------------------------------------------
# 2. HEADER SECTION (Clean & Aligned)
# -----------------------------------------------------------------------------

# We use a container to visually group the header
with st.container():
    # Columns for Logo (left) and Title (right)
    # Tighter ratio [1, 5] ensures proximity
    col_logo, col_title = st.columns([0.8, 6])
    
    with col_logo:
        logo_path = "assets/breer_logo.svg" # Prefer SVG for web
        if not os.path.exists(logo_path):
             # Try absolute path or fallback to png/dark
             logo_path = "assets/logo.svg"
        
        if os.path.exists(logo_path):
            st.image(logo_path, width=110) # Elegant size
        else:
            st.write("🛡️")

    with col_title:
        # Custom HTML Title for perfect control
        st.markdown("""
            <div style='margin-top: 10px;'>
                <h1 style='margin:0; padding:0; font-size: 2.2rem; color:#1E3D59;'>Live Audit Cockpit</h1>
                <p style='margin:0; padding:0; color:#888; font-size: 1rem;'>
                    KI-gestützte Rechnungsprüfung & Lieferschein-Abgleich
                </p>
            </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True) # Spacer

# API Check
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
if not azure_api_key or not azure_endpoint:
    st.error("⚠️ Systemfehler: Azure API Credentials fehlen in der Konfiguration.")
    st.stop()

# -----------------------------------------------------------------------------
# 3. UPLOAD AREA (The "White Card")
# -----------------------------------------------------------------------------

# Container wrapper for styling (conceptually, streamlits container doesn't add div classes easily, 
# so we rely on the clean layout)

st.markdown("### 📂 Dokumentenzentrale")
st.markdown("Laden Sie die Belege hoch, um den automatischen Abgleich zu starten.")

upload_cols = st.columns(3)

with upload_cols[0]:
    st.info("**1. Rechnung** (PDF)")
    uploaded_invoice = st.file_uploader("Rechnung", type=["pdf"], key="inv", label_visibility="collapsed")

with upload_cols[1]:
    st.info("**2. Lieferscheine** (PDF)")
    uploaded_delivery = st.file_uploader("Lieferscheine", type=["pdf"], key="del", accept_multiple_files=True, label_visibility="collapsed")

with upload_cols[2]:
    st.info("**3. Preisliste** (Excel)")
    uploaded_pricelist = st.file_uploader("Preisliste", type=["xlsx"], key="price", accept_multiple_files=True, label_visibility="collapsed")

# Settings Expander (Subtle)
with st.expander("⚙️ Erweiterte Analyse-Einstellungen", expanded=False):
    c_set1, c_set2 = st.columns([1, 2])
    with c_set1:
        azure_deployment_name = st.text_input("Modell-Deployment:", value="gpt-5.2-")
    with c_set2:
        custom_prompt = st.text_area("Fokus-Anweisung:", value="Prüfe auf Preisdifferenzen und fehlende Mengen. Markiere Abweichungen > 0.01 EUR.", height=35)

# -----------------------------------------------------------------------------
# 4. ACTION
# -----------------------------------------------------------------------------
st.markdown("---")
col_btn_1, col_btn_2, col_btn_3 = st.columns([1, 2, 1])
with col_btn_2:
    start_btn = st.button("🚀 PRÜFUNG STARTEN", type="primary", use_container_width=True, disabled=not (uploaded_invoice))

# Session State
if "audit_results" not in st.session_state:
    st.session_state.audit_results = None
if "audit_total_loss" not in st.session_state:
    st.session_state.audit_total_loss = 0.0

# -----------------------------------------------------------------------------
# 5. LOGIC & PROCESSING
# -----------------------------------------------------------------------------
if start_btn:
    parser = InvoiceParser()
    
    # Animated Status Container
    with st.status("🔍 Deep Scan läuft... Bitte warten.", expanded=True) as status:
        
        # A) Invoice
        status.write("📑 Extrahiere Rechnungsdaten...")
        df_invoice = parser.parse_pdf(uploaded_invoice)
        # Fallback if empty
        if df_invoice.empty:
            status.update(label="⚠️ Fehler: Rechnung konnte nicht gelesen werden.", state="error")
            st.stop()
            
        status.write(f"   ✅ {len(df_invoice)} Positionen erkannt.")

        # B) Delivery Notes
        status.write("📦 Analysiere Lieferscheine...")
        delivery_text = ""
        if uploaded_delivery:
            for del_file in uploaded_delivery:
                text = extract_text_from_pdf(del_file)
                delivery_text += text
            status.write("   ✅ Lieferschein-Daten indexiert.")
        else:
            status.write("   ℹ️ Keine Lieferscheine - Nur Plausibilitätsprüfung.")

        # C) Matching Logic (Deterministic + Fast)
        status.write("⚖️ Führe Abgleich durch...")
        results = []
        for index, row in df_invoice.iterrows():
            ls_nr = str(row.get("Rechnung LS-Nr", ""))
            art_nr = str(row.get("Artikel-Nr", ""))
            
            # Logic
            if ls_nr == "UNKNOWN" or ls_nr == "":
                action = "⚠️ LS-Nr fehlt/unlesbar"
            elif uploaded_delivery and ls_nr not in delivery_text:
                action = "❌ FEHLT: Kein Lieferschein"
            elif uploaded_delivery and art_nr not in delivery_text:
                action = "❓ WARNUNG: Artikel nicht auf LS"
            else:
                action = "✅ OK"
            
            # Zero check
            try:
                if float(row.get("Menge", 0).replace(',','.')) == 0:
                    action = "ℹ️ Info (Menge 0)"
            except: pass

            row["Handlung"] = action
            results.append(row)
        
        df_results = pd.DataFrame(results)
        st.session_state.audit_results = df_results
        
        status.update(label="✅ Prüfung erfolgreich abgeschlossen!", state="complete", expanded=False)

# -----------------------------------------------------------------------------
# 6. RESULTS DASHBOARD
# -----------------------------------------------------------------------------
if st.session_state.audit_results is not None:
    df = st.session_state.audit_results
    
    st.markdown("<h3 style='color:#1E3D59; margin-top:2rem;'>📊 Analyse-Report</h3>", unsafe_allow_html=True)

    # 6a. KPI CARDS
    # Calculate Metrics
    count_total = len(df)
    count_error = len(df[df["Handlung"].str.contains("FEHLT|NICHT", case=False, na=False)])
    
    # Calculate Value Risk
    total_risk = 0.0
    df_risks = df[df["Handlung"].str.contains("FEHLT|NICHT", case=False, na=False)].copy()
    if not df_risks.empty:
        def parse_curr(x):
            try: return float(str(x).replace('.','').replace(',','.').strip())
            except: return 0.0
        df_risks['Value'] = df_risks['Preis_Gesamt'].apply(parse_curr)
        total_risk = df_risks['Value'].sum()
        st.session_state.audit_total_loss = total_risk

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Geprüfte Positionen", count_total, border=True)
    kpi2.metric("Kritische Fehler", count_error, delta="Action needed" if count_error > 0 else "Clean", delta_color="inverse", border=True)
    kpi3.metric("Finanzielles Risiko", f"€ {total_risk:,.2f}", delta="Potenzial" if total_risk > 0 else None, delta_color="inverse", border=True)

    # 6b. MAIN TABLE WITH HIGHLIGHTS
    st.markdown("#### 📝 Detail-Ansicht")
    
    # Configure Columns for nice badges
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Handlung": st.column_config.TextColumn(
                "Status",
                help="Ergebnis der KI-Prüfung",
                width="medium",
            ),
            "Preis_Gesamt": st.column_config.NumberColumn(
                "Preis (€)",
                format="%.2f €"
            ),
        },
        hide_index=True
    )

    # 6c. DOWNLOADS (Side by Side)
    st.markdown("---")
    d1, d2 = st.columns(2)
    
    with d1:
        # PDF Generation
        pdf_bytes = generate_audit_pdf(df, st.session_state.audit_total_loss)
        st.download_button(
            label="📄 Offiziellen Prüfbericht (PDF)",
            data=pdf_bytes,
            file_name="Breer_Audit_Report.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    
    with d2:
        # CSV Generation
        csv_bytes = df.to_csv(index=False, sep=";").encode('utf-8')
        st.download_button(
            label="📊 Rohdaten Export (Excel/CSV)",
            data=csv_bytes,
            file_name="audit_data.csv",
            mime="text/csv",
            use_container_width=True
        )

