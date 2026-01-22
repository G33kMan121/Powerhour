import streamlit as st
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Donor Arrival Analyzer", layout="wide")

st.title("🩸 Power Hour Analyzer")
st.write("Upload the 'Arrival Patterns' Excel export to calculate staffing needs.")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Settings")
    
    # Toggle for 4-Week Logic
    report_type = st.radio(
        "Report Duration",
        ["Single Week Data", "4-Week Rollup"],
        index=1, # Defaults to 4-Week because that is standard procedure
        help="Select '4-Week Rollup' to automatically divide the numbers by 4 to get a weekly average."
    )
    
    # Trigger Threshold
    trigger_count = st.number_input(
        "Trigger Point (Donors per 30 mins)", 
        value=10, 
        min_value=1,
        help="The number of donors that requires management presence."
    )

    st.divider()
    st.info("Note: This tool runs entirely in your browser. No data is saved or stored.")

# --- FILE PROCESSING ---
uploaded_file = st.file_uploader("Upload Excel File (.xls, .xlsx, or .csv)", type=["xls", "xlsx", "csv"])

if uploaded_file:
    try:
        # Load data without a header first so we can scan for the real table
        if uploaded_file.name.endswith('.csv'):
             raw_df = pd.read_csv(uploaded_file, header=None)
        else:
             raw_df = pd.read_excel(uploaded_file, header=None)

        # 1. FIND THE DATA GRID
        # We look for the row containing "Time" and "Sunday"
        start_row_index = -1
        end_row_index = -1
        
        for i, row in raw_df.iterrows():
            row_str = row.astype(str).values
            # The specific signature of the header row
            if "Time" in row_str and "Sunday" in row_str:
                start_row_index = i
                break
        
        if start_row_index != -1:
            # Now find where the table ENDS (look for "Totals" or "Units")
            # We scan specifically in column A (index 0)
            for i in range(start_row_index + 1, len(raw_df)):
                val = str(raw_df.iloc[i, 0])
                if "Totals" in val or "Units" in val:
                    end_row_index = i
                    break
            
            # Safety fallback if "Totals" isn't found
            if end_row_index == -1:
                end_row_index = start_row_index + 30 
            
            # Slice the dataframe to get just the numbers grid
            data_df = raw_df.iloc[start_row_index:end_row_index]
            
            # Set the first row as the header
            data_df.columns = data_df.iloc[0]
            data_df = data_df[1:] # Drop that header row from the data
            
            # 2. CLEAN AND TRANSFORM
            # Melt from wide format (Time, Sun, Mon...) to long format (Time, Day, Count)
            melted = data_df.melt(id_vars=["Time"], var_name="Day", value_name="Count")
            
            # Convert counts to numbers
            melted["Count"] = pd.to_numeric(melted["Count"], errors='coerce').fillna(0)
            
            # Apply 4-Week Math if selected
            if report_type == "4-Week Rollup":
                melted["Adjusted Count"] = melted["Count"] / 4
            else:
                melted["Adjusted Count"] = melted["Count"]

            # Filter for Power Hours
            power_hours = melted[melted["Adjusted Count"] >= trigger_count].copy()
            
            # --- DISPLAY RESULTS ---
            st.divider()
            
            if not power_hours.empty:
                st.subheader(f"📅 Power Hour Schedule (Trigger: {trigger_count}+)")
                
                # Define sort order so days appear correctly
                days_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                
                # Prepare text for the copy-paste box
                text_summary = "Power Hour Schedule:\n"

                # Layout: 7 columns (one for each day) for a quick visual overview
                cols = st.columns(7)
                
                # Loop through days in order
                for idx, day in enumerate(days_order):
                    day_data = power_hours[power_hours["Day"] == day]
                    
                    with cols[idx]:
                        st.markdown(f"**{day}**")
                        if not day_data.empty:
                            # Sort by time
                            day_data = day_data.sort_values(by="Time")
                            
                            # Add to text summary
                            times_list = day_data['Time'].tolist()
                            text_summary += f"{day}: {', '.join(times_list)}\n"
                            
                            # Display on screen
                            for _, row in day_data.iterrows():
                                # e.g. "07:00 (10.5)"
                                st.write(f"{row['Time']}")
                                st.caption(f"({round(row['Adjusted Count'], 1)} donors)")
                        else:
                            st.write("-")

                # Copy/Paste Section
                st.divider()
                st.subheader("📧 Copy for Email/Teams")
                st.text_area("Copy this text to send to your team:", value=text_summary, height=250)

            else:
                st.success(f"No times found with {trigger_count} or more donors (adjusted average).")

        else:
            st.error("Could not find the 'Time/Sunday' table. Please check if the file format has changed.")
            
    except Exception as e:
        st.error(f"Error processing file: {e}")
