# n8n Workflow Setup: Excel to Airtable Sales Data Pipeline

This guide will help you set up an n8n workflow to extract sales data from your Excel file and save it to Airtable, then visualize it in a dashboard.

## Prerequisites

1. **n8n Account**: Sign up at [n8n.io](https://n8n.io) or install n8n locally
2. **Airtable Account**: Sign up at [airtable.com](https://airtable.com)
3. **Excel File**: Your `pos_entry_list.xlsx` file

## Step 1: Set Up Airtable Base

### 1.1 Create a New Base
1. Log into Airtable
2. Create a new base called "Sales Data" or similar
3. Create a table called "Sales Transactions"

### 1.2 Set Up Table Fields
Create the following fields in your Airtable table:

| Field Name | Field Type | Notes |
|------------|------------|-------|
| Trans # | Single line text | Transaction number |
| Customer | Single line text | Customer name |
| Date | Date | Transaction date |
| Time | Single line text | Transaction time |
| Net Sales | Number | Decimal number |
| Gross Sales | Number | Decimal number |
| Employee | Single line text | Employee name |
| Commissions | Single line text | Commission details |
| Products | Long text | Product details |
| Status | Single select | Options: Complete, Pending, Cancelled |

### 1.3 Get Your Airtable Credentials
1. Go to [Airtable Account Settings](https://airtable.com/account)
2. Scroll to "API" section
3. Generate a Personal Access Token
4. Copy your Base ID from the base URL: `https://airtable.com/YOUR_BASE_ID/...`

## Step 2: Import n8n Workflow

### 2.1 Open n8n
1. Log into your n8n instance
2. Click "Workflows" in the sidebar
3. Click "Import from File" or "Import from URL"

### 2.2 Import the Workflow
1. Select the `n8n_workflow_excel_to_airtable.json` file
2. The workflow will be imported with placeholder values

### 2.3 Configure Nodes

#### Configure "Read Excel File" Node
1. Click on the "Read Excel File" node
2. **File Path**: 
   - If using n8n Cloud: Upload your Excel file to a cloud storage (Google Drive, Dropbox, etc.) and use the file path
   - If using self-hosted n8n: Use the full path to your file, e.g., `C:\Users\londo\Sales Details from 1st of January 2026\pos_entry_list.xlsx`
   - **Alternative**: Use "Read Binary File" node if you need to upload the file directly

#### Configure "Clean and Filter Data" Node
- This node is pre-configured with JavaScript code to:
  - Filter out header rows
  - Clean numeric values (remove currency symbols)
  - Transform data for Airtable
- No changes needed unless you want to modify the data transformation logic

#### Configure "Append to Airtable" Node
1. Click on the "Append to Airtable" node
2. **Credentials**: 
   - Click "Create New Credential"
   - Enter your Airtable Personal Access Token
   - Save the credential
3. **Base**: Select your Airtable base (or enter Base ID)
4. **Table**: Select "Sales Transactions" table
5. **Field Mapping**: Verify that all fields are correctly mapped:
   - Trans # → Trans #
   - Customer → Customer
   - Date → Date
   - Time → Time
   - Net Sales → Net Sales
   - Gross Sales → Gross Sales
   - Employee → Employee
   - Commissions → Commissions
   - Products → Products
   - Status → Status

## Step 3: Test the Workflow

1. Click "Execute Workflow" button
2. Check the output of each node:
   - "Read Excel File" should show all rows from Excel
   - "Clean and Filter Data" should show only valid transaction rows
   - "Append to Airtable" should show successful record creation
3. Verify in Airtable that records were created correctly

## Step 4: Set Up Automation (Optional)

### Option A: Manual Trigger
- Keep the workflow as-is for manual execution

### Option B: Schedule Trigger
1. Add a "Schedule Trigger" node at the beginning
2. Set it to run daily, weekly, or as needed
3. Connect it to "Read Excel File" node

### Option C: File Watcher
1. Add a "Watch File" node at the beginning
2. Configure it to watch for new Excel files in a specific folder
3. Connect it to "Read Excel File" node

## Step 5: Create Dashboard in Airtable

### 5.1 Create Views
1. In your Airtable table, create different views:
   - **All Transactions**: Default grid view
   - **By Date**: Group by Date field
   - **By Employee**: Group by Employee field
   - **By Status**: Group by Status field

### 5.2 Create Summary Fields
1. Add a formula field for calculations if needed
2. Use summary bar at the bottom to show:
   - Total Net Sales (sum)
   - Total Gross Sales (sum)
   - Count of transactions

### 5.3 Create Dashboard Interface
1. Click "Interfaces" in the top menu
2. Create a new interface
3. Add the following blocks:
   - **Table Block**: Show Sales Transactions table
   - **Chart Block**: 
     - Bar chart: Sales by Employee
     - Line chart: Sales over time (by Date)
     - Pie chart: Sales by Status
   - **Summary Block**: Total Sales, Transaction Count
   - **Filter Block**: Allow filtering by Date, Employee, Status

### 5.4 Dashboard Configuration Example

**Chart 1: Sales by Employee**
- Type: Bar Chart
- X-axis: Employee
- Y-axis: Sum of Net Sales
- Group by: Employee

**Chart 2: Sales Over Time**
- Type: Line Chart
- X-axis: Date
- Y-axis: Sum of Net Sales
- Group by: Date

**Chart 3: Sales by Status**
- Type: Pie Chart
- Field: Status
- Value: Count of records

**Summary Metrics**
- Total Net Sales: Sum of Net Sales field
- Total Gross Sales: Sum of Gross Sales field
- Transaction Count: Count of records
- Average Transaction Value: Average of Net Sales

## Step 6: Share Dashboard

1. Click "Share" on your Airtable interface
2. Set permissions (view-only or edit)
3. Share the link with stakeholders
4. Optionally embed in a website using Airtable's embed feature

## Troubleshooting

### Issue: Excel file not found
- **Solution**: Ensure the file path is correct and accessible to n8n
- Consider using cloud storage or uploading the file directly

### Issue: Data not appearing in Airtable
- **Solution**: 
  - Check Airtable credentials
  - Verify field names match exactly
  - Check data types in Airtable match the data being sent

### Issue: Numbers not formatting correctly
- **Solution**: The "Clean and Filter Data" node handles this, but you may need to adjust the parsing logic if your number format differs

### Issue: Date format issues
- **Solution**: 
  - Ensure Date field in Airtable is set to "Date" type
  - You may need to add date parsing in the "Clean and Filter Data" node

## Advanced Customization

### Add Data Validation
Modify the "Clean and Filter Data" node to add validation:
```javascript
// Example: Validate date format
if (!isValidDate(json['Date'])) {
  // Skip or flag invalid records
}
```

### Add Error Handling
Add an "IF" node after "Clean and Filter Data" to handle errors:
- Route successful records to Airtable
- Route failed records to a log or error table

### Add Deduplication
Add logic to check if a transaction already exists in Airtable before inserting:
- Use "List Records" node to check existing records
- Filter out duplicates before appending

## Next Steps

1. **Automate**: Set up scheduled runs to keep data updated
2. **Enhance**: Add more data transformations or calculations
3. **Integrate**: Connect to other tools (Slack notifications, email reports, etc.)
4. **Visualize**: Create more advanced dashboards with charts and KPIs

## Support

For issues with:
- **n8n**: Check [n8n documentation](https://docs.n8n.io)
- **Airtable**: Check [Airtable support](https://support.airtable.com)
- **Workflow**: Review the node configurations and error messages

