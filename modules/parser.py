import re
import pdfplumber
import pandas as pd
from typing import List, Dict, Optional

class InvoiceParser:
    def __init__(self):
        # Regex for finding the Delivery Note Number (Lieferschein-Nr)
        # Pattern looks for "Lfsch-/Rechn-Nr." followed by numbers
        self.ls_pattern = re.compile(r'Lfsch-/Rechn-Nr\.\s*:\s*(\d+)', re.IGNORECASE)
        
        # Regex for Items: Starts with 6+ digits
        # 867130 Plum ... 10 Fla 9,70 97,00 1
        # Group 1: ArtNr
        # Group 2: Description (everything until quantity)
        # Group 3: Quantity (digits + space + unit) -- simplified to just grab the end
        self.item_pattern = re.compile(r'^(\d{6,})\s+(.+?)\s+(\d+(?:\s*[a-zA-Z]+)?)\s+[\d,.]+\s+[\d,.]+\s*\d*$', re.MULTILINE)
        
        # Regex for Items: Starts with 6+ digits
        # 867130 Plum ... 10 Fla 9,70 97,00 1
        # Also matches lines with JUST the number: "2092982"
        self.simple_item_start = re.compile(r'^(\d{6,})')

    def parse_pdf(self, file_path_or_obj) -> pd.DataFrame:
        """
        Parses the Kammerer Invoice PDF and returns a structured DataFrame.
        """
        extracted_data = []
        current_ls_nr = "UNKNOWN"
        
        # Regex to parse the end of the line: Quantity+Unit Price Total [Marker]
        # Example: "10 Fla 9,70 97,00 1" -> 10, Fla, 9,70, 97,00
        # ... (rest of comments)
        end_pattern = re.compile(r'\s+(\d+)\s*([A-Za-z]+)\s+([\d,.]+)\s+([\d,.]+)(\d)?$', re.IGNORECASE)

        with pdfplumber.open(file_path_or_obj) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    
                    # 1. Check for LS-Nr Header
                    ls_match = self.ls_pattern.search(line)
                    if ls_match:
                        current_ls_nr = ls_match.group(1)
                        continue
                    
                    # 2. Check for Item Line
                    match = self.simple_item_start.match(line)
                    if match:
                        art_nr = match.group(1)
                        # Remove ArtNr from line
                        rest = line[len(art_nr):].strip()
                        
                        # Default values
                        qty, unit, price_single, price_total = "0", "-", "0,00", "0,00"
                        description = rest if rest else "(Keine Bezeichnung)"

                        # Only try to parse details if there is text remaining
                        if rest:
                            # Parse details from the end
                            details_match = end_pattern.search(rest)
                            
                            if details_match:
                                qty = details_match.group(1).replace('.', '')
                                unit = details_match.group(2)
                                price_single = details_match.group(3)
                                price_total = details_match.group(4)
                                description = rest[:details_match.start()].strip()
                        
                        item_entry = {
                            "Rechnung LS-Nr": current_ls_nr,
                            "Artikel-Nr": art_nr,
                            "Bezeichnung": description,
                            "Menge": qty,
                            "Einheit": unit,
                            "Preis_Einzel": price_single,
                            "Preis_Gesamt": price_total,
                            "Original_Zeile": line
                        }
                        
                        extracted_data.append(item_entry)
                        
        return pd.DataFrame(extracted_data)

    def extract_ls_numbers_from_text(self, text: str) -> set:
        """
        Finds all 8-digit numbers in a text that look like LS-Numbers.
        """
        # LS numbers in invoice are 8 digits (e.g. 23406731).
        return set(re.findall(r'\b\d{8}\b', text))

# Test run
if __name__ == "__main__":
    test_path = '/Users/ozan/Documents/Documents/Strategy/BR1/Rechnung_0401_5007287.pdf'
    parser = InvoiceParser()
    df = parser.parse_pdf(test_path)
    print(f"Extracted {len(df)} items.")
    print(df.head().to_string())
    # Save for inspection
    df.to_csv('/Users/ozan/Documents/Documents/Strategy/BR1/parsed_invoice.csv', index=False, sep=';')
