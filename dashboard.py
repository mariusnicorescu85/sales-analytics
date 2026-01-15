import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
import warnings
import os
warnings.filterwarnings('ignore')

# Try to import Airtable (optional)
try:
    from pyairtable import Api
    AIRTABLE_AVAILABLE = True
except ImportError:
    AIRTABLE_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="Sales Dashboard - Complete Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #667eea;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_employee_data():
    """Load employee performance data"""
    try:
        df = pd.read_csv('employee_performance_analysis.csv', skiprows=2)
        df.columns = ['Employee', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 
                     'Gross_Sales_Sum', 'Refunds_Sum', 'Refund_Rate']
        df = df[df['Employee'].notna() & (df['Employee'] != '')]
        numeric_cols = ['Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 
                       'Gross_Sales_Sum', 'Refunds_Sum', 'Refund_Rate']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error loading employee data: {e}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_sales_data():
    """Load sales transaction data - handles any date range and data size"""
    try:
        df = pd.read_csv('Opatra Sales from July 2023-Grid view.csv')
        
        def clean_currency(value):
            if pd.isna(value):
                return 0
            if isinstance(value, str):
                return float(value.replace('£', '').replace(',', '').strip() or 0)
            return float(value) if value else 0
        
        df['Net_Sales'] = df['Net Sales'].apply(clean_currency)
        df['Gross_Sales'] = df['Gross Sales'].apply(clean_currency)
        df['Refunds'] = df['Refunds'].apply(clean_currency)
        
        # Try multiple date formats to handle different date formats
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
        # If that fails, try other common formats
        if df['Date'].isna().any():
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        df = df[df['Date'].notna()]
        df = df[df['Net_Sales'] > 0]
        
        # Extract time components
        if 'Time' in df.columns:
            df['Time_Parsed'] = pd.to_datetime(df['Time'], errors='coerce')
            df['Hour'] = df['Time_Parsed'].dt.hour
            df['Day_of_Week'] = df['Day of the Week']
        
        return df
    except Exception as e:
        st.error(f"Error loading sales data: {e}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_day_of_week_analysis():
    """Load day of week analysis data"""
    try:
        df = pd.read_csv('day_of_week_analysis.csv', skiprows=2)
        df.columns = ['Day', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Net_Sales_Std', 'Gross_Sales_Sum']
        df = df[df['Day'].notna() & (df['Day'] != '')]
        numeric_cols = ['Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Net_Sales_Std', 'Gross_Sales_Sum']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except:
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_hourly_analysis():
    """Load hourly patterns analysis data"""
    try:
        df = pd.read_csv('hourly_patterns_analysis.csv', skiprows=2)
        df.columns = ['Hour', 'Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Gross_Sales_Sum']
        df = df[df['Hour'].notna()]
        df['Hour'] = pd.to_numeric(df['Hour'], errors='coerce')
        numeric_cols = ['Net_Sales_Sum', 'Net_Sales_Mean', 'Transaction_Count', 'Gross_Sales_Sum']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except:
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour, then refresh
def load_product_analysis():
    """Load product patterns analysis data"""
    try:
        df = pd.read_csv('product_patterns_analysis.csv', skiprows=1)
        df.columns = ['Index', 'Product', 'Total_Sales', 'Count', 'Avg_Sale']
        df = df[df['Product'].notna() & (df['Product'] != '')]
        numeric_cols = ['Total_Sales', 'Count', 'Avg_Sale']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        # Filter out negative/zero sales
        df = df[df['Total_Sales'] > 0]
        return df
    except:
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
    st.markdown('<div class="main-header">📊 Complete Sales Analytics Dashboard</div>', unsafe_allow_html=True)
    
    # Load all data
    employee_df = load_employee_data()
    sales_df = load_sales_data()
    day_of_week_df = load_day_of_week_analysis()
    hourly_df = load_hourly_analysis()
    product_df = load_product_analysis()
    
    if sales_df is None:
        st.error("Could not load sales data. Please ensure the CSV files are in the same directory.")
        return
    
    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    
    # Airtable Sync Section (if available)
    if AIRTABLE_AVAILABLE:
        with st.sidebar.expander("☁️ Sync from Airtable", expanded=False):
            st.write("**Sync latest data from Airtable**")
            
            airtable_token = st.text_input(
                "Airtable Token",
                type="password",
                help="Your Airtable Personal Access Token",
                key="airtable_token"
            )
            
            base_id = st.text_input(
                "Base ID",
                value=os.getenv('AIRTABLE_BASE_ID', ''),
                help="Your Airtable Base ID (e.g., appFM5cdHTTI8IugV)",
                key="base_id"
            )
            
            table_name = st.text_input(
                "Table Name",
                value="Opatra Sales from July 2023",
                help="Name of the Airtable table",
                key="table_name"
            )
            
            if st.button("🔄 Sync from Airtable", key="sync_airtable"):
                if airtable_token and base_id and table_name:
                    with st.spinner("Syncing data from Airtable..."):
                        try:
                            api = Api(airtable_token)
                            table = api.table(base_id, table_name)
                            
                            all_records = []
                            for page in table.iterate():
                                all_records.extend(page)
                            
                            if all_records:
                                records_data = []
                                for record in all_records:
                                    record_dict = record['fields'].copy()
                                    records_data.append(record_dict)
                                
                                df = pd.DataFrame(records_data)
                                
                                # Save to CSV
                                csv_path = 'Opatra Sales from July 2023-Grid view.csv'
                                df.to_csv(csv_path, index=False)
                                
                                st.success(f"✅ Synced {len(df)} records from Airtable!")
                                st.info("Click 'Refresh Data' below to load the new data")
                                
                                # Clear cache to force reload
                                st.cache_data.clear()
                            else:
                                st.warning("No records found in Airtable")
                        except Exception as e:
                            st.error(f"❌ Error syncing: {str(e)}")
                            st.info("Check your token, base ID, and table name")
                else:
                    st.warning("Please fill in all Airtable connection details")
            
            st.caption("💡 Get your token from: https://airtable.com/create/tokens")
    
    # Refresh data button
    if st.sidebar.button("🔄 Refresh Data", help="Click to reload data from CSV files (useful after adding new data)"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.caption("💡 **Tip:** After adding new data to CSV files, click 'Refresh Data' to see updates")
    
    all_employees = ['All'] + sorted(sales_df['Employee'].dropna().unique().tolist())
    selected_employee = st.sidebar.selectbox("Select Employee", all_employees)
    
    if sales_df['Date'].notna().any():
        min_date = sales_df['Date'].min().date()
        max_date = sales_df['Date'].max().date()
        
        # Quick date range presets
        st.sidebar.subheader("📅 Date Range")
        use_preset = st.sidebar.radio(
            "Quick Select",
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Last Year", "Custom Range"],
            index=0
        )
        
        if use_preset == "All Time":
            start_date = min_date
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
        
        filtered_sales = sales_df[
            (sales_df['Date'].dt.date >= start_date) & 
            (sales_df['Date'].dt.date <= end_date)
        ]
        
        # Display selected range
        st.sidebar.caption(f"📆 {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}")
    else:
        filtered_sales = sales_df
    
    if selected_employee != 'All':
        filtered_sales = filtered_sales[filtered_sales['Employee'] == selected_employee]
    
    # Employee-specific header
    if selected_employee != 'All' and len(filtered_sales) > 0:
        st.info(f"👤 **Viewing analytics for: {selected_employee}** | 📅 **Date Range:** {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')} | 📊 **{len(filtered_sales):,} transactions**")
    
    # Information about adding new data
    with st.sidebar.expander("ℹ️ Adding New Data"):
        st.write("""
        **Yes, the dashboard will work with new data!**
        
        **To add new sales data:**
        1. Add new rows to `Opatra Sales from July 2023-Grid view.csv`
        2. Keep the same column structure
        3. Dates can be in format: DD/MM/YYYY
        4. Click "🔄 Refresh Data" button above
        
        **Supported date formats:**
        - DD/MM/YYYY (e.g., 15/01/2026)
        - Other common formats are auto-detected
        
        **The dashboard will automatically:**
        - ✅ Handle any date range
        - ✅ Process any number of transactions
        - ✅ Include new employees/products
        - ✅ Update all charts and metrics
        - ✅ Adjust forecasts based on new data
        
        **Note:** Data is cached for 1 hour. Use "Refresh Data" to see updates immediately.
        """)
    
    # Key Metrics
    if selected_employee != 'All':
        st.header(f"📈 Performance Metrics - {selected_employee}")
    else:
        st.header("📈 Key Metrics")
    
    # Calculate metrics
    total_net_sales = filtered_sales['Net_Sales'].sum()
    total_gross_sales = filtered_sales['Gross_Sales'].sum()
    total_transactions = len(filtered_sales)
    avg_transaction = total_net_sales / total_transactions if total_transactions > 0 else 0
    total_refunds = abs(filtered_sales['Refunds'].sum())
    unique_employees = filtered_sales['Employee'].nunique()
    
    # Calculate comparison metrics if employee is selected
    if selected_employee != 'All' and len(sales_df) > len(filtered_sales):
        # Get all data for comparison (same date range, all employees)
        comparison_sales = sales_df[
            (sales_df['Date'].dt.date >= start_date) & 
            (sales_df['Date'].dt.date <= end_date)
        ] if sales_df['Date'].notna().any() else sales_df
        
        all_avg_transaction = comparison_sales['Net_Sales'].sum() / len(comparison_sales) if len(comparison_sales) > 0 else 0
        all_total_sales = comparison_sales['Net_Sales'].sum()
        employee_share = (total_net_sales / all_total_sales * 100) if all_total_sales > 0 else 0
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            delta = total_net_sales - (all_total_sales / comparison_sales['Employee'].nunique()) if comparison_sales['Employee'].nunique() > 0 else None
            st.metric("Total Net Sales", f"£{total_net_sales:,.2f}", 
                     delta=f"{employee_share:.1f}% of total" if employee_share > 0 else None)
        with col2:
            st.metric("Total Gross Sales", f"£{total_gross_sales:,.2f}")
        with col3:
            st.metric("Total Transactions", f"{total_transactions:,}")
        with col4:
            delta = avg_transaction - all_avg_transaction if all_avg_transaction > 0 else None
            delta_str = f"£{delta:,.2f} vs avg" if delta is not None and delta != 0 else None
            st.metric("Avg Transaction", f"£{avg_transaction:,.2f}", delta=delta_str)
        with col5:
            refund_rate = (total_refunds / total_gross_sales * 100) if total_gross_sales > 0 else 0
            st.metric("Refund Rate", f"{refund_rate:.2f}%")
        with col6:
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
            st.metric("Total Net Sales", f"£{total_net_sales:,.2f}")
        with col2:
            st.metric("Total Gross Sales", f"£{total_gross_sales:,.2f}")
        with col3:
            st.metric("Total Transactions", f"{total_transactions:,}")
        with col4:
            st.metric("Avg Transaction", f"£{avg_transaction:,.2f}")
        with col5:
            st.metric("Total Refunds", f"£{total_refunds:,.2f}")
        with col6:
            st.metric("Active Employees", f"{unique_employees}")
    
    st.divider()
    
    # Create tabs for different analyses
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📅 Daily Trends", 
        "📆 Day of Week Analysis", 
        "👥 Employee Performance", 
        "⏰ Hourly Patterns", 
        "🛍️ Product Patterns", 
        "🔮 Future Projections"
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
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
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
                title='Moving Averages',
                xaxis_title='Date',
                yaxis_title='Net Sales (£)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Daily Statistics")
            st.write(f"**Average Daily Sales:** £{daily_sales['Net_Sales'].mean():,.2f}")
            st.write(f"**Best Day:** {daily_sales.loc[daily_sales['Net_Sales'].idxmax(), 'Date'].strftime('%Y-%m-%d')} - £{daily_sales['Net_Sales'].max():,.2f}")
            st.write(f"**Worst Day:** {daily_sales.loc[daily_sales['Net_Sales'].idxmin(), 'Date'].strftime('%Y-%m-%d')} - £{daily_sales['Net_Sales'].min():,.2f}")
            st.write(f"**Standard Deviation:** £{daily_sales['Net_Sales'].std():,.2f}")
        
        with col2:
            st.subheader("Monthly Comparison")
            monthly_comparison = filtered_sales.groupby(filtered_sales['Date'].dt.to_period('M'))['Net_Sales'].sum()
            monthly_comparison.index = monthly_comparison.index.astype(str)
            
            fig = px.bar(
                x=monthly_comparison.index,
                y=monthly_comparison.values,
                labels={'x': 'Month', 'y': 'Net Sales (£)'},
                title='Monthly Sales Comparison'
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    # TAB 2: Day of Week Analysis
    with tab2:
        if selected_employee != 'All':
            st.header(f"📆 Day of Week Analysis - {selected_employee}")
        else:
            st.header("📆 Day of Week Analysis")
        
        if day_of_week_df is not None:
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
                st.plotly_chart(fig, use_container_width=True)
            
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
                st.plotly_chart(fig, use_container_width=True)
            
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
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Day of Week Summary Table")
                display_df = day_of_week_df_ordered.reset_index()
                display_df['Net_Sales_Sum'] = display_df['Net_Sales_Sum'].apply(lambda x: f"£{x:,.2f}")
                display_df['Net_Sales_Mean'] = display_df['Net_Sales_Mean'].apply(lambda x: f"£{x:,.2f}")
                display_df.columns = ['Day', 'Total Sales', 'Avg Sale', 'Transactions', 'Std Dev', 'Gross Sales']
                st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            # Fallback to calculated data
            st.subheader("Sales by Day of Week")
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_sales = filtered_sales.groupby('Day of the Week')['Net_Sales'].agg(['sum', 'mean', 'count'])
            day_sales = day_sales.reindex([d for d in day_order if d in day_sales.index])
            
            fig = px.bar(
                x=day_sales.index,
                y=day_sales['sum'],
                labels={'x': 'Day of Week', 'y': 'Total Net Sales (£)'},
                title='Total Sales by Day of Week'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    # TAB 3: Employee Performance
    with tab3:
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
                comparison_sales = sales_df[
                    (sales_df['Date'].dt.date >= start_date) & 
                    (sales_df['Date'].dt.date <= end_date)
                ] if sales_df['Date'].notna().any() else sales_df
                
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
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                
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
                st.plotly_chart(fig, use_container_width=True)
                
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
                fig.update_layout(height=500, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
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
                fig.update_layout(height=500, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
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
                fig.update_layout(height=500, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
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
                    fig.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No refunds recorded for any employees")
            
            st.subheader("Complete Employee Performance Table")
            display_df = employee_df.sort_values('Net_Sales_Sum', ascending=False).copy()
            display_df['Net_Sales_Sum'] = display_df['Net_Sales_Sum'].apply(lambda x: f"£{x:,.2f}")
            display_df['Net_Sales_Mean'] = display_df['Net_Sales_Mean'].apply(lambda x: f"£{x:,.2f}")
            display_df['Gross_Sales_Sum'] = display_df['Gross_Sales_Sum'].apply(lambda x: f"£{x:,.2f}")
            display_df['Refund_Rate'] = display_df['Refund_Rate'].apply(lambda x: f"{x:.2f}%")
            display_df['Transaction_Count'] = display_df['Transaction_Count'].apply(lambda x: f"{int(x):,}")
            
            display_df.columns = ['Employee', 'Total Net Sales', 'Average Sale', 'Transaction Count', 
                                'Total Gross Sales', 'Refunds Sum', 'Refund Rate']
            
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)
    
    # TAB 4: Hourly Patterns
    with tab4:
        if selected_employee != 'All':
            st.header(f"⏰ Hourly Sales Patterns - {selected_employee}")
        else:
            st.header("⏰ Hourly Sales Patterns")
        
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
                st.plotly_chart(fig, use_container_width=True)
            
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
                st.plotly_chart(fig, use_container_width=True)
            
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
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Peak Hours Analysis")
                peak_hours = hourly_df_sorted.nlargest(5, 'Net_Sales_Sum')
                st.write("**Top 5 Peak Sales Hours:**")
                for idx, row in peak_hours.iterrows():
                    hour_str = f"{int(row['Hour']):02d}:00"
                    st.write(f"**{hour_str}:** £{row['Net_Sales_Sum']:,.2f} ({int(row['Transaction_Count'])} transactions)")
        else:
            # Fallback to calculated data
            if 'Hour' in filtered_sales.columns:
                hourly_sales = filtered_sales.groupby('Hour')['Net_Sales'].agg(['sum', 'mean', 'count']).reset_index()
                hourly_sales = hourly_sales.sort_values('Hour')
                
                fig = px.bar(
                    hourly_sales,
                    x='Hour',
                    y='sum',
                    labels={'sum': 'Total Net Sales (£)', 'Hour': 'Hour of Day'},
                    title='Sales by Hour of Day'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Hourly data not available. Please ensure Time column is properly formatted.")
    
    # TAB 5: Product Patterns
    with tab5:
        if selected_employee != 'All':
            st.header(f"🛍️ Product Patterns - {selected_employee}")
        else:
            st.header("🛍️ Product Patterns Analysis")
        
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
                st.plotly_chart(fig, use_container_width=True)
            
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
                st.plotly_chart(fig, use_container_width=True)
            
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
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Product Performance Summary")
                display_df = product_df.nlargest(30, 'Total_Sales')[['Product', 'Total_Sales', 'Count', 'Avg_Sale']].copy()
                display_df['Total_Sales'] = display_df['Total_Sales'].apply(lambda x: f"£{x:,.2f}")
                display_df['Avg_Sale'] = display_df['Avg_Sale'].apply(lambda x: f"£{x:,.2f}")
                display_df.columns = ['Product', 'Total Sales', 'Transactions', 'Avg Sale']
                st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)
    
    # TAB 6: Future Projections
    with tab6:
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
            forecast_days = st.number_input("Days to Forecast", min_value=7, max_value=365, value=30, step=7)
        
        with col2:
            forecast_months = st.number_input("Months to Forecast", min_value=1, max_value=12, value=6, step=1)
        
        with col3:
            forecast_method = st.selectbox(
                "Forecast Method",
                ["moving_avg", "conservative", "exponential_smoothing"],
                index=0,
                format_func=lambda x: {
                    "moving_avg": "Moving Average (Recommended)",
                    "conservative": "Conservative (No Growth)",
                    "exponential_smoothing": "Exponential Smoothing"
                }[x]
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
            
            fig.update_layout(
                title=f'Daily Sales Forecast ({forecast_days} days) - {method_name}',
                xaxis_title='Date',
                yaxis_title='Net Sales (£)',
                height=500,
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
            
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
            
            fig.update_layout(
                title=f'Monthly Sales Forecast ({forecast_months} months) - {method_name}',
                xaxis_title='Month',
                yaxis_title='Net Sales (£)',
                height=500,
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
            
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

if __name__ == "__main__":
    main()