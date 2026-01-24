import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Donor Arrival Analyzer", layout="centered") 
# Switched layout to 'centered' to make it look more like a document

st.title("🩸 Power Hour Schedule")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Settings")
    
    report_type = st.radio(
        "Report Duration",
        ["Single Week Data", "4-Week Rollup"],
        index=1,
        help="Select '4-Week Rollup' to automatically divide the numbers by 4."
    )
    
    trigger_count = st.number_input(
        "Trigger Point (Donors per 30 mins)", 
        value=10, 
        min_value=1
    )

# --- FILE PROCESSING ---
uploaded_file = st.file_uploader("Upload Excel File", type=["xls", "xlsx", "csv"])

if uploaded_file:
    try:
        # Load data
        if uploaded_file.name.endswith('.csv'):
             raw_df = pd.read_csv(uploaded_file, header=None)
        else:
             raw_df = pd.read_excel(uploaded_file, header=None)

        # 1. FIND THE DATA GRID
        start_row_index = -1
        end_row_index = -1
        
        for i, row in raw_df.iterrows():
            row_str = row.astype(str).values
            if "Time" in row_str and "Sunday" in row_str:
                start_row_index = i
                break
        
        if start_row_index != -1:
            for i in range(start_row_index + 1, len(raw_df)):
                val = str(raw_df.iloc[i, 0])
                if "Totals" in val or "Units" in val:
                    end_row_index = i
                    break
            
            if end_row_index == -1: end_row_index = start_row_index + 30 
            
            data_df = raw_df.iloc[start_row_index:end_row_index]
            data_df.columns = data_df.iloc[0]
            data_df = data_df[1:]
            
            # 2. CLEAN AND TRANSFORM
            melted = data_df.melt(id_vars=["Time"], var_name="Day", value_name="Count")
            melted["Count"] = pd.to_numeric(melted["Count"], errors='coerce').fillna(0)
            
            if report_type == "4-Week Rollup":
                melted["Adjusted Count"] = melted["Count"] / 4
            else:
                melted["Adjusted Count"] = melted["Count"]

            power_hours = melted[melted["Adjusted Count"] >= trigger_count].copy()
            
            # --- NEW DISPLAY LOGIC: CONDENSED TABLE ---
            st.divider()
            
            if not power_hours.empty:
                # Helper for time parsing
                def parse_time(t_str):
                    try: return datetime.strptime(str(t_str).strip(), "%H:%M")
                    except: return None

                days_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                
                # We will build a list of dictionaries to feed into a clean Table
                schedule_rows = []

                for day in days_order:
                    day_data = power_hours[power_hours["Day"] == day].copy()
                    
                    if not day_data.empty:
                        # Convert to time objects for math
                        day_data['TimeObj'] = day_data['Time'].apply(parse_time)
                        day_data = day_data.sort_values(by="TimeObj")
                        
                        # Logic to group consecutive blocks
                        ranges = []
                        if len(day_data) > 0:
                            start_time = day_data.iloc[0]['TimeObj']
                            end_time = start_time
                            max_donors = day_data.iloc[0]['Adjusted Count']
                            
                            for i in range(1, len(day_data)):
                                current_time = day_data.iloc[i]['TimeObj']
                                current_donors = day_data.iloc[i]['Adjusted Count']
                                
                                if current_time == end_time + timedelta(minutes=30):
                                    end_time = current_time # Extend block
                                    if current_donors > max_donors: max_donors = current_donors
                                else:
                                    ranges.append((start_time, end_time, max_donors))
                                    start_time = current_time
                                    end_time = current_time
                                    max_donors = current_donors
                            ranges.append((start_time, end_time, max_donors))
                        
                        # Format the ranges for this day into a single string
                        # e.g. "07:00 - 11:00" OR "07:00 - 09:00 & 14:00 - 16:00"
                        time_strings = []
                        for r in ranges:
                            t_start = r[0]
                            t_end = r[1] + timedelta(minutes=30)
                            peak = int(round(r[2]))
                            time_strings.append(f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')} (Peak: {peak})")
                        
                        final_time_str = "  &  ".join(time_strings)
                        
                        schedule_rows.append({
                            "Day": day,
                            "Power Hour Shift": final_time_str
                        })
                    else:
                        # Keep the day in the list but mark it empty
                        schedule_rows.append({
                            "Day": day,
                            "Power Hour Shift": "No Coverage Needed"
                        })

                # Create the nice table
                df_schedule = pd.DataFrame(schedule_rows)
                
                # Display as a clean static table
                st.table(df_schedule.set_index("Day"))
                
                # Copy Text Generator
                st.subheader("Copy for Email")
                text_output = "Power Hour Schedule:\n"
                for row in schedule_rows:
                    text_output += f"{row['Day']}: {row['Power Hour Shift']}\n"
                
                st.text_area("Select All & Copy", value=text_output, height=200)

            else:
                st.success(f"No times found with {trigger_count} or more donors.")

        else:
            st.error("Could not find the 'Time/Sunday' table.")
            
    except Exception as e:
        st.error(f"Error: {e}")
