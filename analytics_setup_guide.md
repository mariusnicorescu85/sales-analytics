# Analytics & Pattern Recognition Setup Guide

## Overview
This guide shows you how to analyze your sales data for patterns, trends, and insights.

## Option 1: Airtable Built-in Analytics (Quick Start)

### Using Airtable Interfaces
1. **Create Dashboard Interface**
   - Go to Interfaces → Create new interface
   - Add chart blocks for:
     - Sales trends over time
     - Sales by day of week
     - Sales by employee
     - Refund patterns
   - Add summary metrics

2. **Create Views for Analysis**
   - **Sales by Day of Week**: Group by "Day of the Week"
   - **Employee Performance**: Group by "Employee", summarize Net Sales
   - **Refund Analysis**: Filter where Refunds < 0
   - **Time Patterns**: Group by "Time" (hour ranges)

3. **Use Formulas for Pattern Detection**
   - **High-Value Transactions**: `IF({Net Sales} >= 100, "High", "Low")`
   - **Refund Rate**: `IF({Refunds} < 0, "Has Refund", "No Refund")`
   - **Day Performance**: Group by Day of Week to see patterns

## Option 2: Python Analytics (Advanced Pattern Recognition)

### Setup Python Environment

1. **Install Required Packages**
```bash
pip install pandas numpy matplotlib seaborn scikit-learn jupyter pandas-airtable
```

2. **Export Data from Airtable**
   - Use Airtable API or export as CSV
   - Or use Python library to connect directly

### Python Analysis Script

Create `sales_analytics.py`:

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from airtable import Airtable

# Connect to Airtable
BASE_ID = 'appFM5cdHTTI8IugV'
TABLE_NAME = 'Opatra Sales from July 2023'
API_KEY = 'your_api_key'

airtable = Airtable(BASE_ID, TABLE_NAME, API_KEY)
records = airtable.get_all()

# Convert to DataFrame
df = pd.DataFrame([record['fields'] for record in records])

# Data Cleaning
df['Date'] = pd.to_datetime(df['Date'])
df['Net Sales'] = pd.to_numeric(df['Net Sales'], errors='coerce')
df['Gross Sales'] = pd.to_numeric(df['Gross Sales'], errors='coerce')
df['Refunds'] = pd.to_numeric(df['Refunds'], errors='coerce').fillna(0)

# 1. PATTERN RECOGNITION: Day of Week Analysis
day_patterns = df.groupby('Day of the Week')['Net Sales'].agg(['sum', 'mean', 'count'])
print("Sales by Day of Week:")
print(day_patterns)

# 2. TIME PATTERN ANALYSIS
df['Hour'] = pd.to_datetime(df['Time']).dt.hour
hourly_patterns = df.groupby('Hour')['Net Sales'].sum()
print("\nSales by Hour:")
print(hourly_patterns)

# 3. EMPLOYEE PERFORMANCE PATTERNS
employee_performance = df.groupby('Employee').agg({
    'Net Sales': ['sum', 'mean', 'count'],
    'Refunds': 'sum'
})
print("\nEmployee Performance:")
print(employee_performance)

# 4. REFUND PATTERN ANALYSIS
refund_analysis = df[df['Refunds'] < 0].groupby(['Employee', 'Day of the Week']).agg({
    'Refunds': ['sum', 'count']
})
print("\nRefund Patterns:")
print(refund_analysis)

# 5. TREND ANALYSIS
daily_sales = df.groupby(df['Date'].dt.date)['Net Sales'].sum()
print("\nDaily Sales Trend:")
print(daily_sales)

# 6. VISUALIZATIONS
plt.figure(figsize=(15, 10))

# Day of Week Pattern
plt.subplot(2, 3, 1)
day_patterns['sum'].plot(kind='bar')
plt.title('Sales by Day of Week')
plt.ylabel('Total Sales')

# Hourly Pattern
plt.subplot(2, 3, 2)
hourly_patterns.plot(kind='line')
plt.title('Sales by Hour of Day')
plt.ylabel('Total Sales')
plt.xlabel('Hour')

# Employee Performance
plt.subplot(2, 3, 3)
df.groupby('Employee')['Net Sales'].sum().sort_values(ascending=False).head(10).plot(kind='barh')
plt.title('Top 10 Employees by Sales')
plt.xlabel('Total Sales')

# Refund Analysis
plt.subplot(2, 3, 4)
refund_by_employee = df[df['Refunds'] < 0].groupby('Employee')['Refunds'].sum()
refund_by_employee.plot(kind='bar')
plt.title('Refunds by Employee')
plt.ylabel('Total Refunds')

# Daily Trend
plt.subplot(2, 3, 5)
daily_sales.plot(kind='line')
plt.title('Daily Sales Trend')
plt.ylabel('Total Sales')
plt.xlabel('Date')
plt.xticks(rotation=45)

# Product Analysis (if you want to analyze products)
plt.subplot(2, 3, 6)
# Add product analysis here if needed

plt.tight_layout()
plt.savefig('sales_analytics.png', dpi=300, bbox_inches='tight')
plt.show()

# 7. ADVANCED PATTERN RECOGNITION
# Identify peak sales times
peak_hours = hourly_patterns.nlargest(3)
print(f"\nPeak Sales Hours: {peak_hours.index.tolist()}")

# Identify best performing days
best_days = day_patterns['sum'].nlargest(3)
print(f"Best Sales Days: {best_days.index.tolist()}")

# Refund rate by employee
refund_rate = df.groupby('Employee').apply(
    lambda x: (x['Refunds'] < 0).sum() / len(x) * 100 if len(x) > 0 else 0
)
print("\nRefund Rate by Employee (%):")
print(refund_rate.sort_values(ascending=False))

# Export results
df.to_csv('sales_data_export.csv', index=False)
print("\nData exported to sales_data_export.csv")
```

### Run Analysis
```bash
python sales_analytics.py
```

## Option 3: Connect to Business Intelligence Tools

### Google Data Studio / Looker Studio
1. **Connect Airtable**
   - Use Airtable connector or export CSV
   - Create visualizations
   - Set up automated reports

2. **Benefits**
   - Free
   - Easy sharing
   - Real-time updates
   - Interactive dashboards

### Tableau / Power BI
1. **Connect Airtable**
   - Use Airtable API connector
   - Build advanced visualizations
   - Create predictive models

2. **Benefits**
   - Advanced analytics
   - Machine learning capabilities
   - Professional dashboards

### Metabase (Open Source)
1. **Setup**
   - Self-hosted or cloud
   - Connect to Airtable via API
   - SQL-like queries

2. **Benefits**
   - Free/open source
   - SQL queries
   - Custom dashboards

## Option 4: Automated Analytics with n8n

### Create Analytics Workflow
1. **Schedule Trigger** (daily/weekly)
2. **Airtable Node** - Get records
3. **Code Node** - Calculate metrics
4. **Email/Slack Node** - Send reports

### Example n8n Analytics Code
```javascript
// Calculate key metrics
const records = $input.all();
const data = records.map(r => r.json);

const totalSales = data.reduce((sum, r) => sum + (r['Net Sales'] || 0), 0);
const totalRefunds = data.reduce((sum, r) => sum + (Math.abs(r['Refunds'] || 0)), 0);
const refundRate = (totalRefunds / totalSales * 100).toFixed(2);

// Day of week analysis
const daySales = {};
data.forEach(r => {
  const day = r['Day of the Week'];
  if (day) {
    daySales[day] = (daySales[day] || 0) + (r['Net Sales'] || 0);
  }
});

// Employee performance
const employeeSales = {};
data.forEach(r => {
  const emp = r['Employee'];
  if (emp) {
    employeeSales[emp] = (employeeSales[emp] || 0) + (r['Net Sales'] || 0);
  }
});

return [{
  json: {
    totalSales,
    totalRefunds,
    refundRate: `${refundRate}%`,
    bestDay: Object.entries(daySales).sort((a, b) => b[1] - a[1])[0][0],
    topEmployee: Object.entries(employeeSales).sort((a, b) => b[1] - a[1])[0][0],
    dayBreakdown: daySales,
    employeeBreakdown: employeeSales
  }
}];
```

## Option 5: Machine Learning for Pattern Recognition

### Predictive Analytics
```python
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# Prepare features
df['DayOfWeekNum'] = df['Day of the Week'].map({
    'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4,
    'Friday': 5, 'Saturday': 6, 'Sunday': 7
})
df['Hour'] = pd.to_datetime(df['Time']).dt.hour

# Features for prediction
features = ['DayOfWeekNum', 'Hour']
X = df[features].fillna(0)
y = df['Net Sales'].fillna(0)

# Train model
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model = RandomForestRegressor()
model.fit(X_train, y_train)

# Predict best times for sales
predictions = model.predict(X)
print("Predicted sales patterns learned from data")
```

### Anomaly Detection
```python
from sklearn.ensemble import IsolationForest

# Detect unusual transactions
features = ['Net Sales', 'Hour']
X = df[features].fillna(0)
iso_forest = IsolationForest(contamination=0.1)
df['Anomaly'] = iso_forest.fit_predict(X)

# Flag unusual transactions
anomalies = df[df['Anomaly'] == -1]
print(f"Found {len(anomalies)} unusual transactions")
```

## Recommended Approach

### For Quick Insights:
1. **Start with Airtable Interfaces** - Build dashboards
2. **Use Airtable Views** - Group and filter data

### For Advanced Analytics:
1. **Export to Python** - Run pattern recognition scripts
2. **Set up automated reports** - Use n8n to send weekly summaries

### For Team Sharing:
1. **Google Data Studio** - Connect Airtable, create dashboards
2. **Share Airtable Interfaces** - Real-time team access

## Next Steps

1. **Immediate**: Set up Airtable Interfaces for basic analytics
2. **Short-term**: Export data and run Python analysis
3. **Long-term**: Set up automated analytics pipeline with n8n

## Questions to Answer with Analytics

- Which days of the week have highest sales?
- What times of day are most profitable?
- Which employees have the best performance?
- What's the refund rate by employee?
- Are there seasonal patterns?
- What products sell best on which days?
- Are there unusual transactions that need investigation?
