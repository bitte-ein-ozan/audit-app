from fpdf import FPDF
import pandas as pd
import os
from datetime import datetime

class AuditPDF(FPDF):
    def header(self):
        # Logo Logic
        # Try to find the PNG logo
        logo_path = "assets/breer_logo_dark.png"
        if not os.path.exists(logo_path):
             logo_path = os.path.join(os.path.dirname(__file__), "../assets/breer_logo.png")
        
        if os.path.exists(logo_path):
            # Image(path, x, y, w)
            self.image(logo_path, 10, 8, 40)
            self.ln(15) # Move cursor down after logo
        
        # Header Text (Title)
        self.set_font('Arial', 'B', 15)
        self.set_text_color(30, 61, 89)
        # Move Title to the right if logo exists, or center/left
        self.cell(0, 10, 'BREER AUDIT REPORT', 0, 1, 'R') # Right aligned title
        
        self.set_font('Arial', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Erstellt am: {datetime.now().strftime("%d.%m.%Y %H:%M")}', 0, 1, 'R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def generate_audit_pdf(df_results, total_loss):
    pdf = AuditPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- SUMMARY SECTION ---
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, "Zusammenfassung der Prüfung", 0, 1)
    
    pdf.set_font("Arial", "", 10)
    total_items = len(df_results)
    missing_items = len(df_results[df_results['Handlung'].str.contains("NICHT GELIEFERT", na=False)])
    
    pdf.cell(0, 7, f"Geprüfte Positionen: {total_items}", 0, 1)
    
    # Highlight Loss
    pdf.set_text_color(200, 0, 0) # Red
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 7, f"Fehlende Positionen: {missing_items}", 0, 1)
    pdf.cell(0, 7, f"Geschätzte Rückforderung: {total_loss:,.2f} EUR", 0, 1)
    pdf.set_text_color(0) # Reset
    pdf.ln(10)

    # --- TABLE HEADER ---
    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(240, 240, 240)
    
    # Columns: Artikel, Bez, Menge, Preis, Status
    # Widths
    w = [25, 60, 20, 25, 60]
    headers = ["Art-Nr", "Bezeichnung", "Menge", "Preis", "Status"]
    
    for i, h in enumerate(headers):
        pdf.cell(w[i], 7, h, 1, 0, 'C', True)
    pdf.ln()

    # --- TABLE ROWS ---
    pdf.set_font("Arial", "", 8)
    
    for index, row in df_results.iterrows():
        # Status Color
        status = str(row['Handlung'])
        if "NICHT" in status:
            pdf.set_text_color(200, 0, 0) # Red
        elif "ACHTUNG" in status:
            pdf.set_text_color(200, 100, 0) # Orange
        else:
            pdf.set_text_color(0) # Black

        # Data
        art = str(row.get('Artikel-Nr', ''))[:12]
        bez = str(row.get('Bezeichnung', ''))[:35]
        menge = str(row.get('Menge', ''))
        preis = str(row.get('Preis_Gesamt', ''))
        
        pdf.cell(w[0], 6, art, 1)
        pdf.cell(w[1], 6, bez, 1)
        pdf.cell(w[2], 6, menge, 1, 0, 'R')
        pdf.cell(w[3], 6, preis, 1, 0, 'R')
        pdf.cell(w[4], 6, status[:40], 1)
        pdf.ln()

    # Output
    # Return as string (latin-1) for Streamlit download button
    return pdf.output(dest='S').encode('latin-1', 'replace')
