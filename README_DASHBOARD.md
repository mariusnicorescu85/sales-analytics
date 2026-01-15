# Sales Dashboard

Two dashboard options are available to visualize your sales data:

## Option 1: Streamlit Dashboard (Recommended)

The Streamlit dashboard is easier to use and doesn't require a web server.

### Setup:
1. Install Python (if not already installed)
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

### Run:
```bash
streamlit run dashboard.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`

### Features:
- Interactive filters (Employee, Date Range)
- Key metrics overview
- Top employees by sales
- Sales by day of week
- Sales trends over time
- Average transaction values
- Employee performance table
- Product insights

## Option 2: HTML Dashboard

The HTML dashboard is a standalone file that can be opened directly in a browser.

### Usage:
1. **Important**: Due to browser security (CORS), you need to serve the files via a local web server
2. Options to run:
   
   **Option A - Python Simple Server:**
   ```bash
   # Python 3
   python -m http.server 8000
   
   # Then open: http://localhost:8000/dashboard.html
   ```
   
   **Option B - Node.js http-server:**
   ```bash
   npx http-server -p 8000
   
   # Then open: http://localhost:8000/dashboard.html
   ```
   
   **Option C - VS Code Live Server:**
   - Install "Live Server" extension in VS Code
   - Right-click on `dashboard.html` and select "Open with Live Server"

### Features:
- Interactive charts using Chart.js
- Employee and date range filters
- Real-time data updates
- Responsive design
- All visualizations from the Streamlit version

## Data Files Required:
- `employee_performance_analysis.csv`
- `Opatra Sales from July 2023-Grid view.csv`

Both files should be in the same directory as the dashboard files.

## Troubleshooting:

**If data doesn't load:**
- Ensure CSV files are in the same directory
- Check file names match exactly (case-sensitive)
- For HTML dashboard, make sure you're using a local web server (not opening file:// directly)

**If charts don't display:**
- Check browser console for errors (F12)
- Ensure you have internet connection (for CDN resources)
- Try refreshing the page