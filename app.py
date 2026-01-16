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

# MODERN CSS INJECTION (Breer Identity)
st.markdown("""
<style>
    /* Global Background - Very light grey-blue */
    .stApp {
        background-color: #F4F6F9;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Header Area */
    .header-container {
        background-color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        border-bottom: 3px solid #004e92; /* Breer Accent */
    }
    
    h1 {
        color: #002B5B; /* Deep Navy */
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 700;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    h3, h4, h5 {
        color: #002B5B;
    }

    /* Cards */
    div.stContainer {
        background-color: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 20px;
    }

    /* Primary Button (The Breer Blue) */
    .stButton>button {
        background: #004e92;
        color: white;
        font-weight: 600;
        border-radius: 6px;
        border: none;
        padding: 0.6rem 1.2rem;
        transition: background 0.2s;
    }
    .stButton>button:hover {
        background: #003366;
        color: white;
    }

    /* Metrics Styling */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #004e92;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricLabel"] {
        color: #666;
        font-size: 0.9rem;
    }
    div[data-testid="stMetricValue"] {
        color: #002B5B;
        font-weight: 700;
    }

    /* File Uploader */
    .stFileUploader {
        padding: 10px;
        border-radius: 8px;
        background: #f8f9fa;
        border: 1px dashed #ced4da;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
from pathlib import Path
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# -----------------------------------------------------------------------------
# 2. HEADER SECTION
# -----------------------------------------------------------------------------

# Use a clean container for the header
with st.container():
    # Grid Layout: Logo | Title
    c1, c2 = st.columns([1, 6])
    
    with c1:
        # Load the blue logo
        logo_path = "assets/logo.svg" 
        if not os.path.exists(logo_path):
             logo_path = "assets/breer_logo.svg" # Fallback
        
        if os.path.exists(logo_path):
            st.image(logo_path, width=130)
        else:
            st.markdown("## 🛡️") # Emoji fallback

    with c2:
        st.markdown("""
            <div style='padding-top: 10px;'>
                <h1 style='font-size: 2.4rem;'>Audit Cockpit</h1>
                <p style='color: #666; font-size: 1.1rem; margin-top: 5px;'>
                    Automatisierte Rechnungs- & Lieferscheinprüfung
                </p>
            </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# API Check
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
if not azure_api_key or not azure_endpoint:
    st.error("⚠️ Konfigurationsfehler: API Credentials fehlen.")
    st.stop()

# -----------------------------------------------------------------------------
# 3. WORKSPACE (Uploads)
# -----------------------------------------------------------------------------

# Create a visual 'Card' for uploads
with st.container():
    st.markdown("### 📂 Dokumente hochladen")
    
    cols = st.columns(3)
    
    with cols[0]:
        st.markdown("**1. Rechnung** (PDF)")
        uploaded_invoice = st.file_uploader("Rechnung", type=["pdf"], key="inv", label_visibility="collapsed")
    
    with cols[1]:
        st.markdown("**2. Lieferscheine** (PDF)")
        uploaded_delivery = st.file_uploader("Lieferscheine", type=["pdf"], key="del", accept_multiple_files=True, label_visibility="collapsed")
    
    with cols[2]:
        st.markdown("**3. Preisliste** (Excel)")
        uploaded_pricelist = st.file_uploader("Preisliste", type=["xlsx"], key="price", accept_multiple_files=True, label_visibility="collapsed")

    # Action Bar
    st.markdown("---")
    
    # Align button right
    b1, b2, b3 = st.columns([3, 1, 1])
    with b3:
        start_btn = st.button("Prüfung starten ➤", type="primary", use_container_width=True, disabled=not uploaded_invoice)

# -----------------------------------------------------------------------------
# 4. LOGIC
# -----------------------------------------------------------------------------

# Initialize Session
if "audit_results" not in st.session_state:
    st.session_state.audit_results = None
if "audit_total_loss" not in st.session_state:
    st.session_state.audit_total_loss = 0.0

if start_btn:
    parser = InvoiceParser()
    
    # Progress UI
    progress_placeholder = st.empty()
    with progress_placeholder.container():
        st.info("🔄 Analyse läuft... Dokumente werden verarbeitet.")
        
        # 1. Invoice
        df_invoice = parser.parse_pdf(uploaded_invoice)
        if df_invoice.empty:
            st.error("Rechnung konnte nicht gelesen werden.")
            st.stop()
            
        # 2. Delivery
        delivery_text = ""
        if uploaded_delivery:
            for f in uploaded_delivery:
                delivery_text += extract_text_from_pdf(f)
        
        # 3. Match
        results = []
        for index, row in df_invoice.iterrows():
            ls_nr = str(row.get("Rechnung LS-Nr", ""))
            art_nr = str(row.get("Artikel-Nr", ""))
            
            status = "✅ OK"
            if not ls_nr or ls_nr == "UNKNOWN":
                status = "⚠️ LS-Nr fehlt"
            elif uploaded_delivery and ls_nr not in delivery_text:
                status = "❌ Kein Lieferschein"
            elif uploaded_delivery and art_nr not in delivery_text:
                status = "❓ Artikel fehlt"
            
            try:
                if float(row.get("Menge", 0).replace(',','.')) == 0:
                    status = "ℹ️ Menge 0"
            except: pass

            row["Handlung"] = status
            results.append(row)
        
        st.session_state.audit_results = pd.DataFrame(results)
        st.success("Fertig!")
        progress_placeholder.empty() # Remove progress bar

# -----------------------------------------------------------------------------
# 5. DASHBOARD (Results)
# -----------------------------------------------------------------------------

if st.session_state.audit_results is not None:
    df = st.session_state.audit_results
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📊 Prüfergebnis")

    # Metrics
    err_count = len(df[df["Handlung"].str.contains("Kein|fehlt", case=False)])
    
    # Risk Calc
    risk = 0.0
    try:
        df_err = df[df["Handlung"].str.contains("Kein|fehlt", case=False)].copy()
        df_err['V'] = df_err['Preis_Gesamt'].astype(str).str.replace('.','').str.replace(',','.').astype(float)
        risk = df_err['V'].sum()
        st.session_state.audit_total_loss = risk
    except: pass

    m1, m2, m3 = st.columns(3)
    m1.metric("Positionen", len(df))
    m2.metric("Abweichungen", err_count, delta_color="inverse")
    m3.metric("Risiko (€)", f"{risk:,.2f}", delta_color="inverse")

    # Table
    st.markdown("#### Detailübersicht")
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Handlung": st.column_config.TextColumn(
                "Status",
                width="small",
                help="Prüfergebnis"
            ),
            "Preis_Gesamt": st.column_config.NumberColumn("Preis (€)", format="%.2f")
        },
        hide_index=True
    )

    # Export
    st.markdown("---")
    e1, e2 = st.columns(2)
    
    with e1:
        pdf_bytes = generate_audit_pdf(df, st.session_state.audit_total_loss)
        st.download_button("📄 PDF Report", pdf_bytes, "Audit_Report.pdf", "application/pdf", use_container_width=True)
    
    with e2:
        csv = df.to_csv(index=False, sep=";").encode('utf-8')
        st.download_button("📥 Excel/CSV", csv, "audit.csv", "text/csv", use_container_width=True)

