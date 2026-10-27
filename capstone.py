import pandas as pd
import streamlit as st
import numpy as np
import plotly.express as px

# Link to the folder of CSSE time series files on GitHub
url = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/"

# Rows that are cruise ships, events, or Antarctica instead of countries
not_countries = ["Diamond Princess", "MS Zaandam", "Summer Olympics 2020", "Winter Olympics 2022", "Antarctica"]
# Rows listed as Canadian provinces that are really ships or travellers
not_provinces = ["Diamond Princess", "Grand Princess", "Repatriated Travellers"]

def load(kind):
    # Reads the global file for cases ("confirmed") or deaths ("deaths")
    df = pd.read_csv(url + "time_series_covid19_" + kind + "_global.csv")
    # Drops ships, events, and Antarctica
    df = df[~df["Country/Region"].isin(not_countries)]
    df = df[~df["Province/State"].isin(not_provinces)]
    # Keeps only the mainland row for countries that also list overseas territories
    has_main = df[df["Province/State"].isna()]["Country/Region"]
    df = df[df["Province/State"].isna() | ~df["Country/Region"].isin(has_main)]
    # Sums provinces into one row per country
    df = df.drop(columns=["Province/State", "Lat", "Long"])
    df = df.groupby("Country/Region").sum()
    # Flips the table so each country is a column and each date is a row
    df = df.T
    df.index = pd.to_datetime(df.index, format="%m/%d/%y")
    # Removes the asterisk CSSE puts on Taiwan
    df = df.rename(columns={"Taiwan*": "Taiwan"})
    return df

cases = load("confirmed")
deaths = load("deaths")

# Reads the CSSE lookup table that has each country's population
uid = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/UID_ISO_FIPS_LookUp_Table.csv")
# Keeps the country-level rows (no province) and pulls out population
uid = uid[uid["Province_State"].isna()]
pop = uid.set_index("Country_Region")["Population"]
pop = pop.rename(index={"Taiwan*": "Taiwan"})

st.title("COVID-19 by Country")

# Explains what the app shows and how to use it
st.write("This app shows COVID-19 cases and deaths by country using data from the Johns Hopkins CSSE COVID-19 Dashboard. " \
"The data runs from January 22, 2020 to March 9, 2023, when CSSE stopped updating it.")
st.markdown("""
**How to use**
- Pick one or more countries in the sidebar. You can type to search.
- Pick cases or deaths.
- Pick Daily for new counts each day, or Cumulative for the running total.
- For daily counts, the 7-day average smooths out weekend dips and countries that only reported once a week.
- Check Per 100,000 people to compare countries with different populations.
- Drag the date slider to zoom in on a time period.
- Hover over a line to see exact values.
""")

# User picks one or more countries
countries = st.sidebar.multiselect("Countries", list(cases.columns), default=["US"])
# User picks cases or deaths
measure = st.sidebar.radio("Show", ["Cases", "Deaths"])
# User picks new counts per day or running total
view = st.sidebar.radio("Count type", ["Daily", "Cumulative"])
# User picks whether to smooth daily counts (only shown for daily)
smooth = False
if view == "Daily":
    smooth = st.sidebar.checkbox("7-day average", value=True)
# User picks whether to adjust for population
per_capita = st.sidebar.checkbox("Per 100,000 people")
# User picks a date range
first_date = cases.index.min().date()
last_date = cases.index.max().date()
start, end = st.sidebar.slider("Dates", min_value=first_date, max_value=last_date, value=(first_date, last_date))

# Stops and shows a message if no country is picked
if len(countries) == 0:
    st.write("Pick at least one country in the sidebar.")
    st.stop()

# Picks cases or deaths, keeping only the chosen countries
if measure == "Cases":
    data = cases[countries]
else:
    data = deaths[countries]

# Converts running totals to new counts per day
if view == "Daily":
    first = data.iloc[0]
    data = data.diff()
    data.iloc[0] = first
    # Blanks out negative days, since they're corrections to earlier days and not real counts
    data[data < 0] = np.nan
    # Averages each day with the 6 days before it, skipping blank days instead of blanking the whole week
    if smooth:
        data = data.rolling(7, min_periods=1).mean()

# Divides by population to get counts per 100,000 people
if per_capita:
    data = data / pop[data.columns] * 100000

# Keeps only the chosen dates
data = data.loc[pd.to_datetime(start):pd.to_datetime(end)]

# Builds the y-axis label from the user's choices
if view == "Daily":
    label = "New " + measure.lower() + " per day"
else:
    label = "Total " + measure.lower()
if per_capita:
    label = label + " per 100,000 people"
if smooth:
    label = label + " (7-day average)"

# Draws one line per country
fig = px.line(data, labels={"index": "Date", "value": label, "Country/Region": "Country"})

# Rounds hover values: whole numbers for counts, 2 decimals for deaths per 100,000, 1 decimal for cases per 100,000
if per_capita and measure == "Deaths":
    fig.update_yaxes(hoverformat=",.2f")
elif per_capita:
    fig.update_yaxes(hoverformat=",.1f")
else:
    fig.update_yaxes(hoverformat=",.0f")

st.plotly_chart(fig)

# Explains how the data was cleaned
with st.expander("About the data", expanded=True):
    st.markdown("""
- Countries split into provinces in the data (like Canada, China, and Australia) are added up into one total.
- For countries that also list overseas territories (UK, France, Netherlands, Denmark, and New Zealand), only the main country is counted, to match the population numbers.
- China includes Hong Kong and Macau, since that's how CSSE reports them. Hong Kong makes up most of China's reported cases in 2022.
- Cruise ships (Diamond Princess, Grand Princess, MS Zaandam), the 2020 and 2022 Olympics, and Antarctica are removed since they aren't countries.
- CSSE only gives running totals. Daily counts come from subtracting the previous day's total.
- Sometimes a country lowered its total to fix earlier mistakes, which gives a negative daily count. These days are left blank, since there's no way to know which earlier days the fix belongs to. 
Because of this, daily counts can add up to slightly more than the official total. Use Cumulative for official totals.
- The 7-day average uses whichever days in the week aren't blank.
- Daily counts and averages are calculated on the full data before the date filter, so the first day shown is still correct.
- Population comes from the CSSE lookup table.
- Recovered counts aren't included because CSSE stopped tracking them consistently.
""")