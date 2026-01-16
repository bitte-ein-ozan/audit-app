import streamlit as st
import pandas as pd
import os
import io
import base64
from dotenv import load_dotenv
from modules.utils import extract_text_from_pdf, extract_pages_from_pdf, load_excel_data, excel_to_csv_string
from modules.auditor import InvoiceAuditor
from modules.parser import InvoiceParser
from modules.pdf_generator import generate_audit_pdf
import plotly.express as px
import plotly.graph_objects as go
# --- CONFIG ---
st.set_page_config(page_title="Breer Audit Cockpit", page_icon="🛡️", layout="wide", initial_sidebar_state="collapsed")
# --- MODERN CSS ---
st.markdown("""
<style>
    @import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap");
    .stApp { background-color: #F8FAFC; font-family: "Inter", sans-serif; }
    
    /* Header */
    .header-container {
        background: linear-gradient(90deg, #FFFFFF 0%, #F1F5F9 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0, 78, 146, 0.08);
        margin-bottom: 30px;
        display: flex; align-items: center; gap: 30px;
        border-left: 6px solid #004e92;
    }
    .header-text h1 { color: #002B5B; font-size: 2.4rem; font-weight: 800; margin: 0; letter-spacing: -0.5px; }
    .header-text p { color: #64748B; font-size: 1.1rem; margin: 4px 0 0 0; font-weight: 500; }
    
    /* Step Cards */
    .upload-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .upload-card:hover { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(0,0,0,0.06); border-color: #004e92; }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #004e92 0%, #003366 100%);
        color: white; border-radius: 10px; border: none; padding: 0.8rem 2rem;
        font-weight: 600; letter-spacing: 0.5px; box-shadow: 0 4px 12px rgba(0, 78, 146, 0.3);
        width: 100%; transition: all 0.3s ease;
    }
    .stButton>button:hover { box-shadow: 0 6px 18px rgba(0, 78, 146, 0.5); transform: translateY(-1px); }
    
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    div[data-testid="stMetricValue"] { color: #004e92; font-weight: 800; }
    
    /* Footer */
    .footer { text-align: center; color: #94A3B8; font-size: 0.8rem; margin-top: 50px; border-top: 1px solid #E2E8F0; padding-top: 20px; }
</style>
""", unsafe_allow_html=True)
from pathlib import Path
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
# --- HEADER ---
logo_b64 = "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCEtLSBHZW5lcmF0b3I6IEFkb2JlIElsbHVzdHJhdG9yIDE2LjAuNCwgU1ZHIEV4cG9ydCBQbHVnLUluIC4gU1ZHIFZlcnNpb246IDYuMDAgQnVpbGQgMCkgIC0tPgo8IURPQ1RZUEUgc3ZnIFBVQkxJQyAiLS8vVzNDLy9EVEQgU1ZHIDEuMS8vRU4iICJodHRwOi8vd3d3LnczLm9yZy9HcmFwaGljcy9TVkcvMS4xL0RURC9zdmcxMS5kdGQiPgo8c3ZnIHZlcnNpb249IjEuMSIgaWQ9IkViZW5lXzEiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgeG1sbnM6eGxpbms9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGxpbmsiIHg9IjBweCIgeT0iMHB4IgoJIHdpZHRoPSI0MDdweCIgaGVpZ2h0PSI5Ni41cHgiIHZpZXdCb3g9IjAgMCA0MDcgOTYuNSIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgNDA3IDk2LjUiIHhtbDpzcGFjZT0icHJlc2VydmUiPgo8Zz4KCTxwYXRoIGZpbGw9IiMwMDQ1N0MiIGQ9Ik0zOTAuNDMyLDEuMjVjMS40OCwwLDIuOTI2LDAuMzgyLDQuMzM2LDEuMTQ1YzEuNDA5LDAuNzU2LDIuNTA4LDEuODQyLDMuMjk1LDMuMjU5CgkJYzAuNzg1LDEuNDEsMS4xNzksMi44ODIsMS4xNzksNC40MTdjMCwxLjUxOC0wLjM4OSwyLjk3OS0xLjE2OCw0LjM4MWMtMC43NzEsMS40MDItMS44NTgsMi40OTItMy4yNiwzLjI3MQoJCWMtMS4zOTQsMC43NzEtMi44NTQsMS4xNTYtNC4zODIsMS4xNTZjLTEuNTI1LDAtMi45ODktMC4zODYtNC4zOTMtMS4xNTZjLTEuMzkzLTAuNzc5LTIuNDgtMS44NjktMy4yNTktMy4yNzEKCQljLTAuNzc5LTEuNDAyLTEuMTY5LTIuODYzLTEuMTY5LTQuMzgxYzAtMS41MzQsMC4zOTQtMy4wMDYsMS4xODEtNC40MTdjMC43OTQtMS40MTcsMS44OTYtMi41MDMsMy4zMDYtMy4yNTkKCQlDMzg3LjUwOCwxLjYzMiwzODguOTUyLDEuMjUsMzkwLjQzMiwxLjI1TDM5MC40MzIsMS4yNXogTTM5MC40MzIsMi43MDljLTEuMjM3LDAtMi40NDUsMC4zMi0zLjYyLDAuOTU4CgkJYy0xLjE2OSwwLjYzMS0yLjA4NCwxLjUzOS0yLjc0NiwyLjcyMmMtMC42NjIsMS4xNzYtMC45OTMsMi40MDMtMC45OTMsMy42OGMwLDEuMjcsMC4zMjMsMi40ODgsMC45NywzLjY1NwoJCWMwLjY1NCwxLjE2MSwxLjU2NSwyLjA2OCwyLjczMywyLjcyMmMxLjE3LDAuNjQ3LDIuMzg3LDAuOTcsMy42NTYsMC45N2MxLjI3MSwwLDIuNDg5LTAuMzIzLDMuNjU3LTAuOTcKCQljMS4xNjgtMC42NTQsMi4wNzUtMS41NjEsMi43MjMtMi43MjJjMC42NDYtMS4xNjgsMC45NjktMi4zODcsMC45Ny0zLjY1N2MwLTEuMjc3LTAuMzMxLTIuNTA0LTAuOTkzLTMuNjgKCQljLTAuNjU0LTEuMTg0LTEuNTY5LTIuMDkxLTIuNzQ2LTIuNzIyQzM5Mi44NjYsMy4wMjksMzkxLjY2MiwyLjcxLDM5MC40MzIsMi43MDlMMzkwLjQzMiwyLjcwOXogTTM4Ni44ODUsMTQuNzNWNS4yNDVoMy4yNgoJCWMxLjExMywwLDEuOTIsMC4wODksMi40MTgsMC4yNjljMC40OTksMC4xNzEsMC44OTYsMC40NzUsMS4xOTEsMC45MTFjMC4yOTYsMC40MzYsMC40NDQsMC44OTksMC40NDQsMS4zOQoJCWMwLDAuNjkzLTAuMjQ5LDEuMjk3LTAuNzQ4LDEuODExYy0wLjQ5LDAuNTE0LTEuMTQ0LDAuODAyLTEuOTYyLDAuODY0YzAuMzM0LDAuMTQsMC42MDMsMC4zMDgsMC44MDYsMC41MDIKCQljMC4zODEsMC4zNzQsMC44NSwxLjAwMSwxLjQwMSwxLjg4bDEuMTU3LDEuODU3aC0xLjg2OWwtMC44NDEtMS40OTVjLTAuNjYyLTEuMTc2LTEuMTk2LTEuOTEyLTEuNjAyLTIuMjA4CgkJYy0wLjI4LTAuMjE4LTAuNjg4LTAuMzI3LTEuMjI2LTAuMzI3aC0wLjl2NC4wM0gzODYuODg1TDM4Ni44ODUsMTQuNzN6IE0zODguNDE1LDkuMzkyaDEuODU4YzAuODg4LDAsMS40OS0wLjEzMiwxLjgxMS0wLjM5NwoJCWMwLjMyNy0wLjI2NCwwLjQ5LTAuNjE1LDAuNDktMS4wNTFjMC0wLjI4MS0wLjA3OC0wLjUzLTAuMjM0LTAuNzQ5Yy0wLjE1NS0wLjIyNS0wLjM3NC0wLjM5My0wLjY1Mi0wLjUwMgoJCWMtMC4yNzMtMC4xMDgtMC43ODMtMC4xNjMtMS41MzEtMC4xNjRoLTEuNzQxVjkuMzkyTDM4OC40MTUsOS4zOTJ6Ii8+Cgk8cGF0aCBmaWxsPSIjMDA0NTdDIiBkPSJNMjIzLjU4Miw3OC41NjZjLTAuMDkxLTAuNDI0LTAuMjM3LTAuODEyLTAuNDM4LTEuMTY3Yy0wLjIwMi0wLjM1My0wLjQ2LTAuNjQ2LTAuNzczLTAuODc5CgkJYy0wLjMxMy0wLjIzMi0wLjY5Mi0wLjM0OC0xLjEzNi0wLjM0OGMtMS4wNTEsMC0xLjgxLDAuNTg2LTIuMjc0LDEuNzU4cy0wLjY5NywzLjExLTAuNjk3LDUuODE3YzAsMS4yOTUsMC4wNDEsMi40NjcsMC4xMjIsMy41MTcKCQljMC4wOCwxLjA1MSwwLjIyOCwxLjk0NSwwLjQzOSwyLjY4MmMwLjIxMiwwLjczOCwwLjUxNSwxLjMwMywwLjkwOSwxLjY5N2MwLjM5NCwwLjM5NCwwLjkwMywwLjU5MSwxLjUzLDAuNTkxCgkJYzAuMjYzLDAsMC41NTEtMC4wNywwLjg2NC0wLjIxMmMwLjMxMy0wLjE0MSwwLjYwNi0wLjM1MywwLjg3OC0wLjYzNmMwLjI3My0wLjI4MywwLjUwMS0wLjY0MiwwLjY4My0xLjA3NgoJCWMwLjE4Mi0wLjQzNCwwLjI3Mi0wLjk0NCwwLjI3Mi0xLjUzMXYtMi4yMTJoLTIuODc5di0zLjIxM2g3LjA2MnYxMS42NjloLTMuMjEydi0yLjAwMWgtMC4wNjIKCQljLTAuNTI1LDAuODQ5LTEuMTU3LDEuNDUtMS44OTQsMS44MDRjLTAuNzM4LDAuMzU0LTEuNjIxLDAuNTMtMi42NTIsMC41M2MtMS4zMzMsMC0yLjQyLTAuMjMzLTMuMjU4LTAuNjk3CgkJYy0wLjgzOC0wLjQ2NS0xLjQ5NS0xLjE4Mi0xLjk3MS0yLjE1MWMtMC40NzUtMC45NzEtMC43OTMtMi4xNjctMC45NTMtMy41OTJjLTAuMTYyLTEuNDI1LTAuMjQzLTMuMDc1LTAuMjQzLTQuOTU0CgkJYzAtMS44MTksMC4xMTYtMy40MTUsMC4zNDktNC43ODlzMC42MzEtMi41MjEsMS4xOTctMy40NGMwLjU2NC0wLjkxOSwxLjMxMi0xLjYxMSwyLjI0My0yLjA3NQoJCWMwLjkyOS0wLjQ2NSwyLjA5MS0wLjY5NywzLjQ4NC0wLjY5N2MyLjM4NCwwLDQuMTAyLDAuNTkxLDUuMTUyLDEuNzcyYzEuMDUsMS4xODIsMS41NzYsMi44NzUsMS41NzYsNS4wNzdoLTQuMTgzCgkJQzIyMy43MTksNzkuNDA1LDIyMy42NzMsNzguOTksMjIzLjU4Miw3OC41NjZMMjIzLjU4Miw3OC41NjZ6IE0yMzguNzMzLDgzLjM3Yy0wLjA2Mi0wLjQ3NS0wLjE2Ny0wLjg3OS0wLjMxOS0xLjIxMwoJCWMtMC4xNTEtMC4zMzMtMC4zNjMtMC41ODUtMC42MzYtMC43NTdjLTAuMjczLTAuMTcyLTAuNjIxLTAuMjU4LTEuMDQ2LTAuMjU4Yy0wLjQyNCwwLTAuNzcyLDAuMDk2LTEuMDQ1LDAuMjg4CgkJYy0wLjI3MywwLjE5MS0wLjQ5LDAuNDQ1LTAuNjUyLDAuNzU4Yy0wLjE2MiwwLjMxMy0wLjI3OCwwLjY2Mi0wLjM0OCwxLjA0NWMtMC4wNzEsMC4zODQtMC4xMDYsMC43NjktMC4xMDYsMS4xNTJ2MC42MzZoNC4yNzMKCQlDMjM4LjgzNCw4NC4zOTYsMjM4Ljc5Myw4My44NDYsMjM4LjczMyw4My4zN0wyMzguNzMzLDgzLjM3eiBNMjM0LjU4MSw4OC44MTFjMCwwLjQ4NSwwLjAzNSwwLjk1NCwwLjEwNiwxLjQwOQoJCWMwLjA2OSwwLjQ1NSwwLjE4NiwwLjg1OCwwLjM0OCwxLjIxMnMwLjM3NCwwLjYzNywwLjYzNywwLjg0OXMwLjU4NSwwLjMxOCwwLjk3LDAuMzE4YzAuNzA4LDAsMS4yMjMtMC4yNTIsMS41NDYtMC43NTgKCQljMC4zMjItMC41MDQsMC41NDYtMS4yNzIsMC42NjctMi4zMDRoMy43NThjLTAuMDgxLDEuODk5LTAuNTg2LDMuMzQ1LTEuNTE1LDQuMzM0Yy0wLjkzMSwwLjk5LTIuMzk2LDEuNDg1LTQuMzk2LDEuNDg1CgkJYy0xLjUxNSwwLTIuNjk3LTAuMjUzLTMuNTQ2LTAuNzU4Yy0wLjg0OC0wLjUwNC0xLjQ3NS0xLjE3MS0xLjg3OS0yYy0wLjQwNC0wLjgyOC0wLjY1MS0xLjc1OC0wLjc0Mi0yLjc4OAoJCWMtMC4wOTEtMS4wMzEtMC4xMzctMi4wNjItMC4xMzctMy4wOTFjMC0xLjA5MSwwLjA3Ni0yLjE0MywwLjIyOC0zLjE1MnMwLjQ1NC0xLjkxLDAuOTA5LTIuNjk4CgkJYzAuNDU0LTAuNzg4LDEuMTA2LTEuNDE0LDEuOTU1LTEuODc5YzAuODQ4LTAuNDY0LDEuOTc5LTAuNjk2LDMuMzk0LTAuNjk2YzEuMjEyLDAsMi4yMDcsMC4xOTYsMi45ODUsMC41OTEKCQljMC43NzgsMC4zOTQsMS4zODksMC45NSwxLjgzNCwxLjY2N2MwLjQ0NCwwLjcxOCwwLjc0NywxLjU4NiwwLjkwOSwyLjYwNWMwLjE2MSwxLjAyMSwwLjI0MiwyLjE1NywwLjI0MiwzLjQxdjAuOTRoLTguMjczVjg4LjgxMQoJCUwyMzQuNTgxLDg4LjgxMXogTTI0OS4yODgsNzMuMzg0djYuODVoMC4wNjJjMC40NDMtMC42NDYsMC45NDMtMS4xMzEsMS41LTEuNDU1YzAuNTU2LTAuMzIzLDEuMjI4LTAuNDg0LDIuMDE2LTAuNDg0CgkJYzEuNzE3LDAsMi45NzksMC42NzIsMy43ODgsMi4wMTZjMC44MDgsMS4zNDQsMS4yMTIsMy41MywxLjIxMiw2LjU2MWMwLDMuMDMxLTAuNDA0LDUuMjAzLTEuMjEyLDYuNTE3CgkJYy0wLjgwOSwxLjMxMy0yLjA3MSwxLjk3LTMuNzg4LDEuOTdjLTAuODQ5LDAtMS41NjItMC4xNTItMi4xMzctMC40NTVjLTAuNTc2LTAuMzAzLTEuMDk3LTAuODM4LTEuNTYyLTEuNjA1aC0wLjA2djEuNzI4aC00LjAwMQoJCXYtMjEuNjRIMjQ5LjI4OEwyNDkuMjg4LDczLjM4NHogTTI0OS42OTgsOTAuODg3YzAuMjcxLDAuODk4LDAuODczLDEuMzQ4LDEuODAzLDEuMzQ4YzAuOTA5LDAsMS41LTAuNDQ5LDEuNzczLTEuMzQ4CgkJYzAuMjcyLTAuODk5LDAuNDA5LTIuMjM4LDAuNDA5LTQuMDE3YzAtMS43NzctMC4xMzctMy4xMTUtMC40MDktNC4wMTZjLTAuMjczLTAuODk4LTAuODY0LTEuMzQ4LTEuNzczLTEuMzQ4CgkJYy0wLjkzLDAtMS41MzEsMC40NDktMS44MDMsMS4zNDhjLTAuMjczLDAuOS0wLjQxLDIuMjM4LTAuNDEsNC4wMTZDMjQ5LjI4OCw4OC42NDgsMjQ5LjQyNSw4OS45ODcsMjQ5LjY5OCw5MC44ODdMMjQ5LjY5OCw5MC44ODd6CgkJIE0yNzAuMzc2LDcyLjk2djMuNTc1aC0zLjM5NFY3Mi45NkgyNzAuMzc2TDI3MC4zNzYsNzIuOTZ6IE0yNjUuMTYzLDcyLjk2djMuNTc1aC0zLjM5NFY3Mi45NkgyNjUuMTYzTDI2NS4xNjMsNzIuOTZ6CgkJIE0yNjYuODYsODcuNGMtMC4zMjMsMC4xMzItMC42MTYsMC4yMjktMC44NzksMC4yODhjLTAuODQ5LDAuMTgyLTEuNDU0LDAuNDg1LTEuODE4LDAuOTFjLTAuMzY0LDAuNDI0LTAuNTQ1LDEtMC41NDUsMS43MjcKCQljMCwwLjYyNywwLjEyMSwxLjE2MiwwLjM2MywxLjYwNmMwLjI0MywwLjQ0NSwwLjY0NiwwLjY2NywxLjIxMywwLjY2N2MwLjI4MiwwLDAuNTc1LTAuMDQ1LDAuODc4LTAuMTM2CgkJYzAuMzAzLTAuMDkyLDAuNTgxLTAuMjM4LDAuODM0LTAuNDRjMC4yNTItMC4yMDEsMC40NTktMC40NjQsMC42MjEtMC43ODhjMC4xNjItMC4zMjMsMC4yNDMtMC43MDcsMC4yNDMtMS4xNTFWODYuODcKCQlDMjY3LjQ4Niw4Ny4wOTQsMjY3LjE4NCw4Ny4yNywyNjYuODYsODcuNEwyNjYuODYsODcuNHogTTI2MC4xMzIsODMuMzI0YzAtMC45NDgsMC4xNTItMS43NDEsMC40NTUtMi4zNzkKCQljMC4zMDQtMC42MzYsMC43MTItMS4xNTEsMS4yMjgtMS41NDZjMC41MTYtMC4zOTQsMS4xMjItMC42NzYsMS44MTgtMC44NDhjMC42OTctMC4xNzIsMS40MzktMC4yNTgsMi4yMjgtMC4yNTgKCQljMS4yNTMsMCwyLjI2MywwLjEyLDMuMDMxLDAuMzYzYzAuNzY4LDAuMjQyLDEuMzYzLDAuNTg2LDEuNzg3LDEuMDNjMC40MjUsMC40NDUsMC43MTMsMC45NzUsMC44NjQsMS41OTEKCQljMC4xNTEsMC42MTcsMC4yMjgsMS4yODksMC4yMjgsMi4wMTd2OC41NzZjMCwwLjc2OSwwLjAzNCwxLjM2NCwwLjEwNSwxLjc4OGMwLjA3MSwwLjQyNSwwLjIwNywwLjg3OSwwLjQwOSwxLjM2NGgtNAoJCWMtMC4xNDItMC4yNjMtMC4yNDgtMC41NDEtMC4zMTgtMC44MzRjLTAuMDctMC4yOTItMC4xMzctMC41OC0wLjE5Ni0wLjg2NGgtMC4wNjJjLTAuNDg0LDAuODUtMS4wNDYsMS40LTEuNjgyLDEuNjUyCgkJYy0wLjYzNywwLjI1My0xLjQ2LDAuMzc5LTIuNDcxLDAuMzc5Yy0wLjcyNywwLTEuMzQ0LTAuMTI2LTEuODQ5LTAuMzc5Yy0wLjUwNS0wLjI1Mi0wLjkwOS0wLjYwMS0xLjIxMi0xLjA0NQoJCWMtMC4zMDMtMC40NDUtMC41MjYtMC45NDUtMC42NjctMS41MDFjLTAuMTQxLTAuNTU1LTAuMjEyLTEuMTA2LTAuMjEyLTEuNjUxYzAtMC43NjgsMC4wODEtMS40MjksMC4yNDItMS45ODQKCQljMC4xNjItMC41NTcsMC40MS0xLjAzMSwwLjc0My0xLjQyNmMwLjMzMy0wLjM5NCwwLjc1OC0wLjcyMiwxLjI3Mi0wLjk4NGMwLjUxNi0wLjI2MywxLjEzNi0wLjQ5NSwxLjg2NC0wLjY5N2wyLjM2NC0wLjYzNgoJCWMwLjYyNi0wLjE2MiwxLjA2LTAuMzg0LDEuMzAzLTAuNjY3YzAuMjQyLTAuMjgzLDAuMzY0LTAuNjk3LDAuMzY0LTEuMjQzYzAtMC42MjYtMC4xNDctMS4xMTYtMC40NC0xLjQ3cy0wLjc5My0wLjUzLTEuNS0wLjUzCgkJYy0wLjY0NiwwLTEuMTMyLDAuMTkyLTEuNDU1LDAuNTc2cy0wLjQ4NCwwLjg5OC0wLjQ4NCwxLjU0NnYwLjQ1NGgtMy43NTlWODMuMzI0TDI2MC4xMzIsODMuMzI0eiBNMjgyLjg1OSw5My4xMTMKCQljLTAuNDQ1LDAuODEtMS4wMjEsMS4zODQtMS43MjgsMS43MjljLTAuNzA4LDAuMzQzLTEuNTE2LDAuNTE1LTIuNDI1LDAuNTE1Yy0xLjMzNCwwLTIuMzU5LTAuMzQ5LTMuMDc2LTEuMDQ2CgkJYy0wLjcxOC0wLjY5Ny0xLjA3Ni0xLjg2My0xLjA3Ni0zLjVWNzguNzE5aDQuMTgzdjExLjI0M2MwLDAuODQ5LDAuMTQxLDEuNDM5LDAuNDI1LDEuNzcyYzAuMjgyLDAuMzM0LDAuNzM3LDAuNSwxLjM2MywwLjUKCQljMS40NzUsMCwyLjIxMy0wLjg5NywyLjIxMy0yLjY5N1Y3OC43MTloNC4xODJ2MTYuMzA1aC00di0xLjkxSDI4Mi44NTlMMjgyLjg1OSw5My4xMTN6IE0yOTguMDI4LDkzLjI5NgoJCWMtMC40NjUsMC43NjgtMC45ODUsMS4zMDMtMS41NjIsMS42MDVjLTAuNTc1LDAuMzAzLTEuMjg4LDAuNDU1LTIuMTM3LDAuNDU1Yy0xLjcxNywwLTIuOTc5LTAuNjU2LTMuNzg4LTEuOTcKCQlzLTEuMjEyLTMuNDg1LTEuMjEyLTYuNTE3YzAtMy4wMywwLjQwMy01LjIxNywxLjIxMi02LjU2MXMyLjA3MS0yLjAxNiwzLjc4OC0yLjAxNmMwLjc4OCwwLDEuNDYsMC4xNjEsMi4wMTYsMC40ODQKCQljMC41NTYsMC4zMjQsMS4wNTYsMC44MDksMS41LDEuNDU1aDAuMDYxdi02Ljg1aDQuMTgzdjIxLjY0aC00LjAwMXYtMS43MjhIMjk4LjAyOEwyOTguMDI4LDkzLjI5NnogTTI5My45MjEsOTAuODg3CgkJYzAuMjczLDAuODk4LDAuODY0LDEuMzQ4LDEuNzczLDEuMzQ4YzAuOTI5LDAsMS41My0wLjQ0OSwxLjgwMy0xLjM0OGMwLjI3My0wLjg5OSwwLjQwOS0yLjIzOCwwLjQwOS00LjAxNwoJCWMwLTEuNzc3LTAuMTM2LTMuMTE1LTAuNDA5LTQuMDE2Yy0wLjI3Mi0wLjg5OC0wLjg3NC0xLjM0OC0xLjgwMy0xLjM0OGMtMC45MDksMC0xLjUsMC40NDktMS43NzMsMS4zNDgKCQljLTAuMjcyLDAuOS0wLjQwOSwyLjIzOC0wLjQwOSw0LjAxNkMyOTMuNTEyLDg4LjY0OCwyOTMuNjQ4LDg5Ljk4NywyOTMuOTIxLDkwLjg4N0wyOTMuOTIxLDkwLjg4N3ogTTMxMi43MjcsODMuMzcKCQljLTAuMDYxLTAuNDc1LTAuMTY2LTAuODc5LTAuMzE4LTEuMjEzYy0wLjE1MS0wLjMzMy0wLjM2My0wLjU4NS0wLjYzNi0wLjc1N2MtMC4yNzMtMC4xNzItMC42MjItMC4yNTgtMS4wNDYtMC4yNTgKCQljLTAuNDI1LDAtMC43NzMsMC4wOTYtMS4wNDUsMC4yODhjLTAuMjczLDAuMTkxLTAuNDkxLDAuNDQ1LTAuNjUyLDAuNzU4Yy0wLjE2MiwwLjMxMy0wLjI3OCwwLjY2Mi0wLjM1LDEuMDQ1CgkJYy0wLjA3LDAuMzg0LTAuMTA1LDAuNzY5LTAuMTA1LDEuMTUydjAuNjM2aDQuMjczQzMxMi44MjcsODQuMzk2LDMxMi43ODcsODMuODQ2LDMxMi43MjcsODMuMzdMMzEyLjcyNyw4My4zN3ogTTMwOC41NzQsODguODExCgkJYzAsMC40ODUsMC4wMzUsMC45NTQsMC4xMDUsMS40MDljMC4wNzEsMC40NTUsMC4xODgsMC44NTgsMC4zNSwxLjIxMmMwLjE2MSwwLjM1NCwwLjM3NCwwLjYzNywwLjYzNiwwLjg0OQoJCWMwLjI2MywwLjIxMiwwLjU4NiwwLjMxOCwwLjk3LDAuMzE4YzAuNzA3LDAsMS4yMjMtMC4yNTIsMS41NDctMC43NThjMC4zMjItMC41MDQsMC41NDUtMS4yNzIsMC42NjYtMi4zMDRoMy43NTkKCQljLTAuMDgxLDEuODk5LTAuNTg3LDMuMzQ1LTEuNTE3LDQuMzM0Yy0wLjkyOSwwLjk5LTIuMzk0LDEuNDg1LTQuMzk0LDEuNDg1Yy0xLjUxNSwwLTIuNjk3LTAuMjUzLTMuNTQ2LTAuNzU4CgkJYy0wLjg1LTAuNTA0LTEuNDc2LTEuMTcxLTEuODc5LTJjLTAuNDA0LTAuODI4LTAuNjUyLTEuNzU4LTAuNzQzLTIuNzg4Yy0wLjA5MS0xLjAzMS0wLjEzNi0yLjA2Mi0wLjEzNi0zLjA5MQoJCWMwLTEuMDkxLDAuMDc1LTIuMTQzLDAuMjI3LTMuMTUyYzAuMTUyLTEuMDEsMC40NTUtMS45MSwwLjkxLTIuNjk4YzAuNDU0LTAuNzg4LDEuMTA1LTEuNDE0LDEuOTU0LTEuODc5CgkJYzAuODQ5LTAuNDY0LDEuOTc5LTAuNjk2LDMuMzk1LTAuNjk2YzEuMjEyLDAsMi4yMDcsMC4xOTYsMi45ODUsMC41OTFjMC43NzcsMC4zOTQsMS4zODksMC45NSwxLjgzNCwxLjY2NwoJCWMwLjQ0NCwwLjcxOCwwLjc0NywxLjU4NiwwLjkwOSwyLjYwNWMwLjE2MSwxLjAyMSwwLjI0MSwyLjE1NywwLjI0MSwzLjQxdjAuOTRoLTguMjczVjg4LjgxMUwzMDguNTc0LDg4LjgxMXogTTMyNy4zODMsOTMuMjk2CgkJYy0wLjQ2NSwwLjc2OC0wLjk4NCwxLjMwMy0xLjU2MSwxLjYwNXMtMS4yODgsMC40NTUtMi4xMzcsMC40NTVjLTEuNzE4LDAtMi45OC0wLjY1Ni0zLjc4OC0xLjk3CgkJYy0wLjgwOS0xLjMxMy0xLjIxMi0zLjQ4NS0xLjIxMi02LjUxN2MwLTMuMDMsMC40MDMtNS4yMTcsMS4yMTItNi41NjFjMC44MDgtMS4zNDQsMi4wNy0yLjAxNiwzLjc4OC0yLjAxNgoJCWMwLjc4NywwLDEuNDYsMC4xNjEsMi4wMTYsMC40ODRjMC41NTUsMC4zMjQsMS4wNTUsMC44MDksMS41LDEuNDU1aDAuMDZ2LTYuODVoNC4xODR2MjEuNjRoLTQuMDAxdi0xLjcyOEgzMjcuMzgzTDMyNy4zODMsOTMuMjk2egoJCSBNMzIzLjI3Niw5MC44ODdjMC4yNzIsMC44OTgsMC44NjQsMS4zNDgsMS43NzIsMS4zNDhjMC45MywwLDEuNTMxLTAuNDQ5LDEuODA0LTEuMzQ4YzAuMjcyLTAuODk5LDAuNDA4LTIuMjM4LDAuNDA4LTQuMDE3CgkJYzAtMS43NzctMC4xMzYtMy4xMTUtMC40MDgtNC4wMTZjLTAuMjcyLTAuODk4LTAuODc0LTEuMzQ4LTEuODA0LTEuMzQ4Yy0wLjkwOCwwLTEuNSwwLjQ0OS0xLjc3MiwxLjM0OAoJCWMtMC4yNzMsMC45LTAuNDA5LDIuMjM4LTAuNDA5LDQuMDE2QzMyMi44NjcsODguNjQ4LDMyMy4wMDMsODkuOTg3LDMyMy4yNzYsOTAuODg3TDMyMy4yNzYsOTAuODg3eiBNMzM4LjQ5LDczLjE0MnYzLjU3NmgtNC4xODIKCQl2LTMuNTc2SDMzOC40OUwzMzguNDksNzMuMTQyeiBNMzM4LjQ5LDc4LjcxOXYxNi4zMDVoLTQuMTgyVjc4LjcxOUgzMzguNDlMMzM4LjQ5LDc4LjcxOXogTTM0OS4yMjMsODMuMzcKCQljLTAuMDYyLTAuNDc1LTAuMTY4LTAuODc5LTAuMzE5LTEuMjEzYy0wLjE1MS0wLjMzMy0wLjM2My0wLjU4NS0wLjYzNi0wLjc1N2MtMC4yNzMtMC4xNzItMC42MjEtMC4yNTgtMS4wNDctMC4yNTgKCQljLTAuNDI0LDAtMC43NzIsMC4wOTYtMS4wNDUsMC4yODhjLTAuMjcyLDAuMTkxLTAuNDg5LDAuNDQ1LTAuNjUxLDAuNzU4Yy0wLjE2MiwwLjMxMy0wLjI3OCwwLjY2Mi0wLjM0OSwxLjA0NQoJCWMtMC4wNywwLjM4NC0wLjEwNSwwLjc2OS0wLjEwNSwxLjE1MnYwLjYzNmg0LjI3MkMzNDkuMzIyLDg0LjM5NiwzNDkuMjgyLDgzLjg0NiwzNDkuMjIzLDgzLjM3TDM0OS4yMjMsODMuMzd6IE0zNDUuMDcsODguODExCgkJYzAsMC40ODUsMC4wMzUsMC45NTQsMC4xMDUsMS40MDlzMC4xODcsMC44NTgsMC4zNDksMS4yMTJzMC4zNzQsMC42MzcsMC42MzcsMC44NDljMC4yNjIsMC4yMTIsMC41ODUsMC4zMTgsMC45NjksMC4zMTgKCQljMC43MDcsMCwxLjIyNC0wLjI1MiwxLjU0Ni0wLjc1OGMwLjMyMy0wLjUwNCwwLjU0Ny0xLjI3MiwwLjY2Ny0yLjMwNGgzLjc1OWMtMC4wODEsMS44OTktMC41ODYsMy4zNDUtMS41MTcsNC4zMzQKCQljLTAuOTI5LDAuOTktMi4zOTQsMS40ODUtNC4zOTQsMS40ODVjLTEuNTE2LDAtMi42OTctMC4yNTMtMy41NDYtMC43NThjLTAuODUtMC41MDQtMS40NzYtMS4xNzEtMS44NzktMgoJCWMtMC40MDQtMC44MjgtMC42NTItMS43NTgtMC43NDItMi43ODhjLTAuMDkxLTEuMDMxLTAuMTM4LTIuMDYyLTAuMTM4LTMuMDkxYzAtMS4wOTEsMC4wNzYtMi4xNDMsMC4yMjgtMy4xNTIKCQljMC4xNTItMS4wMSwwLjQ1NS0xLjkxLDAuOTEtMi42OThjMC40NTQtMC43ODgsMS4xMDUtMS40MTQsMS45NTQtMS44NzljMC44NDktMC40NjQsMS45NzktMC42OTYsMy4zOTUtMC42OTYKCQljMS4yMTIsMCwyLjIwNywwLjE5NiwyLjk4NSwwLjU5MWMwLjc3NywwLjM5NCwxLjM4OSwwLjk1LDEuODM0LDEuNjY3YzAuNDQzLDAuNzE4LDAuNzQ3LDEuNTg2LDAuOTA5LDIuNjA1CgkJYzAuMTYsMS4wMjEsMC4yNDEsMi4xNTcsMC4yNDEsMy40MXYwLjk0aC04LjI3MlY4OC44MTFMMzQ1LjA3LDg4LjgxMXogTTM1OS41OTYsNzguNzE5djEuOTA5aDAuMDYxCgkJYzAuNDQ0LTAuODA5LDEuMDItMS4zOTksMS43MjgtMS43NzNjMC43MDctMC4zNzQsMS41MTYtMC41NjEsMi40MjUtMC41NjFjMS4zMzQsMCwyLjM1OCwwLjM2MywzLjA3NSwxLjA5MQoJCWMwLjcxOCwwLjcyOCwxLjA3NiwxLjkxLDEuMDc2LDMuNTQ2djEyLjA5M2gtNC4xODJWODMuNzc5YzAtMC44NDktMC4xNDMtMS40MzktMC40MjQtMS43NzJjLTAuMjg0LTAuMzM0LTAuNzM4LTAuNS0xLjM2NC0wLjUKCQljLTEuNDc1LDAtMi4yMTMsMC44OTgtMi4yMTMsMi42OTZ2MTAuODJoLTQuMTgzVjc4LjcxOUgzNTkuNTk2TDM1OS41OTYsNzguNzE5eiBNMzczLjg2MSw5MC4yMzRjMCwwLjcwOCwwLjE4NywxLjI3OCwwLjU2MSwxLjcxMgoJCWMwLjM3MywwLjQzNiwwLjkxNCwwLjY1MiwxLjYyMSwwLjY1MmMwLjY0NiwwLDEuMTYyLTAuMTYxLDEuNTQ2LTAuNDg1YzAuMzg0LTAuMzIzLDAuNTc2LTAuODA4LDAuNTc2LTEuNDU1CgkJYzAtMC41MjQtMC4xNTEtMC45MjQtMC40NTUtMS4xOTZjLTAuMzAzLTAuMjcyLTAuNjU3LTAuNDg5LTEuMDYxLTAuNjUxbC0yLjk0LTEuMDYyYy0xLjE1LTAuNDAzLTIuMDItMC45NzUtMi42MDUtMS43MTIKCQlzLTAuODc5LTEuNjgyLTAuODc5LTIuODM0YzAtMC42NjcsMC4xMS0xLjI5OCwwLjMzNC0xLjg5NGMwLjIyMi0wLjU5NiwwLjU3NC0xLjExNiwxLjA2LTEuNTYyCgkJYzAuNDg1LTAuNDQzLDEuMTA2LTAuNzk4LDEuODY0LTEuMDYxYzAuNzU4LTAuMjYyLDEuNjcyLTAuMzk0LDIuNzQzLTAuMzk0YzEuODk4LDAsMy4zMDMsMC40MDQsNC4yMTMsMS4yMTMKCQljMC45MDksMC44MDgsMS4zNjIsMS45NDksMS4zNjIsMy40MjR2MC42NjdoLTMuNzU4YzAtMC44NS0wLjEzNi0xLjQ3LTAuNDA5LTEuODY0Yy0wLjI3Mi0wLjM5NC0wLjc1My0wLjU5MS0xLjQzOC0wLjU5MQoJCWMtMC41MjYsMC0wLjk4NSwwLjE0Ni0xLjM3OSwwLjQ0Yy0wLjM5NSwwLjI5My0wLjU5MSwwLjczMS0wLjU5MSwxLjMxN2MwLDAuNDA0LDAuMTI2LDAuNzY5LDAuMzc4LDEuMDkxCgkJYzAuMjUzLDAuMzIzLDAuNzMyLDAuNTk3LDEuNDM5LDAuODE4bDIuNTE3LDAuODQ5YzEuMzEyLDAuNDQ0LDIuMjQxLDEuMDI2LDIuNzg4LDEuNzQyYzAuNTQ1LDAuNzE4LDAuODE3LDEuNjkzLDAuODE3LDIuOTI1CgkJYzAsMC44NjktMC4xNTEsMS42MjEtMC40NTUsMi4yNTljLTAuMzAzLDAuNjM2LTAuNzIyLDEuMTY3LTEuMjU3LDEuNTkxYy0wLjUzNiwwLjQyNC0xLjE3MiwwLjcyNy0xLjkxLDAuOTA4CgkJYy0wLjczNiwwLjE4My0xLjU1LDAuMjczLTIuNDM4LDAuMjczYy0xLjE3MywwLTIuMTQ3LTAuMTExLTIuOTI1LTAuMzMzYy0wLjc3OC0wLjIyMi0xLjM5NS0wLjU1Ni0xLjg1LTEKCQljLTAuNDU0LTAuNDQ1LTAuNzcxLTAuOTg1LTAuOTU0LTEuNjIyYy0wLjE4Mi0wLjYzNi0wLjI3Mi0xLjM0OS0wLjI3Mi0yLjEzN3YtMC41NzVoMy43NThWOTAuMjM0TDM3My44NjEsOTAuMjM0eiBNMzg5LjU4Nyw3NC4wNTEKCQl2NC42NjhoMi40MjR2Mi44NDhoLTIuNDI0djguODJjMCwwLjY0NiwwLjA5NSwxLjEwNSwwLjI4OCwxLjM3OWMwLjE5MSwwLjI3MSwwLjU5MSwwLjQwOSwxLjE5NywwLjQwOQoJCWMwLjE2MSwwLDAuMzIzLTAuMDA1LDAuNDg0LTAuMDE2YzAuMTYxLTAuMDEsMC4zMTMtMC4wMjQsMC40NTQtMC4wNDZ2Mi45MWMtMC40NjUsMC0wLjkxMywwLjAxNS0xLjM0OCwwLjA0NQoJCXMtMC44OTQsMC4wNDYtMS4zNzksMC4wNDZjLTAuODA5LDAtMS40Ny0wLjA1Ni0xLjk4NS0wLjE2N2MtMC41MTYtMC4xMS0wLjkxLTAuMzM0LTEuMTgyLTAuNjY3CgkJYy0wLjI3My0wLjMzMy0wLjQ2LTAuNzcyLTAuNTYxLTEuMzE3Yy0wLjEwMi0wLjU0Ni0wLjE1Mi0xLjIzMi0wLjE1Mi0yLjA2MnYtOS4zMzVoLTIuMTIxdi0yLjg0OGgyLjEyMXYtNC42NjhIMzg5LjU4NwoJCUwzODkuNTg3LDc0LjA1MXogTTQwMS40MTgsODMuMzdjLTAuMDYtMC40NzUtMC4xNjYtMC44NzktMC4zMTctMS4yMTNjLTAuMTUyLTAuMzMzLTAuMzY0LTAuNTg1LTAuNjM3LTAuNzU3CgkJcy0wLjYyMi0wLjI1OC0xLjA0Ni0wLjI1OHMtMC43NzIsMC4wOTYtMS4wNDYsMC4yODhjLTAuMjcxLDAuMTkxLTAuNDksMC40NDUtMC42NTEsMC43NThjLTAuMTYxLDAuMzEzLTAuMjc3LDAuNjYyLTAuMzQ5LDEuMDQ1CgkJYy0wLjA3MSwwLjM4NC0wLjEwNSwwLjc2OS0wLjEwNSwxLjE1MnYwLjYzNmg0LjI3MkM0MDEuNTIsODQuMzk2LDQwMS40NzksODMuODQ2LDQwMS40MTgsODMuMzdMNDAxLjQxOCw4My4zN3ogTTM5Ny4yNjcsODguODExCgkJYzAsMC40ODUsMC4wMzQsMC45NTQsMC4xMDUsMS40MDlzMC4xODgsMC44NTgsMC4zNDksMS4yMTJzMC4zNzMsMC42MzcsMC42MzcsMC44NDljMC4yNjMsMC4yMTIsMC41ODYsMC4zMTgsMC45NywwLjMxOAoJCWMwLjcwNywwLDEuMjIyLTAuMjUyLDEuNTQ2LTAuNzU4YzAuMzIzLTAuNTA0LDAuNTQ1LTEuMjcyLDAuNjY2LTIuMzA0aDMuNzU4Yy0wLjA4LDEuODk5LTAuNTg2LDMuMzQ1LTEuNTE1LDQuMzM0CgkJYy0wLjkyOSwwLjk5LTIuMzk1LDEuNDg1LTQuMzk0LDEuNDg1Yy0xLjUxNywwLTIuNjk4LTAuMjUzLTMuNTQ3LTAuNzU4Yy0wLjg0OS0wLjUwNC0xLjQ3NS0xLjE3MS0xLjg3OS0yCgkJYy0wLjQwNC0wLjgyOC0wLjY1MS0xLjc1OC0wLjc0My0yLjc4OGMtMC4wOTEtMS4wMzEtMC4xMzYtMi4wNjItMC4xMzYtMy4wOTFjMC0xLjA5MSwwLjA3Ni0yLjE0MywwLjIyOC0zLjE1MgoJCXMwLjQ1NS0xLjkxLDAuOTA4LTIuNjk4YzAuNDU1LTAuNzg4LDEuMTA3LTEuNDE0LDEuOTU1LTEuODc5YzAuODUtMC40NjQsMS45OC0wLjY5NiwzLjM5NS0wLjY5NmMxLjIxMywwLDIuMjA4LDAuMTk2LDIuOTg1LDAuNTkxCgkJYzAuNzc3LDAuMzk0LDEuMzksMC45NSwxLjgzMywxLjY2N2MwLjQ0NCwwLjcxOCwwLjc0OCwxLjU4NiwwLjkwOSwyLjYwNWMwLjE2MiwxLjAyMSwwLjI0MywyLjE1NywwLjI0MywzLjQxdjAuOTRoLTguMjczVjg4LjgxMQoJCUwzOTcuMjY3LDg4LjgxMXoiLz4KCTxwYXRoIGZpbGw9IiMwMDQ1N0MiIGQ9Ik0xLjc1MSwyLjU4aDYxLjQxYzcuMTU2LDAsMTIuNzc0LDcuNDA2LDEyLjc3NCwxMy4xNjhjMCw0LjIxMi0yLjE0Miw4LjY2MS03LjAwMywxMS40OTIKCQljNS4wODUsMi41MTYsNy44NDIsNy44MzEsNy44NDIsMTIuMDgzYzAsNS43NDMtNS4wODEsMTMuMjc5LTEyLjkyMiwxMy4yNjhMMS43NSw1Mi42MDhMMS43NTEsMi41OEwxLjc1MSwyLjU4eiBNMjQuNDM5LDE2LjUzNwoJCXYyMS44OThoMjMuMzA0di00LjQ4OEgyNy4yNjVWMjAuOTY1bDIwLjQ3OCwwLjAxMXYtNC40MzlIMjQuNDM5TDI0LjQzOSwxNi41Mzd6IE0xNTEuMDg0LDc3Ljg0OGwzNC43MTctMC4wMDZsMTYuMDQ0LDE2Ljc1NgoJCWgtMzQuNTA4TDE1MS4wODQsNzcuODQ4TDE1MS4wODQsNzcuODQ4eiBNMjYxLjE0MiwyMC45NzZoMzcuMTM4djEyLjk3MWgtMzcuMTM4VjIwLjk3NkwyNjEuMTQyLDIwLjk3NnogTTE5MS4yNSwyMC45NzZoMzYuOTkyCgkJdjEyLjk3MUgxOTEuMjVWMjAuOTc2TDE5MS4yNSwyMC45NzZ6IE0yMzIuOTI4LDIuNThoNjUuMzUydjEzLjk1N2gtNDB2MjEuODk4aDQwVjUyLjU5aC02NS4zNTJWMi41OEwyMzIuOTI4LDIuNTh6IE0xNjIuODkxLDIuNTgKCQloNjUuMzUxdjEzLjk1N2gtNDB2MjEuODk4aDQwVjUyLjU5aC02NS4zNTFWMi41OEwxNjIuODkxLDIuNTh6IE0zMDIuNTIyLDIuNThoNjAuNzY0YzkuMDUtMC4wMTIsMTYuNDM3LDguMTc1LDE2LjQzNywxNi4zNDEKCQljMCw2Ljg3NS01LjMyNywxMy4wOTQtMTMuNTI1LDE1LjAyNmwzNS40NTQsMzYuNzg1aC0zNC41MzJMMzMxLjY3LDMzLjk0N1YyMC45NzZoMTguODQydi00LjQzOWgtMjIuMjk0VjUyLjU5aC0yNS42OTVWMi41OAoJCUwzMDIuNTIyLDIuNTh6IE03OS4xNDIsMi41OGg2MC43NjVjOS42NzUtMC4wMTIsMTYuNDUzLDguNjMyLDE2LjQ1MywxNi4yNjJjMCw2Ljk5NC00Ljg1NCwxMi43MTctMTMuMzQ3LDE1LjEwNWwzNi41NDgsMzcuNzI5CgkJaC0zNC42NDVsLTM2LjQyOC0zNy43MjlWMjAuOTc2aDE4Ljk5di00LjQzOWgtMjIuNDQyVjUyLjU5SDc5LjE0MlYyLjU4TDc5LjE0MiwyLjU4eiIvPgo8L2c+Cjwvc3ZnPgo="
st.markdown(f"""
    <div class="header-container">
        <div class="header-logo">
            <img src="data:image/svg+xml;base64,{logo_b64}" style="height: 75px; width: auto;">
        </div>
        <div class="header-text">
            <h1>Audit Cockpit</h1>
            <p>Intelligente Rechnungsprüfung & Diskrepanz-Analyse</p>
        </div>
    </div>
""", unsafe_allow_html=True)
# API Check
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
if not azure_api_key or not azure_endpoint:
    st.error("⚠️ API Credentials fehlen.")
    st.stop()
# --- UPLOAD AREA ---
st.markdown("### 📂 Dokumenten-Eingang")
cols = st.columns(3)
with cols[0]:
    with st.container():
        st.markdown("**1. Rechnung** <span style='color:#004e92'>●</span>", unsafe_allow_html=True)
        st.caption("Das Original-Dokument vom Lieferanten.")
        uploaded_invoice = st.file_uploader("Rechnung", type=["pdf"], key="inv", label_visibility="collapsed")
with cols[1]:
    with st.container():
        st.markdown("**2. Lieferscheine** <span style='color:#64748B'>●</span>", unsafe_allow_html=True)
        st.caption("Optional: Für den Mengenabgleich.")
        uploaded_delivery = st.file_uploader("Lieferscheine", type=["pdf"], key="del", accept_multiple_files=True, label_visibility="collapsed")
with cols[2]:
    with st.container():
        st.markdown("**3. Preisliste** <span style='color:#64748B'>●</span>", unsafe_allow_html=True)
        st.caption("Optional: Für den Preisabgleich.")
        uploaded_pricelist = st.file_uploader("Preisliste", type=["xlsx", "pdf"], key="price", accept_multiple_files=True, label_visibility="collapsed")
st.markdown("<br>", unsafe_allow_html=True)
b1, b2, b3 = st.columns([1, 2, 1])
with b2: start_btn = st.button("ANALYSE STARTEN", type="primary", use_container_width=True, disabled=not uploaded_invoice)
# --- LOGIC ---
if "audit_results" not in st.session_state: st.session_state.audit_results = None
if "audit_total_loss" not in st.session_state: st.session_state.audit_total_loss = 0.0
if start_btn:
    parser = InvoiceParser()
    with st.status("🔍 Deep Scan läuft...", expanded=True) as status:
        st.write("📑 Analysiere Rechnungsdaten...")
        df_invoice = parser.parse_pdf(uploaded_invoice)
        delivery_text = ""
        if uploaded_delivery:
            st.write("📦 Indexiere Lieferscheine...")
            for f in uploaded_delivery: delivery_text += extract_text_from_pdf(f)
        st.write("⚖️ Führe Cross-Check durch...")
        results = []
        for index, row in df_invoice.iterrows():
            ls_nr = str(row.get("Rechnung LS-Nr", ""))
            art_nr = str(row.get("Artikel-Nr", ""))
            status_list = []
            if uploaded_delivery:
                if not ls_nr or ls_nr == "UNKNOWN": status_list.append("⚠️ LS-Nr fehlt")
                elif ls_nr not in delivery_text: status_list.append("❌ Kein Lieferschein")
                elif art_nr not in delivery_text: status_list.append("❓ Artikel fehlt auf LS")
            try:
                if float(row.get("Menge", 0).replace(",",".")) == 0: status_list.append("ℹ️ Menge 0")
            except: pass
            if not status_list: status = "✅ OK"
            else: status = " | ".join(status_list)
            row["Handlung"] = status
            results.append(row)
        st.session_state.audit_results = pd.DataFrame(results)
        st.success("Analyse abgeschlossen.")
# --- DASHBOARD ---
if st.session_state.audit_results is not None:
    df = st.session_state.audit_results
    st.markdown("---, unsafe_allow_html=True")
    st.markdown("### 📊 Dashboard", unsafe_allow_html=True)
    
    err_count = len(df[df["Handlung"].str.contains("Kein|fehlt", case=False)])
    ok_count = len(df) - err_count
    risk = 0.0
    try:
        df_err = df[df["Handlung"].str.contains("Kein Lieferschein", case=False)].copy()
        if not df_err.empty:
            df_err["V"] = df_err["Preis_Gesamt"].astype(str).str.replace(".","").str.replace(",",".").astype(float)
            risk = df_err["V"].sum()
        st.session_state.audit_total_loss = risk
    except: risk = 0.0
    # --- VISUALS ---
    dc1, dc2 = st.columns([1, 2])
    with dc1:
        # Donut Chart
        labels = ["OK", "Fehler/Warnung"]
        values = [ok_count, err_count]
        colors = ["#2ecc71", "#e74c3c"] # Green, Red
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.6, marker=dict(colors=colors))])
        fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=140)
        fig.add_annotation(text=f"{len(df)}", showarrow=False, font=dict(size=20, color="#004e92"), yshift=10)
        fig.add_annotation(text="Total", showarrow=False, font=dict(size=10, color="#666"), yshift=-10)
        st.plotly_chart(fig, use_container_width=True)
    
    with dc2:
        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Gesamt-Positionen", len(df))
        m2.metric("Kritische Fehler", err_count, delta="Action" if err_count > 0 else "Clean", delta_color="inverse")
        m3.metric("Risiko-Wert", f"€ {risk:,.2f}", delta="Verlust" if risk > 0 else None, delta_color="inverse")
    st.markdown("#### 📝 Detail-Liste")
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    e1, e2 = st.columns(2)
    with e1:
        pdf_bytes = generate_audit_pdf(df, st.session_state.audit_total_loss)
        st.download_button("📄 Prüfbericht (PDF)", pdf_bytes, "Audit_Report.pdf", "application/pdf", use_container_width=True)
    with e2:
        csv = df.to_csv(index=False, sep=";").encode("utf-8")
        st.download_button("📥 Rohdaten (CSV)", csv, "audit.csv", "text/csv", use_container_width=True)
# --- FOOTER ---
st.markdown("<div class='footer'>Powered by <b>Breer GmbH</b> • AI Audit Solutions</div>", unsafe_allow_html=True)