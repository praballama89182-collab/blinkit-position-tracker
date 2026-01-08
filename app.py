import streamlit as st
import pandas as pd
import io
from thefuzz import process

# 1. PAGE SETUP
st.set_page_config(page_title="Daily Position Tracker", layout="wide")

def main():
    st.title("📅 Daily Position & Auction Tracker")
    st.markdown("Consolidated side-by-side view of Position, CPM, and Impressions across dates.")

    # 2. SIDEBAR FILTERS
    st.sidebar.header("🔍 Search & Filter")
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

            # Map Target Identifiers
            if 'Keyword' in master_df.columns: master_df['Target'] = master_df['Keyword']
            elif 'Category Name' in master_df.columns: master_df['Target'] = master_df['Category Name']
            elif 'Asset' in master_df.columns: master_df['Target'] = master_df['Asset']
            else: master_df['Target'] = "N/A"

            # Date Formatting for Pivot Headers
            if 'date_ist' in master_df.columns:
                master_df['date_ist'] = pd.to_datetime(master_df['date_ist']).dt.strftime('%Y-%m-%d')
            else:
                st.error("No 'date_ist' column found."); return

            # Numeric Conversion & Rounding to ONE Decimal
            metrics = ['Most Viewed Position', 'CPM', 'Impressions', 'Direct Sales', 'Direct RoAS']
            for col in metrics:
                if col in master_df.columns:
                    master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0).round(1)

            # --- SEARCH CAMPAIGN ---
            all_campaigns = sorted(master_df['Campaign Name'].dropna().unique().tolist())
            search_query = st.sidebar.text_input("Find Campaign (Similar matches)", "")
            if search_query:
                matches = process.extract(search_query, all_campaigns, limit=10)
                campaign_options = ["All Campaigns"] + [m[0] for m in matches if m[1] > 45]
            else:
                campaign_options = ["All Campaigns"] + all_campaigns
            selected_campaign = st.sidebar.selectbox("Select Campaign", campaign_options)

            # Filter data based on selection
            plot_df = master_df if selected_campaign == "All Campaigns" else master_df[master_df['Campaign Name'] == selected_campaign]

            # --- 4. THE PIVOT (Dates as Columns) ---
            pivot_metrics = ['Most Viewed Position', 'CPM', 'Impressions']
            pivot_df = plot_df.pivot_table(
                index=['Campaign Name', 'Target'], 
                columns='date_ist', 
                values=pivot_metrics, 
                aggfunc='first'
            ).round(1)

            # Reorder levels: Date (Level 0) -> Metric (Level 1)
            pivot_df = pivot_df.reorder_levels([1, 0], axis=1).sort_index(axis=1)

            # --- 5. COLOR CODING (Shades of Cool Colors) ---
            def style_cool_shades(df):
                dates = df.columns.get_level_values(0).unique()
                
                # List of Cool Shades: Sky Blue, Light Cyan, Pale Turquoise, Powder Blue, Alice Blue
                cool_colors = ['#E1F5FE', '#E0F7FA', '#E0F2F1', '#F0F4C3', '#E8EAF6', '#F3E5F5']
                date_map = {d: cool_colors[i % len(cool_colors)] for i, d in enumerate(dates)}
                
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                for d in dates:
                    styles.loc[:, d] = f'background-color: {date_map[d]}; color: #333333; border: 1px solid #dee2e6'
                    
                    # Special Highlight for Top Positions (1-3)
                    pos_col = (d, 'Most Viewed Position')
                    if pos_col in df.columns:
                        styles.loc[df[pos_col].between(1, 3), pos_col] += '; background-color: #2E7D32; color: white; font-weight: bold'
                
                return styles

            # DISPLAY
            st.header(f"📊 Tracking: {selected_campaign}")
            st.info("Values are rounded to 1 decimal. Different cool shades distinguish each date.")
            st.dataframe(pivot_df.style.apply(style_cool_shades, axis=None), use_container_width=True)

            # 6. EXPORT
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pivot_df.to_excel(writer)
            st.download_button("📥 Download Daily Pivot Sheet", data=output.getvalue(), file_name="daily_position_tracker.xlsx")

if __name__ == "__main__":
    main()
