import streamlit as st
import pandas as pd
import io
import plotly.graph_objects as go
from thefuzz import process

# 1. PAGE SETUP
st.set_page_config(page_title="Blinkit Ads Intelligence Pro", layout="wide")

def main():
    st.title("🚀 Blinkit Ads Strategic Decision Engine")
    st.markdown("Advanced Performance, Weekly Trends, and Daily Auction Tracker.")

    # 2. SIDEBAR CONFIGURATION
    st.sidebar.header("🎯 Strategy Parameters")
    perf_roas_threshold = st.sidebar.slider("Performance ROAS Threshold", 0.5, 5.0, 1.4, step=0.1)
    bid_roas_threshold = st.sidebar.slider("Bidding Action ROAS Threshold", 0.5, 5.0, 1.8, step=0.1)
    min_spend_waste = st.sidebar.number_input("Min Spend to Flag Waste (₹)", value=200)

    uploaded_files = st.file_uploader("Upload Blinkit Reports (Excel/CSV)", type=['csv', 'xlsx'], accept_multiple_files=True)

    if uploaded_files:
        all_dfs = []
        for file in uploaded_files:
            try:
                if file.name.endswith('.xlsx'):
                    xl = pd.ExcelFile(file)
                    for sheet in xl.sheet_names:
                        df = pd.read_excel(file, sheet_name=sheet)
                        all_dfs.append(df)
                else:
                    all_dfs.append(pd.read_csv(file))
            except Exception as e:
                st.error(f"Error reading {file.name}: {e}")

        if all_dfs:
            # 3. CONSOLIDATION & CLEANING
            master_df = pd.concat(all_dfs, ignore_index=True, sort=False)
            master_df.columns = master_df.columns.str.strip()

            # Mapping Target Identifiers
            if 'Keyword' in master_df.columns: master_df['Target'] = master_df['Keyword']
            elif 'Category Name' in master_df.columns: master_df['Target'] = master_df['Category Name']
            elif 'Asset' in master_df.columns: master_df['Target'] = master_df['Asset']
            else: master_df['Target'] = "N/A"

            # Date Conversion for Trend Analysis
            if 'date_ist' in master_df.columns:
                master_df['date_ist'] = pd.to_datetime(master_df['date_ist'])
                master_df['Day of Week'] = master_df['date_ist'].dt.day_name()
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                master_df['Day of Week'] = pd.Categorical(master_df['Day of Week'], categories=day_order, ordered=True)
                # For Pivot Table
                master_df['date_str'] = master_df['date_ist'].dt.strftime('%Y-%m-%d')

            # Numeric Conversion & ROUNDING to 2 Decimals
            numeric_cols = ['Direct Sales', 'Estimated Budget Consumed', 'CPM', 'Direct RoAS', 'Impressions', 'Most Viewed Position']
            for col in numeric_cols:
                if col in master_df.columns:
                    master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0).round(2)

            # --- SEARCH CAMPAIGN ---
            st.sidebar.markdown("---")
            st.sidebar.header("🔍 Search Campaign")
            all_campaigns = sorted(master_df['Campaign Name'].dropna().unique().tolist())
            search_query = st.sidebar.text_input("Type to find similar campaigns", "")
            if search_query:
                matches = process.extract(search_query, all_campaigns, limit=10)
                campaign_options = ["All Campaigns"] + [match[0] for match in matches if match[1] > 45]
            else:
                campaign_options = ["All Campaigns"] + all_campaigns
            selected_campaign = st.sidebar.selectbox("Select Campaign", campaign_options)

            plot_df = master_df if selected_campaign == "All Campaigns" else master_df[master_df['Campaign Name'] == selected_campaign]

            # --- 4. TABS ---
            tab_daily, tab_trend, tab_perf, tab_eff, tab_bids = st.tabs([
                "📅 Daily Tracker", "📈 Weekly Trends", "🏆 Performance", "🛑 Waste Audit", "⚖️ Bidding"
            ])

            with tab_daily:
                st.subheader("Daily Auction Tracker (Color-Coded & Rounded)")
                pivot_metrics = ['Most Viewed Position', 'CPM', 'Impressions']
                pivot_df = plot_df.pivot_table(index=['Campaign Name', 'Target'], columns='date_str', values=pivot_metrics, aggfunc='first').round(2)
                pivot_df = pivot_df.reorder_levels([1, 0], axis=1).sort_index(axis=1)

                # Styling: Alternating Date Colors
                def style_daily(df):
                    dates = df.columns.get_level_values(0).unique()
                    colors = ['#f8f9fa', '#eef2f7'] # Subtle alternate cool shades
                    date_map = {d: colors[i % 2] for i, d in enumerate(dates)}
                    styles = pd.DataFrame('', index=df.index, columns=df.columns)
                    for d in dates:
                        styles.loc[:, d] = f'background-color: {date_map[d]}'
                        pos_col = (d, 'Most Viewed Position')
                        if pos_col in df.columns:
                            styles.loc[df[pos_col].between(1, 3), pos_col] += '; background-color: #d4edda; color: #155724; font-weight: bold'
                    return styles

                st.dataframe(pivot_df.style.apply(style_daily, axis=None), use_container_width=True)

            with tab_trend:
                st.header("Weekly Spend vs Sales Trend")
                if 'Day of Week' in plot_df.columns:
                    weekly = plot_df.groupby('Day of Week', observed=False).agg({'Estimated Budget Consumed': 'sum', 'Direct Sales': 'sum'}).reset_index()
                    weekly['ROAS'] = (weekly['Direct Sales'] / weekly['Estimated Budget Consumed'].replace(0, 1)).round(2)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=weekly['Day of Week'], y=weekly['Estimated Budget Consumed'], name='Spend', marker_color='#4A90E2'))
                    fig.add_trace(go.Bar(x=weekly['Day of Week'], y=weekly['Direct Sales'], name='Sales', marker_color='#50E3C2'))
                    fig.add_trace(go.Scatter(x=weekly['Day of Week'], y=weekly['ROAS'], name='ROAS', yaxis='y2', line=dict(color='#AB63FA', width=4)))
                    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='group')
                    st.plotly_chart(fig, use_container_width=True)

            with tab_perf:
                st.subheader("Performance Summary (Aggregated)")
                summary = plot_df.groupby(['Target', 'Campaign Name']).agg({'Direct Sales': 'sum', 'Estimated Budget Consumed': 'sum'}).reset_index()
                summary['ROAS'] = (summary['Direct Sales'] / summary['Estimated Budget Consumed'].replace(0, 1)).round(2)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.success(f"Healthy (ROAS >= {perf_roas_threshold})")
                    st.dataframe(summary[summary['ROAS'] >= perf_roas_threshold].sort_values('Direct Sales', ascending=False), use_container_width=True)
                with c2:
                    st.error(f"Below Target (ROAS < {perf_roas_threshold})")
                    st.dataframe(summary[(summary['ROAS'] < perf_roas_threshold) & (summary['ROAS'] > 0)], use_container_width=True)

            with tab_eff:
                st.subheader("Waste Audit (Unique Keywords)")
                # Aggregated Waste logic to avoid repeats
                waste = plot_df.groupby(['Target', 'Campaign Name']).agg({'Direct Sales': 'sum', 'Estimated Budget Consumed': 'sum', 'CPM': 'mean'}).reset_index()
                waste = waste[(waste['Direct Sales'] == 0) & (waste['Estimated Budget Consumed'] > min_spend_waste)].round(2)
                st.dataframe(waste.sort_values('Estimated Budget Consumed', ascending=False), use_container_width=True)

            with tab_bids:
                st.subheader("CPM Optimization (Threshold: " + str(bid_roas_threshold) + ")")
                bids = plot_df.groupby(['Target', 'Campaign Name']).agg({'Direct Sales': 'sum', 'Direct RoAS': 'mean', 'CPM': 'mean'}).reset_index()
                avg_cpm = bids['CPM'].mean()
                bids_opt = bids[(bids['Direct RoAS'] >= bid_roas_threshold) & (bids['CPM'] > avg_cpm)].round(2)
                st.dataframe(bids_opt, use_container_width=True)

            # EXPORT
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                master_df.to_excel(writer, index=False)
            st.download_button("📥 Download Action Plan", data=output.getvalue(), file_name="blinkit_final_report.xlsx")

if __name__ == "__main__":
    main()
