import streamlit as st
import pandas as pd
import io
from thefuzz import process

# 1. PAGE SETUP
st.set_page_config(page_title="Daily Position Tracker", layout="wide")

def main():
    st.title("📅 Daily Position & Strategy Tracker")
    
    # 2. SIDEBAR CONFIGURATION
    st.sidebar.header("🎯 Strategy Parameters")
    target_roas = st.sidebar.slider("Target ROAS Threshold", 0.5, 5.0, 1.4, step=0.1)
    
    uploaded_files = st.file_uploader("Upload Blinkit Reports", type=['csv', 'xlsx'], accept_multiple_files=True)

    if uploaded_files:
        all_dfs = []
        for file in uploaded_files:
            try:
                if file.name.endswith('.xlsx'):
                    xl = pd.ExcelFile(file)
                    for sheet in xl.sheet_names:
                        all_dfs.append(pd.read_excel(file, sheet_name=sheet))
                else:
                    all_dfs.append(pd.read_csv(file))
            except Exception as e:
                st.error(f"Error reading {file.name}: {e}")

        if all_dfs:
            # 3. DATA CLEANING & STANDARDIZATION
            master_df = pd.concat(all_dfs, ignore_index=True, sort=False)
            master_df.columns = master_df.columns.str.strip()

            # Renaming and Mapping
            if 'Most Viewed Position' in master_df.columns:
                master_df = master_df.rename(columns={'Most Viewed Position': 'Position'})
            
            if 'Keyword' in master_df.columns: master_df['Target'] = master_df['Keyword']
            elif 'Category Name' in master_df.columns: master_df['Target'] = master_df['Category Name']
            else: master_df['Target'] = "N/A"

            # Strict Rounding to 1 Decimal
            metrics = ['Position', 'CPM', 'Impressions', 'Direct Sales', 'Direct RoAS', 'Estimated Budget Consumed']
            for col in metrics:
                if col in master_df.columns:
                    master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0).round(1)

            if 'date_ist' in master_df.columns:
                master_df['date_ist'] = pd.to_datetime(master_df['date_ist']).dt.strftime('%Y-%m-%d')

            # Fuzzy Search for Campaigns
            all_campaigns = sorted(master_df['Campaign Name'].dropna().unique().tolist())
            search_query = st.sidebar.text_input("Find Campaign", "")
            if search_query:
                matches = process.extract(search_query, all_campaigns, limit=10)
                campaign_options = ["All Campaigns"] + [m[0] for m in matches if m[1] > 45]
            else:
                campaign_options = ["All Campaigns"] + all_campaigns
            selected_campaign = st.sidebar.selectbox("Select Campaign", campaign_options)

            # Filter data
            plot_df = master_df if selected_campaign == "All Campaigns" else master_df[master_df['Campaign Name'] == selected_campaign]

            # --- 4. MAIN TRACKER (PIVOT TABLE) ---
            st.header("🔍 Daily side-by-side Auction Tracker")
            pivot_metrics = ['Position', 'CPM', 'Impressions']
            pivot_df = plot_df.pivot_table(index=['Campaign Name', 'Target'], columns='date_ist', values=pivot_metrics, aggfunc='first').round(1)
            pivot_df = pivot_df.reorder_levels([1, 0], axis=1).sort_index(axis=1)

            def style_tracker(df):
                dates = df.columns.get_level_values(0).unique()
                cool_colors = ['#E1F5FE', '#E0F7FA', '#E0F2F1', '#F0F4C3', '#E8EAF6']
                date_map = {d: cool_colors[i % len(cool_colors)] for i, d in enumerate(dates)}
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                for d in dates:
                    styles.loc[:, d] = f'background-color: {date_map[d]}; color: #333'
                    if (d, 'Position') in df.columns:
                        styles.loc[df[(d, 'Position')].between(1, 3), (d, 'Position')] += '; background-color: #2E7D32; color: white; font-weight: bold'
                return styles

            st.dataframe(pivot_df.style.apply(style_tracker, axis=None).format(precision=1), use_container_width=True)

            # --- 5. STRATEGIC BREAKDOWN SECTIONS ---
            st.markdown("---")
            st.header("💡 Strategic Search Term Analysis")
            
            # Aggregate data to avoid repeats for the analysis section
            agg_df = plot_df.groupby(['Campaign Name', 'Target'], as_index=False).agg({
                'Position': 'mean',
                'CPM': 'mean',
                'Estimated Budget Consumed': 'sum',
                'Direct Sales': 'sum',
                'Direct RoAS': 'mean'
            }).round(1)

            # A. Top Performers (ROAS > Target)
            st.subheader(f"✅ Top 10 Search Terms (ROAS >= {target_roas})")
            top_perf = agg_df[agg_df['Direct RoAS'] >= target_roas].sort_values('Direct Sales', ascending=False).head(10)
            st.dataframe(top_perf[['Campaign Name', 'Target', 'Position', 'CPM', 'Estimated Budget Consumed', 'Direct Sales', 'Direct RoAS']].style.format(precision=1), use_container_width=True)

            # B. Underperformers (ROAS < Target but > 0)
            st.subheader(f"⚠️ Underperforming Search Terms (ROAS < {target_roas})")
            under_perf = agg_df[(agg_df['Direct RoAS'] < target_roas) & (agg_df['Direct RoAS'] > 0)].sort_values('Estimated Budget Consumed', ascending=False).head(10)
            st.dataframe(under_perf[['Campaign Name', 'Target', 'Position', 'CPM', 'Estimated Budget Consumed', 'Direct Sales', 'Direct RoAS']].style.format(precision=1), use_container_width=True)

            # C. Non-Converters (Zero Sales)
            st.subheader("🛑 Non-Converting Keywords (Waste Audit)")
            non_conv = agg_df[agg_df['Direct Sales'] == 0].sort_values('Estimated Budget Consumed', ascending=False).head(10)
            # Exclude Direct Sales as requested
            st.dataframe(non_conv[['Campaign Name', 'Target', 'Position', 'CPM', 'Estimated Budget Consumed']].style.format(precision=1), use_container_width=True)

            # 6. EXPORT
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pivot_df.to_excel(writer, sheet_name='Daily_Tracker')
                agg_df.to_excel(writer, sheet_name='Performance_Summary', index=False)
            st.download_button("📥 Download Full Analysis", data=output.getvalue(), file_name="position_and_strategy_tracker.xlsx")

if __name__ == "__main__":
    main()
