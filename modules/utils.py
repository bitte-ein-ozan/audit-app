import pandas as pd
import pdfplumber
import io
from typing import Optional, List, Dict, Any

def extract_text_from_pdf(file_stream) -> str:
    """
    Extracts text from a PDF file stream robustly.
    """
    text = ""
    try:
        with pdfplumber.open(file_stream) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"
    return text

def extract_pages_from_pdf(file_stream) -> List[str]:
    """
    Extracts text from a PDF file stream, returning a list of strings (one per page).
    """
    pages_content = []
    try:
        with pdfplumber.open(file_stream) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_content.append(page_text)
                else:
                    pages_content.append("") # Empty page placeholder
    except Exception as e:
        return []
    return pages_content

def load_excel_data(file_stream) -> pd.DataFrame:
    """
    Loads Excel data into a clean DataFrame.
    """
    try:
        df = pd.read_excel(file_stream)
        # Basic cleaning: remove completely empty rows/cols
        df = df.dropna(how='all').dropna(axis=1, how='all')
        # Convert all columns to string for consistency in AI processing
        df = df.astype(str)
        return df
    except Exception as e:
        raise Exception(f"Error reading Excel: {str(e)}")

def excel_to_csv_string(df: pd.DataFrame, max_rows: int = 10000) -> str:
    """
    Converts DataFrame to a CSV string for the LLM prompt.
    Limits rows to prevent token overflow in a demo context.
    """
    return df.head(max_rows).to_csv(index=False)
