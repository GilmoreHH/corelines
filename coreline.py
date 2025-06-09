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

# Define business type categories
def get_business_type_categories():
    """Return a dictionary mapping business types to their consolidated categories."""
    type_categories = {
        # Commercial
        "Bond": "Commercial",
        "Builders Risk/Installation - CL": "Commercial",
        "Bumbershoot": "Commercial",
        "Business Owners": "Commercial",
        "Commercial Auto": "Commercial",
        "Commercial Package": "Commercial",
        "Commercial Property": "Commercial",
        "Commercial Umbrella": "Commercial",
        "Crime": "Commercial",
        "Cyber & Privacy Liability": "Commercial",
        "Directors & Officers": "Commercial",
        "Dwelling Fire CL": "Commercial",
        "Errors and Omissions": "Commercial",
        "Flood - CL": "Commercial",
        "General Liability": "Commercial",
        "Inland Marine CL": "Commercial",
        "Marine Package": "Commercial",
        "Surety": "Commercial",
        "Workers Compensation": "Commercial",
        "Employment Practices Liability": "Commercial",
        "Liquor Liability": "Commercial",
        "Wind Only - CL": "Commercial",
        
        # Homeowners
        "Builders Risk/Installation - PL": "Homeowners",
        "Dwelling Fire - PL": "Homeowners",
        "Homeowners": "Homeowners",
        "Mobile Homeowners": "Homeowners",
        "Wind Only - PL": "Homeowners",
        
        # Marine
        "Charter Watercraft": "Marine",
        "Watercraft": "Marine",
        "Yacht": "Marine",
        
        # Flood
        "Flood - PL": "Flood",
        
        # Specialty Lines
        "Golf Cart": "Specialty",
        "Inland Marine PL": "Specialty",
        "Motorcycle/ATV": "Specialty",
        "Motorhome": "Specialty",
        "Recreational Vehicle": "Specialty",
        "Travel Trailer": "Specialty",
        
        # Life
        "Life": "Life",
        
        # Auto
        "Personal Auto": "Auto",
        
        # CPL/Excess CPL
        "Personal Liability": "CPL",
        
        # Umbrella
        "Umbrella": "Umbrella",
    }
    return type_categories

# Define core lines (now includes all major categories)
def get_core_lines():
    """Return a list of core lines for analysis."""
    return ["Auto", "CPL", "Commercial", "Flood", "Homeowners", "Marine", "Specialty", "Umbrella"]

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

        # Get stage metadata and business type categories
        stage_metadata = get_stage_metadata()
        business_type_categories = get_business_type_categories()
        
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
                CloseDate,
                Renewal_Policy_Premium__c
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
            
            # Map business type to consolidated category
            business_category = business_type_categories.get(business_type, "Other")
            
            data.append({
                'StageName': stage_name,
                'StatusCategory': category,
                'RenewalType': renewal_type,
                'BusinessType': business_type,
                'BusinessCategory': business_category,
                'AccountManager': account_manager,
                'CloseDate': record['CloseDate'],
                'AccountName': record.get('Account', {}).get('Name', 'Unknown Account'),
                'Premium': float(record.get('Renewal_Policy_Premium__c', 0) or 0)
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        return df
    
    except Exception as e:
        st.error(f"Error connecting to Salesforce: {str(e)}")
        return pd.DataFrame()

# Calculate retention rates
def calculate_retention_rates(df):
    """Calculate retention rates by business category."""
    retention_data = []
    
    for category in get_core_lines():
        category_data = df[df['BusinessCategory'] == category]
        
        if len(category_data) > 0:
            total_renewals = len(category_data)
            won_renewals = len(category_data[category_data['StatusCategory'] == 'Won'])
            lost_renewals = len(category_data[category_data['StatusCategory'] == 'Lost'])
            open_renewals = len(category_data[category_data['StatusCategory'] == 'Open'])
            
            # Calculate retention rate based on closed opportunities only
            closed_renewals = won_renewals + lost_renewals
            retention_rate = (won_renewals / closed_renewals * 100) if closed_renewals > 0 else 0
            # Calculate premium metrics
            won_premium = category_data[category_data['StatusCategory'] == 'Won']['Premium'].sum()
            lost_premium = category_data[category_data['StatusCategory'] == 'Lost']['Premium'].sum()
            total_premium = category_data['Premium'].sum()
            premium_retention_rate = (won_premium / (won_premium + lost_premium) * 100) if (won_premium + lost_premium) > 0 else 0
            
            retention_data.append({
                'BusinessCategory': category,
                'Total': total_renewals,
                'Won': won_renewals,
                'Lost': lost_renewals,
                'Open': open_renewals,
                'Closed': closed_renewals,
                'RetentionRate': retention_rate,
                'TotalPremium': total_premium,
                'WonPremium': won_premium,
                'LostPremium': lost_premium,
                'PremiumRetentionRate': premium_retention_rate
            })
    
    return pd.DataFrame(retention_data)

# Streamlit UI
st.title("🎯 Core Lines Renewal Performance Dashboard")
st.markdown("**Focus Areas:** Win Rate Analysis, Workload Allocation & Retention Performance")

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

# Business line filters
st.sidebar.subheader("Business Line Filters")
selected_lines = st.sidebar.multiselect(
    "Select Business Lines",
    options=get_core_lines(),
    default=get_core_lines()
)

# Fetch data
with st.spinner("Loading data from Salesforce..."):
    df = connect_to_salesforce(start_date, end_date)

if not df.empty:
    # Display reporting period
    st.info(f"📅 **Reporting Period:** {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
    
    # Apply business line filter
    df_filtered = df[df['BusinessCategory'].isin(selected_lines)]
    
    if df_filtered.empty:
        st.error("❌ No data available for the selected business lines and date range.")
        st.stop()
    
    # === SECTION 1: RETENTION RATES BY BUSINESS LINE ===
    st.header("📈 Retention Rates by Business Line")
    
    retention_df = calculate_retention_rates(df_filtered)
    retention_df = retention_df[retention_df['Closed'] > 0].sort_values('RetentionRate', ascending=False)
    
    if not retention_df.empty:
        # Retention Rate Chart
        fig = px.bar(
            retention_df,
            x='BusinessCategory',
            y='RetentionRate',
            title='Retention Rate by Business Line (Closed Opportunities Only)',
            color='RetentionRate',
            color_continuous_scale='RdYlGn',
            text='RetentionRate'
        )
        
        fig.update_traces(
            texttemplate='%{text:.1f}%',
            textposition='outside'
        )
        
        fig.update_layout(
            xaxis_title='Business Line',
            yaxis_title='Retention Rate (%)',
            height=500,
            yaxis=dict(range=[0, 100])
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Retention metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            top_retention = retention_df.iloc[0]
            st.metric(
                "🏆 Highest Retention",
                top_retention['BusinessCategory'],
                f"{top_retention['RetentionRate']:.1f}%"
            )
        
        with col2:
            avg_retention = retention_df['RetentionRate'].mean()
            st.metric(
                "📊 Average Retention",
                f"{avg_retention:.1f}%",
                f"Across {len(retention_df)} lines"
            )
        
        with col3:
            total_closed = retention_df['Closed'].sum()
            total_won = retention_df['Won'].sum()
            st.metric(
                "🎯 Overall Retention",
                f"{(total_won/total_closed*100):.1f}%",
                f"{total_won}/{total_closed} renewals"
            )
        
        with col4:
            lowest_retention = retention_df.iloc[-1]
            st.metric(
                "⚠️ Lowest Retention",
                lowest_retention['BusinessCategory'],
                f"{lowest_retention['RetentionRate']:.1f}%"
            )
        # Premium-based metrics
        st.subheader("💰 Premium Retention Analysis")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_premium_at_risk = retention_df['TotalPremium'].sum()
            st.metric(
                "💼 Total Premium",
                f"${total_premium_at_risk:,.0f}",
                "All renewal opportunities"
            )
        
        with col2:
            retained_premium = retention_df['WonPremium'].sum()
            st.metric(
                "✅ Retained Premium",
                f"${retained_premium:,.0f}",
                f"{retained_premium/total_premium_at_risk*100:.1f}% of total" if total_premium_at_risk > 0 else "0%"
            )
        
        with col3:
            lost_premium = retention_df['LostPremium'].sum()
            st.metric(
                "❌ Lost Premium",
                f"${lost_premium:,.0f}",
                f"{lost_premium/total_premium_at_risk*100:.1f}% of total" if total_premium_at_risk > 0 else "0%"
            )
        
        with col4:
            overall_premium_retention = (retained_premium / (retained_premium + lost_premium) * 100) if (retained_premium + lost_premium) > 0 else 0
            st.metric(
                "🎯 Premium Retention Rate",
                f"{overall_premium_retention:.1f}%",
                "Closed opportunities only"
            )
        # Detailed retention breakdown chart
        fig2 = go.Figure()
        
        # Add bars for Won, Lost, and Open
        fig2.add_trace(go.Bar(
            name='Won (Retained)',
            x=retention_df['BusinessCategory'],
            y=retention_df['Won'],
            marker_color='green',
            text=retention_df['Won'],
            textposition='auto'
        ))
        
        fig2.add_trace(go.Bar(
            name='Lost',
            x=retention_df['BusinessCategory'],
            y=retention_df['Lost'],
            marker_color='red',
            text=retention_df['Lost'],
            textposition='auto'
        ))
        
        fig2.add_trace(go.Bar(
            name='Open',
            x=retention_df['BusinessCategory'],
            y=retention_df['Open'],
            marker_color='orange',
            text=retention_df['Open'],
            textposition='auto'
        ))
        
        fig2.update_layout(
            title='Renewal Status Breakdown by Business Line',
            xaxis_title='Business Line',
            yaxis_title='Number of Opportunities',
            barmode='stack',
            height=500
        )
        
        st.plotly_chart(fig2, use_container_width=True)
        
        # Show retention table
        if show_data_tables:
            st.subheader("📋 Detailed Retention Analysis")
            display_retention = retention_df.copy()
            display_retention['RetentionRate'] = display_retention['RetentionRate'].round(1)
            
            # Select only the original columns for display
            display_columns = ['BusinessCategory', 'Total', 'Won', 'Lost', 'Open', 'Closed', 'RetentionRate']
            display_retention_filtered = display_retention[display_columns]
            
            display_retention_filtered.columns = [
                'Business Line', 'Total Opps', 'Won', 'Lost', 'Open', 
                'Closed Opps', 'Retention Rate (%)'
            ]
            st.dataframe(display_retention_filtered, use_container_width=True)
    
    # === SECTION 2: WIN RATE COMPARISON ===
    st.header("🏆 Win Rate Performance: Core Lines vs All Lines")
    
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
    
    # Filter data for analysis (exclude marine from "all lines" comparison)
    df_no_marine = df_filtered[df_filtered['BusinessCategory'] != 'Marine']
    df_core = df_filtered[df_filtered['CloseDate'].notna()]
    
    if not df_core.empty:
        # Calculate win rates for both datasets
        all_lines_rates = calculate_win_rates(df_no_marine)
        core_lines_rates = calculate_win_rates(df_core)
        
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
                name='Selected Lines',
                x=comparison_df['AccountManager'],
                y=comparison_df['Core_Lines_Win_Rate'],
                marker_color='#e74c3c',
                text=comparison_df['Core_Lines_Win_Rate'].round(1),
                textposition='auto',
            ))
            
            fig.update_layout(
                title='Win Rate Comparison: All Lines vs Selected Lines Performance',
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
                    "🥇 Top Performer", 
                    top_performer['AccountManager'],
                    f"{top_performer['Core_Lines_Win_Rate']:.1f}%"
                )
            
            with col2:
                avg_core_rate = comparison_df['Core_Lines_Win_Rate'].mean()
                avg_all_rate = comparison_df['All_Lines_Win_Rate'].mean()
                st.metric(
                    "📊 Average Win Rate",
                    f"{avg_core_rate:.1f}%",
                    f"{avg_core_rate - avg_all_rate:+.1f}% vs All Lines"
                )
            
            with col3:
                best_improvement = comparison_df.loc[comparison_df['Difference'].idxmax()]
                st.metric(
                    "📈 Biggest Advantage",
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
                    'Account Manager', 'All Lines Win Rate (%)', 'Selected Lines Win Rate (%)', 
                    'Difference (%)', 'All Lines Total Opps', 'Selected Lines Total Opps'
                ]
                st.dataframe(display_comparison, use_container_width=True)
        else:
            st.warning(f"⚠️ Not enough data for win rate comparison (minimum {min_opportunities} opportunities required).")
    
    # === SECTION 3: WORKLOAD ALLOCATION ===
    st.header("⚖️ Workload Allocation Analysis")
    st.info("📝 **Weighting System:** Flood policies = 0.5 weight, All other lines = 1.0 weight")
    
    # Prepare workload data
    df_workload = df_filtered.copy()
    df_workload['CloseDate'] = pd.to_datetime(df_workload['CloseDate'])
    
    # Apply weighting: Flood = 0.5, others = 1.0
    df_workload['WeightedCount'] = df_workload['BusinessCategory'].apply(
        lambda x: 0.5 if x == 'Flood' else 1.0
    )
    
    # Determine time grouping based on date range
    date_diff = (end_date - start_date).days
    
    if date_diff <= 31:
        if date_diff <= 7:
            df_workload['TimeGroup'] = df_workload['CloseDate'].dt.strftime('%Y-%m-%d')
            time_label = "Day"
        else:
            df_workload['TimeGroup'] = df_workload['CloseDate'].dt.strftime('%Y-W%U')
            time_label = "Week"
    elif date_diff <= 365:
        df_workload['TimeGroup'] = df_workload['CloseDate'].dt.strftime('%Y-%m')
        time_label = "Month"
    else:
        df_workload['TimeGroup'] = df_workload['CloseDate'].dt.to_period('Q').astype(str)
        time_label = "Quarter"
    
    # Calculate workload by Account Manager and Time Period
    workload_summary = df_workload.groupby(['AccountManager', 'TimeGroup', 'BusinessCategory']).agg({
        'BusinessCategory': 'count',  # Count of opportunities
        'WeightedCount': 'first'  # Get the weight
    }).rename(columns={'BusinessCategory': 'Count'})
    
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
        title=f"Workload Distribution by {time_label} (Weighted)",
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
        if len(am_summary) > 0:
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
        flood_policies = len(df_filtered[df_filtered['BusinessCategory'] == 'Flood'])
        st.metric(
            "🌊 Flood Policies",
            f"{flood_policies}",
            f"Weighted as {flood_policies * 0.5:.0f}"
        )
    
    # Show workload breakdown table
    if show_data_tables:
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
st.markdown("**Dashboard Focus:** Comprehensive Business Line Performance Analysis")
st.markdown("🎯 Designed for strategic decision-making on renewal performance, retention rates, and workload distribution")
