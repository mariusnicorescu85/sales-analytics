# Airtable Dashboard Setup Guide

This guide provides step-by-step instructions for creating a comprehensive sales dashboard in Airtable.

## Dashboard Overview

Your dashboard will display:
- Transaction summary statistics
- Sales trends over time
- Performance by employee
- Sales by status
- Interactive filters and views

## Step 1: Prepare Your Data Structure

### 1.1 Verify Table Structure
Ensure your "Sales Transactions" table has these fields:

| Field Name | Type | Format/Options |
|------------|------|----------------|
| Trans # | Single line text | - |
| Customer | Single line text | - |
| Date | Date | Date only |
| Time | Single line text | - |
| Net Sales | Number | Currency (2 decimals) |
| Gross Sales | Number | Currency (2 decimals) |
| Employee | Single line text | - |
| Commissions | Single line text | - |
| Products | Long text | - |
| Status | Single select | Complete, Pending, Cancelled |

### 1.2 Add Calculated Fields (Optional)

**Profit Margin** (Formula field):
```
IF({Gross Sales} > 0, ({Net Sales} / {Gross Sales}) * 100, 0)
```

**Transaction Value Category** (Formula field):
```
IF({Net Sales} >= 100, "High", IF({Net Sales} >= 50, "Medium", "Low"))
```

## Step 2: Create Views

### 2.1 All Transactions View
- **Name**: "All Transactions"
- **Type**: Grid
- **Fields**: All fields visible
- **Sort**: Date (descending)

### 2.2 Sales by Date View
- **Name**: "Sales by Date"
- **Type**: Grid
- **Group by**: Date
- **Sort**: Date (descending)
- **Summary**: 
  - Net Sales: Sum
  - Gross Sales: Sum
  - Count: Count

### 2.3 Sales by Employee View
- **Name**: "Sales by Employee"
- **Type**: Grid
- **Group by**: Employee
- **Summary**:
  - Net Sales: Sum
  - Gross Sales: Sum
  - Count: Count
  - Net Sales: Average

### 2.4 Sales by Status View
- **Name**: "Sales by Status"
- **Type**: Grid
- **Group by**: Status
- **Summary**:
  - Net Sales: Sum
  - Count: Count

### 2.5 Recent Transactions View
- **Name**: "Recent Transactions"
- **Type**: Grid
- **Filter**: Date is within the last 30 days
- **Sort**: Date (descending)
- **Limit**: 50 records

## Step 3: Create Dashboard Interface

### 3.1 Create New Interface
1. Click "Interfaces" in the top menu
2. Click "Create new interface"
3. Name it "Sales Dashboard"
4. Select your base and table

### 3.2 Add Summary Metrics Block

**Block 1: Key Metrics**
- **Type**: Summary
- **Metrics to display**:
  1. **Total Net Sales**
     - Field: Net Sales
     - Aggregation: Sum
     - Format: Currency
  2. **Total Gross Sales**
     - Field: Gross Sales
     - Aggregation: Sum
     - Format: Currency
  3. **Transaction Count**
     - Field: Any field
     - Aggregation: Count
  4. **Average Transaction Value**
     - Field: Net Sales
     - Aggregation: Average
     - Format: Currency

### 3.3 Add Chart Blocks

**Block 2: Sales Over Time**
- **Type**: Chart
- **Chart Type**: Line Chart
- **X-axis**: Date
- **Y-axis**: Net Sales (Sum)
- **Group by**: Date
- **Title**: "Sales Trend Over Time"
- **Color**: Blue

**Block 3: Sales by Employee**
- **Type**: Chart
- **Chart Type**: Bar Chart
- **X-axis**: Employee
- **Y-axis**: Net Sales (Sum)
- **Group by**: Employee
- **Title**: "Sales Performance by Employee"
- **Color**: Green
- **Sort**: Descending by value

**Block 4: Sales by Status**
- **Type**: Chart
- **Chart Type**: Pie Chart
- **Field**: Status
- **Value**: Count of records
- **Title**: "Transactions by Status"
- **Colors**: Custom (Complete: Green, Pending: Yellow, Cancelled: Red)

**Block 5: Daily Sales Comparison**
- **Type**: Chart
- **Chart Type**: Bar Chart
- **X-axis**: Date
- **Y-axis**: Net Sales (Sum)
- **Group by**: Date
- **Title**: "Daily Sales Comparison"
- **Sort**: Date (ascending)

### 3.4 Add Table Block

**Block 6: Transaction Table**
- **Type**: Table
- **View**: All Transactions
- **Fields to display**:
  - Date
  - Customer
  - Employee
  - Net Sales
  - Gross Sales
  - Status
- **Sort**: Date (descending)
- **Page size**: 25
- **Enable**: Row selection, Filters, Search

### 3.5 Add Filter Block

**Block 7: Dashboard Filters**
- **Type**: Filter
- **Filters to add**:
  1. **Date Range**
     - Field: Date
     - Type: Date range picker
  2. **Employee**
     - Field: Employee
     - Type: Multi-select
  3. **Status**
     - Field: Status
     - Type: Multi-select
  4. **Sales Range**
     - Field: Net Sales
     - Type: Number range

## Step 4: Arrange Dashboard Layout

### Recommended Layout:

```
┌─────────────────────────────────────────────────┐
│  Key Metrics (Summary Block)                   │
│  [Total Net Sales] [Total Gross] [Count] [Avg] │
└─────────────────────────────────────────────────┘
┌──────────────────┬──────────────────────────────┐
│ Sales Over Time  │  Sales by Employee          │
│ (Line Chart)     │  (Bar Chart)                │
├──────────────────┼──────────────────────────────┤
│ Sales by Status  │  Daily Sales Comparison     │
│ (Pie Chart)      │  (Bar Chart)                 │
└──────────────────┴──────────────────────────────┘
┌─────────────────────────────────────────────────┐
│  Dashboard Filters                              │
│  [Date] [Employee] [Status] [Sales Range]      │
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│  Transaction Table                              │
│  [Full table with all transactions]             │
└─────────────────────────────────────────────────┘
```

## Step 5: Customize Appearance

### 5.1 Color Scheme
- **Primary Color**: Choose a brand color
- **Chart Colors**: Use consistent color palette
- **Status Colors**: 
  - Complete: Green (#10B981)
  - Pending: Yellow (#F59E0B)
  - Cancelled: Red (#EF4444)

### 5.2 Typography
- **Title Font**: Bold, larger size
- **Metric Labels**: Clear and readable
- **Chart Labels**: Sufficient size for readability

### 5.3 Spacing
- Add padding between blocks
- Ensure charts are large enough to read
- Keep related metrics grouped together

## Step 6: Add Interactivity

### 6.1 Enable Filtering
- All filters should be connected to the table and charts
- When a filter is applied, all blocks update automatically

### 6.2 Enable Drill-Down
- Make charts clickable to filter the table
- Click on a bar/segment to see related transactions

### 6.3 Add Actions
- Add "View Details" action to table rows
- Add "Export" button for filtered data

## Step 7: Create Additional Views for Analysis

### 7.1 High-Value Transactions
- **Filter**: Net Sales >= 100
- **Sort**: Net Sales (descending)
- **Use case**: Identify top transactions

### 7.2 Employee Performance
- **Group by**: Employee
- **Summary**: 
  - Total Sales
  - Average Transaction
  - Transaction Count
- **Use case**: Performance review

### 7.3 Monthly Summary
- **Group by**: Date (grouped by month)
- **Summary**: 
  - Total Sales
  - Transaction Count
- **Use case**: Monthly reporting

## Step 8: Share and Collaborate

### 8.1 Share Interface
1. Click "Share" on your interface
2. Set permissions:
   - **View only**: For stakeholders
   - **Comment**: For feedback
   - **Edit**: For team members
3. Copy share link

### 8.2 Embed Dashboard (Optional)
1. Get embed code from interface settings
2. Embed in:
   - Company intranet
   - Website
   - Notion page
   - Other tools

### 8.3 Schedule Reports
- Use Airtable Automations to send weekly/monthly summaries
- Export dashboard as PDF
- Send via email to stakeholders

## Step 9: Advanced Features

### 9.1 Conditional Formatting
- Highlight high-value transactions
- Color-code by status
- Show trends with arrows

### 9.2 Linked Records
- Create a separate "Employees" table
- Link transactions to employee records
- Create employee performance dashboard

### 9.3 Formulas for KPIs
Add calculated fields for:
- **Conversion Rate**: (Completed / Total) * 100
- **Average Daily Sales**: Total Sales / Number of Days
- **Top Employee**: Employee with highest sales

### 9.4 Automation
Set up automations for:
- Daily summary emails
- Weekly performance reports
- Alerts for high-value transactions

## Step 10: Maintenance

### 10.1 Regular Updates
- Ensure n8n workflow runs regularly
- Verify data accuracy
- Update filters and views as needed

### 10.2 Performance Optimization
- Limit table views to recent data
- Use filters to reduce load
- Archive old data to separate table

### 10.3 User Feedback
- Collect feedback from dashboard users
- Iterate on design and features
- Add new metrics as needed

## Dashboard Best Practices

1. **Keep it Simple**: Focus on key metrics
2. **Update Regularly**: Ensure data is current
3. **Make it Interactive**: Allow users to explore data
4. **Mobile Friendly**: Test on mobile devices
5. **Fast Loading**: Optimize for performance
6. **Clear Labels**: Use descriptive titles and labels
7. **Consistent Design**: Maintain visual consistency
8. **Actionable Insights**: Show trends and patterns

## Troubleshooting

### Charts not showing data
- Check that fields are properly configured
- Verify data types match (numbers, dates, etc.)
- Ensure filters aren't excluding all data

### Performance issues
- Reduce number of records in views
- Use filters to limit data
- Consider archiving old data

### Sharing issues
- Verify permissions are set correctly
- Check that base is shared if needed
- Ensure interface is published

## Next Steps

1. **Customize**: Adjust dashboard to your specific needs
2. **Automate**: Set up regular data updates
3. **Expand**: Add more tables and relationships
4. **Integrate**: Connect with other tools (Slack, email, etc.)
5. **Analyze**: Use insights to make data-driven decisions

