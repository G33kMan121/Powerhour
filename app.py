import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Donor Arrival Analyzer", layout="centered")

st.title("🩸 Power Hour Schedule")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Settings")
    
    # 1. Choose Strategy
    analysis_mode = st.radio(
        "How should we find peaks?",
        ["Smart Auto-Detect (Recommended)", "Manual Fixed Number"],
        index=0,
        help="Smart Auto-Detect finds the busiest times relative to THIS center's volume. Manual lets you pick a specific number."
    )
    
    # 2. Dynamic Settings based on Strategy
    if analysis_mode == "Manual Fixed Number":
        trigger_count = st.number_input(
            "Trigger Point (Donors per 30 mins)", 
            value=10, min_value=1
        )
    else:
        # Percentile Slider
        percentile_cutoff = st.slider(
            "Peak Sensitivity", 
            min_value=70, max_value=99, value=85,
            help="85 means: 'Only show me the top 15% busiest times of the week.'"
        )
        trigger_count = 0 # Placeholder, calculated later

    st.divider()
    
    report_type = st.radio(
        "Report Duration",
        ["Single Week Data", "4-Week Rollup"],
        index=1,
        help="Select '4-Week Rollup' to automatically divide the numbers by 4."
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

            # --- SMART CALCULATION ---
            # If Auto-Detect is on, we calculate the trigger dynamically
            if analysis_mode == "Smart Auto-Detect (Recommended)":
                # Calculate the percentile (e.g., the value that is higher than 85% of the rest)
                calculated_threshold = melted["Adjusted Count"].quantile(percentile_cutoff / 100.0)
                # Ensure it's at least 1 person
                trigger_count = max(1, calculated_threshold)
                
                st.info(f"📊 **Smart Analysis:** Based on this center's volume, we defined 'Power Hour' as anything above **{round(trigger_count, 1)}** donors.")
            
            # Filter
            power_hours = melted[melted["Adjusted Count"] >= trigger_count].copy()
            
            # --- DISPLAY ---
            st.divider()
            
            if not power_hours.empty:
                def parse_time(t_str):
                    try: return datetime.strptime(str(t_str).strip(), "%H:%M")
                    except: return None

                days_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                schedule_rows = []

                for day in days_order:
                    day_data = power_hours[power_hours["Day"] == day].copy()
                    
                    if not day_data.empty:
                        day_data['TimeObj'] = day_data['Time'].apply(parse_time)
                        day_data = day_data.sort_values(by="TimeObj")
                        
                        ranges = []
                        if len(day_data) > 0:
                            start_time = day_data.iloc[0]['TimeObj']
                            end_time = start_time
                            max_donors = day_data.iloc[0]['Adjusted Count']
                            
                            for i in range(1, len(day_data)):
                                current_time = day_data.iloc[i]['TimeObj']
                                current_donors = day_data.iloc[i]['Adjusted Count']
                                
                                if current_time == end_time + timedelta(minutes=30):
                                    end_time = current_time 
                                    if current_donors > max_donors: max_donors = current_donors
                                else:
                                    ranges.append((start_time, end_time, max_donors))
                                    start_time = current_time
                                    end_time = current_time
                                    max_donors = current_donors
                            ranges.append((start_time, end_time, max_donors))
                        
                        time_strings = []
                        for r in ranges:
                            t_start = r[0]
                            t_end = r[1] + timedelta(minutes=30)
                            peak = int(round(r[2]))
                            time_strings.append(f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')} (Peak: {peak})")
                        
                        final_time_str = "  &  ".join(time_strings)
                        
                        schedule_rows.append({"Day": day, "Power Hour Shift": final_time_str})
                    else:
                        schedule_rows.append({"Day": day, "Power Hour Shift": "No Coverage Needed"})

                df_schedule = pd.DataFrame(schedule_rows)
                st.table(df_schedule.set_index("Day"))
                
                # Text Box
                st.subheader("Copy for Email")
                text_output = "Power Hour Schedule:\n"
                for row in schedule_rows:
                    if "No Coverage" not in row['Power Hour Shift']:
                        text_output += f"{row['Day']}: {row['Power Hour Shift']}\n"
                st.text_area("Select All & Copy", value=text_output, height=200)

            else:
                st.warning(f"No times found! (Try lowering the sensitivity slider in the sidebar)")

        else:
            st.error("Could not find the 'Time/Sunday' table.")
            
    except Exception as e:
        st.error(f"Error: {e}")
