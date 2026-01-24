import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Donor Arrival Analyzer", layout="centered")

st.title("🩸 Power Hour Schedule (Hourly)")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Settings")
    
    # 1. Choose Strategy
    analysis_mode = st.radio(
        "How should we find peaks?",
        ["Smart Auto-Detect (Recommended)", "Manual Fixed Number"],
        index=0,
        help="Smart Auto-Detect finds the busiest times relative to THIS center's volume."
    )
    
    # 2. Dynamic Settings
    if analysis_mode == "Manual Fixed Number":
        trigger_count = st.number_input(
            "Trigger Point (Donors per HOUR)", 
            value=20, min_value=1,
            help="Note: Since we are grouping by hour, this number should be approx double your 30-min trigger."
        )
    else:
        percentile_cutoff = st.slider(
            "Peak Sensitivity", 
            min_value=70, max_value=99, value=85,
            help="85 means: 'Only show me the top 15% busiest hours.'"
        )
        trigger_count = 0 

    st.divider()
    
    report_type = st.radio(
        "Report Duration",
        ["Single Week Data", "4-Week Rollup"],
        index=1
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
            
            # --- NEW: GROUP BY HOUR ---
            # Helper to parse time string to object
            def parse_time(t_str):
                try: return datetime.strptime(str(t_str).strip(), "%H:%M")
                except: return None
                
            melted['TimeObj'] = melted['Time'].apply(parse_time)
            # Floor to the nearest hour (e.g. 7:30 -> 7:00)
            melted['HourObj'] = melted['TimeObj'].dt.floor('h') 
            
            # Group by Day and Hour, SUMMING the counts
            hourly_df = melted.groupby(['Day', 'HourObj'])['Count'].sum().reset_index()
            
            # Format back to string for display (e.g., "07:00")
            hourly_df['Time'] = hourly_df['HourObj'].dt.strftime('%H:%M')
            
            # Apply 4-Week Math to the HOURLY totals
            if report_type == "4-Week Rollup":
                hourly_df["Adjusted Count"] = hourly_df["Count"] / 4
            else:
                hourly_df["Adjusted Count"] = hourly_df["Count"]

            # --- SMART CALCULATION ---
            if analysis_mode == "Smart Auto-Detect (Recommended)":
                calculated_threshold = hourly_df["Adjusted Count"].quantile(percentile_cutoff / 100.0)
                trigger_count = max(1, calculated_threshold)
                st.info(f"📊 **Hourly Analysis:** 'Power Hour' defined as > **{round(trigger_count, 1)}** donors/hour.")
            
            # Filter
            power_hours = hourly_df[hourly_df["Adjusted Count"] >= trigger_count].copy()
            
            # --- DISPLAY ---
            st.divider()
            
            if not power_hours.empty:
                days_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                schedule_rows = []

                for day in days_order:
                    day_data = power_hours[power_hours["Day"] == day].copy()
                    
                    if not day_data.empty:
                        day_data = day_data.sort_values(by="HourObj")
                        
                        ranges = []
                        if len(day_data) > 0:
                            start_time = day_data.iloc[0]['HourObj']
                            end_time = start_time
                            max_donors = day_data.iloc[0]['Adjusted Count']
                            
                            for i in range(1, len(day_data)):
                                current_time = day_data.iloc[i]['HourObj']
                                current_donors = day_data.iloc[i]['Adjusted Count']
                                
                                # Check if this hour follows the previous one (1 hour diff)
                                if current_time == end_time + timedelta(hours=1):
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
                            t_end = r[1] + timedelta(hours=1) # Add 1 hour to show end of block
                            peak = int(round(r[2]))
                            time_strings.append(f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')} (Peak: {peak})")
                        
                        final_time_str = "  &  ".join(time_strings)
                        schedule_rows.append({"Day": day, "Power Hour Shift": final_time_str})
                    else:
                        schedule_rows.append({"Day": day, "Power Hour Shift": "No Coverage Needed"})

                df_schedule = pd.DataFrame(schedule_rows)
                st.table(df_schedule.set_index("Day"))
                
                st.subheader("Copy for Email")
                text_output = "Power Hour Schedule (Hourly Blocks):\n"
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
