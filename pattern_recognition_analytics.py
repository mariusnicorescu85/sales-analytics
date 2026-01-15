"""
Pattern Recognition Analytics Script for Opatra Sales Data
Analyzes sales patterns, trends, and insights from CSV data
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import re
import warnings
warnings.filterwarnings('ignore')

# Set style for better visualizations
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (16, 10)

class SalesPatternAnalyzer:
    def __init__(self, csv_file):
        """Initialize the analyzer with CSV file path"""
        self.csv_file = csv_file
        self.df = None
        self.results = {}
        
    def load_data(self):
        """Load and clean the CSV data"""
        print("Loading data...")
        self.df = pd.read_csv(self.csv_file)
        
        # Clean column names (remove extra spaces)
        self.df.columns = self.df.columns.str.strip()
        
        # Convert date column
        self.df['Date'] = pd.to_datetime(self.df['Date'], errors='coerce')
        
        # Extract time from Time column if it contains datetime
        if 'Time' in self.df.columns:
            self.df['Time'] = pd.to_datetime(self.df['Time'], errors='coerce')
            self.df['Hour'] = self.df['Time'].dt.hour
            self.df['Minute'] = self.df['Time'].dt.minute
        
        # Clean and convert sales columns
        def clean_currency(value):
            if pd.isna(value):
                return 0
            if isinstance(value, str):
                # Remove £, commas, and convert to float
                value = value.replace('£', '').replace(',', '').strip()
                try:
                    return float(value)
                except:
                    return 0
            return float(value) if value else 0
        
        self.df['Net Sales'] = self.df['Net Sales'].apply(clean_currency)
        self.df['Gross Sales'] = self.df['Gross Sales'].apply(clean_currency)
        self.df['Refunds'] = self.df['Refunds'].apply(clean_currency)
        
        # Filter out refunds (negative net sales) for most analyses
        self.df['Is_Refund'] = self.df['Net Sales'] < 0
        self.df_sales = self.df[self.df['Net Sales'] >= 0].copy()
        
        # Extract month and year
        self.df['Month'] = self.df['Date'].dt.month
        self.df['Year'] = self.df['Date'].dt.year
        self.df['Day'] = self.df['Date'].dt.day
        
        print(f"Loaded {len(self.df)} transactions")
        print(f"Sales transactions: {len(self.df_sales)}")
        print(f"Refund transactions: {len(self.df[self.df['Is_Refund']])}")
        
    def analyze_day_of_week_patterns(self):
        """Analyze sales patterns by day of the week"""
        print("\n" + "="*60)
        print("DAY OF WEEK PATTERN ANALYSIS")
        print("="*60)
        
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_patterns = self.df_sales.groupby('Day of the Week').agg({
            'Net Sales': ['sum', 'mean', 'count', 'std'],
            'Gross Sales': 'sum'
        }).round(2)
        
        # Reorder by day of week
        day_patterns = day_patterns.reindex([d for d in day_order if d in day_patterns.index])
        
        print("\nSales Statistics by Day of Week:")
        print(day_patterns)
        
        # Calculate day performance ranking
        day_ranking = day_patterns[('Net Sales', 'sum')].sort_values(ascending=False)
        print(f"\nBest performing day: {day_ranking.index[0]} (£{day_ranking.iloc[0]:,.2f})")
        print(f"Worst performing day: {day_ranking.index[-1]} (£{day_ranking.iloc[-1]:,.2f})")
        
        self.results['day_patterns'] = day_patterns
        self.results['day_ranking'] = day_ranking
        
        return day_patterns
    
    def analyze_time_patterns(self):
        """Analyze sales patterns by time of day"""
        print("\n" + "="*60)
        print("TIME OF DAY PATTERN ANALYSIS")
        print("="*60)
        
        hourly_patterns = self.df_sales.groupby('Hour').agg({
            'Net Sales': ['sum', 'mean', 'count'],
            'Gross Sales': 'sum'
        }).round(2)
        
        print("\nSales Statistics by Hour:")
        print(hourly_patterns)
        
        # Find peak hours
        peak_hours = hourly_patterns[('Net Sales', 'sum')].nlargest(5)
        print(f"\nTop 5 Peak Sales Hours:")
        for hour, sales in peak_hours.items():
            hour_int = int(hour) if not pd.isna(hour) else 0
            print(f"  {hour_int:02d}:00 - £{sales:,.2f}")
        
        # Find quiet hours
        quiet_hours = hourly_patterns[('Net Sales', 'sum')].nsmallest(5)
        print(f"\nTop 5 Quietest Hours:")
        for hour, sales in quiet_hours.items():
            hour_int = int(hour) if not pd.isna(hour) else 0
            print(f"  {hour_int:02d}:00 - £{sales:,.2f}")
        
        self.results['hourly_patterns'] = hourly_patterns
        self.results['peak_hours'] = peak_hours
        
        return hourly_patterns
    
    def analyze_employee_performance(self):
        """Analyze sales performance by employee"""
        print("\n" + "="*60)
        print("EMPLOYEE PERFORMANCE ANALYSIS")
        print("="*60)
        
        employee_perf = self.df_sales.groupby('Employee').agg({
            'Net Sales': ['sum', 'mean', 'count'],
            'Gross Sales': 'sum',
            'Refunds': 'sum'
        }).round(2)
        
        # Calculate refund rate
        refund_counts = self.df.groupby('Employee')['Is_Refund'].sum()
        total_counts = self.df.groupby('Employee').size()
        employee_perf['Refund_Rate'] = (refund_counts / total_counts * 100).round(2)
        
        # Sort by total sales
        employee_perf = employee_perf.sort_values(('Net Sales', 'sum'), ascending=False)
        
        print("\nEmployee Performance Summary:")
        print(employee_perf.head(20))
        
        top_employee = employee_perf.index[0]
        top_sales = employee_perf[('Net Sales', 'sum')].iloc[0]
        print(f"\nTop performing employee: {top_employee} (£{top_sales:,.2f})")
        
        # Average transaction value
        avg_transaction = employee_perf[('Net Sales', 'mean')].sort_values(ascending=False)
        print(f"\nHighest average transaction: {avg_transaction.index[0]} (£{avg_transaction.iloc[0]:,.2f})")
        
        self.results['employee_performance'] = employee_perf
        
        return employee_perf
    
    def analyze_product_patterns(self):
        """Analyze product sales patterns"""
        print("\n" + "="*60)
        print("PRODUCT PATTERN ANALYSIS")
        print("="*60)
        
        # Extract products from Products column
        product_sales = {}
        product_counts = {}
        
        for idx, row in self.df_sales.iterrows():
            products = str(row.get('Products', ''))
            net_sales = row['Net Sales']
            
            # Parse products (format: "Product Name 1xPrice" or "Product Name, Product Name")
            # Simple extraction - look for product names before numbers
            if products and products != 'nan':
                # Split by comma for multiple products
                items = [p.strip() for p in products.split(',')]
                for item in items:
                    # Extract product name (everything before the last number pattern)
                    # Pattern: "Product Name 1xPrice" or "Product Name Price"
                    match = re.match(r'^([^0-9]+?)(?:\s*\d+x?\d*\.?\d*)?$', item.strip())
                    if match:
                        product_name = match.group(1).strip()
                        if product_name:
                            product_sales[product_name] = product_sales.get(product_name, 0) + net_sales / len(items)
                            product_counts[product_name] = product_counts.get(product_name, 0) + 1
        
        # Create DataFrame
        product_df = pd.DataFrame({
            'Product': list(product_sales.keys()),
            'Total_Sales': list(product_sales.values()),
            'Count': list(product_counts.values())
        })
        product_df['Avg_Sale'] = (product_df['Total_Sales'] / product_df['Count']).round(2)
        product_df = product_df.sort_values('Total_Sales', ascending=False)
        
        print("\nTop 20 Products by Sales:")
        print(product_df.head(20).to_string(index=False))
        
        self.results['product_patterns'] = product_df
        
        return product_df
    
    def analyze_trends(self):
        """Analyze sales trends over time"""
        print("\n" + "="*60)
        print("TEMPORAL TREND ANALYSIS")
        print("="*60)
        
        # Daily trends
        daily_sales = self.df_sales.groupby(self.df_sales['Date'].dt.date).agg({
            'Net Sales': ['sum', 'count', 'mean'],
            'Gross Sales': 'sum'
        })
        daily_sales.columns = ['Total_Sales', 'Transaction_Count', 'Avg_Transaction', 'Gross_Sales']
        
        print("\nDaily Sales Summary:")
        print(f"Average daily sales: £{daily_sales['Total_Sales'].mean():,.2f}")
        print(f"Best day: {daily_sales['Total_Sales'].idxmax()} (£{daily_sales['Total_Sales'].max():,.2f})")
        print(f"Worst day: {daily_sales['Total_Sales'].idxmin()} (£{daily_sales['Total_Sales'].min():,.2f})")
        print(f"Average transactions per day: {daily_sales['Transaction_Count'].mean():.1f}")
        
        # Weekly trends
        self.df_sales['Week'] = self.df_sales['Date'].dt.isocalendar().week
        weekly_sales = self.df_sales.groupby('Week').agg({
            'Net Sales': ['sum', 'count'],
            'Gross Sales': 'sum'
        })
        weekly_sales.columns = ['Total_Sales', 'Transaction_Count', 'Gross_Sales']
        
        print("\nWeekly Sales Summary:")
        print(weekly_sales)
        
        # Growth rate
        if len(weekly_sales) > 1:
            growth_rate = ((weekly_sales['Total_Sales'].iloc[-1] - weekly_sales['Total_Sales'].iloc[0]) / 
                          weekly_sales['Total_Sales'].iloc[0] * 100)
            print(f"\nWeek-over-week growth: {growth_rate:.2f}%")
        
        self.results['daily_trends'] = daily_sales
        self.results['weekly_trends'] = weekly_sales
        
        return daily_sales, weekly_sales
    
    def analyze_refund_patterns(self):
        """Analyze refund patterns"""
        print("\n" + "="*60)
        print("REFUND PATTERN ANALYSIS")
        print("="*60)
        
        refunds_df = self.df[self.df['Is_Refund']].copy()
        
        if len(refunds_df) > 0:
            total_refunds = abs(refunds_df['Refunds'].sum())
            total_sales = self.df_sales['Net Sales'].sum()
            refund_rate = (total_refunds / total_sales * 100) if total_sales > 0 else 0
            
            print(f"\nTotal Refunds: £{total_refunds:,.2f}")
            print(f"Total Sales: £{total_sales:,.2f}")
            print(f"Refund Rate: {refund_rate:.2f}%")
            
            # Refunds by employee
            refunds_by_employee = refunds_df.groupby('Employee').agg({
                'Refunds': ['sum', 'count']
            })
            refunds_by_employee.columns = ['Total_Refunds', 'Refund_Count']
            refunds_by_employee['Total_Refunds'] = refunds_by_employee['Total_Refunds'].abs()
            refunds_by_employee = refunds_by_employee.sort_values('Total_Refunds', ascending=False)
            
            print("\nRefunds by Employee:")
            print(refunds_by_employee)
            
            # Refunds by day of week
            refunds_by_day = refunds_df.groupby('Day of the Week')['Refunds'].agg(['sum', 'count'])
            refunds_by_day['Total_Refunds'] = refunds_by_day['sum'].abs()
            refunds_by_day = refunds_by_day.sort_values('Total_Refunds', ascending=False)
            
            print("\nRefunds by Day of Week:")
            print(refunds_by_day[['Total_Refunds', 'count']])
            
            self.results['refund_analysis'] = {
                'total_refunds': total_refunds,
                'refund_rate': refund_rate,
                'by_employee': refunds_by_employee,
                'by_day': refunds_by_day
            }
        else:
            print("No refunds found in the data.")
        
        return self.results.get('refund_analysis', {})
    
    def detect_anomalies(self):
        """Detect unusual patterns and anomalies"""
        print("\n" + "="*60)
        print("ANOMALY DETECTION")
        print("="*60)
        
        anomalies = []
        
        # High-value transactions (outliers)
        Q1 = self.df_sales['Net Sales'].quantile(0.25)
        Q3 = self.df_sales['Net Sales'].quantile(0.75)
        IQR = Q3 - Q1
        upper_bound = Q3 + 1.5 * IQR
        
        high_value = self.df_sales[self.df_sales['Net Sales'] > upper_bound]
        print(f"\nHigh-value transactions (outliers): {len(high_value)}")
        if len(high_value) > 0:
            print("Top 10 highest transactions:")
            top_high = high_value.nlargest(10, 'Net Sales')[['Date', 'Employee', 'Net Sales', 'Products']]
            print(top_high.to_string(index=False))
            anomalies.append(('High Value Transactions', high_value))
        
        # Unusual time patterns
        late_night = self.df_sales[(self.df_sales['Hour'] >= 22) | (self.df_sales['Hour'] <= 6)]
        if len(late_night) > 0:
            print(f"\nLate night/early morning transactions: {len(late_night)}")
            anomalies.append(('Late Night Transactions', late_night))
        
        # Employee with unusual patterns
        employee_avg = self.df_sales.groupby('Employee')['Net Sales'].mean()
        employee_std = self.df_sales.groupby('Employee')['Net Sales'].std()
        
        unusual_employees = []
        for emp in employee_avg.index:
            emp_transactions = self.df_sales[self.df_sales['Employee'] == emp]
            if len(emp_transactions) > 10:  # Only check employees with enough transactions
                z_scores = np.abs((emp_transactions['Net Sales'] - employee_avg[emp]) / employee_std[emp])
                if (z_scores > 3).any():
                    unusual_employees.append(emp)
        
        if unusual_employees:
            print(f"\nEmployees with unusual transaction patterns: {unusual_employees}")
        
        self.results['anomalies'] = anomalies
        
        return anomalies
    
    def generate_visualizations(self):
        """Generate comprehensive visualizations"""
        print("\n" + "="*60)
        print("GENERATING VISUALIZATIONS")
        print("="*60)
        
        fig = plt.figure(figsize=(20, 14))
        
        # 1. Day of Week Sales
        ax1 = plt.subplot(3, 3, 1)
        if 'day_ranking' in self.results:
            self.results['day_ranking'].plot(kind='bar', color='steelblue', ax=ax1)
            ax1.set_title('Total Sales by Day of Week', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Sales (£)')
            ax1.set_xlabel('Day of Week')
            plt.xticks(rotation=45)
        
        # 2. Hourly Sales Pattern
        ax2 = plt.subplot(3, 3, 2)
        if 'hourly_patterns' in self.results:
            self.results['hourly_patterns'][('Net Sales', 'sum')].plot(kind='line', marker='o', ax=ax2, color='green')
            ax2.set_title('Sales by Hour of Day', fontsize=12, fontweight='bold')
            ax2.set_ylabel('Total Sales (£)')
            ax2.set_xlabel('Hour')
            ax2.grid(True, alpha=0.3)
        
        # 3. Top Employees
        ax3 = plt.subplot(3, 3, 3)
        if 'employee_performance' in self.results:
            top_employees = self.results['employee_performance'][('Net Sales', 'sum')].head(10)
            top_employees.plot(kind='barh', ax=ax3, color='coral')
            ax3.set_title('Top 10 Employees by Sales', fontsize=12, fontweight='bold')
            ax3.set_xlabel('Total Sales (£)')
        
        # 4. Daily Sales Trend
        ax4 = plt.subplot(3, 3, 4)
        if 'daily_trends' in self.results:
            self.results['daily_trends']['Total_Sales'].plot(kind='line', ax=ax4, color='purple')
            ax4.set_title('Daily Sales Trend', fontsize=12, fontweight='bold')
            ax4.set_ylabel('Sales (£)')
            ax4.set_xlabel('Date')
            plt.xticks(rotation=45)
            ax4.grid(True, alpha=0.3)
        
        # 5. Transaction Count by Day
        ax5 = plt.subplot(3, 3, 5)
        if 'daily_trends' in self.results:
            self.results['daily_trends']['Transaction_Count'].plot(kind='bar', ax=ax5, color='orange', alpha=0.7)
            ax5.set_title('Transactions per Day', fontsize=12, fontweight='bold')
            ax5.set_ylabel('Number of Transactions')
            ax5.set_xlabel('Date')
            plt.xticks(rotation=45)
        
        # 6. Average Transaction Value by Day of Week
        ax6 = plt.subplot(3, 3, 6)
        if 'day_patterns' in self.results:
            self.results['day_patterns'][('Net Sales', 'mean')].plot(kind='bar', ax=ax6, color='teal')
            ax6.set_title('Average Transaction Value by Day', fontsize=12, fontweight='bold')
            ax6.set_ylabel('Average Sale (£)')
            ax6.set_xlabel('Day of Week')
            plt.xticks(rotation=45)
        
        # 7. Top Products
        ax7 = plt.subplot(3, 3, 7)
        if 'product_patterns' in self.results:
            top_products = self.results['product_patterns'].head(10)
            top_products['Total_Sales'].plot(kind='barh', ax=ax7, color='indigo')
            ax7.set_title('Top 10 Products by Sales', fontsize=12, fontweight='bold')
            ax7.set_xlabel('Total Sales (£)')
            ax7.set_yticklabels([p[:30] + '...' if len(p) > 30 else p for p in top_products['Product']], fontsize=8)
        
        # 8. Refund Analysis
        ax8 = plt.subplot(3, 3, 8)
        if 'refund_analysis' in self.results and 'by_employee' in self.results['refund_analysis']:
            refunds_by_emp = self.results['refund_analysis']['by_employee'].head(10)
            refunds_by_emp['Total_Refunds'].plot(kind='bar', ax=ax8, color='red', alpha=0.7)
            ax8.set_title('Refunds by Employee (Top 10)', fontsize=12, fontweight='bold')
            ax8.set_ylabel('Total Refunds (£)')
            ax8.set_xlabel('Employee')
            plt.xticks(rotation=45)
        
        # 9. Sales Distribution
        ax9 = plt.subplot(3, 3, 9)
        self.df_sales['Net Sales'].hist(bins=50, ax=ax9, color='skyblue', edgecolor='black', alpha=0.7)
        ax9.set_title('Sales Distribution', fontsize=12, fontweight='bold')
        ax9.set_ylabel('Frequency')
        ax9.set_xlabel('Net Sales (£)')
        
        plt.tight_layout()
        plt.savefig('sales_pattern_analysis.png', dpi=300, bbox_inches='tight')
        print("\nVisualizations saved to 'sales_pattern_analysis.png'")
        plt.close()
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report"""
        print("\n" + "="*60)
        print("SUMMARY REPORT")
        print("="*60)
        
        total_sales = self.df_sales['Net Sales'].sum()
        total_transactions = len(self.df_sales)
        avg_transaction = total_sales / total_transactions if total_transactions > 0 else 0
        
        print(f"\nOVERALL STATISTICS")
        print(f"Total Sales: £{total_sales:,.2f}")
        print(f"Total Transactions: {total_transactions:,}")
        print(f"Average Transaction Value: £{avg_transaction:,.2f}")
        print(f"Date Range: {self.df_sales['Date'].min().date()} to {self.df_sales['Date'].max().date()}")
        
        if 'day_ranking' in self.results:
            print(f"\nBEST PERFORMING DAY: {self.results['day_ranking'].index[0]}")
        
        if 'peak_hours' in self.results:
            peak_hour = int(self.results['peak_hours'].index[0]) if not pd.isna(self.results['peak_hours'].index[0]) else 0
            print(f"\nPEAK SALES HOUR: {peak_hour:02d}:00")
        
        if 'employee_performance' in self.results:
            top_emp = self.results['employee_performance'].index[0]
            print(f"\nTOP EMPLOYEE: {top_emp}")
        
        if 'refund_analysis' in self.results:
            refund_rate = self.results['refund_analysis'].get('refund_rate', 0)
            print(f"\nREFUND RATE: {refund_rate:.2f}%")
        
        # Save summary to file
        with open('pattern_analysis_summary.txt', 'w') as f:
            f.write("SALES PATTERN RECOGNITION ANALYSIS SUMMARY\n")
            f.write("="*60 + "\n\n")
            f.write(f"Total Sales: £{total_sales:,.2f}\n")
            f.write(f"Total Transactions: {total_transactions:,}\n")
            f.write(f"Average Transaction Value: £{avg_transaction:,.2f}\n\n")
            f.write("Key Insights:\n")
            if 'day_ranking' in self.results:
                f.write(f"- Best Day: {self.results['day_ranking'].index[0]}\n")
            if 'peak_hours' in self.results:
                f.write(f"- Peak Hour: {self.results['peak_hours'].index[0]}:00\n")
            if 'employee_performance' in self.results:
                f.write(f"- Top Employee: {self.results['employee_performance'].index[0]}\n")
        
        print("\nSummary report saved to 'pattern_analysis_summary.txt'")
    
    def export_results(self):
        """Export detailed results to CSV files"""
        print("\n" + "="*60)
        print("EXPORTING RESULTS")
        print("="*60)
        
        if 'day_patterns' in self.results:
            self.results['day_patterns'].to_csv('day_of_week_analysis.csv')
            print("[OK] Day of week analysis exported")
        
        if 'hourly_patterns' in self.results:
            self.results['hourly_patterns'].to_csv('hourly_patterns_analysis.csv')
            print("[OK] Hourly patterns exported")
        
        if 'employee_performance' in self.results:
            self.results['employee_performance'].to_csv('employee_performance_analysis.csv')
            print("[OK] Employee performance exported")
        
        if 'product_patterns' in self.results:
            self.results['product_patterns'].to_csv('product_patterns_analysis.csv')
            print("[OK] Product patterns exported")
        
        if 'daily_trends' in self.results:
            self.results['daily_trends'].to_csv('daily_trends_analysis.csv')
            print("[OK] Daily trends exported")
        
        print("\nAll results exported to CSV files")
    
    def run_full_analysis(self):
        """Run complete pattern recognition analysis"""
        print("\n" + "="*80)
        print("OPATRA SALES PATTERN RECOGNITION ANALYTICS")
        print("="*80)
        
        # Load data
        self.load_data()
        
        # Run all analyses
        self.analyze_day_of_week_patterns()
        self.analyze_time_patterns()
        self.analyze_employee_performance()
        self.analyze_product_patterns()
        self.analyze_trends()
        self.analyze_refund_patterns()
        self.detect_anomalies()
        
        # Generate outputs
        self.generate_visualizations()
        self.generate_summary_report()
        self.export_results()
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE!")
        print("="*80)
        print("\nGenerated Files:")
        print("  - sales_pattern_analysis.png (visualizations)")
        print("  - pattern_analysis_summary.txt (summary report)")
        print("  - Multiple CSV files with detailed analysis")
        print("\n")


def main():
    """Main function to run the analysis"""
    csv_file = "Opatra Sales from July 2023-Grid view.csv"
    
    analyzer = SalesPatternAnalyzer(csv_file)
    analyzer.run_full_analysis()


if __name__ == "__main__":
    main()
