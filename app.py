import streamlit as st
import pandas as pd
import io
from thefuzz import process

# 1. PAGE SETUP
st.set_page_config(page_title="Daily Position Tracker", layout="wide")

def main():
    st.title("📅 Daily Position Tracker")
    st.markdown("Consolidated side-by-side view of **Position**, **CPM**, and **Impressions** across dates.")

    # 2. SIDEBAR
    st.sidebar.header("🔍 Filters")
    uploaded_files = st.file_uploader("Upload Blinkit Files", type=['csv', 'xlsx'], accept_multiple_files=True)

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
            # 3. DATA CLEANING & RENAMING
            master_df = pd.concat(all_dfs, ignore_index=True, sort=False)
            master_df.columns = master_df.columns.str.strip()

            # Rename "Most Viewed Position" to "Position" immediately
            if 'Most Viewed Position' in master_df.columns:
                master_df = master_df.rename(columns={'Most Viewed Position': 'Position'})

            # Map Target Identifiers
            if 'Keyword' in master_df.columns: master_df['Target'] = master_df['Keyword']
            elif 'Category Name' in master_df.columns: master_df['Target'] = master_df['Category Name']
            else: master_df['Target'] = "N/A"

            # Strict Rounding for the whole dataframe to 1 decimal
            metrics = ['Position', 'CPM', 'Impressions', 'Direct Sales', 'Direct RoAS']
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
            selected_campaign = st.sidebar.selectbox("Select", campaign_options)

            # Filter data
            plot_df = master_df if selected_campaign == "All Campaigns" else master_df[master_df['Campaign Name'] == selected_campaign]

            # --- 4. THE PIVOT (Dates as Columns) ---
            pivot_metrics = ['Position', 'CPM', 'Impressions']
            pivot_df = plot_df.pivot_table(
                index=['Campaign Name', 'Target'], 
                columns='date_ist', 
                values=pivot_metrics, 
                aggfunc='first'
            ).round(1)

            # Order by Date (Level 0) then Metric (Level 1)
            pivot_df = pivot_df.reorder_levels([1, 0], axis=1).sort_index(axis=1)

            # --- 5. STYLING (Cool Colors + 1 Decimal Format) ---
            def style_tracker(df):
                dates = df.columns.get_level_values(0).unique()
                # Cool shades palette
                cool_colors = ['#E1F5FE', '#E0F7FA', '#E0F2F1', '#F0F4C3', '#E8EAF6']
                date_map = {d: cool_colors[i % len(cool_colors)] for i, d in enumerate(dates)}
                
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                for d in dates:
                    styles.loc[:, d] = f'background-color: {date_map[d]}; color: #333'
                    pos_col = (d, 'Position')
                    if pos_col in df.columns:
                        # Highlight Top Positions (1 to 3) in Dark Green
                        styles.loc[df[pos_col].between(1, 3), pos_col] += '; background-color: #2E7D32; color: white; font-weight: bold'
                return styles

            # Force exactly 1 decimal place display
            formatted_df = pivot_df.style.apply(style_tracker, axis=None).format(precision=1)

            st.header(f"📊 Tracking: {selected_campaign}")
            st.info("Columns are grouped by Date. Values rounded to 1 decimal.")
            st.dataframe(formatted_df, use_container_width=True)

            # 6. EXPORT
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pivot_df.to_excel(writer)
            st.download_button("📥 Download Position Tracker", data=output.getvalue(), file_name="position_tracker.xlsx")

if __name__ == "__main__":
    main()
