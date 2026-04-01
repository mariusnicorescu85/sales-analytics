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
    "Bir-ra1": "Bir-ra",
    "Molly ": "Molly Tasheva",  # trailing space variant
    "Leonard Masie": "Leonard Maisie",
    "Nicorescu Codruta": "Codruta Nicorescu",
    # Duplicate/typo variants seen in data
    "Durbala Edmond1": "Durbala Edmond",
    "Edmond1": "Edmond",
    "Eddie1": "Eddie",
    # Opatra employee list variants (from 2026-03-17 export)
    "AishaM": "Aisha",
    "Michiele": "Michela",
    "Roim A": "Roim",
    "Ruby1": "Ruby",
    # PYT employee list variants (from 2026-03-17 export)
    "Ayihab1": "Ayihab",
    "AyshaK": "Aysha",
    "Codruta": "Codruta Nicorescu",
    "ErinA": "Erin",
    "Iqra2": "Iqra",
    "Tuba": "Raja Tuba",
    "T Temitope": "Temitope",
    "T.Molly": "Molly Tasheva",
    "molly1": "Molly Tasheva",
    "adam": "Adam Lee",
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

def apply_chart_theme(fig):
    """Apply unified theme to Plotly figure."""
    fig.update_layout(**CHART_THEME)
    return fig

def render_chart(fig, height=None, key=None):
    """Render Plotly chart with theme and download support."""
    fig = apply_chart_theme(fig)
    if height:
        fig.update_layout(height=height)
    # Format bar chart hover to 2 decimal places
    for trace in fig.data:
        if trace.type == 'bar':
            if getattr(trace, 'orientation', 'v') == 'h':
                trace.hovertemplate = '%{y}<br>%{x:,.2f}<extra></extra>'
            else:
                trace.hovertemplate = '%{x}<br>%{y:,.2f}<extra></extra>'
    kwargs = {"width": "stretch", "config": CHART_CONFIG}
    if key is not None:
        kwargs["key"] = key
    st.plotly_chart(fig, **kwargs)

# Custom CSS
def inject_css():
    bg = "#ffffff"
    card_bg = "#f8f9fa"
    text = "#31333f"
    border = "rgba(102, 126, 234, 0.2)"
    # Use st.html for CSS - st.markdown can render style tags as visible text in some deployments
    st.html(f"""
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
    <style>
    :root {{
        --bg: {bg};
        --card-bg: {card_bg};
        --text: {text};
        --border: {border};
        --font: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    /* Apply DM Sans but NOT to spans - Material icon spans need their own font */
    .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3 {{
        font-family: var(--font) !important;
    }}
    .stApp .stMarkdown span, .stApp [data-testid="stMetric"] span {{
        font-family: var(--font) !important;
    }}
    /* Fix Material icons: sidebar collapse + expanders show "keyboard_double_arrow_right" when font overridden.
       Hide broken icon text and show clean arrows. */
    [data-testid="collapsedControl"] {{
        font-size: 0;
    }}
    [data-testid="collapsedControl"]::before {{
        content: "»";
        font-size: 1.25rem;
        font-family: var(--font) !important;
        font-weight: 700;
        display: inline-block;
    }}
    /* Expander icons - hide keyboard_double_arrow_right text, show › (only target icon span, not label) */
    .stExpander summary [class*="material"] {{
        font-size: 0 !important;
        line-height: 0 !important;
    }}
    .stExpander summary [class*="material"]::before {{
        content: "›";
        font-size: 1.1rem;
        font-family: var(--font) !important;
        font-weight: 700;
    }}
    .header-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.5rem;
        margin: -1rem -1rem 1rem -1rem;
        background: linear-gradient(90deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.08) 100%);
        border-bottom: 1px solid {border};
        font-family: var(--font);
    }}
    .header-brand {{
        font-size: 1.35rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    .header-total {{
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text);
    }}
    .nav-section {{
        margin: 1rem 0;
        padding: 0.5rem 0;
        border-top: 1px solid rgba(102, 126, 234, 0.2);
    }}
    .nav-label {{
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        color: var(--text);
        opacity: 0.7;
        padding: 0.5rem 1rem 0.25rem;
    }}
    .sidebar-kpi-card {{
        margin-top: 1.5rem;
        padding: 1rem;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.15) 100%);
        border-radius: 12px;
        border: 1px solid {border};
        text-align: center;
    }}
    .sidebar-kpi-value {{
        font-size: 1.5rem;
        font-weight: 700;
        color: #667eea;
    }}
    .filter-summary {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
        padding: 14px 20px;
        margin-bottom: 1.5rem;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.06) 0%, rgba(118, 75, 162, 0.06) 50%, rgba(240, 147, 251, 0.04) 100%);
        border-radius: 14px;
        border: 1px solid {border};
        font-size: 0.9rem;
        font-family: var(--font);
    }}
    .filter-badge {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 6px 14px;
        border-radius: 24px;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.02em;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.25);
    }}
    .filter-badge-muted {{
        background: var(--card-bg);
        color: var(--text);
        padding: 6px 14px;
        border-radius: 24px;
        font-weight: 500;
        font-size: 0.85rem;
        border: 1px solid {border};
    }}
    .metric-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        border: 1px solid rgba(255,255,255,0.12);
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
    [data-testid="stSidebar"] .stMarkdown {{
        font-family: var(--font) !important;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        padding: 0.75rem 0;
        overflow-x: auto;
        flex-wrap: nowrap;
        -webkit-overflow-scrolling: touch;
    }}
    .stTabs [data-baseweb="tab"],
    .stTabs [role="tab"] {{
        font-family: var(--font) !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        padding: 0.7rem 1.25rem !important;
        border-radius: 10px;
        white-space: nowrap;
        transition: all 0.2s ease;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"],
    .stTabs [role="tab"][aria-selected="true"] {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        box-shadow: 0 2px 12px rgba(102, 126, 234, 0.4);
    }}
    .stTabs [data-baseweb="tab"][aria-selected="false"],
    .stTabs [role="tab"][aria-selected="false"] {{
        background: var(--card-bg) !important;
        color: var(--text) !important;
        border: 1px solid {border};
    }}
    .stTabs [data-baseweb="tab"][aria-selected="false"]:hover,
    .stTabs [role="tab"][aria-selected="false"]:hover {{
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.12) 100%) !important;
        border-color: rgba(102, 126, 234, 0.4);
    }}
    .empty-state {{
        text-align: center;
        padding: 4rem 2rem;
        background: linear-gradient(180deg, var(--card-bg) 0%, rgba(102, 126, 234, 0.04) 100%);
        border-radius: 16px;
        border: 2px dashed {border};
        color: var(--text);
        margin: 2rem 0;
        font-family: var(--font);
    }}
    .empty-state h3 {{
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }}
    .empty-state p {{
        opacity: 0.8;
        font-size: 0.95rem;
    }}
    .empty-state-icon {{
        font-size: 3.5rem;
        margin-bottom: 1rem;
        opacity: 0.5;
        filter: grayscale(0.2);
    }}
    [data-testid="stMetric"] {{
        background: var(--card-bg);
        padding: 1.1rem 1.25rem;
        border-radius: 14px;
        border: 1px solid {border};
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }}
    [data-testid="stMetric"]:hover {{
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.12);
        border-color: rgba(102, 126, 234, 0.25);
    }}
    .context-banner {{
        padding: 14px 20px;
        border-radius: 12px;
        margin-bottom: 1rem;
        font-family: var(--font);
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 12px;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.08) 100%);
        border: 1px solid rgba(102, 126, 234, 0.25);
    }}
    .context-banner.warning {{
        background: linear-gradient(135deg, rgba(250, 204, 21, 0.12) 0%, rgba(245, 158, 11, 0.08) 100%);
        border-color: rgba(245, 158, 11, 0.35);
    }}
    .section-divider {{
        margin: 1.5rem 0 1rem;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, {border}, transparent);
    }}
    div[data-testid="stHorizontalBlock"] > div:has([data-testid="stMetric"]) {{
        margin-bottom: 0.25rem;
    }}
    </style>
    """)

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


def _parse_positive_product_lines(products):
    """
    Parse Products field into (name, qty, unit_price) for positive lines.
    unit_price is the number in Qty x PRICE; line list weight = qty * unit_price.
    """
    if pd.isna(products) or not isinstance(products, str) or not str(products).strip():
        return []
    lines = []
    for item in [i.strip() for i in products.split(',') if i.strip()]:
        if item.startswith('-') or 'x-' in item:
            continue
        if 'x' not in item:
            continue
        m = re.match(r'^(.+?)\s+(\d+)x([\d.,£]+)$', item)
        if not m:
            continue
        name, qty, price_str = m.group(1).strip(), int(m.group(2)), m.group(3)
        price_match = re.search(r'(\d+\.?\d*)', price_str.replace('£', '').replace(',', ''))
        if not price_match:
            continue
        price = float(price_match.group(1))
        if name and 0 < price <= 50000:
            lines.append((name, qty, price))
    return lines


def _row_transaction_weight(row):
    w = row.get('Transaction_Weight')
    if w is None or pd.isna(w):
        return 1.0
    try:
        x = float(w)
        return x if x >= 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


def _product_transaction_key(row):
    """Stable key for one till sale (dedupes commission-expanded rows)."""
    t = row.get('Transaction')
    if t is not None and not pd.isna(t) and str(t).strip() not in ('', 'nan', 'None'):
        return ('txn', str(t).strip())
    ts = row.get('Date')
    ps = row.get('Products')
    return ('fp', ts, ps)


def _compute_product_from_sales(sales_df):
    """Compute product patterns from sales transaction data (parses Products column).

    Splits each row's Net_Sales across parsed lines by (qty × list unit price) share so
    commission-expanded rows (same Products, fractional Net_Sales) do not duplicate grosses.

    **Distinct_Tx** = number of unique till sales (``Transaction`` when present, else Date+Products)
    that include the SKU with a positive list-weight share.

    **Weighted_Tx** = sum of Transaction_Weight × line share (fractional when commission is split).
    """
    if sales_df is None or len(sales_df) == 0 or 'Products' not in sales_df.columns:
        return None
    product_sales = {}
    product_weighted = {}
    product_txn_keys = {}
    for _, row in sales_df.iterrows():
        lines = _parse_positive_product_lines(row.get('Products'))
        if not lines:
            continue
        weighted = []
        for name, qty, unit_p in lines:
            lw = float(qty) * unit_p
            if lw > 0:
                weighted.append((name, lw))
        if not weighted:
            continue
        S = sum(lw for _, lw in weighted)
        if S <= 0:
            continue
        try:
            net = float(row.get('Net_Sales', 0) or 0)
        except (TypeError, ValueError):
            net = 0.0
        w = _row_transaction_weight(row)
        tx_key = _product_transaction_key(row)
        for name, lw in weighted:
            share = lw / S
            product_sales[name] = product_sales.get(name, 0) + net * share
            product_weighted[name] = product_weighted.get(name, 0) + w * share
            if share > 0:
                if name not in product_txn_keys:
                    product_txn_keys[name] = set()
                product_txn_keys[name].add(tx_key)
    if not product_sales:
        return None
    rows = []
    for p in product_sales:
        n_distinct = len(product_txn_keys.get(p, ()))
        wsum = product_weighted.get(p, 0)
        rows.append({
            'Product': p,
            'Total_Sales': product_sales[p],
            'Distinct_Tx': n_distinct,
            'Weighted_Tx': wsum,
            'Avg_Sale': (product_sales[p] / n_distinct) if n_distinct > 0 else 0.0,
        })
    df = pd.DataFrame(rows)
    df = df[df['Total_Sales'] > 0].sort_values('Total_Sales', ascending=False)
    return df.reset_index(drop=True)


def _calendar_weekday_counts(start_date, end_date):
    """
    Count how many times each weekday occurs in [start_date, end_date] inclusive.
    Returns dict with keys Monday..Sunday. Empty/zero if dates invalid.
    """
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    out = {d: 0 for d in day_order}
    if start_date is None or end_date is None or start_date > end_date:
        return out
    d = start_date
    while d <= end_date:
        out[day_order[d.weekday()]] += 1
        d += timedelta(days=1)
    return out


def _filter_sales_by_calendar_range(sales_df, start_date, end_date):
    """
    Rows whose transaction Date falls on start_date..end_date inclusive (calendar days).

    Uses UTC-normalized YYYY-MM-DD strings so timezone-aware datetimes (e.g. Supabase +00)
    still match sidebar picks. If start_date or end_date is None, returns sales_df.copy().
    """
    if sales_df is None or len(sales_df) == 0:
        return sales_df
    out = sales_df.copy()
    if start_date is None or end_date is None:
        return out
    if 'Date' not in out.columns:
        return out
    ts = pd.to_datetime(out['Date'], errors='coerce', utc=True)
    ymd = ts.dt.strftime('%Y-%m-%d')
    lo = start_date.isoformat() if hasattr(start_date, 'isoformat') else str(start_date)
    hi = end_date.isoformat() if hasattr(end_date, 'isoformat') else str(end_date)
    mask = ts.notna() & (ymd >= lo) & (ymd <= hi)
    return out.loc[mask].copy()


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
    df['Refunds'] = df[refund_col].apply(_clean_currency) if refund_col else 0
    df['Refunds'] = df['Refunds'].fillna(0)
    # Gross Sales = Net Sales + Refunds (when no Gross column: derive from accounting relationship)
    if gross_col:
        df['Gross_Sales'] = df[gross_col].apply(_clean_currency)
    else:
        df['Gross_Sales'] = df['Net_Sales'] + df['Refunds'].abs()
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
        overall_mean = daily_sales['Net_Sales'].mean()
        day_multipliers = {}
        for day in range(7):
            day_sales = daily_sales[daily_sales['DayOfWeek'] == day]['Net_Sales']
            if len(day_sales) > 0 and overall_mean > 0:
                day_multipliers[day] = day_sales.mean() / overall_mean
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
        overall_mean = daily_sales['Net_Sales'].mean()
        day_multipliers = {}
        for day in range(7):
            day_sales = daily_sales[daily_sales['DayOfWeek'] == day]['Net_Sales']
            if len(day_sales) > 0 and overall_mean > 0:
                day_multipliers[day] = day_sales.mean() / overall_mean
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
        overall_mean = daily_sales['Net_Sales'].mean()
        day_multipliers = {}
        for day in range(7):
            day_sales = daily_sales[daily_sales['DayOfWeek'] == day]['Net_Sales']
            if len(day_sales) > 0 and overall_mean > 0:
                day_multipliers[day] = day_sales.mean() / overall_mean
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


@st.fragment
def _render_employee_status_tab(unique_employees):
    """Employee Status tab content - fragment prevents tab reset when changing Status dropdown."""
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
        width="stretch",
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


@st.fragment
def _render_best_team_tab(work_df, start_date, end_date, active_employees):
    """Best Team tab content - fragment prevents tab reset when changing team size slider."""
    st.header("🏆 Best Team for Week")
    date_range_note = f"📅 Using: {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}" if (start_date and end_date) else "📅 Using: All dates"
    st.caption(f"Performance profiles, peak times, and scheduling guidance for active employees. {date_range_note}")
    best_team_emp_col = 'Commission_Employee' if 'Commission_Employee' in work_df.columns else 'Employee'
    if start_date is not None and end_date is not None:
        best_team_df = _filter_sales_by_calendar_range(work_df, start_date, end_date)
    else:
        best_team_df = work_df.copy()
    active_only = best_team_df[best_team_df[best_team_emp_col].isin(active_employees)] if active_employees else best_team_df
    if len(active_only) == 0:
        st.warning("No active employees in the selected date range. Mark employees as active in the Employee Status tab or widen the date range.")
        return
    team_size = st.slider("Team size per day", min_value=1, max_value=10, value=3, help="Number of top performers to recommend per day", key="bt_team_size")
    score_df = active_only.copy()
    if len(score_df) == 0:
        st.warning("No data in the selected date range. Try a different date range in the sidebar.")
        return
    if 'Day of the Week' not in score_df.columns or score_df['Day of the Week'].isna().all():
        score_df = score_df.copy()
        score_df['Day of the Week'] = pd.to_datetime(score_df['Date'], errors='coerce').dt.day_name()
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    by_day = score_df.groupby([best_team_emp_col, 'Day of the Week'])['Net_Sales'].agg(['sum', 'mean', 'count']).reset_index()
    by_day = by_day.rename(columns={'Day of the Week': 'Day', best_team_emp_col: 'Employee', 'sum': 'Total', 'mean': 'Avg', 'count': 'Count'})
    score_df_pre_hour = score_df.copy()  # keep before hour filter for day counts
    has_hour = 'Hour' in score_df.columns and score_df['Hour'].notna().any()
    if has_hour:
        score_df['Hour'] = pd.to_numeric(score_df['Hour'], errors='coerce')
        score_df = score_df[score_df['Hour'].notna() & (score_df['Hour'] >= 0) & (score_df['Hour'] <= 23)]
    by_hour = score_df.groupby([best_team_emp_col, 'Hour'])['Net_Sales'].agg(['sum', 'mean', 'count']).reset_index() if has_hour else None
    if by_hour is not None:
        by_hour = by_hour.rename(columns={best_team_emp_col: 'Employee'})
    # --- Employee Performance Profiles ---
    st.subheader("📋 Employee Performance Profiles")
    st.caption("Averages by day, avg by hour, peak day, peak hour — for each active employee.")
    emp_avg_day = by_day.groupby('Employee')['Avg'].mean().reset_index()
    emp_avg_day.columns = ['Employee', 'Avg_Sales_Per_Day']
    emp_peak_day = by_day.loc[by_day.groupby('Employee')['Avg'].idxmax()][['Employee', 'Day', 'Avg']].rename(columns={'Day': 'Peak_Day', 'Avg': 'Peak_Day_Avg'})
    profile_df = emp_avg_day.merge(emp_peak_day, on='Employee', how='left')
    if by_hour is not None and len(by_hour) > 0:
        emp_avg_hour = by_hour.groupby('Employee')['mean'].mean().reset_index()
        emp_avg_hour.columns = ['Employee', 'Avg_Sales_Per_Hour']
        emp_peak_hour = by_hour.loc[by_hour.groupby('Employee')['mean'].idxmax()][['Employee', 'Hour', 'mean']].rename(columns={'Hour': 'Peak_Hour', 'mean': 'Peak_Hour_Avg'})
        profile_df = profile_df.merge(emp_avg_hour, on='Employee', how='left').merge(emp_peak_hour, on='Employee', how='left')
        profile_df['Peak_Hour'] = profile_df['Peak_Hour'].apply(lambda x: f"{int(x):02d}:00" if pd.notna(x) else '-')
    else:
        profile_df['Avg_Sales_Per_Hour'] = np.nan
        profile_df['Peak_Hour'] = '-'
    profile_df = profile_df.rename(columns={'Avg_Sales_Per_Day': 'Avg Daily (£)', 'Peak_Day': 'Peak Day', 'Peak_Day_Avg': 'Peak Day Avg (£)', 'Avg_Sales_Per_Hour': 'Avg Hourly (£)', 'Peak_Hour': 'Peak Hour'})
    for c in ['Avg Daily (£)', 'Peak Day Avg (£)', 'Avg Hourly (£)']:
        if c in profile_df.columns:
            profile_df[c] = profile_df[c].apply(lambda x: f"£{x:,.2f}" if pd.notna(x) and x > 0 else '-')
    st.dataframe(profile_df, width="stretch", hide_index=True)
    # --- Average per day of week ---
    st.subheader("📅 Average per day of week")
    pivot_day_table = by_day.pivot_table(index='Employee', columns='Day', values='Avg', aggfunc='mean').reindex(columns=day_order)
    if len(pivot_day_table) > 0:
        pivot_day_display = pivot_day_table.reset_index()
        for col in pivot_day_display.columns:
            if col != 'Employee':
                pivot_day_display[col] = pivot_day_display[col].apply(lambda x: f"£{x:,.2f}" if pd.notna(x) and x > 0 else "-")
        st.dataframe(pivot_day_display, width="stretch", hide_index=True)
    else:
        st.caption("No day-of-week data available.")
    # --- Heatmaps ---
    st.subheader("📊 Performance Heatmaps")
    col_hm1, col_hm2 = st.columns(2)
    with col_hm1:
        pivot_day = by_day.pivot_table(index='Employee', columns='Day', values='Avg', aggfunc='mean').reindex(columns=day_order)
        if len(pivot_day) > 0 and pivot_day.notna().any().any():
            fig_day = px.imshow(pivot_day.fillna(0), title="Avg Sales by Day (£)", labels=dict(x="Day", y="Employee", color="Avg £"), color_continuous_scale='Blues', aspect='auto')
            fig_day.update_layout(height=min(400, 80 + len(pivot_day) * 25))
            render_chart(fig_day)
        else:
            st.caption("No day-of-week data available.")
    with col_hm2:
        if by_hour is not None and len(by_hour) > 0:
            pivot_hour = by_hour.pivot_table(index='Employee', columns='Hour', values='mean', aggfunc='mean')
            if len(pivot_hour) > 0:
                pivot_hour = pivot_hour.reindex(sorted(pivot_hour.columns), axis=1)
                pivot_hour.columns = [f"{int(c):02d}:00" for c in pivot_hour.columns]
                fig_hour = px.imshow(pivot_hour.fillna(0), title="Avg Sales by Hour (£)", labels=dict(x="Hour", y="Employee", color="Avg £"), color_continuous_scale='Greens', aspect='auto')
                fig_hour.update_layout(height=min(400, 80 + len(pivot_hour) * 25))
                render_chart(fig_hour)
            else:
                st.caption("No hourly data available.")
        else:
            st.caption("No hourly data. Add a Time column to your data for hour-based insights.")
    # --- Scheduling Guidance ---
    st.subheader("🎯 Scheduling Guidance")
    g_day, g_hour = st.columns(2)
    with g_day:
        sel_day = st.selectbox("Select day", day_order, key="bt_day")
    with g_hour:
        hour_options = ["All hours"] + [f"{h:02d}:00" for h in range(24)]
        sel_hour = st.selectbox("Select hour (optional)", hour_options, key="bt_hour")
    sel_hour_num = int(sel_hour.split(":")[0]) if sel_hour != "All hours" else None
    day_data = by_day[by_day['Day'] == sel_day]
    if len(day_data) > 0:
        top_day = day_data.nlargest(team_size, 'Total')
        rec_names = top_day['Employee'].tolist()
        rec_total = top_day['Total'].sum()
        if by_hour is not None and sel_hour_num is not None:
            hour_data = by_hour[(by_hour['Employee'].isin(rec_names)) & (by_hour['Hour'] == sel_hour_num)]
            if len(hour_data) > 0:
                hour_data = hour_data.sort_values('sum', ascending=False).head(team_size)
                rec_names = hour_data['Employee'].tolist()
                rec_total = hour_data['sum'].sum()
                num_slots = score_df[score_df['Hour'] == sel_hour_num]['Date'].nunique()
                avg_per_slot = rec_total / num_slots if num_slots > 0 else rec_total
                st.success(f"**Recommended for {sel_day} at {sel_hour}:** " + ", ".join(rec_names) + f" (avg ~£{avg_per_slot:,.2f} per {sel_hour} slot)")
                st.caption(f"These employees have the highest sales in this hour. Avg based on {num_slots} occurrence(s) in date range.")
            else:
                num_days = score_df_pre_hour[score_df_pre_hour['Day of the Week'] == sel_day]['Date'].nunique()
                avg_per_day = rec_total / num_days if num_days > 0 else rec_total
                st.success(f"**Recommended for {sel_day}:** " + ", ".join(rec_names) + f" (avg ~£{avg_per_day:,.2f} per {sel_day})")
                st.caption(f"No hourly data for {sel_hour}. Showing day-based avg.")
        else:
            num_days = score_df_pre_hour[score_df_pre_hour['Day of the Week'] == sel_day]['Date'].nunique()
            avg_per_day = rec_total / num_days if num_days > 0 else rec_total
            st.success(f"**Recommended for {sel_day}:** " + ", ".join(rec_names) + f" (avg ~£{avg_per_day:,.2f} per {sel_day})")
            st.caption(f"These employees have the highest total sales on {sel_day}s. Avg based on {num_days} {sel_day}(s) in date range.")
    else:
        st.info(f"No data for {sel_day} in the selected date range.")
    # --- Recommended team by day ---
    st.subheader("📊 Recommended team by day")
    recommendations = []
    for day in day_order:
        day_data = by_day[by_day['Day'] == day].sort_values('Total', ascending=False).reset_index(drop=True)
        if len(day_data) == 0:
            recommendations.append({'Day': day, '1st Best': '-', 'Total 1st': 0, '2nd Best': '-', 'Total 2nd': 0, '3rd Best': '-', 'Total 3rd': 0})
            continue
        def _team_row(start_idx, size):
            subset = day_data.iloc[start_idx:start_idx + size]
            if len(subset) == 0:
                return '-', 0
            return ', '.join(subset['Employee'].tolist()), subset['Total'].sum()
        names1, est1 = _team_row(0, team_size)
        names2, est2 = _team_row(team_size, team_size)
        names3, est3 = _team_row(team_size * 2, team_size)
        recommendations.append({'Day': day, '1st Best': names1, 'Total 1st': est1, '2nd Best': names2, 'Total 2nd': est2, '3rd Best': names3, 'Total 3rd': est3})
    rec_df = pd.DataFrame(recommendations)
    st.dataframe(rec_df, width="stretch", hide_index=True, column_config={
        'Day': st.column_config.TextColumn('Day'),
        '1st Best': st.column_config.TextColumn('1st best team'),
        'Total 1st': st.column_config.NumberColumn('Total sales (in range)', format='£%.2f'),
        '2nd Best': st.column_config.TextColumn('2nd best team'),
        'Total 2nd': st.column_config.NumberColumn('Total sales (in range)', format='£%.2f'),
        '3rd Best': st.column_config.TextColumn('3rd best team'),
        'Total 3rd': st.column_config.NumberColumn('Total sales (in range)', format='£%.2f'),
    })
    st.info("💡 Use the heatmaps and profiles to match employees to their strongest days and hours. Consider availability and preferences when scheduling.")


def main():
    # Session state for UI preferences
    if "tab_index" not in st.session_state:
        st.session_state.tab_index = 0

    inject_css()

    # Header will be rendered after we have filtered_sales

    # Load all data with loading spinner
    with st.spinner("Loading sales data..."):
        sales_df, data_source = load_sales_data()
        employee_df = load_employee_data()
        if employee_df is None and sales_df is not None:
            employee_df = _compute_employee_performance_from_sales(sales_df)
    if sales_df is None:
        st.error("Could not load sales data. Check Supabase credentials in .env, or ensure PYT Sales Data_rows.csv and Opatra Sales Data_rows.csv are in the project folder.")
        return
    
    # Sidebar filters
    st.sidebar.header("🔍 Filters")

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
    
    st.sidebar.caption("💡 **Tip:** Data loads directly from Supabase. Click 'Refresh Data' to see updates.")
    
    # Apply shop filter to get working dataset
    if selected_shop != 'All Shops' and 'Shop' in sales_df.columns:
        work_df = sales_df[sales_df['Shop'] == selected_shop].copy()
    else:
        work_df = sales_df.copy()

    # Expand by commission for correct attribution: sales/refunds go to who gets commission, not who processed
    work_df_attributed = _expand_sales_by_commission(work_df)
    if work_df_attributed is not None and len(work_df_attributed) > 0:
        work_df = work_df_attributed

    # Recompute employee performance from commission-attributed data (who gets credit, not who processed)
    if len(work_df) > 0:
        employee_df = _compute_employee_performance_from_sales(work_df)
    # Load employee active/inactive status
    employee_status = load_employee_status()
    
    # Date range selection must come first so we can filter employees by who has data in that range
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
            start_date = max_date - timedelta(days=6)  # 7 days inclusive
        elif use_preset == "Last 30 Days":
            end_date = max_date
            start_date = max_date - timedelta(days=29)  # 30 days inclusive
        elif use_preset == "Last 90 Days":
            end_date = max_date
            start_date = max_date - timedelta(days=89)  # 90 days inclusive
        elif use_preset == "Last Year":
            end_date = max_date
            start_date = max_date - timedelta(days=364)  # 365 days inclusive
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
        
        filtered_sales = _filter_sales_by_calendar_range(work_df, start_date, end_date)
        
        # Display selected range
        st.sidebar.caption(f"📆 {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}")
    else:
        filtered_sales = work_df.copy()
        # Set default dates if no date data
        start_date = None
        end_date = None

    # Legacy: no longer used (multi-year comparison replaced sidebar toggle)
    compare_to_last_year = False

    # Get unique employees from the DATE-FILTERED data (only those with transactions in the selected range)
    emp_col = 'Commission_Employee' if 'Commission_Employee' in filtered_sales.columns else 'Employee'
    if emp_col in filtered_sales.columns:
        unique_employees_in_range = filtered_sales[emp_col].dropna().unique()
        unique_employees_in_range = [str(emp).strip() for emp in unique_employees_in_range if pd.notna(emp) and str(emp).strip() not in ['', 'nan', 'NaN', 'None']]
        unique_employees_in_range = sorted(list(set(unique_employees_in_range)))
    else:
        unique_employees_in_range = []
    # All employees (for Employee Status tab - so you can mark anyone active/inactive)
    if emp_col in work_df.columns:
        unique_employees_all = work_df[emp_col].dropna().unique()
        unique_employees_all = [str(emp).strip() for emp in unique_employees_all if pd.notna(emp) and str(emp).strip() not in ['', 'nan', 'NaN', 'None']]
        unique_employees_all = sorted(list(set(unique_employees_all)))
    else:
        unique_employees_all = []
    # Separate active and inactive (from date range - for dropdown)
    active_employees = [e for e in unique_employees_in_range if is_employee_active(e, employee_status)]
    inactive_employees = [e for e in unique_employees_in_range if not is_employee_active(e, employee_status)]
    
    # Employee filter: show active first, then inactive with label (inactive = only those in date range)
    show_inactive_in_filter = st.sidebar.checkbox("Include inactive employees in filter", value=True, help="When checked, shows inactive employees who have transactions in the selected date range")
    if show_inactive_in_filter:
        emp_options = ['All'] + active_employees + [f"{e} (inactive)" for e in inactive_employees]
    else:
        emp_options = ['All'] + active_employees
    select_key = f"emp_select_{start_date}_{end_date}" if (start_date is not None and end_date is not None) else "emp_select_all"
    selected_employee_raw = st.sidebar.selectbox("Select Employee", emp_options, key=select_key, help="View analytics for a specific employee or All for combined view")
    # Normalize selection (strip "(inactive)" for filtering and display)
    selected_employee = selected_employee_raw.replace(" (inactive)", "").strip() if selected_employee_raw != 'All' else 'All'
    
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
                    date_filtered = _filter_sales_by_calendar_range(work_df, start_date, end_date)
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
    
    # When "Include inactive employees" is unchecked and viewing All, filter to active only
    if selected_employee == 'All' and not show_inactive_in_filter and active_employees:
        emp_col = 'Commission_Employee' if 'Commission_Employee' in filtered_sales.columns else 'Employee'
        if emp_col in filtered_sales.columns:
            filtered_sales = filtered_sales[filtered_sales[emp_col].isin(active_employees)].copy()

    # Enforce sidebar calendar range again after employee / active filters (robust to tz-aware Date)
    filtered_sales = _filter_sales_by_calendar_range(filtered_sales, start_date, end_date)
    
    # Tab 4 leaderboard / export: same calendar range as the dashboard, and same inactive rule as the rest of the app
    perf_base = (
        _filter_sales_by_calendar_range(work_df, start_date, end_date)
        if start_date is not None and end_date is not None
        else work_df.copy()
    )
    perf_emp_col = 'Commission_Employee' if 'Commission_Employee' in perf_base.columns else 'Employee'
    if not show_inactive_in_filter and active_employees and perf_emp_col in perf_base.columns:
        perf_base = perf_base[perf_base[perf_emp_col].isin(active_employees)].copy()
    employee_df_display = (
        _compute_employee_performance_from_sales(perf_base) if len(perf_base) > 0 else None
    )
    
    # Employee-specific context banner (styled, not st.info)
    if selected_employee != 'All':
        date_range_str = (f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}" 
                         if start_date is not None and end_date is not None else "All dates")
        if len(filtered_sales) > 0:
            st.markdown(f"""
            <div class="context-banner">
                <span>👤</span>
                <span><strong>{selected_employee}</strong> · {date_range_str} · <strong>{len(filtered_sales):,}</strong> transactions</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="context-banner warning">
                <span>⚠️</span>
                <span>No data for <strong>{selected_employee}</strong> in {date_range_str}</span>
            </div>
            """, unsafe_allow_html=True)
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

    # Page title
    st.title("📊 Sales Analytics for Opatra & PYT")

    # Active filter summary bar
    date_str = (f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}" 
               if (start_date is not None and end_date is not None) else "All dates")
    shop_badge = selected_shop if selected_shop != 'All Shops' else "All Shops"
    emp_badge = selected_employee if selected_employee != 'All' else "All Employees"
    tx_count = f"{len(filtered_sales):,}"
    st.markdown(f"""
    <div class="filter-summary">
        <span class="filter-badge">🏪 {shop_badge}</span>
        <span class="filter-badge">👤 {emp_badge}</span>
        <span class="filter-badge">📅 {date_str}</span>
        <span class="filter-badge-muted">📊 {tx_count} transactions</span>
    </div>
    """, unsafe_allow_html=True)

    # Empty state when no data
    if len(filtered_sales) == 0:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <h3>No sales data for the selected filters</h3>
            <p>Try adjusting the date range, employee, or shop to see analytics.</p>
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

    # Multi-year comparison: same calendar dates shifted back by whole years (respects shop, employee, date filters).
    # Labels show the actual comparison window (not calendar-year totals), e.g. Aug 2025–Feb 2026 vs Aug 2024–Feb 2025.
    year_comparison_rows = []

    def _comparison_period_label(d0, d1):
        """Human-readable span for the prior-period window (sidebar dates may be date or datetime)."""
        a = pd.Timestamp(d0).normalize()
        b = pd.Timestamp(d1).normalize()
        return f"{a.strftime('%d %b %Y')} – {b.strftime('%d %b %Y')}"

    if start_date and end_date and work_df['Date'].notna().any():
        def _shift_date_to_year(d, years_back):
            try:
                return d.replace(year=d.year - years_back)
            except ValueError:
                return d.replace(year=d.year - years_back, day=28)

        current_year = start_date.year
        all_years_in_data = set(work_df['Date'].dropna().dt.year.astype(int))
        prev_years = sorted([y for y in all_years_in_data if y < current_year], reverse=True)
        emp_col_comp = 'Commission_Employee' if 'Commission_Employee' in work_df.columns else 'Employee'

        for year in prev_years:
            years_back = current_year - year
            py_start = _shift_date_to_year(start_date, years_back)
            py_end = _shift_date_to_year(end_date, years_back)
            py_sales = _filter_sales_by_calendar_range(work_df, py_start, py_end)
            if selected_employee != 'All' and emp_col_comp in py_sales.columns:
                py_sales = py_sales[py_sales[emp_col_comp].astype(str).str.strip() == selected_employee.strip()]
            if selected_employee == 'All' and not show_inactive_in_filter and active_employees and emp_col_comp in py_sales.columns:
                py_sales = py_sales[py_sales[emp_col_comp].isin(active_employees)]
            if len(py_sales) == 0:
                continue
            tx = int(round(py_sales['Transaction_Weight'].sum())) if 'Transaction_Weight' in py_sales.columns else len(py_sales)
            gross = py_sales['Gross_Sales'].sum()
            net = py_sales['Net_Sales'].sum()
            ref = abs(py_sales['Refunds'].sum()) if 'Refunds' in py_sales.columns else 0
            period_label = _comparison_period_label(py_start, py_end)
            year_comparison_rows.append({
                'sort_key': pd.Timestamp(py_end).normalize(),
                'period_label': period_label,
                'net_sales': net,
                'gross_sales': gross,
                'transactions': tx,
                'avg_transaction': net / tx if tx > 0 else 0,
                'refunds': ref,
                'active_employees': py_sales[emp_col_comp].nunique() if emp_col_comp in py_sales.columns else 0,
            })

    def _year_comparison_lines(metric_key, current_val, is_pct=False, is_currency=False):
        """Build comparison lines for a metric: (comparison_text, value_text) for each prior window. Value = actual amount that period."""
        result = []
        for data in sorted(year_comparison_rows, key=lambda r: r['sort_key'], reverse=True):
            prev = data.get(metric_key)
            if prev is None or (is_pct and prev == 0):
                continue
            plab = data.get('period_label', '')
            if is_pct:
                change = (current_val - prev) / prev * 100
                line = f"vs {plab}: {change:+.1f}%"
            elif is_currency:
                change = current_val - prev
                line = f"vs {plab}: £{change:+,.2f}"
            else:
                change = current_val - prev
                line = f"vs {plab}: {change:+,.0f}"
            # Format actual value for that year
            if is_currency or metric_key in ('net_sales', 'gross_sales', 'refunds', 'avg_transaction'):
                value_fmt = f"£{prev:,.2f}"
            else:
                value_fmt = f"{int(prev):,}"
            result.append((line, value_fmt))
        return result

    def _metric_card_html(label, value_fmt, delta_text=None, delta_positive=None, year_lines=None):
        """Build a full metric card as HTML so label, value, delta and year comparisons are all inside the box."""
        # When we have year comparisons, don't show the first entry (delta) - only show the block after the separation line
        delta_html = ""
        if delta_text and not year_lines:
            delta_color = "#28a745" if (delta_positive is True) else "#dc3545" if (delta_positive is False) else "#666"
            delta_html = f'<div style="font-size:0.85em;color:{delta_color};margin-top:2px">{delta_text}</div>'
        years_html = ""
        if year_lines:
            is_refund = "refund" in label.lower()
            rows = []
            for item in year_lines:
                line = item[0] if isinstance(item, tuple) else item
                value = item[1] if isinstance(item, tuple) else ""
                pos = ": +" in line or "£+" in line
                if not pos and (": -" in line or "£-" in line):
                    pos = False
                else:
                    pos = None if not pos else True
                if is_refund and pos is not None:
                    pos = not pos
                c = "#28a745" if pos is True else "#dc3545" if pos is False else "#666"
                row = f'<div style="display:flex;justify-content:space-between;align-items:center;margin:2px 0;gap:8px"><span style="color:{c}">{line}</span><span style="color:#333;font-weight:500">{value}</span></div>'
                rows.append(row)
            years_html = f'<div style="font-size:0.9em;line-height:1.4;margin-top:6px;padding-top:6px;border-top:1px solid #eee;overflow-wrap:break-word;word-break:break-word">{"".join(rows)}</div>'
        return f"""
        <div style="border:1px solid #e0e0e0;border-radius:8px;padding:12px;background:#fff;margin-bottom:8px;box-shadow:0 1px 2px rgba(0,0,0,0.05)">
            <div style="font-size:0.85em;color:#666">{label}</div>
            <div style="font-size:1.5em;font-weight:600">{value_fmt}</div>
            {delta_html}
            {years_html}
        </div>
        """
    
    # Calculate comparison metrics if employee is selected
    if selected_employee != 'All' and len(work_df) > len(filtered_sales) and start_date and end_date:
        # Get all data for comparison (same date range, all employees)
        comparison_sales = (
            _filter_sales_by_calendar_range(work_df, start_date, end_date)
            if (start_date and end_date)
            else work_df.copy()
        )
        
        comp_tx = comparison_sales['Transaction_Weight'].sum() if 'Transaction_Weight' in comparison_sales.columns else len(comparison_sales)
        all_avg_transaction = comparison_sales['Net_Sales'].sum() / comp_tx if comp_tx > 0 else 0
        all_total_sales = comparison_sales['Net_Sales'].sum()
        employee_share = (total_net_sales / all_total_sales * 100) if all_total_sales > 0 else 0
        
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        # Year comparisons (same employee, same period previous years)
        net_lines = _year_comparison_lines('net_sales', total_net_sales, is_pct=True)
        gross_lines = _year_comparison_lines('gross_sales', total_gross_sales, is_pct=True)
        tx_lines = _year_comparison_lines('transactions', total_transactions, is_pct=True)
        avg_lines = _year_comparison_lines('avg_transaction', avg_transaction, is_currency=True)
        ref_lines = _year_comparison_lines('refunds', total_refunds, is_currency=True)

        def _emp_metric(label, value_fmt, lines, delta_override=None):
            pos = None
            first = lines[0] if lines else None
            d = first[0] if isinstance(first, tuple) else first
            if d and "vs " in str(d):
                pos = ": +" in d or "£+" in d
                if not pos:
                    pos = False if (": -" in d or "£-" in d) else None
                if "refund" in label.lower() and pos is not None:
                    pos = not pos  # less refunds = good
            # Don't show first entry (delta) when we have year_lines - only show the block after separation line
            html = _metric_card_html(label, value_fmt, delta_text=None, delta_positive=pos, year_lines=lines)
            st.html(html)

        with col1:
            delta_override = f"{employee_share:.1f}% of total" if employee_share > 0 else None
            _emp_metric("Total Net Sales", f"£{total_net_sales:,.2f}", net_lines, delta_override)
        with col2:
            _emp_metric("Total Gross Sales", f"£{total_gross_sales:,.2f}", gross_lines)
        with col3:
            _emp_metric("Total Transactions", f"{total_transactions:,}", tx_lines)
        with col4:
            delta_override = None
            if avg_transaction - all_avg_transaction != 0 and all_avg_transaction > 0:
                d = avg_transaction - all_avg_transaction
                delta_override = f"-£{abs(d):,.2f}" if d < 0 else f"+£{d:,.2f}"
                delta_override = delta_override + " vs avg"
            _emp_metric("Avg Transaction", f"£{avg_transaction:,.2f}", avg_lines, delta_override)
        with col5:
            _emp_metric("Total Refunds", f"£{total_refunds:,.2f}", ref_lines)
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

        def _render_metric_with_years(label, value_fmt, metric_key, current_val, is_pct=False, is_currency=False, help_base="", show_year_comparisons=True):
            lines = _year_comparison_lines(metric_key, current_val, is_pct=is_pct, is_currency=is_currency) if show_year_comparisons else []
            first = lines[0] if lines else None
            d = first[0] if isinstance(first, tuple) else (str(first) if first else None)
            pos = None
            if d and isinstance(d, str) and "vs " in d:
                pos = ": +" in d or "£+" in d
                if not pos:
                    pos = False if (": -" in d or "£-" in d) else None
                if "refund" in label.lower() and pos is not None:
                    pos = not pos
            year_lines = lines if show_year_comparisons else None
            html = _metric_card_html(label, value_fmt, delta_text=None, delta_positive=pos, year_lines=year_lines)
            st.html(html)

        with col1:
            _render_metric_with_years("Total Net Sales", f"£{total_net_sales:,.2f}", 'net_sales', total_net_sales, is_pct=True, help_base="Net sales for the selected period.")
        with col2:
            _render_metric_with_years("Total Gross Sales", f"£{total_gross_sales:,.2f}", 'gross_sales', total_gross_sales, is_pct=True, help_base="Gross sales before refunds.")
        with col3:
            _render_metric_with_years("Total Transactions", f"{total_transactions:,}", 'transactions', total_transactions, is_pct=True, help_base="Number of transactions.")
        with col4:
            _render_metric_with_years("Avg Transaction", f"£{avg_transaction:,.2f}", 'avg_transaction', avg_transaction, is_currency=True, help_base="Average transaction value.")
        with col5:
            _render_metric_with_years("Total Refunds", f"£{total_refunds:,.2f}", 'refunds', total_refunds, is_currency=True, help_base="Total refund amount.")
        with col6:
            _render_metric_with_years("Active Employees", f"{unique_employees_count}", 'active_employees', unique_employees_count, show_year_comparisons=False)
        
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

    # Create tabs for different analyses
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
        "📅 Daily Trends",
        "📆 Day of Week",
        "👤 Employee Status",
        "👥 Employee Performance",
        "⏰ Hourly Patterns",
        "🛍️ Product Patterns",
        "🔮 Future Projections",
        "🏆 Best Team",
        "📈 Trends & Seasonality",
        "🏪 Shop Comparison",
        "🛒 Transaction Analytics",
        "🔍 Advanced Insights",
    ])

    # TAB 1: Daily Trends
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
            render_chart(fig)
        
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
            render_chart(fig)
        
        st.caption("📊 For best/worst day and monthly trends, see **Trends & Seasonality** tab.")

    # TAB 2: Day of Week
    with tab2:
        if selected_employee != 'All':
            st.header(f"📆 Day of Week Analysis - {selected_employee}")
        else:
            st.header("📆 Day of Week Analysis")

        st.caption(
            "Charts use your **filtered transactions**. "
            "**Weekdays in range** counts how many Mondays, Tuesdays, etc. fall inside the sidebar date range. "
            "**Avg net (per weekday day)** = total net on that weekday ÷ that count (treats dates with no sales as £0)."
        )

        # Always derive from filtered_sales so date range, shop, and employee filters apply
        if len(filtered_sales) == 0:
            st.warning(f"No data available for {selected_employee if selected_employee != 'All' else 'the selected filters'}.")
        else:
            # Local frame only — do not assign to work_df (would shadow full shop data for later tabs)
            dow_df = filtered_sales.copy()

            # Ensure Day of Week column exists - calculate from Date if needed
            if 'Day of the Week' not in dow_df.columns or dow_df['Day of the Week'].isna().all():
                if 'Date' in dow_df.columns and dow_df['Date'].notna().any():
                    dow_df['Day of the Week'] = dow_df['Date'].dt.day_name()
                else:
                    st.error("No date data available to calculate day of week.")
                    st.stop()

            day_col = 'Day of the Week'

            # Filter out rows with null day of week
            valid_sales = dow_df[dow_df[day_col].notna()].copy()

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

                wd_counts = _calendar_weekday_counts(start_date, end_date)
                if sum(wd_counts.values()) == 0 and valid_sales['Date'].notna().any():
                    wd_counts = _calendar_weekday_counts(
                        valid_sales['Date'].min().date(),
                        valid_sales['Date'].max().date(),
                    )
                day_sales_plot['Weekdays_In_Range'] = day_sales_plot['Day'].map(wd_counts).fillna(0).astype(int)
                day_sales_plot['Avg_Net_Per_Weekday'] = np.where(
                    day_sales_plot['Weekdays_In_Range'] > 0,
                    day_sales_plot['Net_Sales_Sum'] / day_sales_plot['Weekdays_In_Range'],
                    0.0,
                )
                day_sales_plot['Avg_Gross_Per_Weekday'] = np.where(
                    day_sales_plot['Weekdays_In_Range'] > 0,
                    day_sales_plot['Gross_Sales_Sum'] / day_sales_plot['Weekdays_In_Range'],
                    0.0,
                )

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
                    render_chart(fig)

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
                    render_chart(fig)

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
                    render_chart(fig)

                with col2:
                    title = (
                        f'Avg net per calendar day - {selected_employee}'
                        if selected_employee != 'All'
                        else 'Average net per calendar day (÷ weekdays in range)'
                    )
                    st.subheader("Average net per calendar day")
                    fig = px.bar(
                        day_sales_plot,
                        x='Day',
                        y='Avg_Net_Per_Weekday',
                        labels={'Avg_Net_Per_Weekday': 'Avg net (£)', 'Day': 'Day of Week'},
                        color='Avg_Net_Per_Weekday',
                        color_continuous_scale='Teal',
                        title=title,
                    )
                    fig.update_layout(
                        height=400,
                        showlegend=False,
                        xaxis={'categoryorder': 'array', 'categoryarray': day_order},
                    )
                    render_chart(fig)

                st.subheader("Average gross per calendar day")
                fig_g = px.bar(
                    day_sales_plot,
                    x='Day',
                    y='Avg_Gross_Per_Weekday',
                    labels={'Avg_Gross_Per_Weekday': 'Avg gross (£)', 'Day': 'Day of Week'},
                    color='Avg_Gross_Per_Weekday',
                    color_continuous_scale='Purples',
                    title=(
                        f'Avg gross per calendar day - {selected_employee}'
                        if selected_employee != 'All'
                        else 'Average gross per calendar day (÷ weekdays in range)'
                    ),
                )
                fig_g.update_layout(
                    height=380,
                    showlegend=False,
                    xaxis={'categoryorder': 'array', 'categoryarray': day_order},
                )
                render_chart(fig_g)

                st.subheader("Weekday detail table")
                display_df = day_sales_plot.copy()
                display_df['Total_Net'] = display_df['Net_Sales_Sum'].apply(lambda x: f"£{x:,.2f}")
                display_df['Total_Gross'] = display_df['Gross_Sales_Sum'].apply(lambda x: f"£{x:,.2f}")
                display_df['Avg_Net_Per_Day'] = display_df['Avg_Net_Per_Weekday'].apply(lambda x: f"£{x:,.2f}")
                display_df['Avg_Gross_Per_Day'] = display_df['Avg_Gross_Per_Weekday'].apply(lambda x: f"£{x:,.2f}")
                display_df['Avg_Ticket'] = display_df['Net_Sales_Mean'].apply(lambda x: f"£{x:,.2f}")
                display_df['Std_Dev_Ticket'] = display_df['Net_Sales_Std'].apply(
                    lambda x: f"£{x:,.2f}" if pd.notna(x) and x > 0 else "N/A"
                )
                display_df = display_df[
                    [
                        'Day',
                        'Weekdays_In_Range',
                        'Total_Net',
                        'Total_Gross',
                        'Avg_Net_Per_Day',
                        'Avg_Gross_Per_Day',
                        'Transaction_Count',
                        'Avg_Ticket',
                        'Std_Dev_Ticket',
                    ]
                ]
                display_df.columns = [
                    'Day',
                    'Weekdays in range',
                    'Total net',
                    'Total gross',
                    'Avg net / that weekday',
                    'Avg gross / that weekday',
                    'Transactions',
                    'Average £ per sale',
                    'Variation in sale amounts',
                ]
                st.dataframe(display_df, width="stretch", hide_index=True)
            else:
                st.warning(f"No valid day of week data found for {selected_employee if selected_employee != 'All' else 'the selected filters'}. Found {len(dow_df)} total rows but none with valid day of week.")
    
    # TAB 3: Employee Status
    with tab3:
        _render_employee_status_tab(unique_employees_all)

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
                comparison_sales = (
                    _filter_sales_by_calendar_range(work_df, start_date, end_date)
                    if (start_date and end_date)
                    else work_df.copy()
                )
                
                if len(comparison_sales) > len(filtered_sales):
                    st.subheader("📈 Performance Comparison")
                    comp_col1, comp_col2, comp_col3 = st.columns(3)
                    comp_emp_col = 'Commission_Employee' if 'Commission_Employee' in comparison_sales.columns else 'Employee'
                    all_avg_sale = comparison_sales['Net_Sales'].mean()
                    all_total = comparison_sales['Net_Sales'].sum()
                    all_employee_count = comparison_sales[comp_emp_col].nunique()
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
                        # Rank among all employees (by commission attribution)
                        employee_totals = comparison_sales.groupby(comp_emp_col)['Net_Sales'].sum().sort_values(ascending=False)
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
                        render_chart(fig)
                
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
                render_chart(fig)
                
        else:
            st.header("👥 Employee Performance Analysis")
        
        if employee_df_display is not None:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Top Employees by Total Sales")
                top_employees = employee_df_display.nlargest(15, 'Net_Sales_Sum')
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
                render_chart(fig)
            
            with col2:
                st.subheader("Top Employees by Average Transaction")
                top_avg = employee_df_display[employee_df_display['Transaction_Count'] >= 10].nlargest(15, 'Net_Sales_Mean')
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
                render_chart(fig)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Transaction Volume by Employee")
                top_volume = employee_df_display.nlargest(15, 'Transaction_Count')
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
                render_chart(fig)
            
            with col2:
                st.subheader("Refund Rate Analysis")
                refund_analysis = employee_df_display[employee_df_display['Refund_Rate'] > 0].sort_values('Refund_Rate', ascending=False)
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
                    render_chart(fig)
                else:
                    st.info("No refunds recorded for any employees")
            
            st.subheader("Complete Employee Performance Table")
            export_df = employee_df_display.sort_values('Net_Sales_Sum', ascending=False).copy()
            export_df = export_df.rename(columns={
                'Net_Sales_Sum': 'Total Net Sales',
                'Net_Sales_Mean': 'Average Sale',
                'Transaction_Count': 'Transaction Count',
                'Gross_Sales_Sum': 'Total Gross Sales',
                'Refunds_Sum': 'Refunds Sum',
                'Refund_Rate': 'Refund Rate',
            })
            export_df = export_df[['Employee', 'Total Net Sales', 'Average Sale', 'Transaction Count', 'Total Gross Sales', 'Refunds Sum', 'Refund Rate']]
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
            st.dataframe(display_df, width="stretch", hide_index=True, height=400)
    
    # TAB 5: Hourly Patterns
    with tab5:
        if selected_employee != 'All':
            st.header(f"⏰ Hourly Sales Patterns - {selected_employee}")
        else:
            st.header("⏰ Hourly Sales Patterns")

        # Always derive from filtered_sales (date range, shop, employee, active/inactive)
        hourly_sales = _compute_hourly_from_sales(filtered_sales)
        if hourly_sales is not None and len(hourly_sales) > 0:
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
                render_chart(fig)

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
                render_chart(fig)

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
                render_chart(fig)

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

    # TAB 6: Product Patterns
    with tab6:
        if selected_employee != 'All':
            st.header(f"🛍️ Product Patterns - {selected_employee}")
        else:
            st.header("🛍️ Product Patterns Analysis")

        if start_date is not None and end_date is not None:
            st.caption(f"Product totals use transactions from **{start_date.strftime('%b %d, %Y')}** to **{end_date.strftime('%b %d, %Y')}** (same as sidebar).")
        else:
            st.caption("Product totals use **all available dates** (no date column or range).")
        st.caption(
            "Volume bars: **each product’s share of row Net_Sales** (qty × list unit price weights). "
            "**Transaction count** chart = **distinct till sales** (same sale with split commission counts once). "
            "The table also shows **weighted** slices (commission × line share) for analysts."
        )

        product_source = _filter_sales_by_calendar_range(filtered_sales, start_date, end_date)
        _pk = f"p6_{start_date}_{end_date}_{selected_shop}_{selected_employee}"

        if 'Products' not in product_source.columns:
            st.info("Product data not available in the sales data.")
        else:
            product_df_filtered = _compute_product_from_sales(product_source)
            if product_df_filtered is not None and len(product_df_filtered) > 0:
                net_in_view = float(product_source['Net_Sales'].sum()) if 'Net_Sales' in product_source.columns else 0.0
                attrib_all = float(product_df_filtered['Total_Sales'].sum())
                gap = net_in_view - attrib_all
                if net_in_view != 0:
                    st.caption(
                        f"**Sanity check:** Sum of attributed product totals **£{attrib_all:,.2f}** vs **net sales in this view "
                        f"£{net_in_view:,.2f}** ({100 * attrib_all / net_in_view:.0f}% matched). "
                        f"Difference **£{gap:,.2f}** is from rows with no parseable priced lines, empty **Products**, or "
                        f"attribution dropped when a SKU’s net share is negative."
                    )
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
                            labels={'Total_Sales': 'Attributed net (£)'},
                            color='Total_Sales',
                            color_continuous_scale='Blues',
                            title=title
                        )
                        fig.update_layout(height=600, showlegend=False, xaxis_tickformat=".2f")
                        render_chart(fig, key=f"{_pk}_vol")
                    else:
                        st.info("No product data available for the selected filters.")

                with col2:
                    title = f'Top Products by Count - {selected_employee}' if selected_employee != 'All' else 'Top 20 Products by Transaction Count'
                    st.subheader("Top Products by Transaction Count")
                    top_count = product_df_filtered.nlargest(20, 'Distinct_Tx')
                    if len(top_count) > 0:
                        fig = px.bar(
                            top_count,
                            x='Distinct_Tx',
                            y='Product',
                            orientation='h',
                            labels={'Distinct_Tx': 'Distinct sales (#)'},
                            color='Distinct_Tx',
                            color_continuous_scale='Greens',
                            title=title
                        )
                        fig.update_layout(height=600, showlegend=False, xaxis_tickformat="d")
                        render_chart(fig, key=f"{_pk}_cnt")
                    else:
                        st.info("No product data available for the selected filters.")

                col1, col2 = st.columns(2)

                with col1:
                    title = f'Top Products by Avg Sale - {selected_employee}' if selected_employee != 'All' else 'Top Products by Average Sale Value'
                    st.subheader("Top Products by Average Sale Value")
                    top_avg = product_df_filtered[product_df_filtered['Distinct_Tx'] > 0].nlargest(20, 'Avg_Sale')
                    if len(top_avg) > 0:
                        fig = px.bar(
                            top_avg,
                            x='Avg_Sale',
                            y='Product',
                            orientation='h',
                            labels={'Avg_Sale': 'Avg attributed net / distinct sale (£)'},
                            color='Avg_Sale',
                            color_continuous_scale='Oranges',
                            title=title
                        )
                        fig.update_layout(height=600, showlegend=False, xaxis_tickformat=".2f")
                        render_chart(fig, key=f"{_pk}_avg")
                    else:
                        st.info("No product data available for the selected filters.")

                with col2:
                    st.subheader("Product Performance Summary")
                    display_df = product_df_filtered.head(30)[['Product', 'Total_Sales', 'Distinct_Tx', 'Weighted_Tx', 'Avg_Sale']].copy()
                    display_df['Total_Sales'] = display_df['Total_Sales'].apply(lambda x: f"£{x:,.2f}")
                    display_df['Distinct_Tx'] = display_df['Distinct_Tx'].apply(lambda x: f"{int(x):,}")
                    display_df['Weighted_Tx'] = display_df['Weighted_Tx'].apply(lambda x: f"{float(x):.2f}")
                    display_df['Avg_Sale'] = display_df['Avg_Sale'].apply(lambda x: f"£{x:,.2f}")
                    display_df.columns = ['Product', 'Total Sales', 'Sales (#)', 'Weighted tx', 'Avg per sale']
                    st.dataframe(display_df, width="stretch", hide_index=True, height=600)
            else:
                st.info("No product data available in the filtered data.")

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
            render_chart(fig)
            
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
            render_chart(fig)
            
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
            st.dataframe(forecast_display, width="stretch", hide_index=True)
            
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

    # TAB 8: Best Team
    with tab8:
        best_team_emp_col = 'Commission_Employee' if 'Commission_Employee' in work_df.columns else 'Employee'
        if start_date is not None and end_date is not None:
            best_team_df = _filter_sales_by_calendar_range(work_df, start_date, end_date)
        else:
            best_team_df = work_df.copy()
        active_only = best_team_df[best_team_df[best_team_emp_col].isin(active_employees)] if active_employees else best_team_df
        if len(active_only) == 0:
            st.warning("No active employees in the selected date range. Mark employees as active in the Employee Status tab or widen the date range.")
        else:
            _render_best_team_tab(work_df, start_date, end_date, active_employees)

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
                    render_chart(fig)
                with col2:
                    if monthly['MoM_Change'].notna().any():
                        fig = px.line(monthly, x='Month', y='MoM_Change', markers=True, labels={'MoM_Change': 'MoM % Change'}, title='Month-over-Month % Change')
                        fig.add_hline(y=0, line_dash="dash", line_color="gray")
                        fig.update_layout(height=350)
                        render_chart(fig)
                st.dataframe(monthly[['Month', 'Net_Sales', 'Transactions', 'Avg_Sale', 'MoM_Change', 'YoY_Change']].round(2), width="stretch", hide_index=True)
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
                render_chart(fig)
            with st.expander("📅 Seasonality", expanded=False):
                seas_df = filtered_sales.copy()
                if 'Day of the Week' not in seas_df.columns or seas_df['Day of the Week'].isna().all():
                    seas_df['Day of the Week'] = pd.to_datetime(seas_df['Date'], errors='coerce').dt.day_name()
                monthly_by_dow = seas_df.groupby([seas_df['Date'].dt.to_period('M'), 'Day of the Week'])['Net_Sales'].sum().reset_index()
                monthly_by_dow['Month'] = monthly_by_dow['Date'].astype(str)
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                fig = px.bar(monthly_by_dow, x='Month', y='Net_Sales', color='Day of the Week', labels={'Net_Sales': 'Net Sales (£)'}, title='Monthly Sales by Day of Week', color_discrete_sequence=CHART_COLORWAY)
                fig.update_layout(height=400, barmode='stack')
                render_chart(fig)

    # TAB 10: Shop Comparison
    with tab10:
        st.header("🏪 Shop Comparison")
        if 'Shop' not in sales_df.columns or sales_df['Shop'].nunique() < 2:
            st.info("Shop comparison requires data from multiple shops. Select 'All Shops' in the sidebar to see this analysis.")
        else:
            compare_df = (
                _filter_sales_by_calendar_range(work_df, start_date, end_date)
                if (start_date and end_date)
                else work_df.copy()
            )
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
                    render_chart(fig)
                with col2:
                    fig = px.bar(sm, x='Shop', y='Avg Sale', color='Shop', labels={'Avg Sale': 'Avg Transaction (£)'}, title='Average Transaction by Shop')
                    fig.update_layout(showlegend=False, height=350, yaxis_tickformat=".2f")
                    render_chart(fig)
                st.dataframe(sm, width="stretch", hide_index=True, column_config={
                    'Net Sales': st.column_config.NumberColumn('Net Sales (£)', format='£%.2f'),
                    'Avg Sale': st.column_config.NumberColumn('Avg Sale (£)', format='£%.2f'),
                    'Refunds': st.column_config.NumberColumn('Refunds (£)', format='£%.2f'),
                })
                monthly_by_shop = compare_df.groupby([compare_df['Date'].dt.to_period('M'), 'Shop'])['Net_Sales'].sum().reset_index()
                monthly_by_shop['Month'] = monthly_by_shop['Date'].astype(str)
                fig = px.line(monthly_by_shop, x='Month', y='Net_Sales', color='Shop', markers=True, labels={'Net_Sales': 'Net Sales (£)'}, title='Monthly Trend by Shop')
                fig.update_layout(height=400)
                render_chart(fig)

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
                        render_chart(fig)
                    with col2:
                        basket_emp_col = 'Commission_Employee' if 'Commission_Employee' in tx_df.columns else 'Employee'
                        by_emp = tx_df.groupby(basket_emp_col)['Items_Count'].mean().reset_index().rename(columns={basket_emp_col: 'Employee'}).sort_values('Items_Count', ascending=False).head(15)
                        if len(by_emp) > 0:
                            fig = px.bar(by_emp, x='Items_Count', y='Employee', orientation='h', labels={'Items_Count': 'Avg Items'}, title='Avg Basket Size by Employee (by commission)')
                            fig.update_layout(height=350, xaxis_tickformat=".2f")
                            render_chart(fig)
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
                render_chart(fig)
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
                            render_chart(fig)
                        with col2:
                            if 'Hour' in refunds.columns and refunds['Hour'].notna().any():
                                refund_by_hour = refunds.groupby('Hour')['Refunds'].sum().abs().reset_index()
                                fig = px.bar(refund_by_hour, x='Hour', y='Refunds', labels={'Refunds': 'Refunds (£)'}, title='Refunds by Hour of Day')
                                fig.update_layout(height=350, yaxis_tickformat=".2f")
                                render_chart(fig)
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
                                st.dataframe(rp_df, width="stretch", hide_index=True)
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
            adv_calendar_sales = _filter_sales_by_calendar_range(filtered_sales, start_date, end_date)
            with st.expander("🛍️ Product Mix & Share", expanded=True):
                product_mix_df = _compute_product_from_sales(adv_calendar_sales)
                if product_mix_df is not None and len(product_mix_df) > 0:
                    top = product_mix_df.head(15)
                    top['Share_%'] = top['Total_Sales'] / top['Total_Sales'].sum() * 100
                    fig = px.pie(top, values='Share_%', names='Product', title='Product Mix (Top 15)', color_discrete_sequence=CHART_COLORWAY)
                    fig.update_layout(height=400)
                    fig.update_traces(textinfo='percent+label', texttemplate='%{percent:.2%}')
                    render_chart(fig, key=f"mix_{start_date}_{end_date}_{selected_shop}_{selected_employee}")
                else:
                    st.info("No product data available.")
            with st.expander("👤 Product-Employee Affinity", expanded=True):
                aff_emp_col = 'Commission_Employee' if 'Commission_Employee' in filtered_sales.columns else 'Employee'
                if 'Products' in filtered_sales.columns and aff_emp_col in filtered_sales.columns:
                    emp_product_sales = {}
                    for _, row in adv_calendar_sales.iterrows():
                        emp = row.get(aff_emp_col)
                        ps = row.get('Products', '')
                        if pd.isna(emp) or pd.isna(ps) or not isinstance(ps, str):
                            continue
                        lines = _parse_positive_product_lines(ps)
                        weighted = []
                        for name, qty, unit_p in lines:
                            lw = float(qty) * unit_p
                            if lw > 0:
                                weighted.append((name, lw))
                        if not weighted:
                            continue
                        S = sum(lw for _, lw in weighted)
                        if S <= 0:
                            continue
                        try:
                            net = float(row.get('Net_Sales', 0) or 0)
                        except (TypeError, ValueError):
                            net = 0.0
                        for name, lw in weighted:
                            key = (emp, name)
                            emp_product_sales[key] = emp_product_sales.get(key, 0) + net * (lw / S)
                    if emp_product_sales:
                        ep_df = pd.DataFrame([{'Employee': k[0], 'Product': k[1], 'Sales': v} for k, v in emp_product_sales.items()])
                        top_combos = ep_df.nlargest(20, 'Sales')
                        fig = px.bar(top_combos, x='Sales', y='Product', color='Employee', orientation='h', labels={'Sales': 'Sales (£)'}, title='Top Product-Employee Combinations')
                        fig.update_layout(height=500, barmode='stack', xaxis_tickformat=".2f")
                        render_chart(fig)
                    else:
                        st.info("No product-employee data.")
                else:
                    st.info("Products and Employee columns required.")
            with st.expander("📊 Employee Consistency", expanded=True):
                adv_emp_col = 'Commission_Employee' if 'Commission_Employee' in filtered_sales.columns else 'Employee'
                if employee_df is not None and adv_emp_col in filtered_sales.columns:
                    emp_daily = filtered_sales.groupby([adv_emp_col, filtered_sales['Date'].dt.date])['Net_Sales'].sum().reset_index()
                    emp_std = emp_daily.groupby(adv_emp_col)['Net_Sales'].agg(['mean', 'std', 'count']).reset_index()
                    emp_std = emp_std.rename(columns={adv_emp_col: 'Employee'})
                    emp_std = emp_std[emp_std['count'] >= 5]
                    emp_std['CV'] = np.where(emp_std['mean'] > 0, emp_std['std'] / emp_std['mean'] * 100, 0)
                    emp_std = emp_std.sort_values('CV')
                    if len(emp_std) > 0:
                        st.caption("Most consistent = lowest coefficient of variation (CV). Lower CV = more predictable daily performance.")
                        fig = px.bar(emp_std.head(15), x='Employee', y='CV', labels={'CV': 'CV %'}, title='Employee Consistency (Lower = More Consistent)')
                        fig.update_layout(height=350, yaxis_tickformat=".2f")
                        render_chart(fig)
                        st.dataframe(emp_std[['Employee', 'mean', 'std', 'CV']].round(2), width="stretch", hide_index=True)
                else:
                    st.info("Need employee data.")
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
                            render_chart(fig)
                            st.dataframe(anomalies[['Date', 'Net_Sales', 'Z_Score']].round(2), width="stretch", hide_index=True)
                        else:
                            st.info("No significant anomalies detected (Z-score > 2).")
                    else:
                        st.info("Insufficient variance for anomaly detection.")
                else:
                    st.info("Need at least 7 days of data for anomaly detection.")

if __name__ == "__main__":
    main()