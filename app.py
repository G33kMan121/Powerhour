import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Donor Arrival Analyzer", layout="centered")

st.title("🩸 Power Hour Schedule")
st.write("Identifies the absolute busiest hours of the day for management support.")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Settings")
    
    # 1. The "Limit" Rule
    max_slots = st.number_input(
        "Max Power Hours per Day", 
        value=2, 
        min_value=1, 
        max_value=5,
        help="The tool will strictly limit the output to this many hours per day (e.g., the top 2 busiest hours)."
    )
    
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
            
            # --- GROUP BY HOUR ---
            def parse_time(t_str):
                try: return datetime.strptime(str(t_str).strip(), "%H:%M")
                except: return None
                
            melted['TimeObj'] = melted['Time'].apply(parse_time)
            melted['HourObj'] = melted['TimeObj'].dt.floor('h') 
            
            # Group by Day and Hour
            hourly_df = melted.groupby(['Day', 'HourObj'])['Count'].sum().reset_index()
            hourly_df['Time'] = hourly_df['HourObj'].dt.strftime('%H:%M')
            
            # Apply 4-Week Math
            if report_type == "4-Week Rollup":
                hourly_df["Adjusted Count"] = hourly_df["Count"] / 4
            else:
                hourly_df["Adjusted Count"] = hourly_df["Count"]

            # --- DISPLAY WITH "TOP N" LOGIC ---
            st.divider()
            
            days_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            schedule_rows = []

            for day in days_order:
                day_data = hourly_df[hourly_df["Day"] == day].copy()
                
                if not day_data.empty:
                    # KEY CHANGE: Just grab the top N busiest hours
                    # We sort by Count (Largest first) and take the top 'max_slots'
                    top_hours = day_data.nlargest(max_slots, 'Adjusted Count').copy()
                    
                    # Now sort those selected hours by TIME so they appear in order (Morning -> Night)
                    top_hours = top_hours.sort_values(by="HourObj")
                    
                    # Logic to check if they are back-to-back (Merging blocks)
                    ranges = []
                    if len(top_hours) > 0:
                        start_time = top_hours.iloc[0]['HourObj']
                        end_time = start_time
                        max_donors = top_hours.iloc[0]['Adjusted Count']
                        
                        for i in range(1, len(top_hours)):
                            current_time = top_hours.iloc[i]['HourObj']
                            current_donors = top_hours.iloc[i]['Adjusted Count']
                            
                            # Check if contiguous (1 hour diff)
                            if current_time == end_time + timedelta(hours=1):
                                end_time = current_time 
                                if current_donors > max_donors: max_donors = current_donors
                            else:
                                ranges.append((start_time, end_time, max_donors))
                                start_time = current_time
                                end_time = current_time
                                max_donors = current_donors
                        ranges.append((start_time, end_time, max_donors))
                    
                    # Format String
                    time_strings = []
                    for r in ranges:
                        t_start = r[0]
                        t_end = r[1] + timedelta(hours=1) # End of the block
                        peak = int(round(r[2]))
                        time_strings.append(f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')} (Peak: {peak})")
                    
                    final_time_str = "  &  ".join(time_strings)
                    schedule_rows.append({"Day": day, "Top Priority Shifts": final_time_str})
                else:
                    schedule_rows.append({"Day": day, "Top Priority Shifts": "-"})

            df_schedule = pd.DataFrame(schedule_rows)
            st.table(df_schedule.set_index("Day"))
            
            # Copy Text
            st.subheader("Copy for Email")
            text_output = "Power Hour Schedule (Top Priority):\n"
            for row in schedule_rows:
                if row['Top Priority Shifts'] != "-":
                    text_output += f"{row['Day']}: {row['Top Priority Shifts']}\n"
            st.text_area("Select All & Copy", value=text_output, height=200)

        else:
            st.error("Could not find the 'Time/Sunday' table.")
            
    except Exception as e:
        st.error(f"Error: {e}")
