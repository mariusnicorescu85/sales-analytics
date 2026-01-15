"""
Airtable Sync Script
Syncs data from Airtable to CSV for the dashboard
Run this script to update your CSV files with latest Airtable data
"""

import os
import pandas as pd
from pyairtable import Api
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def sync_airtable_to_csv(airtable_token, base_id, table_name, output_csv_path):
    """
    Sync data from Airtable to CSV
    
    Args:
        airtable_token: Your Airtable Personal Access Token
        base_id: Your Airtable Base ID (found in Airtable API docs)
        table_name: Name of the table to sync
        output_csv_path: Path where CSV will be saved
    """
    try:
        # Initialize Airtable API
        api = Api(airtable_token)
        table = api.table(base_id, table_name)
        
        print(f"Fetching data from Airtable table: {table_name}...")
        
        # Get all records
        all_records = []
        for page in table.iterate():
            all_records.extend(page)
        
        print(f"Retrieved {len(all_records)} records from Airtable")
        
        # Convert to DataFrame
        records_data = []
        for record in all_records:
            record_dict = record['fields'].copy()
            record_dict['id'] = record['id']  # Include Airtable record ID
            records_data.append(record_dict)
        
        if not records_data:
            print("No records found in Airtable")
            return False
        
        df = pd.DataFrame(records_data)
        
        # Reorder columns to match expected format (if columns exist)
        expected_columns = [
            'Transaction', 'Customer', 'Date', 'Time', 'Day of the Week',
            'Net Sales', 'Gross Sales', 'Refunds', 'Employee', 'Commissions', 'Products'
        ]
        
        # Only include columns that exist in the data
        available_columns = [col for col in expected_columns if col in df.columns]
        other_columns = [col for col in df.columns if col not in expected_columns]
        df = df[available_columns + other_columns]
        
        # Save to CSV
        df.to_csv(output_csv_path, index=False)
        print(f"✅ Successfully synced {len(df)} records to {output_csv_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error syncing from Airtable: {e}")
        print("\nTroubleshooting:")
        print("1. Check your Airtable Personal Access Token")
        print("2. Verify the Base ID and Table Name")
        print("3. Ensure your token has read access to the base")
        return False

def main():
    """Main function to sync Airtable data"""
    
    print("=" * 60)
    print("Airtable to CSV Sync Tool")
    print("=" * 60)
    print()
    
    # Configuration - Update these with your Airtable details
    AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN', '')
    BASE_ID = os.getenv('AIRTABLE_BASE_ID', '')
    TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME', 'Opatra Sales from July 2023')
    OUTPUT_CSV = 'Opatra Sales from July 2023-Grid view.csv'
    
    # If not set via environment variables, prompt user
    if not AIRTABLE_TOKEN:
        print("Airtable Configuration")
        print("-" * 60)
        AIRTABLE_TOKEN = input("Enter your Airtable Personal Access Token: ").strip()
        if not AIRTABLE_TOKEN:
            print("❌ Token is required. Exiting.")
            return
    
    if not BASE_ID:
        BASE_ID = input("Enter your Airtable Base ID (e.g., appFM5cdHTTI8IugV): ").strip()
        if not BASE_ID:
            print("❌ Base ID is required. Exiting.")
            return
    
    # Optional: let user specify table name
    user_table = input(f"Enter table name (press Enter for '{TABLE_NAME}'): ").strip()
    if user_table:
        TABLE_NAME = user_table
    
    print()
    print("Syncing data...")
    print("-" * 60)
    
    success = sync_airtable_to_csv(
        AIRTABLE_TOKEN,
        BASE_ID,
        TABLE_NAME,
        OUTPUT_CSV
    )
    
    if success:
        print()
        print("=" * 60)
        print("✅ Sync completed successfully!")
        print(f"📁 Updated file: {OUTPUT_CSV}")
        print("🔄 You can now refresh the dashboard to see the latest data")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ Sync failed. Please check the error messages above.")
        print("=" * 60)

if __name__ == "__main__":
    main()