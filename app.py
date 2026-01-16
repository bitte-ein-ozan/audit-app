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

# Page Configuration
st.set_page_config(
    page_title="AI Rechnungsprüfer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Professional Look
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .main > div {
        padding-top: 2rem;
    }
    .stButton>button {
        background-color: #0056b3;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        height: 50px;
    }
    h1 {
        color: #1e3d59;
        text-align: center;
    }
    h3 {
        color: #1e3d59;
    }
    .metric-box {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
from pathlib import Path
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# --- HEADER WITH LOGO ---
c_head1, c_head2 = st.columns([1, 3])
with c_head1:
    logo_path = "assets/logo.svg"
    if not os.path.exists(logo_path):
        # Try finding relative to current file if started differently
        logo_path = os.path.join(os.path.dirname(__file__), "assets/breer_logo.svg")
    
    if os.path.exists(logo_path):
        st.image(logo_path, width=200)
    else:
        st.write("🛡️") 

with c_head2:
    st.title("🛡️ Live AI Audit-Cockpit")

st.markdown("<h4 style='text-align: center; color: #555;'>Intelligente Rechnungsprüfung & Diskrepanz-Analyse</h4>", unsafe_allow_html=True)
st.markdown("---")

# API Key Handling (Hidden check)
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

if not azure_api_key or not azure_endpoint:
    st.error("⚠️ Kritischer Fehler: Azure OpenAI Credentials fehlen. Bitte prüfen Sie die .env Datei.")
    st.stop()

# --- UPLOAD SECTION (CENTERED & STYLED) ---
with st.container():
    col_u1, col_u2 = st.columns([1, 10])
    with col_u2:
        st.subheader("📂 Dokumentenzentrale")
        st.info("Bitte laden Sie die relevanten Dokumente für den Abgleich hoch. Das System akzeptiert PDF und Excel.")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**1. Rechnung**")
        uploaded_invoice = st.file_uploader("Rechnung hochladen (PDF)", type=["pdf"], key="inv")
    with c2:
        st.markdown("**2. Lieferscheine**")
        uploaded_delivery = st.file_uploader("Lieferscheine hochladen (PDF)", type=["pdf"], key="del", accept_multiple_files=True)
    with c3:
        st.markdown("**3. Preisliste**")
        uploaded_pricelist = st.file_uploader("Preisliste hochladen (Excel)", type=["xlsx"], key="price", accept_multiple_files=True)

# --- ADVANCED SETTINGS (EXPANDER) ---
st.markdown(" ")
with st.expander("⚙️ Experten-Einstellungen / KI-Prompt anpassen", expanded=False):
    st.markdown("Definieren Sie spezielle Prüfregeln für diesen Durchlauf.")
    
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        azure_deployment_name = st.text_input("Azure Deployment Name:", value="gpt-5.2-", help="Der Name Ihrer Bereitstellung in Azure AI Studio (oft anders als der Modellname!)")
    
    custom_prompt = st.text_area(
        "KI-Instruktionen:",
        value="Prüfe bitte genau auf Preisabweichungen zwischen Rechnung und Preisliste sowie auf Mengenabweichungen laut Lieferschein. Gib auch an, wenn Artikel fehlen oder falsche Rabatte berechnet wurden.",
        height=100
    )

# --- ACTION BUTTON ---
st.markdown("---")
c_act1, c_act2, c_act3 = st.columns([1, 1, 1])
with c_act2:
    run_audit = st.button("🚀 JETZT PRÜFUNG STARTEN", type="primary", use_container_width=True, disabled=not (uploaded_invoice and uploaded_pricelist))

# Initialize Session State
if "audit_results" not in st.session_state:
    st.session_state.audit_results = None
if "audit_total_loss" not in st.session_state:
    st.session_state.audit_total_loss = 0.0

if run_audit:
    # --- PROCESSING STATE ---
    # auditor = InvoiceAuditor(azure_api_key, azure_endpoint) # AI Optional
    parser = InvoiceParser()

    # Professional Progress UI
    with st.status("🔄 Systemstatus: Hybride Analyse läuft...", expanded=True) as status:

        status.write("📄 **Schritt 1:** Analysiere Rechnungsstruktur (Python-Engine)...")
        # Use the smart parser instead of raw text
        df_invoice = parser.parse_pdf(uploaded_invoice)
        status.write(f"   ↳ {len(df_invoice)} Rechnungspositionen erkannt.")

        status.write("📦 **Schritt 2:** Scanne Lieferscheine...")
        delivery_text = ""
        found_ls_numbers = set()
        
        if uploaded_delivery:
            for del_file in uploaded_delivery:
                # Extract text for item checking
                text = extract_text_from_pdf(del_file)
                delivery_text += text
                # Extract LS Numbers found in this file
                found_ls_numbers.update(parser.extract_ls_numbers_from_text(text))
            
            status.write(f"   ↳ {len(found_ls_numbers)} Lieferscheine im Text identifiziert.")
        else:
            status.write("ℹ️ Keine Lieferscheine hochgeladen.")

        status.write("⚡ **Schritt 3:** Führe deterministischen Abgleich durch...")
        
        # LOGIC: Check Delivery
        results = []
        for index, row in df_invoice.iterrows():
            ls_nr = str(row["Rechnung LS-Nr"])
            art_nr = str(row["Artikel-Nr"])
            
            # Check 1: LS Number
            if ls_nr == "UNKNOWN":
                action = "⚠️ LS-Nr nicht lesbar"
            elif ls_nr not in delivery_text: # Simple text search is safer than regex set sometimes
                action = "❌ NICHT GELIEFERT: Kein Lieferschein"
            else:
                # Check 2: Article on LS
                # We check if Article Number appears in the Delivery Text
                if art_nr in delivery_text:
                     action = "✅ OK (Gefunden)"
                else:
                     action = "❓ ACHTUNG: Artikel fehlt auf LS"
            
            # Check 3: Zero Quantity (Sub-items)
            if row["Menge"] == "0":
                 action = "ℹ️ Info-Position (Menge 0)"

            row["Handlung"] = action
            results.append(row)
        
        df_results = pd.DataFrame(results)
        
        # Store in Session State
        st.session_state.audit_results = df_results
        
        status.update(label="✅ Analyse erfolgreich abgeschlossen!", state="complete", expanded=False)

# --- RESULTS DASHBOARD ---
if st.session_state.audit_results is not None:
    df_results = st.session_state.audit_results
    
    st.markdown("## 📊 Analyse-Ergebnis (Smart-Check)")

    # Dashboard Metrics
    total_items = len(df_results)
    missing_ls = len(df_results[df_results["Handlung"].str.contains("Kein Lieferschein")])
    missing_art = len(df_results[df_results["Handlung"].str.contains("Artikel fehlt")])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Gesamtpositionen", total_items)
    c2.metric("Fehlende Lieferscheine", missing_ls, delta="-Fehler", delta_color="inverse")
    c3.metric("Artikel nicht auf LS", missing_art, delta="-Warnung", delta_color="inverse")

    # --- CRITICAL SECTION ---
    df_missing = df_results[df_results["Handlung"].str.contains("NICHT GELIEFERT", na=False)]
    
    total_loss = 0.0
    if not df_missing.empty:
        st.markdown("---")
        st.error(f"🛑 AKTION ERFORDERLICH: {len(df_missing)} Positionen ohne Lieferschein!")
        
        # Calculate Sum
        try:
            # Cleanup 'Preis_Gesamt' (remove '1' at end if parser failed, replace , with .)
            # Parser output: "97,001" -> "97.00"
            def clean_price(val):
                if isinstance(val, str):
                    val = val.replace('.', '').replace(',', '.')
                    if val.endswith('1'): val = val[:-1] # Remove VAT marker heuristic
                    return float(val)
                return 0.0
            
            # Create a copy to avoid SettingWithCopyWarning on view
            df_missing = df_missing.copy()
            df_missing['Wert'] = df_missing['Preis_Gesamt'].apply(clean_price)
            total_loss = df_missing['Wert'].sum()
            st.session_state.audit_total_loss = total_loss
            st.metric("Rückforderungssumme (Geschätzt)", f"€{total_loss:,.2f}")
        except:
            total_loss = 0.0

        st.dataframe(df_missing, use_container_width=True)

        # --- VISUALIZATION ---
        st.markdown("---")
        st.subheader("📊 Visuelle Auswertung")
        
        c_chart1, c_chart2 = st.columns(2)
        
        with c_chart1:
            # Prepare data for Pie Chart
            status_counts = df_results['Handlung'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Anzahl']
            fig_pie = px.pie(status_counts, values='Anzahl', names='Status', title='Statusverteilung aller Positionen',
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c_chart2:
            if not df_missing.empty:
                # Top 10 Missing Items by Cost
                df_top_missing = df_missing.groupby('Bezeichnung')['Wert'].sum().sort_values(ascending=False).head(10).reset_index()
                fig_bar = px.bar(df_top_missing, x='Wert', y='Bezeichnung', orientation='h', 
                                 title='Top 10 Fehlende Positionen nach Wert (€)',
                                 color='Wert', color_continuous_scale='Reds')
                st.plotly_chart(fig_bar, use_container_width=True)

        # --- PDF REPORT ---
        st.markdown("---")
        st.subheader("📑 Report Generierung")
        
        # Generate PDF only when button is clicked? No, generate it ready for download.
        # But st.download_button needs data upfront.
        # Let's generate it now since it's fast.
        
        # Use session state total_loss
        pdf_bytes = generate_audit_pdf(df_results, st.session_state.audit_total_loss)
        
        st.download_button(
            label="📄 PDF-Prüfbericht herunterladen",
            data=pdf_bytes,
            file_name="Audit_Report_Breer.pdf",
            mime="application/pdf"
        )

    # --- FULL TABLE ---
    st.markdown("---")
    st.subheader("📝 Alle Positionen")
    
    def highlight_rows(row):
        val = str(row['Handlung'])
        if "NICHT" in val: return ['background-color: #ffcdd2'] * len(row)
        if "ACHTUNG" in val: return ['background-color: #fff9c4'] * len(row)
        return [''] * len(row)

    st.dataframe(df_results.style.apply(highlight_rows, axis=1), use_container_width=True)

    # Export
    csv = df_results.to_csv(index=False, sep=';').encode('utf-8')
    st.download_button(
        label="📥 CSV-Daten herunterladen",
        data=csv,
        file_name="audit_smart_fast.csv",
        mime="text/csv",
        key='download-csv'
    )
