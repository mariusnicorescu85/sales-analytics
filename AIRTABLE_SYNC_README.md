# Airtable Integration Guide

## Current Situation

When you add new data to Airtable, it **does NOT automatically appear** in the dashboard. You need to sync the data first.

## Two Ways to Sync Airtable Data

### Option 1: Sync from Dashboard (Easiest) ⭐

1. **Install Airtable package:**
   ```bash
   pip install pyairtable
   ```

2. **Run the dashboard:**
   ```bash
   streamlit run dashboard.py
   ```

3. **In the dashboard sidebar:**
   - Expand "☁️ Sync from Airtable"
   - Enter your Airtable Personal Access Token
   - Enter your Base ID (e.g., `appFM5cdHTTI8IugV`)
   - Enter your Table Name (e.g., `Opatra Sales from July 2023`)
   - Click "🔄 Sync from Airtable"
   - Click "🔄 Refresh Data" to load the synced data

### Option 2: Use Sync Script

1. **Run the sync script:**
   ```bash
   sync_airtable.bat
   ```
   Or manually:
   ```bash
   python airtable_sync.py
   ```

2. **The script will:**
   - Prompt for your Airtable token and base ID
   - Download all records from Airtable
   - Save them to `Opatra Sales from July 2023-Grid view.csv`
   - Update the CSV file that the dashboard reads

3. **Then refresh the dashboard** to see new data

## Getting Your Airtable Credentials

### Personal Access Token
1. Go to https://airtable.com/create/tokens
2. Create a new token
3. Give it read access to your base
4. Copy the token

### Base ID
1. Open your Airtable base
2. Go to Help → API documentation
3. The Base ID is shown at the top (e.g., `appFM5cdHTTI8IugV`)

### Table Name
- This is the exact name of your table in Airtable
- Usually: `Opatra Sales from July 2023`

## Setting Up Environment Variables (Optional)

To avoid entering credentials each time, create a `.env` file:

```
AIRTABLE_TOKEN=your_token_here
AIRTABLE_BASE_ID=appFM5cdHTTI8IugV
AIRTABLE_TABLE_NAME=Opatra Sales from July 2023
```

## Workflow Recommendations

### Daily Workflow:
1. Add new sales data to Airtable
2. Open dashboard
3. Click "Sync from Airtable" in sidebar
4. Click "Refresh Data"
5. View updated analytics

### Automated Workflow (Advanced):
- Set up a scheduled task (Windows Task Scheduler) to run `sync_airtable.bat` daily
- Or use Airtable Automations to trigger a webhook that syncs data

## Troubleshooting

**"No records found"**
- Check your table name matches exactly
- Verify your token has read access

**"Error syncing"**
- Verify your Base ID is correct
- Check your token hasn't expired
- Ensure column names match expected format

**"Data not updating"**
- Make sure to click "Refresh Data" after syncing
- Check the CSV file was actually updated (check file timestamp)

## What Happens When You Add Data to Airtable?

1. ✅ **Data is in Airtable** - Your new records are stored
2. ❌ **Dashboard doesn't see it yet** - CSV file is outdated
3. ✅ **Sync from Airtable** - Downloads latest data
4. ✅ **Refresh Dashboard** - Loads new CSV data
5. ✅ **See updated analytics** - All charts and metrics update

## Security Note

- Never commit your Airtable token to version control
- Use environment variables for production
- Tokens can be revoked and recreated if needed