from fpdf import FPDF
import pandas as pd
import os
from datetime import datetime

class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.logo_path = os.path.join(os.path.dirname(__file__), '../assets/logo.png')
        # Check if logo exists, if not, no logo
        if not os.path.exists(self.logo_path):
             self.logo_path = None

    def header(self):
        if self.logo_path:
            # Logo
            try:
                self.image(self.logo_path, 10, 8, 33)
            except:
                pass
        # Font
        self.set_font('Arial', 'B', 15)
        # Title
        self.cell(80)
        self.cell(30, 10, 'Prüfbericht Rechnungsanalyse', 0, 0, 'C')
        # Line break
        self.ln(20)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Page number
        self.cell(0, 10, 'Seite ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 6, label, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, text):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 5, text)
        self.ln()

    def add_metrics(self, total, missing_ls, missing_art, value_loss):
        self.set_font('Arial', '', 11)
        self.cell(0, 10, f"Erstellungsdatum: {datetime.now().strftime('%d.%m.%Y %H:%M')}", 0, 1)
        self.ln(5)
        self.set_font('Arial', 'B', 11)
        self.cell(90, 10, f"Gesamtpositionen: {total}", 1)
        self.cell(90, 10, f"Rückforderungssumme: {value_loss}", 1, 1)
        self.set_text_color(200, 0, 0)
        self.cell(90, 10, f"Fehlende Lieferscheine: {missing_ls}", 1)
        self.cell(90, 10, f"Artikel fehlt auf LS: {missing_art}", 1, 1)
        self.set_text_color(0, 0, 0)
        self.ln(10)

    def add_table(self, df):
        # Simple table
        self.set_font('Arial', 'B', 10)
        col_widths = [30, 30, 80, 20, 30] # LS, Art, Desc, Qty, Price
        headers = ['LS-Nr', 'Art-Nr', 'Bezeichnung', 'Menge', 'Preis']
        
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, 1)
        self.ln()
        
        self.set_font('Arial', '', 9)
        for _, row in df.iterrows():
            if self.get_y() > 270:
                self.add_page()
            
            ls = str(row.get('Rechnung LS-Nr', ''))[:15]
            art = str(row.get('Artikel-Nr', ''))[:15]
            desc = str(row.get('Bezeichnung', ''))[:40]
            qty = str(row.get('Menge', ''))
            price = str(row.get('Preis_Gesamt', ''))
            
            self.cell(col_widths[0], 6, ls, 1)
            self.cell(col_widths[1], 6, art, 1)
            self.cell(col_widths[2], 6, desc, 1)
            self.cell(col_widths[3], 6, qty, 1)
            self.cell(col_widths[4], 6, price, 1)
            self.ln()

def generate_audit_pdf(df_results, total_loss):
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Filter missing
    df_missing = df_results[df_results['Handlung'].str.contains("NICHT GELIEFERT", na=False)]
    
    # Metrics
    total = len(df_results)
    missing_ls = len(df_results[df_results['Handlung'].str.contains("Kein Lieferschein")])
    missing_art = len(df_results[df_results['Handlung'].str.contains("Artikel fehlt")])
    
    pdf.chapter_title("Zusammenfassung")
    pdf.add_metrics(total, missing_ls, missing_art, f"EUR {total_loss:,.2f}")
    
    if not df_missing.empty:
        pdf.chapter_title("Detail-Liste: Nicht gelieferte Positionen")
        pdf.chapter_body("Folgende Positionen wurden abgerechnet, aber es liegt kein entsprechender Lieferschein vor oder der Artikel fehlt darauf.")
        pdf.add_table(df_missing)
    else:
        pdf.chapter_body("Keine Abweichungen gefunden.")
        
    return bytes(pdf.output())
