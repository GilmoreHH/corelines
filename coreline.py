import streamlit as st
from simple_salesforce import Salesforce
import os
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import datetime

# Load environment variables from .env file
load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="Core Lines Renewal Performance Dashboard",
    page_icon="🎯",
    layout="wide",
)

# Define all stages and their simplified categories
def get_stage_metadata():
    """Return a dictionary of stages with their categories."""
    stages = {
        "New": {"category": "Open"},
        "Information Gathering": {"category": "Open"},
        "Rating": {"category": "Open"},
        "Proposal Generation": {"category": "Open"},
        "Decision Pending": {"category": "Open"},
        "Pre-Bind Review": {"category": "Open"},
        "Quote to Bind": {"category": "Open"},
        "Binding": {"category": "Open"},
        "Billing": {"category": "Open"},
        "Post-Binding": {"category": "Open"},
        "Closed Won": {"category": "Won"},
        "Closed Lost": {"category": "Lost"}
    }
    return stages

# Define core lines
def get_core_lines():
    """Return a list of core lines for analysis."""
    return ["Auto", "Flood", "Homeowners", "Umbrella"]

# Function to connect to Salesforce and run SOQL queries
def connect_to_salesforce(start_date=None, end_date=None):
    """Connect to Salesforce and execute SOQL queries with optional date range."""
    try:
        # Salesforce connection using environment variables
        sf = Salesforce(
            username=os.getenv("SF_USERNAME_PRO"),
            password=os.getenv("SF_PASSWORD_PRO"),
            security_token=os.getenv("SF_SECURITY_TOKEN_PRO"),
        )

        # Get stage metadata
        stage_metadata = get_stage_metadata()
        
        # Prepare date filter
        date_filter = ""
        if start_date and end_date:
            # Convert dates to Salesforce date format (YYYY-MM-DD)
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            date_filter = f"AND CloseDate >= {start_date_str} AND CloseDate <= {end_date_str}"
        
        # Query Account Manager information
        account_query = """
            SELECT 
                Id, 
                Name,
                Account_Manager__c,
                Account_Manager__r.Name
            FROM Account
            WHERE Account_Manager__c != null
        """
        
        account_results = sf.query_all(account_query)
        
        # Create a dictionary to map Account IDs to their Account Managers
        account_manager_map = {}
        for record in account_results['records']:
            account_id = record['Id']
            producer_name = record.get('Account_Manager__r', {}).get('Name', 'Not Assigned')
            account_manager_map[account_id] = producer_name
        
        # Query Opportunity records with Account relationship
        opportunity_query = f"""
            SELECT 
                Id, 
                StageName, 
                Type,
                AccountId,
                Account.Name,
                New_Business_or_Renewal__c,
                CloseDate
            FROM Opportunity
            WHERE New_Business_or_Renewal__c IN ('Personal Lines - Renewal', 'Commercial Lines - Renewal')
            {date_filter}
        """
        
        opportunity_results = sf.query_all(opportunity_query)
        
        # Process results into a DataFrame
        data = []
        for record in opportunity_results['records']:
            stage_name = record['StageName']
            renewal_type = record['New_Business_or_Renewal__c']
            business_type = record.get('Type', 'Not Specified')
            account_id = record['AccountId']
            
            # Get account manager from the account_manager_map
            account_manager = account_manager_map.get(account_id, "Not Assigned")
            
            # Get stage category
            category = stage_metadata.get(stage_name, {"category": "Unknown"})["category"]
            
            data.append({
                'StageName': stage_name,
                'StatusCategory': category,
                'RenewalType': renewal_type,
                'BusinessType': business_type,
                'AccountManager': account_manager,
                'CloseDate': record['CloseDate'],
                'AccountName': record.get('Account', {}).get('Name', 'Unknown Account')
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        return df
    
    except Exception as e:
        st.error(f"Error connecting to Salesforce: {str(e)}")
        return pd.DataFrame()

# Streamlit UI
st.title("🎯 Core Lines Renewal Performance Dashboard")
st.markdown("**Focus Areas:** Win Rate Analysis & Workload Allocation for Strategic Decision Making")

# Get current date
today = datetime.datetime.today()

# Sidebar for filters
st.sidebar.header("📊 Dashboard Filters")

# Date range selection
st.sidebar.subheader("Date Range Selection")
date_range_type = st.sidebar.radio(
    "Select Date Range Type",
    ["Predefined", "Custom"]
)

# Date range logic
if date_range_type == "Predefined":
    time_period = st.sidebar.selectbox(
        "Select Time Period",
        options=["Last 7 Days", "Last 30 Days", "Last Quarter", "Year to Date"],
        index=2  # Default to Last Quarter
    )
    
    # Determine dates based on selection
    if time_period == "Last 7 Days":
        start_date = today - datetime.timedelta(days=7)
        end_date = today
    elif time_period == "Last 30 Days":
        start_date = today - datetime.timedelta(days=30)
        end_date = today
    elif time_period == "Last Quarter":
        start_date = today - datetime.timedelta(days=90)
        end_date = today
    else:  # Year to Date
        start_date = datetime.datetime(today.year, 1, 1).date()
        end_date = today
else:
    # Custom date range
    start_date = st.sidebar.date_input(
        "Start Date", 
        value=today - datetime.timedelta(days=90),
        max_value=today
    )
    end_date = st.sidebar.date_input(
        "End Date", 
        value=today,
        max_value=today
    )

    # Validate dates
    if start_date > end_date:
        st.sidebar.error("Start date must be before or equal to end date.")
        start_date, end_date = end_date, start_date

# Additional display options
st.sidebar.subheader("Display Options")
show_data_tables = st.sidebar.checkbox("Show Data Tables", value=True)
min_opportunities = st.sidebar.slider("Minimum Opportunities for Win Rate Analysis", 
                                     min_value=1, max_value=10, value=3)

# Fetch data
with st.spinner("Loading data from Salesforce..."):
    df = connect_to_salesforce(start_date, end_date)

if not df.empty:
    # Display reporting period
    st.info(f"📅 **Reporting Period:** {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
    
    # Get core lines data
    core_lines = get_core_lines()
    
    # Filter data for analysis
    df_no_marine = df[~df['BusinessType'].str.contains('Marine', case=False, na=False)]
    df_core = df[df['BusinessType'].isin(core_lines) & df['CloseDate'].notna()]
    
    if df_core.empty:
        st.error("❌ No core lines data available for the selected date range.")
        st.stop()
    
    # Calculate metrics for both datasets
    def calculate_win_rates(dataframe):
        """Calculate win rates by account manager."""
        am_status_df = dataframe.groupby(['AccountManager', 'StatusCategory']).size().reset_index(name='Count')
        am_pivot = am_status_df.pivot(index='AccountManager', columns='StatusCategory', values='Count').fillna(0)
        
        # Ensure all categories exist
        for category in ['Won', 'Lost', 'Open']:
            if category not in am_pivot.columns:
                am_pivot[category] = 0
        
        # Calculate totals and win rates
        am_pivot['Total'] = am_pivot.sum(axis=1)
        closed_ops = am_pivot['Won'] + am_pivot['Lost']
        am_pivot['Win_Rate'] = (am_pivot['Won'] / closed_ops * 100).fillna(0).round(1)
        
        return am_pivot
    
    # Calculate win rates for both datasets
    all_lines_rates = calculate_win_rates(df_no_marine)
    core_lines_rates = calculate_win_rates(df_core)
    
    # === SECTION 1: WIN RATE COMPARISON ===
    st.header("🏆 Win Rate Performance: Core Lines vs All Lines")
    
    # Create comparison data
    comparison_data = []
    common_managers = set(all_lines_rates.index) & set(core_lines_rates.index)
    
    for manager in common_managers:
        all_closed = all_lines_rates.loc[manager, 'Won'] + all_lines_rates.loc[manager, 'Lost']
        core_closed = core_lines_rates.loc[manager, 'Won'] + core_lines_rates.loc[manager, 'Lost']
        
        if all_closed >= min_opportunities and core_closed >= min_opportunities:
            comparison_data.append({
                'AccountManager': manager,
                'All_Lines_Win_Rate': all_lines_rates.loc[manager, 'Win_Rate'],
                'Core_Lines_Win_Rate': core_lines_rates.loc[manager, 'Win_Rate'],
                'Difference': core_lines_rates.loc[manager, 'Win_Rate'] - all_lines_rates.loc[manager, 'Win_Rate'],
                'All_Lines_Total': int(all_lines_rates.loc[manager, 'Total']),
                'Core_Lines_Total': int(core_lines_rates.loc[manager, 'Total'])
            })
    
    if comparison_data:
        comparison_df = pd.DataFrame(comparison_data)
        comparison_df = comparison_df.sort_values('Core_Lines_Win_Rate', ascending=False)
        
        # Win Rate Comparison Chart
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='All Lines (Exc. Marine)',
            x=comparison_df['AccountManager'],
            y=comparison_df['All_Lines_Win_Rate'],
            marker_color='#3498db',
            text=comparison_df['All_Lines_Win_Rate'].round(1),
            textposition='auto',
        ))
        
        fig.add_trace(go.Bar(
            name='Core Lines Only',
            x=comparison_df['AccountManager'],
            y=comparison_df['Core_Lines_Win_Rate'],
            marker_color='#e74c3c',
            text=comparison_df['Core_Lines_Win_Rate'].round(1),
            textposition='auto',
        ))
        
        fig.update_layout(
            title='Win Rate Comparison: All Lines vs Core Lines Performance',
            xaxis_title='Account Manager',
            yaxis_title='Win Rate (%)',
            barmode='group',
            height=500,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Key Insights
        col1, col2, col3 = st.columns(3)
        
        with col1:
            top_performer = comparison_df.iloc[0]
            st.metric(
                "🥇 Top Core Lines Performer", 
                top_performer['AccountManager'],
                f"{top_performer['Core_Lines_Win_Rate']:.1f}%"
            )
        
        with col2:
            avg_core_rate = comparison_df['Core_Lines_Win_Rate'].mean()
            avg_all_rate = comparison_df['All_Lines_Win_Rate'].mean()
            st.metric(
                "📊 Average Core Lines Win Rate",
                f"{avg_core_rate:.1f}%",
                f"{avg_core_rate - avg_all_rate:+.1f}% vs All Lines"
            )
        
        with col3:
            best_improvement = comparison_df.loc[comparison_df['Difference'].idxmax()]
            st.metric(
                "📈 Biggest Core Lines Advantage",
                best_improvement['AccountManager'],
                f"+{best_improvement['Difference']:.1f}%"
            )
        
        # Show comparison table
        if show_data_tables:
            st.subheader("📋 Detailed Win Rate Comparison")
            display_comparison = comparison_df.copy()
            display_comparison['All_Lines_Win_Rate'] = display_comparison['All_Lines_Win_Rate'].round(1)
            display_comparison['Core_Lines_Win_Rate'] = display_comparison['Core_Lines_Win_Rate'].round(1)
            display_comparison['Difference'] = display_comparison['Difference'].round(1)
            
            display_comparison.columns = [
                'Account Manager', 'All Lines Win Rate (%)', 'Core Lines Win Rate (%)', 
                'Difference (%)', 'All Lines Total Opps', 'Core Lines Total Opps'
            ]
            st.dataframe(display_comparison, use_container_width=True)
    else:
        st.warning(f"⚠️ Not enough data for win rate comparison (minimum {min_opportunities} opportunities required).")
    
    # === SECTION 2: WORKLOAD ALLOCATION ===
    st.header("⚖️ Core Lines Workload Allocation Analysis")
    st.info("📝 **Weighting System:** Flood policies = 0.5 weight, All other core lines = 1.0 weight")
    
    # Prepare workload data
    df_core_workload = df_core.copy()
    df_core_workload['CloseDate'] = pd.to_datetime(df_core_workload['CloseDate'])
    
    # Apply weighting: Flood = 0.5, others = 1.0
    df_core_workload['WeightedCount'] = df_core_workload['BusinessType'].apply(
        lambda x: 0.5 if x == 'Flood' else 1.0
    )
    
    # Determine time grouping based on date range
    date_diff = (end_date - start_date).days
    
    if date_diff <= 31:
        if date_diff <= 7:
            df_core_workload['TimeGroup'] = df_core_workload['CloseDate'].dt.strftime('%Y-%m-%d')
            time_label = "Day"
        else:
            df_core_workload['TimeGroup'] = df_core_workload['CloseDate'].dt.strftime('%Y-W%U')
            time_label = "Week"
    elif date_diff <= 365:
        df_core_workload['TimeGroup'] = df_core_workload['CloseDate'].dt.strftime('%Y-%m')
        time_label = "Month"
    else:
        df_core_workload['TimeGroup'] = df_core_workload['CloseDate'].dt.to_period('Q').astype(str)
        time_label = "Quarter"
    
    # Calculate workload by Account Manager and Time Period
    workload_summary = df_core_workload.groupby(['AccountManager', 'TimeGroup', 'BusinessType']).agg({
        'BusinessType': 'count',  # Count of opportunities
        'WeightedCount': 'first'  # Get the weight
    }).rename(columns={'BusinessType': 'Count'})
    
    # Apply the weighting
    workload_summary['WeightedCount'] = workload_summary['Count'] * workload_summary['WeightedCount']
    workload_summary = workload_summary.reset_index()
    
    # Calculate totals per account manager and time period
    time_totals = workload_summary.groupby(['AccountManager', 'TimeGroup']).agg({
        'Count': 'sum',
        'WeightedCount': 'sum'
    }).reset_index()
    
    # Workload Over Time Chart
    fig = px.bar(
        time_totals,
        x="TimeGroup",
        y="WeightedCount",
        color="AccountManager",
        title=f"Core Lines Workload Distribution by {time_label} (Weighted)",
        barmode="group",
        height=500
    )
    fig.update_layout(
        xaxis_title=time_label, 
        yaxis_title="Weighted Policy Count",
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Overall Workload Summary
    st.subheader("📊 Account Manager Workload Summary")
    
    am_summary = time_totals.groupby('AccountManager').agg({
        'Count': 'sum',
        'WeightedCount': 'sum'
    }).reset_index()
    am_summary = am_summary.sort_values('WeightedCount', ascending=False)
    am_summary['Workload_Reduction'] = am_summary['Count'] - am_summary['WeightedCount']
    am_summary.columns = ['Account Manager', 'Total Policies', 'Weighted Total', 'Workload Reduction']
    
    # Workload Summary Chart
    fig = px.bar(
        am_summary.head(10),  # Top 10 by workload
        x="Account Manager",
        y="Weighted Total",
        title="Account Manager Workload Ranking (Weighted Total)",
        color="Weighted Total",
        color_continuous_scale=px.colors.sequential.Viridis,
        text="Weighted Total"
    )
    fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Key Workload Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        highest_workload = am_summary.iloc[0]
        st.metric(
            "🔥 Highest Workload",
            highest_workload['Account Manager'],
            f"{highest_workload['Weighted Total']:.0f} policies"
        )
    
    with col2:
        total_reduction = am_summary['Workload Reduction'].sum()
        st.metric(
            "💡 Total Workload Reduction",
            f"{total_reduction:.0f} policies",
            "Due to Flood weighting"
        )
    
    with col3:
        avg_workload = am_summary['Weighted Total'].mean()
        st.metric(
            "📊 Average Workload",
            f"{avg_workload:.0f} policies",
            f"Across {len(am_summary)} managers"
        )
    
    with col4:
        flood_policies = len(df_core[df_core['BusinessType'] == 'Flood'])
        st.metric(
            "🌊 Flood Policies",
            f"{flood_policies}",
            f"Weighted as {flood_policies * 0.5:.0f}"
        )
    
    # Detailed workload breakdown
    if show_data_tables:
        st.subheader(f"📋 Detailed Workload Breakdown by {time_label}")
        
        # Create comprehensive breakdown
        detailed_breakdown = []
        
        for (manager, time_period), period_data in workload_summary.groupby(['AccountManager', 'TimeGroup']):
            row = {
                'Account Manager': manager,
                time_label: time_period,
                'Auto': 0, 'Flood': 0, 'Homeowners': 0, 'Umbrella': 0
            }
            
            # Fill in actual values
            for _, line_data in period_data.iterrows():
                line_type = line_data['BusinessType']
                count = line_data['Count']
                
                if line_type in ['Auto', 'Flood', 'Homeowners', 'Umbrella']:
                    row[line_type] = count
            
            # Calculate totals
            row['Total_Count'] = sum([row['Auto'], row['Flood'], row['Homeowners'], row['Umbrella']])
            row['Weighted_Total'] = row['Auto'] + (row['Flood'] * 0.5) + row['Homeowners'] + row['Umbrella']
            
            detailed_breakdown.append(row)
        
        if detailed_breakdown:
            detailed_df = pd.DataFrame(detailed_breakdown)
            detailed_df = detailed_df.sort_values([time_label, 'Account Manager'])
            
            # Format for display
            display_cols = ['Account Manager', time_label, 'Homeowners', 'Flood', 'Auto', 'Umbrella', 'Total_Count', 'Weighted_Total']
            detailed_display = detailed_df[display_cols].copy()
            detailed_display.columns = ['Account Manager', time_label, 'Home', 'Flood', 'Auto', 'Umbrella', 'Total Count', 'Weighted Total']
            
            st.dataframe(detailed_display, use_container_width=True)
            
            # Show calculation example
            st.success("💡 **Example:** If John has Home: 100, Flood: 200, Auto: 150, Umbrella: 50 → Weighted Total = 400 (500 total - 100 reduction from Flood)")
        
        # Overall summary table
        st.subheader("📊 Overall Account Manager Summary")
        st.dataframe(am_summary, use_container_width=True)

else:
    st.error("❌ No data available for the selected date range. Please adjust your filters or check your Salesforce connection.")
    st.info("💡 **Troubleshooting Tips:**")
    st.markdown("""
    - Verify your Salesforce credentials in the .env file
    - Check if there are renewal opportunities in the selected date range
    - Ensure the renewal types ('Personal Lines - Renewal', 'Commercial Lines - Renewal') exist in your data
    - Try expanding the date range
    """)

# Footer
st.markdown("---")
st.markdown("**Dashboard Focus:** Core Lines (Auto, Flood, Homeowners, Umbrella) Performance Analysis")
st.markdown("🎯 Designed for strategic decision-making on renewal performance and workload distribution")
