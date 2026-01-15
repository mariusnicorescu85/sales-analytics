# 📊 Sales Analytics Dashboard

A comprehensive Streamlit dashboard for analyzing sales data with interactive visualizations, employee performance metrics, and future projections.

## 🚀 Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the dashboard:**
   ```bash
   streamlit run dashboard.py
   ```
   
   Or double-click `run_dashboard.bat` on Windows

3. **Open in browser:**
   - The dashboard will automatically open at `http://localhost:8501`

## 📁 Required Files

The dashboard reads from these CSV files (should be in the same directory):

- `Opatra Sales from July 2023-Grid view.csv` - Main sales transaction data
- `employee_performance_analysis.csv` - Employee metrics (optional)
- `day_of_week_analysis.csv` - Day of week patterns (optional)
- `hourly_patterns_analysis.csv` - Hourly patterns (optional)
- `product_patterns_analysis.csv` - Product analysis (optional)

If optional files are missing, the dashboard will calculate them from the main sales data.

## ✨ Features

- 📅 **Daily Trends Analysis** - Sales trends over time with moving averages
- 📆 **Day of Week Analysis** - Performance by day of the week
- 👥 **Employee Performance** - Top performers, averages, and metrics
- ⏰ **Hourly Patterns** - Peak sales hours identification
- 🛍️ **Product Patterns** - Top products by sales volume
- 🔮 **Future Projections** - Sales forecasting with multiple methods
- ☁️ **Airtable Integration** - Sync data directly from Airtable
- 🔍 **Interactive Filters** - Filter by employee and date range

## 🌐 Deploy to Streamlit Cloud

See `DEPLOY_STREAMLIT_CLOUD.md` for detailed instructions.

**Quick steps:**
1. Push code to GitHub
2. Go to https://share.streamlit.io
3. Connect your repository
4. Deploy!

## 🔄 Syncing from Airtable

If your data is in Airtable:

1. **In the dashboard sidebar:**
   - Expand "☁️ Sync from Airtable"
   - Enter your Airtable credentials
   - Click "🔄 Sync from Airtable"

2. **Or use the sync script:**
   ```bash
   python airtable_sync.py
   ```

See `AIRTABLE_SYNC_README.md` for more details.

## 📊 Dashboard Tabs

1. **Daily Trends** - Daily sales, moving averages, monthly comparisons
2. **Day of Week** - Sales patterns by weekday
3. **Employee Performance** - Rankings, averages, transaction volumes
4. **Hourly Patterns** - Peak hours and hourly sales distribution
5. **Product Patterns** - Top products by sales, count, and average
6. **Future Projections** - Forecasts with multiple methods

## 🛠️ Requirements

- Python 3.8+
- See `requirements.txt` for all dependencies

## 📝 Notes

- Data is cached for 1 hour (or click "Refresh Data" to reload immediately)
- The dashboard automatically handles new data when you add rows to CSV files
- All calculations are done dynamically based on your data

## 🤝 Support

For issues or questions, check the documentation files:
- `DEPLOY_STREAMLIT_CLOUD.md` - Deployment guide
- `AIRTABLE_SYNC_README.md` - Airtable integration
- `HOSTING_GUIDE.md` - Hosting options

## 📄 License

This project is for internal use.