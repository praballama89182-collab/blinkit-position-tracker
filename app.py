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
    
    st.sidebar.markdown("---")
    st.sidebar.header("🔎 Search Filters")
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
            # 3. DATA CLEANING
            master_df = pd.concat(all_dfs, ignore_index=True, sort=False)
            master_df.columns = master_df.columns.str.strip()

            if 'Most Viewed Position' in master_df.columns:
                master_df = master_df.rename(columns={'Most Viewed Position': 'Position'})
            
            if 'Keyword' in master_df.columns: master_df['Target'] = master_df['Keyword']
            elif 'Category Name' in master_df.columns: master_df['Target'] = master_df['Category Name']
            else: master_df['Target'] = "N/A"

            # Numeric Rounding to 1 Decimal
            metrics = ['Position', 'CPM', 'Impressions', 'Direct Sales', 'Direct RoAS', 'Estimated Budget Consumed']
            for col in metrics:
                if col in master_df.columns:
                    master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0).round(1)

            if 'date_ist' in master_df.columns:
                master_df['date_ist'] = pd.to_datetime(master_df['date_ist']).dt.strftime('%Y-%m-%d')

            # --- SEARCH BUTTON LOGIC ---
            search_query = st.sidebar.text_input("Enter Exact Search Term", help="Type the exact keyword to filter everything below.")
            search_clicked = st.sidebar.button("🔍 Exact Search")

            # Initial Campaign Filter (Fuzzy)
            all_campaigns = sorted(master_df['Campaign Name'].dropna().unique().tolist())
            camp_query = st.sidebar.text_input("Filter by Campaign (Optional)", "")
            if camp_query:
                matches = process.extract(camp_query, all_campaigns, limit=5)
                campaign_options = ["All Campaigns"] + [m[0] for m in matches if m[1] > 45]
            else:
                campaign_options = ["All Campaigns"] + all_campaigns
            selected_campaign = st.sidebar.selectbox("Select Campaign", campaign_options)

            # APPLY FILTERS
            final_df = master_df.copy()
            if selected_campaign != "All Campaigns":
                final_df = final_df[final_df['Campaign Name'] == selected_campaign]
            
            # --- THE EXACT SEARCH FILTER ---
            if search_query and search_clicked:
                final_df = final_df[final_df['Target'].astype(str).str.lower() == search_query.lower().strip()]
                if final_df.empty:
                    st.sidebar.warning(f"No exact match found for '{search_query}'")

            # --- 4. MAIN TRACKER (PIVOT TABLE) ---
            st.header("🔍 Daily side-by-side Auction Tracker")
            if not final_df.empty:
                pivot_metrics = ['Position', 'CPM', 'Impressions']
                pivot_df = final_df.pivot_table(index=['Campaign Name', 'Target'], columns='date_ist', values=pivot_metrics, aggfunc='first').round(1)
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
                
                agg_df = final_df.groupby(['Campaign Name', 'Target'], as_index=False).agg({
                    'Position': 'mean', 'CPM': 'mean', 'Estimated Budget Consumed': 'sum',
                    'Direct Sales': 'sum', 'Direct RoAS': 'mean'
                }).round(1)

                # A. Top Performers
                st.subheader(f"✅ Top Performers (ROAS >= {target_roas})")
                top_perf = agg_df[agg_df['Direct RoAS'] >= target_roas].sort_values('Direct Sales', ascending=False).head(10)
                st.dataframe(top_perf[['Campaign Name', 'Target', 'Position', 'CPM', 'Estimated Budget Consumed', 'Direct Sales', 'Direct RoAS']].style.format(precision=1), use_container_width=True)

                # B. Underperformers
                st.subheader(f"⚠️ Underperformers (ROAS < {target_roas})")
                under_perf = agg_df[(agg_df['Direct RoAS'] < target_roas) & (agg_df['Direct RoAS'] > 0)].sort_values('Estimated Budget Consumed', ascending=False).head(10)
                st.dataframe(under_perf[['Campaign Name', 'Target', 'Position', 'CPM', 'Estimated Budget Consumed', 'Direct Sales', 'Direct RoAS']].style.format(precision=1), use_container_width=True)

                # C. Non-Converters
                st.subheader("🛑 Non-Converting Keywords")
                non_conv = agg_df[agg_df['Direct Sales'] == 0].sort_values('Estimated Budget Consumed', ascending=False).head(10)
                st.dataframe(non_conv[['Campaign Name', 'Target', 'Position', 'CPM', 'Estimated Budget Consumed']].style.format(precision=1), use_container_width=True)
            else:
                st.info("No data available for the current filters.")

            # 6. EXPORT
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button("📥 Download Filtered Data", data=output.getvalue(), file_name="exact_search_tracker.xlsx")

if __name__ == "__main__":
    main()
