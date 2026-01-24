import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Donor Arrival Analyzer", layout="centered")

st.title("Power Hour Schedule")
st.write("Identifies the absolute busiest single-hour blocks for management support.")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Settings")
    
    # 1. The "Limit" Rule
    max_slots = st.number_input(
        "Standard Power Hours per day", 
        value=2, 
        min_value=1, 
        max_value=5,
        help="This is the rule for Mon-Fri. Saturdays are automatically limited to 1."
    )
    
    st.divider()
    
    report_type = st.radio(
        "Report Duration",
        ["Single Week Data", "4-Week Rollup"],
        index=1,
        help="Select 4-Week Rollup if the file contains a month of data summed up."
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
            
            # Sum up donors per hour
            hourly_df = melted.groupby(['Day', 'HourObj'])['Count'].sum().reset_index()
            hourly_df['Time'] = hourly_df['HourObj'].dt.strftime('%H:%M')
            
            # Apply 4-Week Math
            if report_type == "4-Week Rollup":
                hourly_df["Adjusted Count"] = hourly_df["Count"] / 4
            else:
                hourly_df["Adjusted Count"] = hourly_df["Count"]

            # --- DISPLAY TOP N SEPARATE HOURS ---
            st.divider()
            
            days_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            schedule_rows = []

            for day in days_order:
                day_data = hourly_df[hourly_df["Day"] == day].copy()
                
                # Check for "Closed" days
                total_donors_for_day = day_data['Adjusted Count'].sum()
                
                if total_donors_for_day == 0:
                     schedule_rows.append({"Day": day, "Power Hours": "Closed"})
                elif not day_data.empty:
                    
                    # --- THE SATURDAY RULE ---
                    if day == "Saturday":
                        current_limit = 1
                    else:
                        current_limit = max_slots
                    
                    # 1. Grab the Top N busiest hours
                    top_hours = day_data.nlargest(current_limit, 'Adjusted Count').copy()
                    
                    # 2. Sort them by TIME
                    top_hours = top_hours.sort_values(by="HourObj")
                    
                    # 3. Format them
                    time_strings = []
                    for _, row in top_hours.iterrows():
                        t_start = row['HourObj']
                        t_end = t_start + timedelta(hours=1)
                        peak = int(round(row['Adjusted Count']))
                        
                        if peak > 0:
                            time_strings.append(f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')} (Peak: {peak})")
                    
                    if not time_strings:
                        final_time_str = "Closed"
                    else:
                        final_time_str = "  |  ".join(time_strings)
                        
                    schedule_rows.append({"Day": day, "Power Hours": final_time_str})
                else:
                    schedule_rows.append({"Day": day, "Power Hours": "Closed"})

            df_schedule = pd.DataFrame(schedule_rows)
            st.table(df_schedule.set_index("Day"))
            
            # Copy Text
            st.subheader("Copy for Email")
            text_output = "Power Hour Schedule:\n"
            for row in schedule_rows:
                text_output += f"{row['Day']}: {row['Power Hours']}\n"
            st.text_area("Select All & Copy", value=text_output, height=200)

        else:
            st.error("Could not find the 'Time/Sunday' table.")
            
    except Exception as e:
        st.error(f"Error: {e}")
