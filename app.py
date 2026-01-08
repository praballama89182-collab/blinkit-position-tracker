import streamlit as st
import pandas as pd
import io

# 1. PAGE SETUP
st.set_page_config(page_title="Blinkit Daily Tracker", layout="wide")

def main():
    st.title("📅 Blinkit Daily Side-by-Side Auction Tracker")
    st.markdown("Upload **Excel (.xlsx)** or **CSV** files to see day-wise changes in Position, CPM, and Impressions.")

    # 2. FILE UPLOADER
    uploaded_files = st.file_uploader("Upload Blinkit Reports", type=['csv', 'xlsx'], accept_multiple_files=True)

    if uploaded_files:
        all_dfs = []
        for file in uploaded_files:
            try:
                if file.name.endswith('.xlsx'):
                    xl = pd.ExcelFile(file)
                    for sheet in xl.sheet_names:
                        df_sheet = pd.read_excel(file, sheet_name=sheet)
                        if not df_sheet.empty:
                            all_dfs.append(df_sheet)
                else:
                    df_csv = pd.read_csv(file)
                    all_dfs.append(df_csv)
            except Exception as e:
                st.error(f"Error reading {file.name}: {e}")

        if all_dfs:
            # 3. STANDARDIZATION & CLEANING
            master_df = pd.concat(all_dfs, ignore_index=True, sort=False)
            master_df.columns = master_df.columns.str.strip()

            # Identify the target (Keyword/Category/Asset)
            if 'Keyword' in master_df.columns: master_df['Target'] = master_df['Keyword']
            elif 'Category Name' in master_df.columns: master_df['Target'] = master_df['Category Name']
            elif 'Asset' in master_df.columns: master_df['Target'] = master_df['Asset']
            else: master_df['Target'] = "Unknown"

            # Date Formatting for Column Headers
            if 'date_ist' in master_df.columns:
                master_df['date_ist'] = pd.to_datetime(master_df['date_ist']).dt.strftime('%Y-%m-%d')
            else:
                st.error("No 'date_ist' column found.")
                return

            # Numeric cleaning
            metrics = ['Most Viewed Position', 'CPM', 'Impressions']
            for m in metrics:
                if m in master_df.columns:
                    master_df[m] = pd.to_numeric(master_df[m], errors='coerce').fillna(0)

            # 4. THE PIVOT (Dates to Columns)
            # This creates a Multi-Index column structure: Date -> Metric
            pivot_df = master_df.pivot_table(
                index=['Campaign Name', 'Target'],
                columns='date_ist',
                values=metrics,
                aggfunc={'Most Viewed Position': 'mean', 'CPM': 'mean', 'Impressions': 'sum'}
            )

            # Reorder columns so they group by Date first, then Metric
            pivot_df = pivot_df.reorder_levels([1, 0], axis=1).sort_index(axis=1)

            # 5. UI & DISPLAY
            st.sidebar.header("Filter Results")
            search_query = st.sidebar.text_input("Search Keyword/Campaign")
            
            if search_query:
                mask = (pivot_df.index.get_level_values(0).astype(str).str.contains(search_query, case=False) | 
                        pivot_df.index.get_level_values(1).astype(str).str.contains(search_query, case=False))
                display_df = pivot_df[mask]
            else:
                display_df = pivot_df

            st.header("🔍 Daily Side-by-Side Tracker")
            
            # Highlight Position 1-3 in Green
            def color_pos(val):
                if isinstance(val, (int, float)) and 1 <= val <= 3:
                    return 'background-color: #C6EFCE; color: #006100;'
                return ''

            st.dataframe(display_df.style.applymap(color_pos), use_container_width=True)

            # 6. EXPORT TO EXCEL
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                display_df.to_excel(writer)
            st.download_button("📥 Download Daily Tracker Sheet", data=output.getvalue(), file_name="daily_side_by_side_tracker.xlsx")

if __name__ == "__main__":
    main()
