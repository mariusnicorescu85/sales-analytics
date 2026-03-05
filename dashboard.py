import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
from scipy import stats
import warnings
import os
import re
import json
warnings.filterwarnings('ignore')

# Employee status - stored in Supabase (with local JSON fallback when Supabase unavailable)
EMPLOYEE_STATUS_FILE = 'employee_status.json'

# Load .env file so SUPABASE_URL and SUPABASE_KEY are available
from dotenv import load_dotenv
# Load from script directory and cwd (works when run from project root or Streamlit)
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Employee name normalization mapping
# Add known variations here - format: "variant_name": "canonical_name"
# These apply to data from Supabase and local CSV
EMPLOYEE_NAME_MAPPING = {
    # Duaa variants
    "Duaaz": "Duaa Zainab",
    "Duaa": "Duaa Zainab",
    "DuaaZ": "Duaa Zainab",
    # From normalize_names.py (typos, order, shorthand)
    "Bir_ra Thanvi": "Bir-ra Thanvi",
    "Bir-ra B": "Bir-ra Thanvi",
    "Molly ": "Molly Tasheva",  # trailing space variant
    "Leonard Masie": "Leonard Maisie",
    "Nicorescu Codruta": "Codruta Nicorescu",
    # Duplicate/typo variants seen in data
    "Durbala Edmond1": "Durbala Edmond",
    # Add more as you discover them - check Debug: Data & Columns for unique names
}

def normalize_employee_name(name):
    """
    Normalize employee names to handle variations.
    Uses manual mapping first (exact + case-insensitive), then applies normalization rules.
    """
    if pd.isna(name) or name == '':
        return name

    name_str = str(name).strip()
    # Collapse multiple spaces
    name_str = ' '.join(name_str.split())
    if not name_str:
        return name

    # Check manual mapping first (exact match)
    if name_str in EMPLOYEE_NAME_MAPPING:
        return EMPLOYEE_NAME_MAPPING[name_str]

    # Case-insensitive match (e.g. "Duaaz" vs "duaaz")
    for variant, canonical in EMPLOYEE_NAME_MAPPING.items():
        if variant.strip().lower() == name_str.lower():
            return canonical

    return name_str

def find_similar_employee_names(df):
    """
    Find potentially duplicate employee names by comparing normalized versions.
    Returns a dictionary of potential duplicates.
    """
    if 'Employee' not in df.columns:
        return {}
    
    # Get unique employee names
    employees = df['Employee'].dropna().unique()
    
    # Create normalized versions (remove spaces, lowercase)
    normalized_map = {}
    for emp in employees:
        normalized = re.sub(r'\s+', '', str(emp).lower())
        if normalized not in normalized_map:
            normalized_map[normalized] = []
        normalized_map[normalized].append(emp)
    
    # Find duplicates (same normalized version but different original names)
    duplicates = {norm: names for norm, names in normalized_map.items() 
                  if len(names) > 1 and len(set(names)) > 1}
    
    return duplicates


def _employee_status_path():
    """Path to employee status JSON file (fallback when Supabase unavailable)."""
    return Path(__file__).resolve().parent / EMPLOYEE_STATUS_FILE


def _load_employee_status_from_json():
    """Load employee status from local JSON file."""
    path = _employee_status_path()
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def load_employee_status():
    """Load employee active/inactive status from Supabase, or local JSON fallback. Returns dict {employee_name: 'active'|'inactive'}."""
    # Try Supabase first when configured
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            response = supabase.table(SUPABASE_TABLE_EMPLOYEE_STATUS).select('employee_name, status').execute()
            if response.data:
                return {row['employee_name']: row['status'] for row in response.data}
        except Exception:
            pass
    return _load_employee_status_from_json()


def save_employee_status(status_dict):
    """Save employee status to Supabase, or local JSON fallback. Returns True on success."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            rows = [{'employee_name': k, 'status': v} for k, v in status_dict.items()]
            supabase.table(SUPABASE_TABLE_EMPLOYEE_STATUS).upsert(rows, on_conflict='employee_name').execute()
            return True
        except Exception:
            pass
    # Fallback to local JSON
    path = _employee_status_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(status_dict, f, indent=2)
        return True
    except IOError:
        return False


def is_employee_active(employee_name, status_dict):
    """Return True if employee is active (default True when not in dict)."""
    return status_dict.get(str(employee_name).strip(), 'active').lower() == 'active'


# Supabase configuration - supports st.secrets (Streamlit Cloud) and os.getenv (local)
def _get_secret_or_env(key, default=''):
    """Get config from st.secrets (Streamlit Cloud) or os.getenv (local)."""
    try:
        val = st.secrets[key]
        return val if val else os.getenv(key, default)
    except (KeyError, AttributeError, FileNotFoundError, TypeError):
        return os.getenv(key, default)


SUPABASE_URL = _get_secret_or_env('SUPABASE_URL', '')
SUPABASE_KEY = _get_secret_or_env('SUPABASE_KEY', '')
SUPABASE_TABLE_PYT = _get_secret_or_env('SUPABASE_TABLE_PYT', 'PYT Sales Data')
SUPABASE_TABLE_OPATRA = _get_secret_or_env('SUPABASE_TABLE_OPATRA', 'Opatra Sales Data')
SUPABASE_TABLE_EMPLOYEE_STATUS = _get_secret_or_env('SUPABASE_TABLE_EMPLOYEE_STATUS', 'employee_status')

# Page configuration
st.set_page_config(
    page_title="Sales Dashboard - Complete Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Chart theme - unified palette matching dashboard gradient
CHART_COLORWAY = ["#667eea", "#764ba2", "#f093fb", "#4facfe", "#43e97b", "#fa709a"]
CHART_THEME = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    colorway=CHART_COLORWAY,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=50, b=50, l=50, r=50),
    hovermode="x unified",
    yaxis=dict(tickformat=".2f"),
)
CHART_CONFIG = {"displayModeBar": True, "displaylogo": False, "toImageButtonOptions": {"format": "png", "filename": "chart"}}

def apply_chart_theme(fig, dark=False):
    """Apply unified theme to Plotly figure."""
    fig.update_layout(**CHART_THEME)
    if dark:
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.2)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.2)", tickformat=".2f"),
        )
    return fig

def render_chart(fig, dark=False, height=None):
    """Render Plotly chart with theme and download support."""
    fig = apply_chart_theme(fig, dark)
    if height:
        fig.update_layout(height=height)
    # Format bar chart hover to 2 decimal places
    for trace in fig.data:
        if trace.type == 'bar':
            if getattr(trace, 'orientation', 'v') == 'h':
                trace.hovertemplate = '%{y}<br>%{x:,.2f}<extra></extra>'
            else:
                trace.hovertemplate = '%{x}<br>%{y:,.2f}<extra></extra>'
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

# Custom CSS - applied dynamically based on dark mode
def inject_css(dark_mode=False):
    bg = "#0e1117" if dark_mode else "#ffffff"
    card_bg = "#1e2130" if dark_mode else "#f8f9fa"
    text = "#fafafa" if dark_mode else "#31333f"
    border = "rgba(102, 126, 234, 0.3)" if dark_mode else "rgba(102, 126, 234, 0.2)"
    # Dark mode: override Streamlit's main containers (target .stApp root for full coverage)
    dark_overrides = ""
    if dark_mode:
        dark_overrides = """
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] main, [data-testid="stAppViewContainer"] .block-container {
        background-color: #0e1117 !important;
    }
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
        background-color: #0e1117 !important;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp span, .stApp label, .stApp .stMarkdown, .stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"] {
        color: #fafafa !important;
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] .stCaption {
        color: #fafafa !important;
    }
    .stApp [data-testid="stMetric"] {
        background-color: #1e2130 !important;
        border-color: rgba(102, 126, 234, 0.3) !important;
    }
    .stApp .stTabs [data-baseweb="tab"][aria-selected="false"], .stApp .stTabs [role="tab"][aria-selected="false"] {
        background: #1e2130 !important;
        color: #fafafa !important;
    }
    .stApp .stTabs [data-baseweb="tab"][aria-selected="false"]:hover, .stApp .stTabs [role="tab"][aria-selected="false"]:hover {
        background: #2d3142 !important;
    }
    .stApp .stExpander {
        background-color: #1e2130 !important;
        border-color: rgba(102, 126, 234, 0.3) !important;
    }
    .stApp .stDataFrame, .stApp [data-testid="stDataFrame"] {
        background-color: #1e2130 !important;
    }
    .stApp .stCaption {
        color: #b0b0b0 !important;
    }
    .stApp {
        color-scheme: dark;
    }
    """
    st.markdown(f"""
    <style>
    :root {{
        --bg: {bg};
        --card-bg: {card_bg};
        --text: {text};
        --border: {border};
    }}
    {dark_overrides}
    .main-header {{
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #667eea;
        margin-bottom: 0.5rem;
    }}
    .filter-summary {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 10px 16px;
        margin-bottom: 1.5rem;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
        border-radius: 10px;
        border: 1px solid {border};
        font-size: 0.9rem;
    }}
    .filter-badge {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 500;
    }}
    .metric-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.25);
        border: 1px solid rgba(255,255,255,0.1);
    }}
    .metric-card-wrapper {{
        padding: 0.5rem;
        background: var(--card-bg);
        border-radius: 12px;
        border: 1px solid var(--border);
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        margin-bottom: 0.5rem;
    }}
    [data-testid="stSidebar"] > div:first-child {{
        position: sticky;
        top: 0;
        max-height: 100vh;
        overflow-y: auto;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 10px;
        padding: 0.75rem 0;
    }}
    .stTabs [data-baseweb="tab"],
    .stTabs [role="tab"] {{
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        padding: 0.85rem 1.75rem !important;
        border-radius: 10px;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"],
    .stTabs [role="tab"][aria-selected="true"] {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="false"],
    .stTabs [role="tab"][aria-selected="false"] {{
        background: #f0f2f6 !important;
        color: #31333f !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="false"]:hover,
    .stTabs [role="tab"][aria-selected="false"]:hover {{
        background: #e0e4eb !important;
    }}
    .empty-state {{
        text-align: center;
        padding: 3rem 2rem;
        background: var(--card-bg);
        border-radius: 12px;
        border: 2px dashed var(--border);
        color: var(--text);
        margin: 2rem 0;
    }}
    .empty-state-icon {{
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.6;
    }}
    [data-testid="stMetric"] {{
        background: var(--card-bg);
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }}
    </style>
    """, unsafe_allow_html=True)

def _compute_employee_performance_from_sales(sales_df):
    """
    Compute employee performance metrics from sales transaction data.
    Uses Commission_Employee (who gets commission) for attribution, not who processed.
    """
    if sales_df is None or len(sales_df) == 0:
        return None
    # Use Commission_Employee if available (from expanded/by-commission view)
    emp_col = 'Commission_Employee' if 'Commission_Employee' in sales_df.columns else 'Employee'
    if emp_col not in sales_df.columns:
        return None
    weight_col = 'Transaction_Weight' if 'Transaction_Weight' in sales_df.columns else None
    if weight_col:
        agg = sales_df.groupby(emp_col).agg(
            Net_Sales_Sum=('Net_Sales', 'sum'),
            Gross_Sales_Sum=('Gross_Sales', 'sum'),
            Refunds_Sum=('Refunds', 'sum'),
            Transaction_Count=(weight_col, 'sum'),
        ).reset_index()
    else:
        agg = sales_df.groupby(emp_col).agg(
            Net_Sales_Sum=('Net_Sales', 'sum'),
            Gross_Sales_Sum=('Gross_Sales', 'sum'),
            Refunds_Sum=('Refunds', 'sum'),
            Transaction_Count=('Net_Sales', 'count'),
        ).reset_index()
    agg['Net_Sales_Mean'] = np.where(agg['Transaction_Count'] > 0, agg['Net_Sales_Sum'] / agg['Transaction_Count'], 0)
    agg['Refunds_Sum'] = agg['Refunds_Sum'].abs()
    agg['Refund_Rate'] = np.where(
        agg['Gross_Sales_Sum'] > 0,
        agg['Refunds_Sum'] / agg['Gross_Sales_Sum'] * 100,
        0
    )
    agg = agg.rename(columns={emp_col: 'Employee'})
    return agg[agg['Employee'].notna() & (agg['Employee'].astype(str) != '')]


def _compute_day_of_week_from_sales(sales_df):
    """Compute day-of-week analysis from sales transaction data."""
    if sales_df is None or len(sales_df) == 0 or 'Date' not in sales_df.columns:
        return None
    df = sales_df.copy()
    if 'Day of the Week' not in df.columns or df['Day of the Week'].isna().all():
        df['Day of the Week'] = pd.to_datetime(df['Date'], errors='coerce').dt.day_name()
    valid = df[df['Day of the Week'].notna()]
    if len(valid) == 0:
        return None
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    agg = valid.groupby('Day of the Week')['Net_Sales'].agg(['sum', 'mean', 'count', 'std']).reset_index()
    agg.columns = ['Day', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Net_Sales_Std']
    gross = valid.groupby('Day of the Week')['Gross_Sales'].sum().reset_index()
    gross.columns = ['Day', 'Gross_Sales_Sum']
    agg = agg.merge(gross, on='Day', how='left')
    agg['Gross_Sales_Sum'] = agg['Gross_Sales_Sum'].fillna(0)
    for d in day_order:
        if d not in agg['Day'].values:
            agg = pd.concat([agg, pd.DataFrame([{'Day': d, 'Net_Sales_Sum': 0, 'Net_Sales_Mean': 0, 'Transaction_Count': 0, 'Net_Sales_Std': 0, 'Gross_Sales_Sum': 0}])], ignore_index=True)
    agg = agg.set_index('Day').reindex(day_order).reset_index()
    return agg


def _compute_hourly_from_sales(sales_df):
    """Compute hourly patterns from sales transaction data."""
    if sales_df is None or len(sales_df) == 0 or 'Hour' not in sales_df.columns:
        return None
    valid = sales_df[sales_df['Hour'].notna()].copy()
    valid['Hour'] = pd.to_numeric(valid['Hour'], errors='coerce')
    valid = valid[valid['Hour'].notna() & (valid['Hour'] >= 0) & (valid['Hour'] <= 23)]
    if len(valid) == 0:
        return None
    agg = valid.groupby('Hour')['Net_Sales'].agg(['sum', 'mean', 'count']).reset_index()
    agg.columns = ['Hour', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count']
    gross = valid.groupby('Hour')['Gross_Sales'].sum().reset_index()
    gross.columns = ['Hour', 'Gross_Sales_Sum']
    agg = agg.merge(gross, on='Hour', how='left')
    agg['Gross_Sales_Sum'] = agg['Gross_Sales_Sum'].fillna(0)
    return agg.sort_values('Hour')


def _compute_product_from_sales(sales_df):
    """Compute product patterns from sales transaction data (parses Products column)."""
    if sales_df is None or len(sales_df) == 0 or 'Products' not in sales_df.columns:
        return None
    product_sales = {}
    product_count = {}
    for _, row in sales_df.iterrows():
        products = row.get('Products')
        if pd.notna(products) and isinstance(products, str):
            for item in [i.strip() for i in products.split(',') if i.strip()]:
                if item.startswith('-') or 'x-' in item:
                    continue
                if 'x' in item:
                    m = re.match(r'^(.+?)\s+(\d+)x([\d.,£]+)$', item)
                    if m:
                        name, qty, price_str = m.group(1).strip(), int(m.group(2)), m.group(3)
                        price_match = re.search(r'(\d+\.?\d*)', price_str.replace('£', '').replace(',', ''))
                        if not price_match:
                            continue
                        price = float(price_match.group(1))
                        if 0 < price <= 50000 and name:
                            product_sales[name] = product_sales.get(name, 0) + price
                            product_count[name] = product_count.get(name, 0) + qty
    if not product_sales:
        return None
    rows = [{'Product': p, 'Total_Sales': product_sales[p], 'Count': product_count.get(p, 0),
             'Avg_Sale': product_sales[p] / product_count.get(p, 1) if product_count.get(p, 0) else 0}
            for p in product_sales]
    df = pd.DataFrame(rows)
    df = df[df['Total_Sales'] > 0].sort_values('Total_Sales', ascending=False)
    return df.reset_index(drop=True)


def _parse_commission_recipients(comm_str):
    """
    Parse Commission column (format: 'Name1: amt1, Name2: amt2') into list of (name, amount).
    Returns list of (normalized_name, commission_amount). Uses Employee as fallback when empty.
    """
    if not comm_str or not str(comm_str).strip() or str(comm_str).strip().lower() in ('nan', 'none', ''):
        return []
    parts = []
    for segment in str(comm_str).split(','):
        segment = segment.strip()
        if ':' in segment:
            name = segment.split(':', 1)[0].strip()
            rest = segment.split(':', 1)[1].strip()
            amt = _clean_currency(rest)
            if name:
                parts.append((normalize_employee_name(name), amt))
    return parts


def _expand_sales_by_commission(df):
    """
    Expand sales rows by commission recipients for correct attribution.
    Sales/refunds are attributed to whoever receives commission, not who processed the transaction.
    When Commission has multiple recipients, amounts are split proportionally by commission.
    When Commission is empty, falls back to Employee (who processed).
    Returns df with Commission_Employee, proportional Net_Sales/Gross_Sales/Refunds, Transaction_Weight.
    """
    if df is None or len(df) == 0:
        return df
    comm_col = next((c for c in df.columns if str(c).strip().lower() in ('commissions', 'commission')), None)
    if comm_col is None and 'Employee' not in df.columns:
        return df
    emp_col = 'Employee' if 'Employee' in df.columns else None

    rows = []
    for idx, row in df.iterrows():
        comm_str = row[comm_col] if comm_col and pd.notna(row.get(comm_col)) else ''
        recipients = _parse_commission_recipients(comm_str)
        emp_fallback = row[emp_col] if emp_col and pd.notna(row.get(emp_col)) and str(row.get(emp_col)).strip() else None

        if not recipients:
            # No commission data: attribute to Employee (who processed)
            if emp_fallback and str(emp_fallback).strip() not in ('', 'nan'):
                att_emp = normalize_employee_name(str(emp_fallback).strip())
                new_row = row.to_dict()
                new_row['Commission_Employee'] = att_emp
                new_row['Transaction_Weight'] = 1.0
                rows.append(new_row)
            else:
                # No employee either - keep row with null Commission_Employee
                new_row = row.to_dict()
                new_row['Commission_Employee'] = pd.NA
                new_row['Transaction_Weight'] = 1.0
                rows.append(new_row)
            continue

        # Split proportionally by commission amount
        total_comm = sum(amt for _, amt in recipients)
        if total_comm <= 0:
            # Equal split when no valid commission amounts
            n = len(recipients)
            shares = [1.0 / n] * n
        else:
            shares = [amt / total_comm for _, amt in recipients]

        net = row.get('Net_Sales', 0) or 0
        gross = row.get('Gross_Sales', 0) or net
        refund = row.get('Refunds', 0) or 0

        for i, (name, _) in enumerate(recipients):
            share = shares[i] if i < len(shares) else 0
            new_row = row.to_dict()
            new_row['Commission_Employee'] = name
            new_row['Net_Sales'] = net * share
            new_row['Gross_Sales'] = gross * share
            new_row['Refunds'] = refund * share
            new_row['Transaction_Weight'] = share
            rows.append(new_row)

    out = pd.DataFrame(rows)
    # Preserve dtypes for key columns
    for c in ['Date', 'Hour', 'Shop', 'Products', 'Transaction']:
        if c in df.columns and c in out.columns:
            out[c] = out[c]
    return out


def _count_items_per_transaction(products_str):
    """Count line items from Products string (e.g. 'Prod A 1x10, Prod B 2x5' -> 3)."""
    if pd.isna(products_str) or not isinstance(products_str, str):
        return 0
    count = 0
    for item in [i.strip() for i in products_str.split(',') if i.strip()]:
        if item.startswith('-') or 'x-' in item:
            continue
        if 'x' in item:
            m = re.match(r'^.+?\s+(\d+)x', item)
            if m:
                count += int(m.group(1))
    return count


@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_employee_data():
    """Load employee performance data from file (if it exists)."""
    for base in [Path(__file__).resolve().parent, Path.cwd()]:
        path = base / 'employee_performance_analysis.csv'
        if path.exists():
            try:
                df = pd.read_csv(path, skiprows=2)
                df.columns = ['Employee', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count',
                             'Gross_Sales_Sum', 'Refunds_Sum', 'Refund_Rate']
                df = df[df['Employee'].notna() & (df['Employee'] != '')]
                for col in ['Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Gross_Sales_Sum', 'Refunds_Sum', 'Refund_Rate']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                return df
            except Exception as e:
                st.warning(f"Could not load employee_performance_analysis.csv: {e}")
                break
    return None

def _clean_currency(value):
    """Clean currency values to float"""
    if pd.isna(value):
        return 0
    if isinstance(value, str):
        cleaned = re.sub(r'[^\d.-]', '', value.strip())
        if cleaned == '' or cleaned == '-':
            return 0
        try:
            return float(cleaned)
        except ValueError:
            return 0
    try:
        return float(value) if value else 0
    except (ValueError, TypeError):
        return 0


def _normalize_supabase_columns(df):
    """Map Supabase column names to expected format (handles case variations from CSV import)"""
    # Strip BOM and whitespace from column names
    df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]
    column_map = {}
    for col in df.columns:
        c = str(col).strip().lower()
        if c in ('trans #', 'trans_num', 'transaction'):
            column_map[col] = 'Transaction'
        elif c in ('day of the week', 'day_of_the_week'):
            column_map[col] = 'Day of the Week'
        elif c == 'employee':
            column_map[col] = 'Employee'
        elif c == 'date':
            column_map[col] = 'Date'
        elif c in ('net sales', 'net_sales'):
            column_map[col] = 'Net Sales'
        elif c in ('gross sales', 'gross_sales'):
            column_map[col] = 'Gross Sales'
        elif c == 'refunds':
            column_map[col] = 'Refunds'
        elif c.replace(' ', '_') in ('time', 'timestamp', 'created_at', 'transaction_time', 'trans_time', 'created'):
            column_map[col] = 'Time'
        elif c == 'products':
            column_map[col] = 'Products'
        elif c in ('commissions', 'commission'):
            column_map[col] = 'Commissions'
    if column_map:
        df = df.rename(columns=column_map)
    return df


def _process_sales_df(df):
    """Apply common processing to sales dataframe (from Supabase or CSV)"""
    df = _normalize_supabase_columns(df)
    def _col_matches(col, *names):
        c = str(col).strip().lower()
        return c in names or c.replace(' ', '_') in names or c.replace('_', ' ') in names
    net_col = next((c for c in df.columns if _col_matches(c, 'net sales', 'net_sales')), None)
    gross_col = next((c for c in df.columns if _col_matches(c, 'gross sales', 'gross_sales')), None)
    refund_col = next((c for c in df.columns if _col_matches(c, 'refunds')), None)
    date_col = next((c for c in df.columns if _col_matches(c, 'date')), None)
    if not net_col or not date_col:
        return None
    df['Net_Sales'] = df[net_col].apply(_clean_currency)
    df['Gross_Sales'] = df[gross_col].apply(_clean_currency) if gross_col else df['Net_Sales']
    df['Refunds'] = df[refund_col].apply(_clean_currency) if refund_col else 0
    # Parse dates: try DD/MM/YYYY first, then ISO (YYYY-MM-DD) - keep original for fallback
    date_series = df[date_col].copy()
    df['Date'] = pd.to_datetime(date_series, format='%d/%m/%Y', errors='coerce')
    if df['Date'].isna().any():
        df['Date'] = pd.to_datetime(date_series, errors='coerce')  # fallback uses original values
    df = df[df['Date'].notna()]
    df = df[(df['Net_Sales'] > 0) | (df['Refunds'] != 0)]
    emp_col = next((c for c in df.columns if str(c).lower() == 'employee'), None)
    if emp_col:
        df['Employee'] = df[emp_col].astype(str).str.strip()
        df['Employee'] = df['Employee'].replace(['', 'nan', 'NaN', 'None'], pd.NA)
        df['Employee'] = df['Employee'].apply(normalize_employee_name)
    def _is_time_col(col):
        c = str(col).strip().lower().replace(' ', '_')
        if c in ('time', 'timestamp', 'created_at', 'transaction_time', 'trans_time', 'created'):
            return True
        # Fuzzy: column contains 'time' or 'timestamp' (e.g. "Transaction Time", "created_at")
        if 'timestamp' in c or (c.endswith('_time') or c.endswith('time')) and 'day' not in c and 'week' not in c:
            return True
        return False
    time_col = next((c for c in df.columns if _is_time_col(c)), None)
    if time_col:
        # Handle numeric Unix timestamps (Supabase/PostgreSQL may return these)
        time_vals = df[time_col].copy()
        if np.issubdtype(time_vals.dtype, np.number):
            time_vals = pd.to_datetime(time_vals, unit='s', errors='coerce')
        else:
            time_vals = pd.to_datetime(time_vals, errors='coerce')
        df['Time_Parsed'] = time_vals
        # Supabase may return Python datetime objects (dtype object) - ensure we can extract hour
        def _extract_hour(val):
            if pd.isna(val):
                return np.nan
            if hasattr(val, 'hour'):
                return val.hour
            s = str(val).strip()
            # ISO datetime: 2021-08-24T17:21:21.000+01:00
            m = re.search(r'T(\d{1,2}):', s)
            if m:
                return int(m.group(1))
            # Time-only: 17:21:21 or 09:53:04
            m = re.match(r'(\d{1,2}):\d{2}', s)
            if m:
                return int(m.group(1))
            return np.nan
        hours = df[time_col].apply(_extract_hour)
        if hours.notna().any():
            df['Hour'] = hours
        elif pd.api.types.is_datetime64_any_dtype(df['Time_Parsed']) and df['Time_Parsed'].notna().any():
            df['Hour'] = df['Time_Parsed'].dt.hour
        else:
            df['Hour'] = np.nan
    # Fallback: extract hour from Date if Date has time component (e.g. full datetime string)
    if 'Hour' not in df.columns or (df['Hour'].isna().all() if 'Hour' in df.columns else False):
        date_parsed = pd.to_datetime(df['Date'], errors='coerce')
        if pd.api.types.is_datetime64_any_dtype(date_parsed) and date_parsed.notna().any():
            has_time = date_parsed.dt.hour.notna() & (date_parsed.dt.hour != 0)
            if has_time.any():
                df['Hour'] = date_parsed.dt.hour
            elif 'Hour' not in df.columns:
                df['Hour'] = np.nan
        elif 'Hour' not in df.columns:
            df['Hour'] = np.nan
    # Ensure Date is datetime before using .dt accessor
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    if 'Day of the Week' not in df.columns or df['Day of the Week'].isna().all():
        if 'Date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Date']) and df['Date'].notna().any():
            df['Day of the Week'] = df['Date'].dt.day_name()
    if 'Day of the Week' in df.columns:
        df['Day_of_Week'] = df['Day of the Week']
    products_col = next((c for c in df.columns if str(c).lower() == 'products'), None)
    if products_col and products_col != 'Products':
        df['Products'] = df[products_col]
    return df


def _load_from_csv():
    """Fallback: load from local CSV files when Supabase fails"""
    # Try script dir first, then cwd (Streamlit may run from different path)
    search_dirs = [Path(__file__).resolve().parent, Path.cwd()]
    csv_files = [
        ("PYT Sales Data_rows.csv", "PYT"),
        ("Opatra Sales Data_rows.csv", "Opatra"),
    ]
    for base in search_dirs:
        all_dfs = []
        for fname, shop in csv_files:
            path = base / fname
            if path.exists():
                try:
                    df = pd.read_csv(path)
                    df["Shop"] = shop
                    all_dfs.append(df)
                except Exception:
                    pass
        if all_dfs:
            return all_dfs
    return []


@st.cache_data(ttl=300)  # 5 min cache - use Refresh Data to force reload
def load_sales_data():
    """Load sales transaction data from Supabase, with CSV fallback. Returns (df, source) or (None, None)."""
    try:
        all_dfs = []
        data_source = None  # 'Supabase' or 'Local CSV'
        # Try Supabase first if configured
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                from supabase import create_client
                supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                table_configs = [
                    (SUPABASE_TABLE_PYT, 'PYT'),
                    (SUPABASE_TABLE_OPATRA, 'Opatra'),
                ]
                page_size = 1000
                for table_name, shop in table_configs:
                    try:
                        all_rows = []
                        offset = 0
                        while True:
                            response = supabase.table(table_name).select('*').range(offset, offset + page_size - 1).execute()
                            if not response.data:
                                break
                            all_rows.extend(response.data)
                            if len(response.data) < page_size:
                                break
                            offset += page_size
                        if all_rows:
                            df = pd.DataFrame(all_rows)
                            df['Shop'] = shop
                            all_dfs.append(df)
                    except Exception as e:
                        st.warning(f"Supabase {table_name}: {e}")
                if all_dfs:
                    data_source = "Supabase"
            except Exception as e:
                st.warning(f"Supabase connection failed: {e}")

        # Fallback to local CSV if Supabase returned nothing
        if not all_dfs:
            all_dfs = _load_from_csv()
            if all_dfs:
                data_source = "Local CSV"
                st.info("📁 Loaded from local CSV files (Supabase unavailable or empty).")

        if not all_dfs:
            st.error("No sales data loaded. Add SUPABASE_URL/KEY in .env or place PYT Sales Data_rows.csv and Opatra Sales Data_rows.csv in the project folder.")
            return None, None

        df = pd.concat(all_dfs, ignore_index=True)
        df = _process_sales_df(df)
        if df is None or len(df) == 0:
            # Try CSV fallback if Supabase data failed to process
            csv_dfs = _load_from_csv()
            if csv_dfs:
                df = pd.concat(csv_dfs, ignore_index=True)
                df = _process_sales_df(df)
                if df is not None and len(df) > 0:
                    data_source = "Local CSV"
                    st.info("📁 Using local CSV files (Supabase data had format issues).")
        if df is None or len(df) == 0:
            st.error("Data loaded but missing required columns (Net Sales, Date) or all rows filtered out.")
            with st.expander("Debug: columns received"):
                raw = pd.concat(all_dfs, ignore_index=True)
                st.write("Columns:", list(raw.columns))
                st.write("Row count:", len(raw))
                if len(raw) > 0:
                    row = raw.iloc[0]
                    date_val = next((row[c] for c in raw.columns if str(c).lower() == 'date'), 'N/A')
                    net_val = next((row[c] for c in raw.columns if 'net' in str(c).lower() and 'sales' in str(c).lower()), 'N/A')
                    st.write("Sample Date:", date_val)
                    st.write("Sample Net Sales:", net_val)
            return None, None
        return df, data_source or "Supabase"  # default to Supabase if we got data from it
    except Exception as e:
        st.error(f"Error loading sales data: {e}")
        return None, None

@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_day_of_week_analysis():
    """Load day of week analysis from file (if it exists)."""
    for base in [Path(__file__).resolve().parent, Path.cwd()]:
        path = base / 'day_of_week_analysis.csv'
        if path.exists():
            try:
                df = pd.read_csv(path, skiprows=2)
                df.columns = ['Day', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Net_Sales_Std', 'Gross_Sales_Sum']
                df = df[df['Day'].notna() & (df['Day'] != '')]
                for col in ['Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Net_Sales_Std', 'Gross_Sales_Sum']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                return df
            except Exception:
                break
    return None

@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_hourly_analysis():
    """Load hourly patterns analysis from file (if it exists)."""
    for base in [Path(__file__).resolve().parent, Path.cwd()]:
        path = base / 'hourly_patterns_analysis.csv'
        if path.exists():
            try:
                df = pd.read_csv(path, skiprows=2)
                df.columns = ['Hour', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Gross_Sales_Sum']
                df = df[df['Hour'].notna()]
                df['Hour'] = pd.to_numeric(df['Hour'], errors='coerce')
                for col in ['Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Gross_Sales_Sum']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                return df
            except Exception:
                break
    return None

@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_product_analysis():
    """Load product patterns analysis from file (if it exists)."""
    for base in [Path(__file__).resolve().parent, Path.cwd()]:
        path = base / 'product_patterns_analysis.csv'
        if path.exists():
            try:
                df = pd.read_csv(path, skiprows=1)
                df.columns = ['Index', 'Product', 'Total_Sales', 'Count', 'Avg_Sale']
                df = df[df['Product'].notna() & (df['Product'] != '')]
                for col in ['Total_Sales', 'Count', 'Avg_Sale']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df = df[df['Total_Sales'] > 0]
                return df
            except Exception:
                break
    return None

def forecast_sales(sales_df, periods=30, method='moving_avg'):
    """Improved forecast using multiple methods"""
    if len(sales_df) < 7:  # Need at least a week of data
        return None
    
    # Group by date
    daily_sales = sales_df.groupby(sales_df['Date'].dt.date)['Net_Sales'].sum().reset_index()
    daily_sales['Date'] = pd.to_datetime(daily_sales['Date'])
    daily_sales = daily_sales.sort_values('Date')
    daily_sales['DayOfWeek'] = daily_sales['Date'].dt.dayofweek
    
    # Generate future dates
    last_date = daily_sales['Date'].max()
    future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=periods, freq='D')
    future_days_of_week = [d.dayofweek for d in future_dates]
    
    if method == 'moving_avg':
        # Method 1: Moving Average with Day-of-Week Seasonality
        # Use recent average (last 30 days) adjusted by day-of-week patterns
        recent_days = min(30, len(daily_sales))
        recent_avg = daily_sales['Net_Sales'].tail(recent_days).mean()
        
        # Calculate day-of-week multipliers
        day_multipliers = {}
        for day in range(7):
            day_sales = daily_sales[daily_sales['DayOfWeek'] == day]['Net_Sales']
            if len(day_sales) > 0:
                day_multipliers[day] = day_sales.mean() / daily_sales['Net_Sales'].mean()
            else:
                day_multipliers[day] = 1.0
        
        # Calculate recent growth trend (last 30 days vs previous 30 days)
        if len(daily_sales) >= 60:
            recent_30 = daily_sales['Net_Sales'].tail(30).mean()
            previous_30 = daily_sales['Net_Sales'].tail(60).head(30).mean()
            growth_rate = (recent_30 - previous_30) / previous_30 if previous_30 > 0 else 0
            # Cap growth rate to realistic levels (±20% per month)
            growth_rate = np.clip(growth_rate, -0.2, 0.2)
        else:
            growth_rate = 0
        
        # Forecast: base on recent average, adjusted for day-of-week, with gradual trend
        forecast_values = []
        for i, day_of_week in enumerate(future_days_of_week):
            # Apply day-of-week multiplier
            base_forecast = recent_avg * day_multipliers.get(day_of_week, 1.0)
            # Apply gradual growth trend (diminishing over time)
            trend_factor = 1 + (growth_rate * (i / periods) * 0.3)  # Diminishing trend
            forecast_values.append(max(0, base_forecast * trend_factor))
        
        forecast_df = pd.DataFrame({
            'Date': future_dates,
            'Forecast': forecast_values
        })
        
        return forecast_df, recent_avg, growth_rate, 'Moving Average with Seasonality'
    
    elif method == 'exponential_smoothing':
        # Method 2: Exponential Smoothing (weight recent data more)
        alpha = 0.3  # Smoothing parameter
        recent_days = min(30, len(daily_sales))
        recent_data = daily_sales['Net_Sales'].tail(recent_days).values
        
        # Calculate exponentially weighted average
        weights = np.exp(np.linspace(-1, 0, len(recent_data)))
        weights = weights / weights.sum()
        base_forecast = np.sum(recent_data * weights)
        
        # Day-of-week adjustments
        day_multipliers = {}
        for day in range(7):
            day_sales = daily_sales[daily_sales['DayOfWeek'] == day]['Net_Sales']
            if len(day_sales) > 0:
                day_multipliers[day] = day_sales.mean() / daily_sales['Net_Sales'].mean()
            else:
                day_multipliers[day] = 1.0
        
        forecast_values = [max(0, base_forecast * day_multipliers.get(dow, 1.0)) 
                          for dow in future_days_of_week]
        
        forecast_df = pd.DataFrame({
            'Date': future_dates,
            'Forecast': forecast_values
        })
        
        return forecast_df, base_forecast, 0, 'Exponential Smoothing'
    
    else:  # 'conservative'
        # Method 3: Conservative - Use recent average with day-of-week only
        recent_days = min(30, len(daily_sales))
        recent_avg = daily_sales['Net_Sales'].tail(recent_days).mean()
        
        # Day-of-week multipliers
        day_multipliers = {}
        for day in range(7):
            day_sales = daily_sales[daily_sales['DayOfWeek'] == day]['Net_Sales']
            if len(day_sales) > 0:
                day_multipliers[day] = day_sales.mean() / daily_sales['Net_Sales'].mean()
            else:
                day_multipliers[day] = 1.0
        
        forecast_values = [max(0, recent_avg * day_multipliers.get(dow, 1.0)) 
                          for dow in future_days_of_week]
        
        forecast_df = pd.DataFrame({
            'Date': future_dates,
            'Forecast': forecast_values
        })
        
        return forecast_df, recent_avg, 0, 'Conservative (Recent Average)'

def forecast_monthly(sales_df, months=6, method='moving_avg'):
    """Improved monthly forecast"""
    monthly_sales = sales_df.groupby(sales_df['Date'].dt.to_period('M'))['Net_Sales'].sum()
    monthly_sales.index = pd.to_datetime(monthly_sales.index.astype(str))
    monthly_sales = monthly_sales.sort_index()
    
    if len(monthly_sales) < 3:
        return None
    
    last_month = monthly_sales.index[-1]
    future_months = pd.date_range(start=last_month + pd.DateOffset(months=1), periods=months, freq='MS')
    
    if method == 'moving_avg':
        # Use recent average (last 3-6 months) with growth trend
        recent_months = min(6, len(monthly_sales))
        recent_avg = monthly_sales.tail(recent_months).mean()
        
        # Calculate growth trend from last 3 months vs previous 3 months
        if len(monthly_sales) >= 6:
            recent_3 = monthly_sales.tail(3).mean()
            previous_3 = monthly_sales.tail(6).head(3).mean()
            growth_rate = (recent_3 - previous_3) / previous_3 if previous_3 > 0 else 0
            # Cap monthly growth to ±10%
            growth_rate = np.clip(growth_rate, -0.1, 0.1)
        else:
            growth_rate = 0
        
        # Forecast with diminishing trend
        forecast_values = []
        for i in range(months):
            trend_factor = 1 + (growth_rate * (i / months) * 0.5)  # Diminishing trend
            forecast_values.append(max(0, recent_avg * trend_factor))
        
        forecast_df = pd.DataFrame({
            'Month': future_months,
            'Forecast': forecast_values
        })
        
        return forecast_df, recent_avg, growth_rate, 'Moving Average'
    
    elif method == 'exponential_smoothing':
        # Method: Exponential Smoothing (weight recent months more)
        alpha = 0.3  # Smoothing parameter
        recent_months = min(6, len(monthly_sales))
        recent_data = monthly_sales.tail(recent_months).values
        
        # Calculate exponentially weighted average
        weights = np.exp(np.linspace(-1, 0, len(recent_data)))
        weights = weights / weights.sum()
        base_forecast = np.sum(recent_data * weights)
        
        # Calculate growth trend from recent weighted data
        if len(monthly_sales) >= 6:
            # Compare last 3 months (weighted) vs previous 3 months
            recent_3_weighted = np.sum(monthly_sales.tail(3).values * np.exp(np.linspace(-1, 0, 3)) / np.sum(np.exp(np.linspace(-1, 0, 3))))
            previous_3 = monthly_sales.tail(6).head(3).mean()
            growth_rate = (recent_3_weighted - previous_3) / previous_3 if previous_3 > 0 else 0
            # Cap monthly growth to ±10%
            growth_rate = np.clip(growth_rate, -0.1, 0.1)
        else:
            growth_rate = 0
        
        # Forecast with diminishing trend
        forecast_values = []
        for i in range(months):
            trend_factor = 1 + (growth_rate * (i / months) * 0.5)  # Diminishing trend
            forecast_values.append(max(0, base_forecast * trend_factor))
        
        forecast_df = pd.DataFrame({
            'Month': future_months,
            'Forecast': forecast_values
        })
        
        return forecast_df, base_forecast, growth_rate, 'Exponential Smoothing'
    
    else:  # 'conservative'
        # Conservative: just use recent average
        recent_months = min(6, len(monthly_sales))
        recent_avg = monthly_sales.tail(recent_months).mean()
        
        forecast_values = [max(0, recent_avg) for _ in range(months)]
        
        forecast_df = pd.DataFrame({
            'Month': future_months,
            'Forecast': forecast_values
        })
        
        return forecast_df, recent_avg, 0, 'Conservative'

def main():
    # Session state for UI preferences
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = False
    if "tab_index" not in st.session_state:
        st.session_state.tab_index = 0

    dark_mode = st.session_state.dark_mode
    inject_css(dark_mode)

    st.markdown('<div class="main-header">📊 Complete Sales Analytics Dashboard</div>', unsafe_allow_html=True)

    # Load all data with loading spinner
    with st.spinner("Loading sales data..."):
        sales_df, data_source = load_sales_data()
        employee_df = load_employee_data()
        if employee_df is None and sales_df is not None:
            employee_df = _compute_employee_performance_from_sales(sales_df)
        day_of_week_df = load_day_of_week_analysis()
        if day_of_week_df is None and sales_df is not None:
            day_of_week_df = _compute_day_of_week_from_sales(sales_df)
        hourly_df = load_hourly_analysis()
        if hourly_df is None and sales_df is not None:
            hourly_df = _compute_hourly_from_sales(sales_df)
        product_df = load_product_analysis()
        if product_df is None and sales_df is not None:
            product_df = _compute_product_from_sales(sales_df)

    if sales_df is None:
        st.error("Could not load sales data. Check Supabase credentials in .env, or ensure PYT Sales Data_rows.csv and Opatra Sales Data_rows.csv are in the project folder.")
        return
    
    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    st.session_state.dark_mode = st.sidebar.toggle(
        "🌙 Dark mode",
        value=st.session_state.dark_mode,
        help="Switch between light and dark theme for the dashboard"
    )

    # Shop filter
    if 'Shop' in sales_df.columns:
        unique_shops = sorted(sales_df['Shop'].dropna().unique().tolist())
        all_shops = ['All Shops'] + unique_shops
        selected_shop = st.sidebar.selectbox("Select Shop", all_shops, help="Filter by shop (PYT, Opatra, etc.)")
    else:
        selected_shop = 'All Shops'
    
    # Refresh data button
    if st.sidebar.button("🔄 Refresh Data", help="Click to reload data from Supabase"):
        st.cache_data.clear()
        st.success("✅ Cache cleared! Reloading data...")
        st.rerun()
    
    # Data source indicator
    if data_source:
        if data_source == "Supabase":
            st.sidebar.caption("☁️ **Data source:** Supabase — Employee, Commission, Refunds presented by attribution")
        else:
            st.sidebar.caption("📁 **Data source:** Local CSV files")
    
    # Debug section for data/columns (helps diagnose missing employees)
    with st.sidebar.expander("🔍 Debug: Data & Columns", expanded=False):
        if sales_df is not None and len(sales_df) > 0:
            st.write(f"**Total rows:** {len(sales_df):,}")
            st.write(f"**Columns from Supabase:** {list(sales_df.columns)}")
            if 'Employee' in sales_df.columns:
                emp_count = sales_df['Employee'].dropna().nunique()
                emp_sample = sales_df['Employee'].dropna().unique()[:10].tolist()
                st.write(f"**Unique employees:** {emp_count}")
                st.write(f"**Sample employees:** {emp_sample}")
                # Show potential duplicates (similar names that may need mapping)
                similar = find_similar_employee_names(sales_df)
                if similar:
                    st.write("**⚠️ Potential duplicates** (add to EMPLOYEE_NAME_MAPPING in dashboard.py):")
                    for norm, names in list(similar.items())[:5]:
                        st.write(f"  `{names[0]}` ← map from: {names[1:]}")
            else:
                st.write("❌ **'Employee' column not found** — check your Supabase table has an 'Employee' column (or 'employee' after import)")
            if 'Refunds' in sales_df.columns:
                raw_refunds_sum = sales_df['Refunds'].sum()
                st.write(f"**Refunds sum:** {raw_refunds_sum:.2f}")
            comm_col = next((c for c in sales_df.columns if str(c).strip().lower() in ('commissions', 'commission')), None)
            if comm_col:
                sample = sales_df[comm_col].dropna().head(3).tolist()
                st.write(f"**Commission column:** {comm_col} | Sample: {sample}")
                st.caption("Attribution from Supabase: Commission = who gets credit; Employee = who processed. Refunds follow Commission.")
            time_cols = [c for c in sales_df.columns if 'time' in str(c).lower() or str(c).lower() in ('timestamp', 'created_at')]
            hour_ok = 'Hour' in sales_df.columns and sales_df['Hour'].notna().any()
            if time_cols:
                sample = sales_df[time_cols[0]].dropna().iloc[0] if sales_df[time_cols[0]].notna().any() else "N/A"
                st.write(f"**Time column:** {time_cols[0]} | Sample: `{sample}` | Hour parsed: {'✓' if hour_ok else '✗'}")
            else:
                st.write("**Time column:** Not found (hourly patterns need Time, timestamp, created_at, transaction_time)")
            if not hour_ok:
                st.caption("💡 Add a Time column to your Supabase table (e.g. `time`, `created_at`, `timestamp`) with values like `09:53:04` or `2023-07-14T09:53:04+00`. Or ensure your Date column includes full datetime.")
        else:
            st.write("❌ No sales data loaded")
    
    st.sidebar.caption("💡 **Tip:** Data loads directly from Supabase. Click 'Refresh Data' to see updates.")
    
    with st.sidebar.expander("👤 Mark employees active/inactive", expanded=True):
        st.caption("Go to the **Employee Status** tab in the main area to mark employees as active or inactive. Use the Status dropdown for each employee, then click **Save Employee Status**.")
    
    # Apply shop filter to get working dataset
    if selected_shop != 'All Shops' and 'Shop' in sales_df.columns:
        work_df = sales_df[sales_df['Shop'] == selected_shop].copy()
    else:
        work_df = sales_df.copy()

    # Expand by commission for correct attribution: sales/refunds go to who gets commission, not who processed
    work_df_orig = work_df.copy()  # Keep for day/hour/product (avoid double-counting)
    work_df_attributed = _expand_sales_by_commission(work_df)
    if work_df_attributed is not None and len(work_df_attributed) > 0:
        work_df = work_df_attributed

    # Recompute employee performance from commission-attributed data (who gets credit, not who processed)
    if len(work_df) > 0:
        employee_df = _compute_employee_performance_from_sales(work_df)
    # When a specific shop is selected, recompute day/hour/product from non-expanded data
    if selected_shop != 'All Shops' and len(work_df_orig) > 0:
        day_of_week_df = _compute_day_of_week_from_sales(work_df_orig)
        hourly_df = _compute_hourly_from_sales(work_df_orig)
        product_df = _compute_product_from_sales(work_df_orig)
    
    # Load employee active/inactive status
    employee_status = load_employee_status()
    
    # Get unique employees from Commission_Employee (who gets credit) when available, else Employee
    emp_col = 'Commission_Employee' if 'Commission_Employee' in work_df.columns else 'Employee'
    if emp_col in work_df.columns:
        unique_employees = work_df[emp_col].dropna().unique()
        unique_employees = [str(emp).strip() for emp in unique_employees if pd.notna(emp) and str(emp).strip() not in ['', 'nan', 'NaN', 'None']]
        unique_employees = sorted(list(set(unique_employees)))
    else:
        unique_employees = []
    # Separate active and inactive for display
    active_employees = [e for e in unique_employees if is_employee_active(e, employee_status)]
    inactive_employees = [e for e in unique_employees if not is_employee_active(e, employee_status)]
    
    # Employee filter: show active first, then inactive with label
    show_inactive_in_filter = st.sidebar.checkbox("Include inactive employees in filter", value=True, help="Uncheck to hide inactive employees from the Employee dropdown")
    if show_inactive_in_filter:
        emp_options = ['All'] + active_employees + [f"{e} (inactive)" for e in inactive_employees]
    else:
        emp_options = ['All'] + active_employees
    selected_employee_raw = st.sidebar.selectbox("Select Employee", emp_options, help="View analytics for a specific employee or All for combined view")
    # Normalize selection (strip "(inactive)" for filtering and display)
    selected_employee = selected_employee_raw.replace(" (inactive)", "").strip() if selected_employee_raw != 'All' else 'All'
    
    if work_df['Date'].notna().any():
        min_date = work_df['Date'].min().date()
        max_date = work_df['Date'].max().date()
        
        # Quick date range presets
        st.sidebar.subheader("📅 Date Range")
        use_preset = st.sidebar.radio(
            "Quick Select",
            ["All Time", "This Week", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Last Year", "YTD", "Custom Range"],
            index=0,
            help="Choose a preset range or select Custom for manual dates"
        )

        if use_preset == "All Time":
            start_date = min_date
            end_date = max_date
        elif use_preset == "This Week":
            # Monday of current week to today
            today = max_date
            start_of_week = today - timedelta(days=today.weekday())
            start_date = max(min_date, start_of_week)
            end_date = max_date
        elif use_preset == "Last 7 Days":
            end_date = max_date
            start_date = max_date - timedelta(days=7)
        elif use_preset == "Last 30 Days":
            end_date = max_date
            start_date = max_date - timedelta(days=30)
        elif use_preset == "Last 90 Days":
            end_date = max_date
            start_date = max_date - timedelta(days=90)
        elif use_preset == "Last Year":
            end_date = max_date
            start_date = max_date - timedelta(days=365)
        elif use_preset == "YTD":
            start_date = max(min_date, max_date.replace(month=1, day=1))
            end_date = max_date
        else:  # Custom Range
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_date = st.date_input(
                    "Start Date",
                    value=min_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="start_date"
                )
            with col2:
                end_date = st.date_input(
                    "End Date",
                    value=max_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="end_date"
                )
        
        # Ensure start_date <= end_date
        if start_date > end_date:
            st.sidebar.warning("⚠️ Start date must be before end date. Using all time range.")
            start_date = min_date
            end_date = max_date
        
        filtered_sales = work_df[
            (work_df['Date'].dt.date >= start_date) & 
            (work_df['Date'].dt.date <= end_date)
        ]
        
        # Display selected range
        st.sidebar.caption(f"📆 {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}")
    else:
        filtered_sales = work_df
        # Set default dates if no date data
        start_date = None
        end_date = None
    
    if selected_employee != 'All':
        # Filter by Commission_Employee (who gets credit) when available, else Employee (who processed)
        filter_col = 'Commission_Employee' if 'Commission_Employee' in filtered_sales.columns else 'Employee'
        if filter_col in filtered_sales.columns:
            # First try exact match (with stripped whitespace)
            employee_mask = filtered_sales[filter_col].astype(str).str.strip() == selected_employee.strip()
            # If no exact match, try case-insensitive
            if not employee_mask.any():
                employee_mask = filtered_sales[filter_col].astype(str).str.strip().str.lower() == selected_employee.strip().lower()
            filtered_sales = filtered_sales[employee_mask].copy()
            
            # Ensure Day of Week column is available in filtered data
            if 'Day of the Week' not in filtered_sales.columns and 'Date' in filtered_sales.columns:
                filtered_sales['Day of the Week'] = filtered_sales['Date'].dt.day_name()
            
            # Debug info if no data found
            if len(filtered_sales) == 0:
                # Check what we have before employee filtering
                check_col = 'Commission_Employee' if 'Commission_Employee' in work_df.columns else 'Employee'
                if start_date is not None and end_date is not None:
                    date_filtered = work_df[
                        (work_df['Date'].dt.date >= start_date) & 
                        (work_df['Date'].dt.date <= end_date)
                    ]
                    before_filter_count = len(date_filtered)
                    employees_in_range = date_filtered[check_col].dropna().unique() if check_col in date_filtered.columns else []
                else:
                    before_filter_count = len(work_df)
                    employees_in_range = work_df[check_col].dropna().unique() if check_col in work_df.columns else []
                # Check if employee exists at all
                all_employees = work_df[check_col].dropna().unique() if check_col in work_df.columns else []
                employee_exists = any(
                    str(emp).strip().lower() == selected_employee.strip().lower() 
                    for emp in all_employees
                )
                
                if employee_exists:
                    st.sidebar.warning(f"⚠️ '{selected_employee}' exists in data but has no transactions in the selected date range.")
                else:
                    st.sidebar.warning(f"⚠️ '{selected_employee}' not found in data. Check spelling or try a different employee.")
        else:
            st.error("Employee/Commission column not found in data!")
            filtered_sales = pd.DataFrame()  # Empty DataFrame
    
    # Employee-specific header
    if selected_employee != 'All':
        if len(filtered_sales) > 0:
            date_range_str = f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}" if start_date and end_date else "All dates"
            st.info(f"👤 **Viewing analytics for: {selected_employee}** | 📅 **Date Range:** {date_range_str} | 📊 **{len(filtered_sales):,} transactions**")
        else:
            date_range_str = f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}" if start_date and end_date else "All dates"
            st.warning(f"⚠️ **No data found for: {selected_employee}** | 📅 **Date Range:** {date_range_str}")
            # Show available employees for debugging
            with st.expander("🔍 Debug: Available Employees"):
                debug_emp_col = 'Commission_Employee' if 'Commission_Employee' in work_df.columns else 'Employee'
                all_employees_list = sorted(work_df[debug_emp_col].dropna().unique().tolist())
                st.write(f"**Total employees in data (by commission):** {len(all_employees_list)}")
                st.write("**First 20 employees:**")
                for emp in all_employees_list[:20]:
                    count = len(work_df[work_df[debug_emp_col] == emp])
                    st.write(f"- {emp} ({count} attributed rows)")
                if len(all_employees_list) > 20:
                    st.write(f"... and {len(all_employees_list) - 20} more")
    
    # Information about adding new data
    with st.sidebar.expander("ℹ️ Data Source"):
        st.write("""
        **Data loads directly from Supabase**
        
        Sales data is fetched from Supabase tables:
        - PYT Sales Data
        - Opatra Sales Data
        
        **To see new data:**
        1. Add records to your Supabase tables
        2. Click "🔄 Refresh Data" above
        
        **Employee name normalization:** Variant names (e.g. "DuaaZ", "Bir_ra Thanvi") 
        are mapped to canonical names in `dashboard.py` → `EMPLOYEE_NAME_MAPPING`. 
        Add new mappings there as you discover duplicates. Check "Debug: Data & Columns" 
        for potential duplicates.
        
        **Supported date formats:** DD/MM/YYYY
        **Note:** Data is cached 1 hour. Use "Refresh Data" to see updates.
        """)

    # Active filter summary bar
    date_str = (f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}" 
               if (start_date is not None and end_date is not None) else "All dates")
    shop_badge = selected_shop if selected_shop != 'All Shops' else "All Shops"
    emp_badge = selected_employee if selected_employee != 'All' else "All Employees"
    st.markdown(f"""
    <div class="filter-summary">
        <span class="filter-badge">🏪 {shop_badge}</span>
        <span class="filter-badge">👤 {emp_badge}</span>
        <span class="filter-badge">📅 {date_str}</span>
        <span class="filter-badge">📊 {len(filtered_sales):,} transactions</span>
    </div>
    """, unsafe_allow_html=True)

    # Empty state when no data
    if len(filtered_sales) == 0:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <h3>No sales data for the selected filters</h3>
            <p>Try adjusting the date range, employee, or shop.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    st.divider()

    # Key Metrics
    if selected_employee != 'All':
        st.header(f"📈 Performance Metrics - {selected_employee}")
    else:
        st.header("📈 Key Metrics")
    
    # Calculate metrics
    total_net_sales = filtered_sales['Net_Sales'].sum()
    total_gross_sales = filtered_sales['Gross_Sales'].sum()
    total_transactions = filtered_sales['Transaction_Weight'].sum() if 'Transaction_Weight' in filtered_sales.columns else len(filtered_sales)
    total_transactions = int(round(total_transactions))  # Weight sum may be float
    avg_transaction = total_net_sales / total_transactions if total_transactions > 0 else 0
    
    # Calculate refunds - ensure column exists and handle properly
    if 'Refunds' in filtered_sales.columns:
        # Sum refunds (they're negative values, so we take absolute value for display)
        refunds_sum = filtered_sales['Refunds'].sum()
        total_refunds = abs(refunds_sum) if pd.notna(refunds_sum) else 0
        
        # Debug: Check if refunds are actually numeric
        refunds_nonzero = filtered_sales[filtered_sales['Refunds'] != 0]
        if len(refunds_nonzero) > 0:
            # Verify refunds are numeric
            refunds_sample = refunds_nonzero['Refunds'].head(5)
            refunds_types = [type(x).__name__ for x in refunds_sample]
            if 'str' in refunds_types:
                # Refunds are still strings - need to clean them again
                st.warning("⚠️ Refunds column contains strings. Re-cleaning refunds...")
                filtered_sales['Refunds'] = filtered_sales['Refunds'].apply(
                    lambda x: float(re.sub(r'[^\d.-]', '', str(x).strip())) if pd.notna(x) and str(x).strip() not in ['', '-', 'nan'] else 0
                )
                refunds_sum = filtered_sales['Refunds'].sum()
                total_refunds = abs(refunds_sum) if pd.notna(refunds_sum) else 0
    else:
        total_refunds = 0
    
    att_col = 'Commission_Employee' if 'Commission_Employee' in filtered_sales.columns else 'Employee'
    unique_employees_count = filtered_sales[att_col].nunique() if att_col in filtered_sales.columns else 0

    # KPI trend: period-over-period comparison (vs prior period of same length)
    prev_net_sales = prev_avg_transaction = prev_transactions = prev_refunds = None
    if start_date and end_date and work_df['Date'].notna().any():
        period_days = (end_date - start_date).days + 1
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=period_days - 1)
        prev_sales = work_df[
            (work_df['Date'].dt.date >= prev_start_date) &
            (work_df['Date'].dt.date <= prev_end_date)
        ]
        if selected_employee != 'All':
            prev_col = 'Commission_Employee' if 'Commission_Employee' in prev_sales.columns else 'Employee'
            if prev_col in prev_sales.columns:
                prev_sales = prev_sales[prev_sales[prev_col].astype(str).str.strip() == selected_employee.strip()]
        if len(prev_sales) > 0:
            prev_net_sales = prev_sales['Net_Sales'].sum()
            prev_transactions = int(round(prev_sales['Transaction_Weight'].sum())) if 'Transaction_Weight' in prev_sales.columns else len(prev_sales)
            prev_avg_transaction = prev_net_sales / prev_transactions if prev_transactions > 0 else 0
            prev_refunds = abs(prev_sales['Refunds'].sum()) if 'Refunds' in prev_sales.columns else 0

    def _trend_delta(current, prev, is_pct=False):
        """Format delta for period-over-period comparison."""
        if prev is None or prev == 0:
            return None
        change = (current - prev) / prev * 100 if is_pct else current - prev
        if is_pct:
            return f"{change:+.1f}% vs prior period"
        if abs(change) >= 1:
            return f"{change:+,.0f} vs prior period"
        return f"{change:+.2f} vs prior period"
    
    # Calculate comparison metrics if employee is selected
    if selected_employee != 'All' and len(work_df) > len(filtered_sales) and start_date and end_date:
        # Get all data for comparison (same date range, all employees)
        comparison_sales = work_df[
            (work_df['Date'].dt.date >= start_date) &
            (work_df['Date'].dt.date <= end_date)
        ] if work_df['Date'].notna().any() else work_df
        
        comp_tx = comparison_sales['Transaction_Weight'].sum() if 'Transaction_Weight' in comparison_sales.columns else len(comparison_sales)
        all_avg_transaction = comparison_sales['Net_Sales'].sum() / comp_tx if comp_tx > 0 else 0
        all_total_sales = comparison_sales['Net_Sales'].sum()
        employee_share = (total_net_sales / all_total_sales * 100) if all_total_sales > 0 else 0
        
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        
        with col1:
            comp_emp_col = 'Commission_Employee' if 'Commission_Employee' in comparison_sales.columns else 'Employee'
            n_emp = comparison_sales[comp_emp_col].nunique() if comp_emp_col in comparison_sales.columns else 0
            delta = total_net_sales - (all_total_sales / n_emp) if n_emp > 0 else None
            st.metric("Total Net Sales", f"£{total_net_sales:,.2f}", 
                     delta=f"{employee_share:.1f}% of total" if employee_share > 0 else None)
        with col2:
            st.metric("Total Gross Sales", f"£{total_gross_sales:,.2f}")
        with col3:
            st.metric("Total Transactions", f"{total_transactions:,}")
        with col4:
            delta = avg_transaction - all_avg_transaction if all_avg_transaction > 0 else None
            if delta is not None and delta != 0:
                # Format delta string with sign at the very beginning for proper parsing
                # Streamlit needs to see the negative sign first to determine arrow direction
                if delta < 0:
                    delta_str = f"-£{abs(delta):,.2f} vs avg"
                else:
                    delta_str = f"+£{delta:,.2f} vs avg"
                # Use "normal" for standard colors: positive=green, negative=red
                delta_color = "normal"
                help_text = f"Compared to average transaction value of £{all_avg_transaction:,.2f}"
            else:
                delta_str = None
                delta_color = None
                help_text = "Average transaction value"
            st.metric("Avg Transaction", f"£{avg_transaction:,.2f}", 
                     delta=delta_str, delta_color=delta_color, help=help_text)
        with col5:
            st.metric("Total Refunds", f"£{total_refunds:,.2f}")
        with col6:
            refund_rate = (total_refunds / total_gross_sales * 100) if total_gross_sales > 0 else 0
            st.metric("Refund Rate", f"{refund_rate:.2f}%")
        with col7:
            # Days worked in period
            days_worked = filtered_sales['Date'].nunique()
            st.metric("Days Active", f"{days_worked}")
        
        # Employee-specific insights
        st.subheader("📊 Employee Insights")
        insight_col1, insight_col2, insight_col3, insight_col4 = st.columns(4)
        
        with insight_col1:
            daily_avg = total_net_sales / days_worked if days_worked > 0 else 0
            st.metric("Daily Average", f"£{daily_avg:,.2f}")
        
        with insight_col2:
            best_day_sales = filtered_sales.groupby(filtered_sales['Date'].dt.date)['Net_Sales'].sum().max()
            st.metric("Best Day Sales", f"£{best_day_sales:,.2f}")
        
        with insight_col3:
            best_day = filtered_sales.groupby(filtered_sales['Date'].dt.date)['Net_Sales'].sum().idxmax()
            if isinstance(best_day, pd.Timestamp):
                st.metric("Best Day", best_day.strftime('%b %d, %Y'))
            else:
                st.metric("Best Day", str(best_day)[:10] if len(str(best_day)) > 10 else str(best_day))
        
        with insight_col4:
            top_product_sales = filtered_sales.groupby('Products')['Net_Sales'].sum().max() if 'Products' in filtered_sales.columns else 0
            st.metric("Top Product Sale", f"£{top_product_sales:,.2f}")
    else:
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            delta = _trend_delta(total_net_sales, prev_net_sales, is_pct=True) if prev_net_sales else None
            st.metric("Total Net Sales", f"£{total_net_sales:,.2f}", delta=delta,
                     help="Net sales for the selected period. Delta shows % change vs prior period of same length.")
        with col2:
            st.metric("Total Gross Sales", f"£{total_gross_sales:,.2f}",
                     help="Gross sales before refunds")
        with col3:
            delta = _trend_delta(total_transactions, prev_transactions, is_pct=True) if prev_transactions else None
            st.metric("Total Transactions", f"{total_transactions:,}", delta=delta,
                     help="Number of transactions. Delta shows % change vs prior period.")
        with col4:
            delta = _trend_delta(avg_transaction, prev_avg_transaction) if prev_avg_transaction and prev_avg_transaction > 0 else None
            st.metric("Avg Transaction", f"£{avg_transaction:,.2f}", delta=delta,
                     help="Average transaction value")
        with col5:
            delta = _trend_delta(total_refunds, prev_refunds) if prev_refunds is not None else None
            st.metric("Total Refunds", f"£{total_refunds:,.2f}", delta=delta,
                     help="Total refund amount")
        with col6:
            st.metric("Active Employees", f"{unique_employees_count}",
                     help="Number of unique employees with sales in this period")
        
        # Debug: Show refund statistics if refunds are 0 but should exist
        if total_refunds == 0 and 'Refunds' in filtered_sales.columns:
            refunds_nonzero = filtered_sales[filtered_sales['Refunds'] != 0]
            if len(refunds_nonzero) > 0:
                with st.expander("🔍 Debug: Refund Data Check"):
                    st.write(f"**Found {len(refunds_nonzero)} rows with non-zero refunds**")
                    st.write(f"**Raw refund sum:** {filtered_sales['Refunds'].sum():.2f}")
                    st.write(f"**Sample refund values:** {refunds_nonzero['Refunds'].head(10).tolist()}")
                    st.write("**Note:** If refunds show 0 but you see data here, try clicking '🔄 Refresh Data' in the sidebar to clear the cache.")
    
    st.divider()

    # Quick navigation hint
    tab_names = ["Daily Trends", "Day of Week", "Employee Status", "Employee Performance", "Hourly Patterns", "Product Patterns", "Future Projections", "Best Team", "Trends & Seasonality", "Shop Comparison", "Transaction Analytics", "Advanced Insights"]
    st.caption("📑 **Sections:** " + " • ".join(tab_names))

    # Create tabs for different analyses (Employee Status early for visibility)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
        "📅 Daily Trends", 
        "📆 Day of Week Analysis", 
        "👤 Employee Status",
        "👥 Employee Performance", 
        "⏰ Hourly Patterns", 
        "🛍️ Product Patterns", 
        "🔮 Future Projections",
        "🏆 Best Team for Week",
        "📈 Trends & Seasonality",
        "🏪 Shop Comparison",
        "🛒 Transaction Analytics",
        "🔍 Advanced Insights"
    ])
    
    # TAB 1: Daily Trends Analysis
    with tab1:
        if selected_employee != 'All':
            st.header(f"📅 Daily Sales Trends - {selected_employee}")
        else:
            st.header("📅 Daily Sales Trends")
        
        col1, col2 = st.columns(2)
        
        with col1:
            title = f'Daily Sales Trend - {selected_employee}' if selected_employee != 'All' else 'Daily Sales Trend'
            st.subheader("Daily Sales Over Time")
            daily_sales = filtered_sales.groupby(filtered_sales['Date'].dt.date)['Net_Sales'].sum().reset_index()
            daily_sales['Date'] = pd.to_datetime(daily_sales['Date'])
            daily_sales = daily_sales.sort_values('Date')
            
            fig = px.line(
                daily_sales,
                x='Date',
                y='Net_Sales',
                labels={'Net_Sales': 'Net Sales (£)', 'Date': 'Date'},
                title=title
            )
            fig.update_traces(mode='lines+markers', line=dict(width=2))
            fig.update_layout(height=400)
            render_chart(fig, dark_mode)
        
        with col2:
            title = f'Moving Averages - {selected_employee}' if selected_employee != 'All' else 'Moving Averages'
            st.subheader("7-Day Moving Average")
            daily_sales['Moving_Avg_7'] = daily_sales['Net_Sales'].rolling(window=7, min_periods=1).mean()
            daily_sales['Moving_Avg_30'] = daily_sales['Net_Sales'].rolling(window=30, min_periods=1).mean()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=daily_sales['Date'],
                y=daily_sales['Net_Sales'],
                name='Daily Sales',
                mode='lines',
                opacity=0.3
            ))
            fig.add_trace(go.Scatter(
                x=daily_sales['Date'],
                y=daily_sales['Moving_Avg_7'],
                name='7-Day Average',
                mode='lines',
                line=dict(width=2)
            ))
            fig.add_trace(go.Scatter(
                x=daily_sales['Date'],
                y=daily_sales['Moving_Avg_30'],
                name='30-Day Average',
                mode='lines',
                line=dict(width=2)
            ))
            fig.update_layout(
                title=title,
                xaxis_title='Date',
                yaxis_title='Net Sales (£)',
                height=400
            )
            render_chart(fig, dark_mode)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Daily Statistics")
            if len(daily_sales) > 0:
                st.write(f"**Average Daily Sales:** £{daily_sales['Net_Sales'].mean():,.2f}")
                best_day_idx = daily_sales['Net_Sales'].idxmax()
                worst_day_idx = daily_sales['Net_Sales'].idxmin()
                st.write(f"**Best Day:** {daily_sales.loc[best_day_idx, 'Date'].strftime('%Y-%m-%d')} - £{daily_sales.loc[best_day_idx, 'Net_Sales']:,.2f}")
                st.write(f"**Worst Day:** {daily_sales.loc[worst_day_idx, 'Date'].strftime('%Y-%m-%d')} - £{daily_sales.loc[worst_day_idx, 'Net_Sales']:,.2f}")
                st.write(f"**Standard Deviation:** £{daily_sales['Net_Sales'].std():,.2f}")
            else:
                st.info("No data available for the selected filters.")
        
        with col2:
            title = f'Monthly Comparison - {selected_employee}' if selected_employee != 'All' else 'Monthly Sales Comparison'
            st.subheader("Monthly Comparison")
            monthly_comparison = filtered_sales.groupby(filtered_sales['Date'].dt.to_period('M'))['Net_Sales'].sum()
            monthly_df = pd.DataFrame({
                'Month': monthly_comparison.index.astype(str),
                'Net_Sales': monthly_comparison.values
            })
            fig = px.bar(
                monthly_df,
                x='Month',
                y='Net_Sales',
                labels={'Net_Sales': 'Net Sales (£)'},
                title=title
            )
            fig.update_layout(height=300)
            render_chart(fig, dark_mode)
    
    # TAB 2: Day of Week Analysis
    with tab2:
        if selected_employee != 'All':
            st.header(f"📆 Day of Week Analysis - {selected_employee}")
        else:
            st.header("📆 Day of Week Analysis")
        
        # Use pre-aggregated data only if viewing all employees AND data exists
        # Otherwise, always calculate from filtered_sales to show employee-specific patterns
        if selected_employee == 'All' and day_of_week_df is not None:
            # Use pre-aggregated data when viewing all employees
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Sales by Day of Week")
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                day_of_week_df_ordered = day_of_week_df.set_index('Day').reindex([d for d in day_order if d in day_of_week_df['Day'].values])
                
                fig = px.bar(
                    day_of_week_df_ordered,
                    x=day_of_week_df_ordered.index,
                    y='Net_Sales_Sum',
                    labels={'Net_Sales_Sum': 'Total Net Sales (£)', 'index': 'Day of Week'},
                    color='Net_Sales_Sum',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=400, showlegend=False)
                render_chart(fig, dark_mode)
            
            with col2:
                st.subheader("Average Transaction by Day")
                fig = px.bar(
                    day_of_week_df_ordered,
                    x=day_of_week_df_ordered.index,
                    y='Net_Sales_Mean',
                    labels={'Net_Sales_Mean': 'Average Sale (£)', 'index': 'Day of Week'},
                    color='Net_Sales_Mean',
                    color_continuous_scale='Greens'
                )
                fig.update_layout(height=400, showlegend=False)
                render_chart(fig, dark_mode)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Transaction Count by Day")
                fig = px.bar(
                    day_of_week_df_ordered,
                    x=day_of_week_df_ordered.index,
                    y='Transaction_Count',
                    labels={'Transaction_Count': 'Number of Transactions', 'index': 'Day of Week'},
                    color='Transaction_Count',
                    color_continuous_scale='Oranges'
                )
                fig.update_layout(height=400, showlegend=False)
                render_chart(fig, dark_mode)
            
            with col2:
                st.subheader("Day of Week Summary Table")
                display_df = day_of_week_df_ordered.reset_index()
                display_df['Net_Sales_Sum'] = display_df['Net_Sales_Sum'].apply(lambda x: f"£{x:,.2f}")
                display_df['Net_Sales_Mean'] = display_df['Net_Sales_Mean'].apply(lambda x: f"£{x:,.2f}")
                display_df.columns = ['Day', 'Total Sales', 'Avg Sale', 'Transactions', 'Std Dev', 'Gross Sales']
                st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            # Calculate from filtered data (supports employee filtering)
            if len(filtered_sales) == 0:
                st.warning(f"No data available for {selected_employee if selected_employee != 'All' else 'the selected filters'}.")
            else:
                # Make a copy to work with
                work_df = filtered_sales.copy()
                
                # Ensure Day of Week column exists - calculate from Date if needed
                if 'Day of the Week' not in work_df.columns or work_df['Day of the Week'].isna().all():
                    if 'Date' in work_df.columns and work_df['Date'].notna().any():
                        work_df['Day of the Week'] = work_df['Date'].dt.day_name()
                    else:
                        st.error("No date data available to calculate day of week.")
                        st.stop()
                
                day_col = 'Day of the Week'
                
                # Filter out rows with null day of week
                valid_sales = work_df[work_df[day_col].notna()].copy()
                
                if len(valid_sales) > 0:
                    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    
                    # Group by day of week
                    day_sales = valid_sales.groupby(day_col)['Net_Sales'].agg(['sum', 'mean', 'count', 'std']).reset_index()
                    day_sales.columns = ['Day', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Net_Sales_Std']
                    
                    # Get gross sales
                    gross_by_day = valid_sales.groupby(day_col)['Gross_Sales'].sum().reset_index()
                    gross_by_day.columns = ['Day', 'Gross_Sales_Sum']
                    day_sales = day_sales.merge(gross_by_day, on='Day', how='left')
                    day_sales['Gross_Sales_Sum'] = day_sales['Gross_Sales_Sum'].fillna(0)
                    
                    # Reindex to ensure all days are in order and fill missing days
                    day_sales = day_sales.set_index('Day')
                    for day in day_order:
                        if day not in day_sales.index:
                            day_sales.loc[day] = [0, 0, 0, 0, 0]
                    
                    day_sales = day_sales.reindex(day_order)
                    
                    # Reset index to make Day a column for easier plotting
                    day_sales_plot = day_sales.reset_index()
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        title = f'Sales by Day of Week - {selected_employee}' if selected_employee != 'All' else 'Sales by Day of Week'
                        st.subheader("Sales by Day of Week")
                        fig = px.bar(
                            day_sales_plot,
                            x='Day',
                            y='Net_Sales_Sum',
                            labels={'Net_Sales_Sum': 'Total Net Sales (£)', 'Day': 'Day of Week'},
                            color='Net_Sales_Sum',
                            color_continuous_scale='Blues',
                            title=title
                        )
                        fig.update_layout(
                            height=400, 
                            showlegend=False,
                            xaxis={'categoryorder': 'array', 'categoryarray': day_order}
                        )
                        render_chart(fig, dark_mode)
                    
                    with col2:
                        title = f'Avg Transaction by Day - {selected_employee}' if selected_employee != 'All' else 'Average Transaction by Day'
                        st.subheader("Average Transaction by Day")
                        fig = px.bar(
                            day_sales_plot,
                            x='Day',
                            y='Net_Sales_Mean',
                            labels={'Net_Sales_Mean': 'Average Sale (£)', 'Day': 'Day of Week'},
                            color='Net_Sales_Mean',
                            color_continuous_scale='Greens',
                            title=title
                        )
                        fig.update_layout(
                            height=400, 
                            showlegend=False,
                            xaxis={'categoryorder': 'array', 'categoryarray': day_order}
                        )
                        render_chart(fig, dark_mode)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        title = f'Transaction Count by Day - {selected_employee}' if selected_employee != 'All' else 'Transaction Count by Day'
                        st.subheader("Transaction Count by Day")
                        fig = px.bar(
                            day_sales_plot,
                            x='Day',
                            y='Transaction_Count',
                            labels={'Transaction_Count': 'Number of Transactions', 'Day': 'Day of Week'},
                            color='Transaction_Count',
                            color_continuous_scale='Oranges',
                            title=title
                        )
                        fig.update_layout(
                            height=400, 
                            showlegend=False,
                            xaxis={'categoryorder': 'array', 'categoryarray': day_order}
                        )
                        render_chart(fig, dark_mode)
                    
                    with col2:
                        st.subheader("Day of Week Summary Table")
                        display_df = day_sales_plot.copy()
                        display_df['Net_Sales_Sum'] = display_df['Net_Sales_Sum'].apply(lambda x: f"£{x:,.2f}")
                        display_df['Net_Sales_Mean'] = display_df['Net_Sales_Mean'].apply(lambda x: f"£{x:,.2f}")
                        display_df['Gross_Sales_Sum'] = display_df['Gross_Sales_Sum'].apply(lambda x: f"£{x:,.2f}")
                        display_df['Net_Sales_Std'] = display_df['Net_Sales_Std'].apply(lambda x: f"£{x:,.2f}" if pd.notna(x) and x > 0 else "N/A")
                        display_df = display_df[['Day', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Net_Sales_Std', 'Gross_Sales_Sum']]
                        display_df.columns = ['Day', 'Total Sales', 'Avg Sale', 'Transactions', 'Std Dev', 'Gross Sales']
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                else:
                    st.warning(f"No valid day of week data found for {selected_employee if selected_employee != 'All' else 'the selected filters'}. Found {len(work_df)} total rows but none with valid day of week.")
    
    # TAB 3: Employee Status (active/inactive) - placed early for visibility
    with tab3:
        st.header("👤 Employee Status")
        st.caption("Mark employees as active or inactive. Inactive employees are excluded from Best Team recommendations.")
        status_dict = load_employee_status()
        for emp in unique_employees:
            if emp not in status_dict:
                status_dict[emp] = 'active'
        status_df = pd.DataFrame([
            {'Employee': emp, 'Status': status_dict.get(emp, 'active')}
            for emp in sorted(unique_employees)
        ])
        edited = st.data_editor(
            status_df,
            column_config={
                'Employee': st.column_config.TextColumn('Employee', disabled=True, help="Employee name"),
                'Status': st.column_config.SelectboxColumn('Status', options=['active', 'inactive'], required=True, help="Active = included in Best Team; Inactive = excluded from recommendations"),
            },
            use_container_width=True,
            hide_index=True,
            key='employee_status_editor'
        )
        if st.button("💾 Save Employee Status", key='save_status'):
            new_status = {row['Employee']: row['Status'] for _, row in edited.iterrows()}
            if save_employee_status(new_status):
                st.success("✅ Employee status saved.")
                st.rerun()
            else:
                st.error("Could not save. Check Supabase connection or file permissions.")

    # TAB 4: Employee Performance
    with tab4:
        if selected_employee != 'All':
            st.header(f"👥 Performance Analysis - {selected_employee}")
            
            # Employee-specific detailed analysis
            if len(filtered_sales) > 0:
                st.subheader("📊 Performance Summary")
                
                emp_col1, emp_col2, emp_col3, emp_col4 = st.columns(4)
                
                with emp_col1:
                    total_sales = filtered_sales['Net_Sales'].sum()
                    st.metric("Total Sales", f"£{total_sales:,.2f}")
                
                with emp_col2:
                    avg_sale = filtered_sales['Net_Sales'].mean()
                    st.metric("Average Sale", f"£{avg_sale:,.2f}")
                
                with emp_col3:
                    transaction_count = len(filtered_sales)
                    st.metric("Transactions", f"{transaction_count:,}")
                
                with emp_col4:
                    days_active = filtered_sales['Date'].nunique()
                    st.metric("Days Active", f"{days_active}")
                
                # Comparison with all employees (same date range)
                comparison_sales = work_df[
                    (work_df['Date'].dt.date >= start_date) & 
                    (work_df['Date'].dt.date <= end_date)
                ] if work_df['Date'].notna().any() else work_df
                
                if len(comparison_sales) > len(filtered_sales):
                    st.subheader("📈 Performance Comparison")
                    comp_col1, comp_col2, comp_col3 = st.columns(3)
                    
                    all_avg_sale = comparison_sales['Net_Sales'].mean()
                    all_total = comparison_sales['Net_Sales'].sum()
                    all_employee_count = comparison_sales['Employee'].nunique()
                    avg_per_employee = all_total / all_employee_count if all_employee_count > 0 else 0
                    
                    with comp_col1:
                        vs_avg = ((avg_sale - all_avg_sale) / all_avg_sale * 100) if all_avg_sale > 0 else 0
                        st.metric("Avg Sale vs All", f"£{avg_sale:,.2f}", 
                                 delta=f"{vs_avg:+.1f}%", delta_color="normal" if vs_avg >= 0 else "inverse")
                    
                    with comp_col2:
                        vs_total = ((total_sales - avg_per_employee) / avg_per_employee * 100) if avg_per_employee > 0 else 0
                        st.metric("Total vs Avg Employee", f"£{total_sales:,.2f}",
                                 delta=f"{vs_total:+.1f}%", delta_color="normal" if vs_total >= 0 else "inverse")
                    
                    with comp_col3:
                        # Rank among all employees
                        employee_totals = comparison_sales.groupby('Employee')['Net_Sales'].sum().sort_values(ascending=False)
                        rank = (employee_totals.index.get_loc(selected_employee) + 1) if selected_employee in employee_totals.index else None
                        total_employees = len(employee_totals)
                        if rank:
                            percentile = ((total_employees - rank + 1) / total_employees * 100) if total_employees > 0 else 0
                            st.metric("Rank", f"#{rank} of {total_employees}", 
                                     delta=f"Top {percentile:.0f}%", delta_color="normal" if percentile >= 50 else "inverse")
                
                # Employee's best products
                st.subheader("🛍️ Top Products Sold")
                if 'Products' in filtered_sales.columns:
                    product_sales = {}
                    for products in filtered_sales['Products'].dropna():
                        if isinstance(products, str):
                            items = products.split(',')
                            for item in items:
                                if 'x' in item:
                                    try:
                                        product_name = item.split('x')[0].strip()
                                        if product_name:
                                            # Try to extract sale amount
                                            sale_amount = filtered_sales[filtered_sales['Products'].str.contains(product_name, na=False)]['Net_Sales'].sum()
                                            product_sales[product_name] = product_sales.get(product_name, 0) + 1
                                    except:
                                        pass
                    
                    if product_sales:
                        top_products = pd.Series(product_sales).sort_values(ascending=False).head(10)
                        fig = px.bar(
                            x=top_products.values,
                            y=top_products.index,
                            orientation='h',
                            labels={'x': 'Number of Sales', 'y': 'Product'},
                            title=f'Top Products - {selected_employee}'
                        )
                        fig.update_layout(height=400, xaxis_tickformat=".2f")
                        render_chart(fig, dark_mode)
                
                # Employee's performance over time
                st.subheader("📈 Sales Trend")
                monthly_emp_sales = filtered_sales.groupby(filtered_sales['Date'].dt.to_period('M'))['Net_Sales'].sum()
                monthly_emp_sales.index = monthly_emp_sales.index.astype(str)
                
                fig = px.line(
                    x=monthly_emp_sales.index,
                    y=monthly_emp_sales.values,
                    markers=True,
                    labels={'x': 'Month', 'y': 'Net Sales (£)'},
                    title=f'Monthly Sales Trend - {selected_employee}'
                )
                fig.update_layout(height=400)
                render_chart(fig, dark_mode)
                
        else:
            st.header("👥 Employee Performance Analysis")
        
        if employee_df is not None:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Top Employees by Total Sales")
                top_employees = employee_df.nlargest(15, 'Net_Sales_Sum')
                fig = px.bar(
                    top_employees,
                    x='Net_Sales_Sum',
                    y='Employee',
                    orientation='h',
                    labels={'Net_Sales_Sum': 'Total Net Sales (£)'},
                    color='Net_Sales_Sum',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=500, showlegend=False, xaxis_tickformat=".2f")
                render_chart(fig, dark_mode)
            
            with col2:
                st.subheader("Top Employees by Average Transaction")
                top_avg = employee_df[employee_df['Transaction_Count'] >= 10].nlargest(15, 'Net_Sales_Mean')
                fig = px.bar(
                    top_avg,
                    x='Net_Sales_Mean',
                    y='Employee',
                    orientation='h',
                    labels={'Net_Sales_Mean': 'Average Sale (£)'},
                    color='Net_Sales_Mean',
                    color_continuous_scale='Greens'
                )
                fig.update_layout(height=500, showlegend=False, xaxis_tickformat=".2f")
                render_chart(fig, dark_mode)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Transaction Volume by Employee")
                top_volume = employee_df.nlargest(15, 'Transaction_Count')
                fig = px.bar(
                    top_volume,
                    x='Transaction_Count',
                    y='Employee',
                    orientation='h',
                    labels={'Transaction_Count': 'Number of Transactions'},
                    color='Transaction_Count',
                    color_continuous_scale='Oranges'
                )
                fig.update_layout(height=500, showlegend=False, xaxis_tickformat=".2f")
                render_chart(fig, dark_mode)
            
            with col2:
                st.subheader("Refund Rate Analysis")
                refund_analysis = employee_df[employee_df['Refund_Rate'] > 0].sort_values('Refund_Rate', ascending=False)
                if len(refund_analysis) > 0:
                    fig = px.bar(
                        refund_analysis.head(10),
                        x='Refund_Rate',
                        y='Employee',
                        orientation='h',
                        labels={'Refund_Rate': 'Refund Rate (%)'},
                        color='Refund_Rate',
                        color_continuous_scale='Reds'
                    )
                    fig.update_layout(height=400, showlegend=False, xaxis_tickformat=".2f")
                    render_chart(fig, dark_mode)
                else:
                    st.info("No refunds recorded for any employees")
            
            st.subheader("Complete Employee Performance Table")
            export_df = employee_df.sort_values('Net_Sales_Sum', ascending=False).copy()
            export_df.columns = ['Employee', 'Total Net Sales', 'Average Sale', 'Transaction Count', 'Total Gross Sales', 'Refunds Sum', 'Refund Rate']
            col_export, _ = st.columns([1, 4])
            with col_export:
                st.download_button("📥 Export CSV", export_df.to_csv(index=False), "employee_performance.csv", "text/csv", help="Download table as CSV")
            display_df = export_df.copy()
            display_df['Total Net Sales'] = display_df['Total Net Sales'].apply(lambda x: f"£{float(x):,.2f}")
            display_df['Average Sale'] = display_df['Average Sale'].apply(lambda x: f"£{float(x):,.2f}")
            display_df['Total Gross Sales'] = display_df['Total Gross Sales'].apply(lambda x: f"£{float(x):,.2f}")
            display_df['Refunds Sum'] = display_df['Refunds Sum'].apply(lambda x: f"£{float(x):,.2f}")
            display_df['Refund Rate'] = display_df['Refund Rate'].apply(lambda x: f"{float(x):.2f}%")
            display_df['Transaction Count'] = display_df['Transaction Count'].apply(lambda x: f"{int(float(x)):,}")
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)
    
    # TAB 5: Hourly Patterns
    with tab5:
        if selected_employee != 'All':
            st.header(f"⏰ Hourly Sales Patterns - {selected_employee}")
        else:
            st.header("⏰ Hourly Sales Patterns")
        
        # Use pre-aggregated data only if no employee filter is applied
        # Otherwise, calculate from filtered_sales to show employee-specific patterns
        if selected_employee != 'All' or 'Hour' not in filtered_sales.columns or hourly_df is None:
            # Calculate from filtered data (supports employee filtering)
            if 'Hour' in filtered_sales.columns and filtered_sales['Hour'].notna().any():
                hourly_sales = filtered_sales.groupby('Hour')['Net_Sales'].agg(['sum', 'mean', 'count']).reset_index()
                hourly_sales.columns = ['Hour', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count']
                hourly_sales = hourly_sales.sort_values('Hour')
                hourly_sales['Gross_Sales_Sum'] = filtered_sales.groupby('Hour')['Gross_Sales'].sum().values
                
                col1, col2 = st.columns(2)
                
                with col1:
                    title = f'Sales by Hour - {selected_employee}' if selected_employee != 'All' else 'Sales by Hour of Day'
                    st.subheader("Sales by Hour of Day")
                    fig = px.bar(
                        hourly_sales,
                        x='Hour',
                        y='Net_Sales_Sum',
                        labels={'Net_Sales_Sum': 'Total Net Sales (£)', 'Hour': 'Hour of Day'},
                        color='Net_Sales_Sum',
                        color_continuous_scale='Purples',
                        title=title
                    )
                    fig.update_layout(height=400, showlegend=False)
                    render_chart(fig, dark_mode)
                
                with col2:
                    title = f'Avg Transaction by Hour - {selected_employee}' if selected_employee != 'All' else 'Average Transaction Value by Hour'
                    st.subheader("Average Transaction by Hour")
                    fig = px.line(
                        hourly_sales,
                        x='Hour',
                        y='Net_Sales_Mean',
                        markers=True,
                        labels={'Net_Sales_Mean': 'Average Sale (£)', 'Hour': 'Hour of Day'},
                        title=title
                    )
                    fig.update_layout(height=400)
                    render_chart(fig, dark_mode)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    title = f'Transaction Volume by Hour - {selected_employee}' if selected_employee != 'All' else 'Transaction Volume by Hour'
                    st.subheader("Transaction Volume by Hour")
                    fig = px.bar(
                        hourly_sales,
                        x='Hour',
                        y='Transaction_Count',
                        labels={'Transaction_Count': 'Number of Transactions', 'Hour': 'Hour of Day'},
                        color='Transaction_Count',
                        color_continuous_scale='Blues',
                        title=title
                    )
                    fig.update_layout(height=400, showlegend=False)
                    render_chart(fig, dark_mode)
                
                with col2:
                    st.subheader("Peak Hours Analysis")
                    peak_hours = hourly_sales.nlargest(5, 'Net_Sales_Sum')
                    if len(peak_hours) > 0:
                        st.write(f"**Top 5 Peak Sales Hours{' - ' + selected_employee if selected_employee != 'All' else ''}:**")
                        for idx, row in peak_hours.iterrows():
                            hour_str = f"{int(row['Hour']):02d}:00"
                            st.write(f"**{hour_str}:** £{row['Net_Sales_Sum']:,.2f} ({int(row['Transaction_Count'])} transactions)")
                    else:
                        st.info("No hourly data available for the selected filters.")
            else:
                st.info(
                    "**Hourly data not available.** Ensure your data has a Time column (or timestamp, created_at, transaction_time) "
                    "with values like `09:53:04` or `2023-07-14T09:53:04+00`. Check Debug: Data & Columns for column names."
                )
        else:
            # Use pre-aggregated data when viewing all employees
            if hourly_df is not None:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Sales by Hour of Day")
                    hourly_df_sorted = hourly_df.sort_values('Hour')
                    fig = px.bar(
                        hourly_df_sorted,
                        x='Hour',
                        y='Net_Sales_Sum',
                        labels={'Net_Sales_Sum': 'Total Net Sales (£)', 'Hour': 'Hour of Day'},
                        color='Net_Sales_Sum',
                        color_continuous_scale='Purples'
                    )
                    fig.update_layout(height=400, showlegend=False)
                    render_chart(fig, dark_mode)
                
                with col2:
                    st.subheader("Average Transaction by Hour")
                    fig = px.line(
                        hourly_df_sorted,
                        x='Hour',
                        y='Net_Sales_Mean',
                        markers=True,
                        labels={'Net_Sales_Mean': 'Average Sale (£)', 'Hour': 'Hour of Day'},
                        title='Average Transaction Value by Hour'
                    )
                    fig.update_layout(height=400)
                    render_chart(fig, dark_mode)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Transaction Volume by Hour")
                    fig = px.bar(
                        hourly_df_sorted,
                        x='Hour',
                        y='Transaction_Count',
                        labels={'Transaction_Count': 'Number of Transactions', 'Hour': 'Hour of Day'},
                        color='Transaction_Count',
                        color_continuous_scale='Blues'
                    )
                    fig.update_layout(height=400, showlegend=False)
                    render_chart(fig, dark_mode)
                
                with col2:
                    st.subheader("Peak Hours Analysis")
                    peak_hours = hourly_df_sorted.nlargest(5, 'Net_Sales_Sum')
                    st.write("**Top 5 Peak Sales Hours:**")
                    for idx, row in peak_hours.iterrows():
                        hour_str = f"{int(row['Hour']):02d}:00"
                        st.write(f"**{hour_str}:** £{row['Net_Sales_Sum']:,.2f} ({int(row['Transaction_Count'])} transactions)")
    
    # TAB 6: Product Patterns
    with tab6:
        if selected_employee != 'All':
            st.header(f"🛍️ Product Patterns - {selected_employee}")
        else:
            st.header("🛍️ Product Patterns Analysis")
        
        # Use pre-aggregated data only if no employee filter is applied
        # Otherwise, calculate from filtered_sales to show employee-specific patterns
        if selected_employee != 'All' or product_df is None:
            # Calculate from filtered data (supports employee filtering)
            if 'Products' in filtered_sales.columns and filtered_sales['Products'].notna().any():
                # Extract product sales from filtered data
                product_sales_dict = {}
                product_count_dict = {}
                product_amounts_dict = {}
                
                for idx, row in filtered_sales.iterrows():
                    products = row['Products']
                    sale_amount = row['Net_Sales']
                    
                    if pd.notna(products) and isinstance(products, str):
                        # Split by comma and process each product
                        items = [i.strip() for i in products.split(',') if i.strip()]
                        num_items = len([i for i in items if 'x' in i and not i.startswith('-')])
                        
                        for item in items:
                            item = item.strip()
                            # Skip refunds (negative items)
                            if item.startswith('-') or 'x-' in item:
                                continue
                                
                            if 'x' in item:
                                try:
                                    # Format: "Product Name 1x135.00" or "Product Name 1x£135.00"
                                    # Pattern: [Product Name] [quantity]x[price]
                                    # Use regex to match: text, optional space, number, 'x', price
                                    pattern = r'^(.+?)\s+(\d+)x([\d.,£]+)$'
                                    match = re.match(pattern, item)
                                    
                                    if match:
                                        product_name = match.group(1).strip()
                                        quantity = int(match.group(2))
                                        price_str = match.group(3).strip()
                                        
                                        # Clean and parse price
                                        price_clean = price_str.replace('£', '').replace(',', '').strip()
                                        price_match = re.search(r'(\d+\.?\d*)', price_clean)
                                        if price_match:
                                            price = float(price_match.group(1))
                                            # Sanity check: reasonable price range
                                            if price <= 0 or price > 50000:  # Max £50k per item
                                                continue
                                        else:
                                            continue
                                        
                                        if product_name and len(product_name) > 0:
                                            # Price is already the total for this line item
                                            if product_name not in product_sales_dict:
                                                product_sales_dict[product_name] = 0
                                                product_count_dict[product_name] = 0
                                            
                                            product_sales_dict[product_name] += price
                                            product_count_dict[product_name] += quantity
                                    else:
                                        # Fallback: try simpler pattern or skip
                                        # If we can't parse, skip this item to avoid incorrect data
                                        continue
                                        
                                except Exception as e:
                                    # Skip items that fail to parse
                                    continue
                
                # Create DataFrame from calculated data
                if product_sales_dict:
                    product_data = []
                    for product, total_sales in product_sales_dict.items():
                        count = product_count_dict.get(product, 0)
                        avg_sale = total_sales / count if count > 0 else 0
                        product_data.append({
                            'Product': product,
                            'Total_Sales': total_sales,
                            'Count': count,
                            'Avg_Sale': avg_sale
                        })
                    
                    product_df_filtered = pd.DataFrame(product_data)
                    product_df_filtered = product_df_filtered[product_df_filtered['Total_Sales'] > 0].sort_values('Total_Sales', ascending=False)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        title = f'Top Products by Sales - {selected_employee}' if selected_employee != 'All' else 'Top 20 Products by Sales Volume'
                        st.subheader("Top Products by Sales Volume")
                        top_products = product_df_filtered.head(20)
                        if len(top_products) > 0:
                            fig = px.bar(
                                top_products,
                                x='Total_Sales',
                                y='Product',
                                orientation='h',
                                labels={'Total_Sales': 'Total Sales (£)'},
                                color='Total_Sales',
                                color_continuous_scale='Blues',
                                title=title
                            )
                            fig.update_layout(height=600, showlegend=False, xaxis_tickformat=".2f")
                            render_chart(fig, dark_mode)
                        else:
                            st.info("No product data available for the selected filters.")
                    
                    with col2:
                        title = f'Top Products by Count - {selected_employee}' if selected_employee != 'All' else 'Top 20 Products by Transaction Count'
                        st.subheader("Top Products by Transaction Count")
                        top_count = product_df_filtered.nlargest(20, 'Count')
                        if len(top_count) > 0:
                            fig = px.bar(
                                top_count,
                                x='Count',
                                y='Product',
                                orientation='h',
                                labels={'Count': 'Number of Transactions'},
                                color='Count',
                                color_continuous_scale='Greens',
                                title=title
                            )
                            fig.update_layout(height=600, showlegend=False, xaxis_tickformat=".2f")
                            render_chart(fig, dark_mode)
                        else:
                            st.info("No product data available for the selected filters.")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        title = f'Top Products by Avg Sale - {selected_employee}' if selected_employee != 'All' else 'Top Products by Average Sale Value'
                        st.subheader("Top Products by Average Sale Value")
                        top_avg = product_df_filtered[product_df_filtered['Count'] >= 1].nlargest(20, 'Avg_Sale')
                        if len(top_avg) > 0:
                            fig = px.bar(
                                top_avg,
                                x='Avg_Sale',
                                y='Product',
                                orientation='h',
                                labels={'Avg_Sale': 'Average Sale (£)'},
                                color='Avg_Sale',
                                color_continuous_scale='Oranges',
                                title=title
                            )
                            fig.update_layout(height=600, showlegend=False, xaxis_tickformat=".2f")
                            render_chart(fig, dark_mode)
                        else:
                            st.info("No product data available for the selected filters.")
                    
                    with col2:
                        st.subheader("Product Performance Summary")
                        display_df = product_df_filtered.head(30)[['Product', 'Total_Sales', 'Count', 'Avg_Sale']].copy()
                        display_df['Total_Sales'] = display_df['Total_Sales'].apply(lambda x: f"£{x:,.2f}")
                        display_df['Avg_Sale'] = display_df['Avg_Sale'].apply(lambda x: f"£{x:,.2f}")
                        display_df.columns = ['Product', 'Total Sales', 'Transactions', 'Avg Sale']
                        st.dataframe(display_df, use_container_width=True, height=600)
                else:
                    st.info("No product data available in the filtered data.")
            else:
                st.info("Product data not available in the sales data.")
        else:
            # Use pre-aggregated data when viewing all employees
            if product_df is not None:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Top 20 Products by Sales Volume")
                    top_products = product_df.nlargest(20, 'Total_Sales')
                    fig = px.bar(
                        top_products,
                        x='Total_Sales',
                        y='Product',
                        orientation='h',
                        labels={'Total_Sales': 'Total Sales (£)'},
                        color='Total_Sales',
                        color_continuous_scale='Blues'
                    )
                    fig.update_layout(height=600, showlegend=False)
                    render_chart(fig, dark_mode)
                
                with col2:
                    st.subheader("Top 20 Products by Transaction Count")
                    top_count = product_df.nlargest(20, 'Count')
                    fig = px.bar(
                        top_count,
                        x='Count',
                        y='Product',
                        orientation='h',
                        labels={'Count': 'Number of Transactions'},
                        color='Count',
                        color_continuous_scale='Greens'
                    )
                    fig.update_layout(height=600, showlegend=False)
                    render_chart(fig, dark_mode)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Top Products by Average Sale Value")
                    top_avg = product_df[product_df['Count'] >= 5].nlargest(20, 'Avg_Sale')
                    fig = px.bar(
                        top_avg,
                        x='Avg_Sale',
                        y='Product',
                        orientation='h',
                        labels={'Avg_Sale': 'Average Sale (£)'},
                        color='Avg_Sale',
                        color_continuous_scale='Oranges'
                    )
                    fig.update_layout(height=600, showlegend=False)
                    render_chart(fig, dark_mode)
                
                with col2:
                    st.subheader("Product Performance Summary")
                    display_df = product_df.nlargest(30, 'Total_Sales')[['Product', 'Total_Sales', 'Count', 'Avg_Sale']].copy()
                    display_df['Total_Sales'] = display_df['Total_Sales'].apply(lambda x: f"£{x:,.2f}")
                    display_df['Avg_Sale'] = display_df['Avg_Sale'].apply(lambda x: f"£{x:,.2f}")
                    display_df.columns = ['Product', 'Total Sales', 'Transactions', 'Avg Sale']
                    st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)
    
    # TAB 7: Future Projections
    with tab7:
        if selected_employee != 'All':
            st.header(f"🔮 Future Sales Projections - {selected_employee}")
        else:
            st.header("🔮 Future Sales Projections")
        
        st.info("""
        **Improved Forecasting Methodology:** 
        The forecasts use moving averages with day-of-week seasonality adjustments and realistic growth caps.
        - **Moving Average**: Uses recent averages (last 30 days) adjusted for day-of-week patterns
        - **Conservative**: Uses recent average only, no growth trend
        - **Exponential Smoothing**: Weights recent data more heavily
        
        Forecasts account for weekly patterns and cap growth rates to realistic levels. These are estimates for guidance only.
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            forecast_days = st.number_input("Days to Forecast", min_value=7, max_value=365, value=30, step=7, help="Number of days to project into the future")
        
        with col2:
            forecast_months = st.number_input("Months to Forecast", min_value=1, max_value=12, value=6, step=1, help="Number of months to project")
        
        with col3:
            forecast_method = st.selectbox(
                "Forecast Method",
                ["moving_avg", "conservative", "exponential_smoothing"],
                index=0,
                format_func=lambda x: {
                    "moving_avg": "Moving Average (Recommended)",
                    "conservative": "Conservative (No Growth)",
                    "exponential_smoothing": "Exponential Smoothing"
                }[x],
                help="Moving Average uses seasonality; Conservative assumes no growth; Exponential Smoothing weights recent data more"
            )
        
        # Daily Forecast
        st.subheader("📅 Daily Sales Forecast")
        forecast_result = forecast_sales(filtered_sales, periods=forecast_days, method=forecast_method)
        
        if forecast_result:
            forecast_df, base_avg, growth_rate, method_name = forecast_result
            
            # Get historical daily data
            daily_sales = filtered_sales.groupby(filtered_sales['Date'].dt.date)['Net_Sales'].sum().reset_index()
            daily_sales['Date'] = pd.to_datetime(daily_sales['Date'])
            daily_sales = daily_sales.sort_values('Date')
            daily_sales['Type'] = 'Historical'
            
            # Calculate recent average for comparison
            recent_days = min(30, len(daily_sales))
            recent_avg_actual = daily_sales['Net_Sales'].tail(recent_days).mean()
            
            forecast_df['Type'] = 'Forecast'
            forecast_df = forecast_df.rename(columns={'Forecast': 'Net_Sales'})
            
            # Combine
            combined = pd.concat([
                daily_sales[['Date', 'Net_Sales', 'Type']],
                forecast_df[['Date', 'Net_Sales', 'Type']]
            ])
            
            fig = go.Figure()
            
            # Historical data
            hist_data = combined[combined['Type'] == 'Historical']
            fig.add_trace(go.Scatter(
                x=hist_data['Date'],
                y=hist_data['Net_Sales'],
                mode='lines+markers',
                name='Historical Sales',
                line=dict(color='blue', width=2),
                opacity=0.7
            ))
            
            # Forecast data
            forecast_data = combined[combined['Type'] == 'Forecast']
            fig.add_trace(go.Scatter(
                x=forecast_data['Date'],
                y=forecast_data['Net_Sales'],
                mode='lines+markers',
                name='Forecast',
                line=dict(color='red', width=2, dash='dash')
            ))
            
            # Add average line for reference
            fig.add_hline(
                y=recent_avg_actual,
                line_dash="dot",
                line_color="gray",
                annotation_text=f"Recent Avg: £{recent_avg_actual:,.2f}",
                annotation_position="right"
            )
            
            forecast_title = f'Daily Sales Forecast ({forecast_days} days) - {selected_employee} - {method_name}' if selected_employee != 'All' else f'Daily Sales Forecast ({forecast_days} days) - {method_name}'
            fig.update_layout(
                title=forecast_title,
                xaxis_title='Date',
                yaxis_title='Net Sales (£)',
                height=500,
                hovermode='x unified'
            )
            render_chart(fig, dark_mode)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Recent Average", f"£{recent_avg_actual:,.2f}")
            with col2:
                growth_pct = growth_rate * 100 if growth_rate != 0 else 0
                st.metric("Growth Rate", f"{growth_pct:.1f}%")
            with col3:
                avg_forecast = forecast_df['Net_Sales'].mean()
                st.metric("Forecast Average", f"£{avg_forecast:,.2f}")
            with col4:
                projected_total = forecast_df['Net_Sales'].sum()
                st.metric(f"Projected Total ({forecast_days} days)", f"£{projected_total:,.2f}")
        else:
            st.info("📊 **Insufficient data for daily forecast.** Need at least 7 days of sales data. Try a wider date range.")
        
        # Monthly Forecast
        st.subheader("📆 Monthly Sales Forecast")
        monthly_forecast = forecast_monthly(filtered_sales, months=forecast_months, method=forecast_method)
        
        if monthly_forecast:
            forecast_df, base_avg, growth_rate, method_name = monthly_forecast
            
            # Get historical monthly data
            monthly_sales = filtered_sales.groupby(filtered_sales['Date'].dt.to_period('M'))['Net_Sales'].sum()
            monthly_sales.index = pd.to_datetime(monthly_sales.index.astype(str))
            monthly_sales = monthly_sales.sort_index()
            
            # Calculate recent monthly average
            recent_months = min(6, len(monthly_sales))
            recent_monthly_avg = monthly_sales.tail(recent_months).mean()
            
            fig = go.Figure()
            
            # Historical
            fig.add_trace(go.Scatter(
                x=monthly_sales.index,
                y=monthly_sales.values,
                mode='lines+markers',
                name='Historical Monthly Sales',
                line=dict(color='blue', width=3),
                marker=dict(size=8)
            ))
            
            # Forecast
            fig.add_trace(go.Scatter(
                x=forecast_df['Month'],
                y=forecast_df['Forecast'],
                mode='lines+markers',
                name='Monthly Forecast',
                line=dict(color='red', width=3, dash='dash'),
                marker=dict(size=8)
            ))
            
            # Add average line
            fig.add_hline(
                y=recent_monthly_avg,
                line_dash="dot",
                line_color="gray",
                annotation_text=f"Recent Avg: £{recent_monthly_avg:,.2f}",
                annotation_position="right"
            )
            
            forecast_title = f'Monthly Sales Forecast ({forecast_months} months) - {selected_employee} - {method_name}' if selected_employee != 'All' else f'Monthly Sales Forecast ({forecast_months} months) - {method_name}'
            fig.update_layout(
                title=forecast_title,
                xaxis_title='Month',
                yaxis_title='Net Sales (£)',
                height=500,
                hovermode='x unified'
            )
            render_chart(fig, dark_mode)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Recent Monthly Avg", f"£{recent_monthly_avg:,.2f}")
            with col2:
                growth_pct = growth_rate * 100 if growth_rate != 0 else 0
                st.metric("Monthly Growth", f"{growth_pct:.1f}%")
            with col3:
                avg_forecast = forecast_df['Forecast'].mean()
                st.metric("Forecast Average", f"£{avg_forecast:,.2f}")
            with col4:
                projected_total = forecast_df['Forecast'].sum()
                st.metric(f"Projected Total ({forecast_months} months)", f"£{projected_total:,.2f}")
            
            # Forecast table
            st.subheader("Monthly Forecast Details")
            forecast_display = forecast_df.copy()
            forecast_display['Month'] = forecast_display['Month'].dt.strftime('%Y-%m')
            forecast_display['Forecast'] = forecast_display['Forecast'].apply(lambda x: f"£{x:,.2f}")
            forecast_display.columns = ['Month', 'Projected Sales']
            st.download_button("📥 Export forecast CSV", forecast_df[['Month', 'Forecast']].assign(Month=forecast_df['Month'].dt.strftime('%Y-%m')).to_csv(index=False), "monthly_forecast.csv", "text/csv", key="export_forecast", help="Download forecast as CSV")
            st.dataframe(forecast_display, use_container_width=True, hide_index=True)
            
            # Additional insights
            st.subheader("📊 Forecast Insights")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Forecast Assumptions:**")
                st.write(f"- Based on last {recent_months} months of data")
                st.write(f"- Method: {method_name}")
                if growth_rate != 0:
                    st.write(f"- Growth trend: {growth_rate*100:.1f}% per month (capped at ±10%)")
                else:
                    st.write("- No growth trend applied (conservative)")
                st.write("- Accounts for day-of-week patterns (daily forecast)")
            
            with col2:
                st.write("**Important Notes:**")
                st.write("⚠️ Forecasts are estimates based on historical patterns")
                st.write("⚠️ Actual results may vary due to external factors")
                st.write("⚠️ Use forecasts as guidance, not guarantees")
                st.write("⚠️ Shorter forecast periods are generally more accurate")
        else:
            st.info("📊 **Insufficient data for monthly forecast.** Need at least 3 months of sales data. Try a wider date range.")

    # TAB 8: Best Team for Week
    with tab8:
        st.header("🏆 Best Team for Week")
        st.caption("Recommended team based on daily and hourly performance. Uses only active employees.")
        active_only = work_df[work_df['Employee'].isin(active_employees)] if active_employees else work_df
        if len(active_only) == 0:
            st.warning("No active employees. Mark employees as active in the Employee Status tab.")
        else:
            team_size = st.slider("Team size per day", min_value=1, max_value=10, value=3, help="Number of top performers to recommend per day")
            lookback_days = st.number_input("Lookback period (days)", min_value=7, max_value=365, value=90, help="Use data from last N days for performance scoring")
            if work_df['Date'].notna().any():
                max_date = pd.Timestamp(work_df['Date'].max())
                cutoff_date = max_date - timedelta(days=lookback_days)
                score_df = active_only[pd.to_datetime(active_only['Date'], errors='coerce') >= cutoff_date].copy()
            else:
                score_df = active_only.copy()
            if len(score_df) == 0:
                st.warning("No data in the lookback period. Try a longer lookback or check date range.")
            else:
                if 'Day of the Week' not in score_df.columns or score_df['Day of the Week'].isna().all():
                    score_df = score_df.copy()
                    score_df['Day of the Week'] = pd.to_datetime(score_df['Date'], errors='coerce').dt.day_name()
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                by_day = score_df.groupby(['Employee', 'Day of the Week'])['Net_Sales'].agg(['sum', 'mean', 'count']).reset_index()
                by_day = by_day.rename(columns={'Day of the Week': 'Day', 'sum': 'Total', 'mean': 'Avg', 'count': 'Count'})
                recommendations = []
                for day in day_order:
                    day_data = by_day[by_day['Day'] == day]
                    if len(day_data) == 0:
                        recommendations.append({'Day': day, 'Recommended': '-', 'Est_Total': 0})
                        continue
                    top = day_data.nlargest(team_size, 'Total')
                    names = ', '.join(top['Employee'].tolist())
                    est_total = top['Total'].sum()
                    recommendations.append({'Day': day, 'Recommended': names, 'Est_Total': est_total})
                rec_df = pd.DataFrame(recommendations)
                st.subheader("📊 Recommended team by day")
                st.dataframe(rec_df, use_container_width=True, hide_index=True, column_config={
                    'Day': st.column_config.TextColumn('Day'),
                    'Recommended': st.column_config.TextColumn('Top performers'),
                    'Est_Total': st.column_config.NumberColumn('Est. total sales (£)', format='£%.2f'),
                })
                if 'Hour' in score_df.columns and score_df['Hour'].notna().any():
                    st.subheader("⏰ Peak hours by employee")
                    by_hour = score_df.groupby(['Employee', 'Hour'])['Net_Sales'].sum().reset_index()
                    emp_best_hour = by_hour.loc[by_hour.groupby('Employee')['Net_Sales'].idxmax()]
                    emp_best_hour = emp_best_hour[['Employee', 'Hour']].sort_values('Employee')
                    st.dataframe(emp_best_hour, use_container_width=True, hide_index=True)
                st.info("💡 Recommendations are based on historical sales. Consider availability and preferences when scheduling.")

    # TAB 9: Trends & Seasonality
    with tab9:
        st.header("📈 Trends & Seasonality")
        if len(filtered_sales) == 0:
            st.warning("No data for the selected filters.")
        else:
            with st.expander("📊 Month-over-Month & Year-over-Year", expanded=True):
                monthly = filtered_sales.groupby(filtered_sales['Date'].dt.to_period('M')).agg(
                    Net_Sales=('Net_Sales', 'sum'),
                    Transactions=('Net_Sales', 'count'),
                    Avg_Sale=('Net_Sales', 'mean')
                ).reset_index()
                monthly['Month'] = monthly['Date'].astype(str)
                monthly['MoM_Change'] = monthly['Net_Sales'].pct_change() * 100
                monthly['YoY_Change'] = monthly['Net_Sales'].pct_change(periods=12) * 100
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(monthly, x='Month', y='Net_Sales', labels={'Net_Sales': 'Net Sales (£)'}, title='Monthly Sales')
                    fig.update_layout(height=350)
                    render_chart(fig, dark_mode)
                with col2:
                    if monthly['MoM_Change'].notna().any():
                        fig = px.line(monthly, x='Month', y='MoM_Change', markers=True, labels={'MoM_Change': 'MoM % Change'}, title='Month-over-Month % Change')
                        fig.add_hline(y=0, line_dash="dash", line_color="gray")
                        fig.update_layout(height=350)
                        render_chart(fig, dark_mode)
                st.dataframe(monthly[['Month', 'Net_Sales', 'Transactions', 'Avg_Sale', 'MoM_Change', 'YoY_Change']].round(2), use_container_width=True, hide_index=True)
            with st.expander("📉 Sales Velocity & Best/Worst Periods", expanded=True):
                daily = filtered_sales.groupby(filtered_sales['Date'].dt.date)['Net_Sales'].sum().reset_index()
                daily['Date'] = pd.to_datetime(daily['Date'])
                avg_daily = daily['Net_Sales'].mean()
                weekly = filtered_sales.groupby(filtered_sales['Date'].dt.to_period('W'))['Net_Sales'].sum()
                st.metric("Average Daily Sales", f"£{avg_daily:,.2f}")
                col1, col2 = st.columns(2)
                with col1:
                    best = daily.loc[daily['Net_Sales'].idxmax()]
                    worst = daily.loc[daily['Net_Sales'].idxmin()]
                    st.write(f"**Best Day:** {best['Date'].strftime('%Y-%m-%d')} — £{best['Net_Sales']:,.2f}")
                    st.write(f"**Worst Day:** {worst['Date'].strftime('%Y-%m-%d')} — £{worst['Net_Sales']:,.2f}")
                with col2:
                    if len(weekly) > 0:
                        best_week = weekly.idxmax()
                        worst_week = weekly.idxmin()
                        st.write(f"**Best Week:** {best_week} — £{weekly.max():,.2f}")
                        st.write(f"**Worst Week:** {worst_week} — £{weekly.min():,.2f}")
                fig = px.histogram(daily, x='Net_Sales', nbins=30, labels={'Net_Sales': 'Daily Sales (£)'}, title='Distribution of Daily Sales')
                fig.update_layout(height=300)
                render_chart(fig, dark_mode)
            with st.expander("📅 Seasonality", expanded=False):
                seas_df = filtered_sales.copy()
                if 'Day of the Week' not in seas_df.columns or seas_df['Day of the Week'].isna().all():
                    seas_df['Day of the Week'] = pd.to_datetime(seas_df['Date'], errors='coerce').dt.day_name()
                monthly_by_dow = seas_df.groupby([seas_df['Date'].dt.to_period('M'), 'Day of the Week'])['Net_Sales'].sum().reset_index()
                monthly_by_dow['Month'] = monthly_by_dow['Date'].astype(str)
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                fig = px.bar(monthly_by_dow, x='Month', y='Net_Sales', color='Day of the Week', labels={'Net_Sales': 'Net Sales (£)'}, title='Monthly Sales by Day of Week', color_discrete_sequence=CHART_COLORWAY)
                fig.update_layout(height=400, barmode='stack')
                render_chart(fig, dark_mode)

    # TAB 10: Shop Comparison
    with tab10:
        st.header("🏪 Shop Comparison")
        if 'Shop' not in sales_df.columns or sales_df['Shop'].nunique() < 2:
            st.info("Shop comparison requires data from multiple shops. Select 'All Shops' in the sidebar to see this analysis.")
        else:
            compare_df = work_df.copy()
            if start_date and end_date and compare_df['Date'].notna().any():
                compare_df = compare_df[(compare_df['Date'].dt.date >= start_date) & (compare_df['Date'].dt.date <= end_date)]
            if selected_employee != 'All':
                comp_emp_col = 'Commission_Employee' if 'Commission_Employee' in compare_df.columns else 'Employee'
                if comp_emp_col in compare_df.columns:
                    compare_df = compare_df[compare_df[comp_emp_col].astype(str).str.strip() == selected_employee.strip()]
            shops = compare_df['Shop'].dropna().unique().tolist()
            if len(shops) < 2:
                st.info("Filter to 'All Shops' and 'All' employees for full shop comparison.")
            else:
                shop_metrics = []
                for shop in shops:
                    s = compare_df[compare_df['Shop'] == shop]
                    tx_count = int(round(s['Transaction_Weight'].sum())) if 'Transaction_Weight' in s.columns else len(s)
                    shop_metrics.append({
                        'Shop': shop,
                        'Net Sales': s['Net_Sales'].sum(),
                        'Transactions': tx_count,
                        'Avg Sale': s['Net_Sales'].mean(),
                        'Refunds': abs(s['Refunds'].sum()) if 'Refunds' in s.columns else 0,
                    })
                sm = pd.DataFrame(shop_metrics)
                sm['Refund Rate %'] = np.where(sm['Net Sales'] > 0, sm['Refunds'] / (sm['Net Sales'] + sm['Refunds']) * 100, 0)
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(sm, x='Shop', y='Net Sales', color='Shop', labels={'Net Sales': 'Net Sales (£)'}, title='Total Sales by Shop')
                    fig.update_layout(showlegend=False, height=350, yaxis_tickformat=".2f")
                    render_chart(fig, dark_mode)
                with col2:
                    fig = px.bar(sm, x='Shop', y='Avg Sale', color='Shop', labels={'Avg Sale': 'Avg Transaction (£)'}, title='Average Transaction by Shop')
                    fig.update_layout(showlegend=False, height=350, yaxis_tickformat=".2f")
                    render_chart(fig, dark_mode)
                st.dataframe(sm, use_container_width=True, hide_index=True, column_config={
                    'Net Sales': st.column_config.NumberColumn('Net Sales (£)', format='£%.2f'),
                    'Avg Sale': st.column_config.NumberColumn('Avg Sale (£)', format='£%.2f'),
                    'Refunds': st.column_config.NumberColumn('Refunds (£)', format='£%.2f'),
                })
                monthly_by_shop = compare_df.groupby([compare_df['Date'].dt.to_period('M'), 'Shop'])['Net_Sales'].sum().reset_index()
                monthly_by_shop['Month'] = monthly_by_shop['Date'].astype(str)
                fig = px.line(monthly_by_shop, x='Month', y='Net_Sales', color='Shop', markers=True, labels={'Net_Sales': 'Net Sales (£)'}, title='Monthly Trend by Shop')
                fig.update_layout(height=400)
                render_chart(fig, dark_mode)

    # TAB 11: Transaction Analytics
    with tab11:
        st.header("🛒 Transaction Analytics")
        if len(filtered_sales) == 0:
            st.warning("No data for the selected filters.")
        else:
            with st.expander("📦 Basket Size", expanded=True):
                if 'Products' in filtered_sales.columns:
                    tx_df = filtered_sales.copy()
                    tx_df['Items_Count'] = tx_df['Products'].apply(_count_items_per_transaction)
                    items = tx_df['Items_Count']
                    avg_items = items.mean()
                    st.metric("Average Items per Transaction", f"{avg_items:.1f}")
                    col1, col2 = st.columns(2)
                    with col1:
                        nbins = min(20, max(1, int(items.max()) + 1))
                        fig = px.histogram(tx_df, x='Items_Count', nbins=nbins, labels={'Items_Count': 'Items per Transaction'}, title='Basket Size Distribution')
                        fig.update_layout(height=350)
                        render_chart(fig, dark_mode)
                    with col2:
                        basket_emp_col = 'Commission_Employee' if 'Commission_Employee' in tx_df.columns else 'Employee'
                        by_emp = tx_df.groupby(basket_emp_col)['Items_Count'].mean().reset_index().rename(columns={basket_emp_col: 'Employee'}).sort_values('Items_Count', ascending=False).head(15)
                        if len(by_emp) > 0:
                            fig = px.bar(by_emp, x='Items_Count', y='Employee', orientation='h', labels={'Items_Count': 'Avg Items'}, title='Avg Basket Size by Employee (by commission)')
                            fig.update_layout(height=350, xaxis_tickformat=".2f")
                            render_chart(fig, dark_mode)
                else:
                    st.info("Products column not found. Basket size requires product data.")
            with st.expander("💰 Transaction Size Distribution", expanded=True):
                bins = [0, 25, 50, 100, 200, 500, 1000, float('inf')]
                labels_bin = ['£0-25', '£25-50', '£50-100', '£100-200', '£200-500', '£500-1000', '£1000+']
                tx_dist_df = filtered_sales.copy()
                tx_dist_df['Tx_Bucket'] = pd.cut(tx_dist_df['Net_Sales'], bins=bins, labels=labels_bin)
                tx_dist = tx_dist_df.groupby('Tx_Bucket', observed=True).size().reset_index(name='Count')
                fig = px.bar(tx_dist, x='Tx_Bucket', y='Count', labels={'Tx_Bucket': 'Transaction Size', 'Count': 'Count'}, title='Transaction Value Distribution')
                fig.update_layout(height=350)
                render_chart(fig, dark_mode)
            with st.expander("↩️ Refund Patterns", expanded=True):
                if 'Refunds' in filtered_sales.columns:
                    refunds = filtered_sales[filtered_sales['Refunds'] != 0]
                    if len(refunds) > 0:
                        col1, col2 = st.columns(2)
                        with col1:
                            ref_emp_col = 'Commission_Employee' if 'Commission_Employee' in refunds.columns else 'Employee'
                            refund_by_emp = refunds.groupby(ref_emp_col)['Refunds'].agg(['sum', 'count']).reset_index()
                            refund_by_emp['Refund_Sum'] = refund_by_emp['sum'].abs()
                            refund_by_emp = refund_by_emp.rename(columns={ref_emp_col: 'Employee'})
                            refund_by_emp = refund_by_emp.sort_values('Refund_Sum', ascending=False).head(15)
                            fig = px.bar(refund_by_emp, x='Refund_Sum', y='Employee', orientation='h', labels={'Refund_Sum': 'Refunds (£)'}, title='Refunds by Employee (by commission)')
                            fig.update_layout(height=350, xaxis_tickformat=".2f")
                            render_chart(fig, dark_mode)
                        with col2:
                            if 'Hour' in refunds.columns and refunds['Hour'].notna().any():
                                refund_by_hour = refunds.groupby('Hour')['Refunds'].sum().abs().reset_index()
                                fig = px.bar(refund_by_hour, x='Hour', y='Refunds', labels={'Refunds': 'Refunds (£)'}, title='Refunds by Hour of Day')
                                fig.update_layout(height=350, yaxis_tickformat=".2f")
                                render_chart(fig, dark_mode)
                        if 'Products' in refunds.columns:
                            st.subheader("Refunds by Product")
                            refund_products = {}
                            for _, row in refunds.iterrows():
                                ps = row.get('Products', '')
                                if pd.notna(ps) and isinstance(ps, str):
                                    for item in ps.split(','):
                                        if item.strip().startswith('-'):
                                            refund_products[item.strip()] = refund_products.get(item.strip(), 0) + 1
                            if refund_products:
                                rp_df = pd.DataFrame([{'Product': k, 'Refund_Count': v} for k, v in sorted(refund_products.items(), key=lambda x: -x[1])[:15]])
                                st.dataframe(rp_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No refunds in the selected period.")
                else:
                    st.info("Refunds column not found.")

    # TAB 12: Advanced Insights
    with tab12:
        st.header("🔍 Advanced Insights")
        if len(filtered_sales) == 0:
            st.warning("No data for the selected filters.")
        else:
            with st.expander("🛍️ Product Mix & Share", expanded=True):
                if product_df is not None and len(product_df) > 0:
                    top = product_df.head(15)
                    top['Share_%'] = top['Total_Sales'] / top['Total_Sales'].sum() * 100
                    fig = px.pie(top, values='Share_%', names='Product', title='Product Mix (Top 15)', color_discrete_sequence=CHART_COLORWAY)
                    fig.update_layout(height=400)
                    fig.update_traces(textinfo='percent+label', texttemplate='%{percent:.2%}')
                    render_chart(fig, dark_mode)
                else:
                    st.info("No product data available.")
            with st.expander("👤 Product-Employee Affinity", expanded=True):
                aff_emp_col = 'Commission_Employee' if 'Commission_Employee' in filtered_sales.columns else 'Employee'
                if 'Products' in filtered_sales.columns and aff_emp_col in filtered_sales.columns:
                    emp_product_sales = {}
                    for _, row in filtered_sales.iterrows():
                        emp = row.get(aff_emp_col)
                        ps = row.get('Products', '')
                        if pd.isna(emp) or pd.isna(ps) or not isinstance(ps, str):
                            continue
                        for item in [i.strip() for i in ps.split(',') if i.strip()]:
                            if item.startswith('-') or 'x-' in item:
                                continue
                            if 'x' in item:
                                m = re.match(r'^(.+?)\s+(\d+)x([\d.,£]+)$', item)
                                if m:
                                    name, qty, price_str = m.group(1).strip(), int(m.group(2)), m.group(3)
                                    pm = re.search(r'(\d+\.?\d*)', price_str.replace('£', '').replace(',', ''))
                                    if pm and 0 < float(pm.group(1)) <= 50000:
                                        key = (emp, name)
                                        emp_product_sales[key] = emp_product_sales.get(key, 0) + float(pm.group(1)) * qty
                    if emp_product_sales:
                        ep_df = pd.DataFrame([{'Employee': k[0], 'Product': k[1], 'Sales': v} for k, v in emp_product_sales.items()])
                        top_combos = ep_df.nlargest(20, 'Sales')
                        fig = px.bar(top_combos, x='Sales', y='Product', color='Employee', orientation='h', labels={'Sales': 'Sales (£)'}, title='Top Product-Employee Combinations')
                        fig.update_layout(height=500, barmode='stack', xaxis_tickformat=".2f")
                        render_chart(fig, dark_mode)
                    else:
                        st.info("No product-employee data.")
                else:
                    st.info("Products and Employee columns required.")
            with st.expander("📊 Employee Consistency", expanded=True):
                if employee_df is not None and 'Employee' in filtered_sales.columns:
                    emp_daily = filtered_sales.groupby(['Employee', filtered_sales['Date'].dt.date])['Net_Sales'].sum().reset_index()
                    emp_std = emp_daily.groupby('Employee')['Net_Sales'].agg(['mean', 'std', 'count']).reset_index()
                    emp_std = emp_std[emp_std['count'] >= 5]
                    emp_std['CV'] = np.where(emp_std['mean'] > 0, emp_std['std'] / emp_std['mean'] * 100, 0)
                    emp_std = emp_std.sort_values('CV')
                    if len(emp_std) > 0:
                        st.caption("Most consistent = lowest coefficient of variation (CV). Lower CV = more predictable daily performance.")
                        fig = px.bar(emp_std.head(15), x='Employee', y='CV', labels={'CV': 'CV %'}, title='Employee Consistency (Lower = More Consistent)')
                        fig.update_layout(height=350, yaxis_tickformat=".2f")
                        render_chart(fig, dark_mode)
                        st.dataframe(emp_std[['Employee', 'mean', 'std', 'CV']].round(2), use_container_width=True, hide_index=True)
                else:
                    st.info("Need employee data.")
            with st.expander("⏰ Peak Hours by Employee", expanded=True):
                if 'Hour' in filtered_sales.columns and filtered_sales['Hour'].notna().any() and 'Employee' in filtered_sales.columns:
                    by_emp_hour = filtered_sales.groupby(['Employee', 'Hour'])['Net_Sales'].sum().reset_index()
                    emp_best = by_emp_hour.loc[by_emp_hour.groupby('Employee')['Net_Sales'].idxmax()]
                    emp_best = emp_best[['Employee', 'Hour']].sort_values('Employee')
                    st.dataframe(emp_best, use_container_width=True, hide_index=True, column_config={'Hour': st.column_config.NumberColumn('Peak Hour', format='%d:00')})
                else:
                    st.info("Hour and Employee columns required.")
            with st.expander("⚠️ Anomaly Detection", expanded=True):
                daily = filtered_sales.groupby(filtered_sales['Date'].dt.date)['Net_Sales'].sum().reset_index()
                if len(daily) >= 7:
                    mean = daily['Net_Sales'].mean()
                    std = daily['Net_Sales'].std()
                    if std > 0:
                        daily['Z_Score'] = (daily['Net_Sales'] - mean) / std
                        anomalies = daily[daily['Z_Score'].abs() > 2]
                        if len(anomalies) > 0:
                            st.caption("Days with Z-score > 2 (unusually high or low sales).")
                            fig = px.scatter(daily, x='Date', y='Net_Sales', color='Z_Score', color_continuous_scale='RdBu_r', labels={'Net_Sales': 'Net Sales (£)'}, title='Daily Sales with Anomalies Highlighted')
                            fig.update_layout(height=350)
                            render_chart(fig, dark_mode)
                            st.dataframe(anomalies[['Date', 'Net_Sales', 'Z_Score']].round(2), use_container_width=True, hide_index=True)
                        else:
                            st.info("No significant anomalies detected (Z-score > 2).")
                    else:
                        st.info("Insufficient variance for anomaly detection.")
                else:
                    st.info("Need at least 7 days of data for anomaly detection.")

if __name__ == "__main__":
    main()