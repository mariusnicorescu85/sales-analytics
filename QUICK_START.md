# Quick Start Guide: Excel to Airtable Dashboard

## 🚀 Quick Setup (5 Minutes)

### 1. Airtable Setup (2 minutes)
1. Go to [airtable.com](https://airtable.com) and sign in
2. Create new base: "Sales Dashboard"
3. Create table: "Sales Transactions"
4. Add fields (copy from SETUP_INSTRUCTIONS.md)
5. Get your Base ID from the URL
6. Get Personal Access Token from Account Settings → API

### 2. n8n Setup (2 minutes)
1. Go to [n8n.io](https://n8n.io) or open your n8n instance
2. Import `n8n_workflow_excel_to_airtable.json`
3. Configure:
   - **Read Excel File**: Update file path to your Excel file location
   - **Append to Airtable**: 
     - Add Airtable credentials (use your Personal Access Token)
     - Select your base and table
     - Verify field mappings

### 3. Run Workflow (1 minute)
1. Click "Execute Workflow"
2. Check each node output
3. Verify data in Airtable

### 4. Create Dashboard (5 minutes)
1. In Airtable, click "Interfaces"
2. Create new interface: "Sales Dashboard"
3. Add blocks:
   - Summary metrics (Total Sales, Count, Average)
   - Charts (Sales over time, by employee, by status)
   - Transaction table
   - Filters
4. Share your dashboard!

## 📋 Field Mapping Reference

| Excel Column | Airtable Field | Type |
|--------------|----------------|------|
| Trans # | Trans # | Text |
| Customer | Customer | Text |
| Date | Date | Date |
| Time | Time | Text |
| Net Sales | Net Sales | Number |
| Gross Sales | Gross Sales | Number |
| Employee | Employee | Text |
| Commissions | Commissions | Text |
| Products | Products | Long text |
| Status | Status | Single select |

## ⚙️ Common Configurations

### File Path Options

**Option 1: Local File (Self-hosted n8n)**
```
C:\Users\londo\Sales Details from 1st of January 2026\pos_entry_list.xlsx
```

**Option 2: Cloud Storage**
- Upload to Google Drive/Dropbox
- Use corresponding n8n nodes to read from cloud

**Option 3: Upload Directly**
- Use "Read Binary File" node
- Upload file through n8n interface

### Airtable Credentials
- **Type**: Personal Access Token
- **Scopes**: `data.records:read`, `data.records:write`, `schema.bases:read`
- **Where to get**: Airtable Account → API → Personal Access Tokens

## 🎯 Dashboard Quick Setup

### Essential Blocks (Minimum Viable Dashboard)
1. **Summary Block**: Total Net Sales, Transaction Count
2. **Line Chart**: Sales over time
3. **Bar Chart**: Sales by employee
4. **Table**: All transactions with filters

### Advanced Blocks (Full Dashboard)
- Add all blocks from AIRTABLE_DASHBOARD_GUIDE.md
- Customize colors and layout
- Add interactive filters

## 🔄 Automation Options

### Daily Updates
1. Add "Schedule Trigger" node
2. Set to run daily at specific time
3. Connect to "Read Excel File"

### On File Change
1. Add "Watch File" node
2. Set to watch Excel file location
3. Connect to "Read Excel File"

### Manual Only
- Keep workflow as-is
- Run manually when needed

## ❗ Troubleshooting Quick Fixes

**Problem**: File not found
- **Fix**: Check file path, use forward slashes or double backslashes in Windows

**Problem**: No data in Airtable
- **Fix**: Check credentials, verify field names match exactly

**Problem**: Numbers showing as text
- **Fix**: The "Clean and Filter Data" node handles this automatically

**Problem**: Dashboard not updating
- **Fix**: Refresh Airtable, check that workflow ran successfully

## 📚 Full Documentation

- **Setup Details**: See `SETUP_INSTRUCTIONS.md`
- **Dashboard Guide**: See `AIRTABLE_DASHBOARD_GUIDE.md`
- **n8n Docs**: [docs.n8n.io](https://docs.n8n.io)
- **Airtable Docs**: [support.airtable.com](https://support.airtable.com)

## ✅ Checklist

- [ ] Airtable base created
- [ ] Table with all fields set up
- [ ] Airtable credentials obtained
- [ ] n8n workflow imported
- [ ] File path configured
- [ ] Airtable node configured
- [ ] Workflow tested successfully
- [ ] Data visible in Airtable
- [ ] Dashboard interface created
- [ ] Charts and metrics added
- [ ] Dashboard shared with team

## 🎉 You're Done!

Your sales data is now flowing from Excel → Airtable → Dashboard!

Need help? Check the detailed guides or n8n/Airtable documentation.

