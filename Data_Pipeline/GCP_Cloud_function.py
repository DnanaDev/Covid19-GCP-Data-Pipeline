# ### Google Cloud Function Script  "Function execution took 7867 ms, finished with status code: 200"
# HTTP Trigger (No Authentication - DO NOT PUBLISH) :
# REMOVED
#

# +
import json
from urllib.request import urlopen
import pandas as pd
import datetime
from google.cloud import storage
from os import listdir, getcwd
from os.path import isfile, join


def list_cases_stat(json_obj, column):
    """
    This function takes in the JSON retrieved from the API and returns a list of integers for the specified
    column, can be used to then plot the time-series.
    :param json_obj: The JSON object returned by the API.
    :param column: The metric that is to be returned, dailyconfirmed etc.
    :return: Returns a list of integers of the time series for the specified stat.
    """
    stat_list = []
    for daily_num in json_obj['cases_time_series']:
        stat_list.append(daily_num[column])
    try:
        stat_list_int = [int(x) for x in stat_list]
    except ValueError:
        stat_list_int = stat_list

    return stat_list_int


def make_dataframe(file_loc):
    """"Makes Dataframe with parsed data and and returns it with an option to save it as a CSV.
    Data starting - 2020-01-30.
    Args:
    file_loc:str. Location to store file.
    Downloads:Dataframe. With Columns DailyConfirmed, DailyDeceased, DailyRecovered."""

    # Fetching The JSON
    with urlopen("https://api.covid19india.org/data.json") as response:
        source = response.read()
        data = json.loads(source)

    # Getting Data From Json Object using list_cases_stat function
    daily_conf = list_cases_stat(data, 'dailyconfirmed')
    daily_dec = list_cases_stat(data, 'dailydeceased')
    daily_rec = list_cases_stat(data, 'dailyrecovered')
    total_conf = list_cases_stat(data, 'totalconfirmed')
    total_dec = list_cases_stat(data, 'totaldeceased')
    total_rec = list_cases_stat(data, 'totalrecovered')

    list_dates = list_cases_stat(data, 'dateymd')

    # Converting Dates to 'datetime'
    new_date = []

    for date in list_dates:
        # if entry is not of valid format continue to next
        try:
            new_date.append(datetime.datetime.strptime(date, '%Y-%m-%d'))
        except ValueError:
            continue

    list_dates = new_date

    dataframe = pd.DataFrame(index=list_dates, data=
    {'DailyConfirmed': daily_conf, 'DailyDeceased': daily_dec, 'DailyRecovered': daily_rec,
     'TotalConfirmed': total_conf, 'TotalDeceased': total_dec, 'TotalRecovered': total_rec})
    # Renaming Index to be consistent with all other CSVs
    dataframe.rename_axis(index='Date', inplace=True)

    dataframe.to_csv(file_loc)

    print(f"Downloaded Daily Stats CSV at '{file_loc}'")


def make_state_dataframe(file_loc):
    """Returns Dataframe with parsed data for national and statewise cases timeseries.
    Optional to save CSV. Data starting - 2020-03-14.
    Args:
    save: Saves the cleaned CSV.
    Returns:Dataframe. With stacked Columns DailyConfirmed, DailyDeceased, DailyRecovered
    for each state and Total - National time series.
    """

    # Dictionary for renaming state codes to full state names, slightly wasteful,
    # additional API call to different file.
    response = urlopen("https://api.covid19india.org/data.json")
    source = response.read()
    data = json.loads(source)

    # creating dict for pandas DF rename mapper.
    state_identifier = {}
    for record in data['statewise']:
        state_identifier[record['statecode']] = record['state']

    # Read in CSV, rename, pivot to make datetime index
    state_daily_data = pd.read_csv('https://api.covid19india.org/csv/latest/state_wise_daily.csv')
    state_daily_data.drop(['Date_YMD'], axis=1, inplace=True)
    state_daily_data.rename(columns=state_identifier, inplace=True)
    state_daily_data.Date = pd.to_datetime(state_daily_data.Date)
    state_daily_data = state_daily_data.pivot(index='Date', columns='Status')

    # Melt stacked Column index Dataframe to long Dataframe
    state_daily_data.reset_index(inplace=True)
    state_daily_data = state_daily_data.melt(id_vars=['Date'])

    # renaming orphan column with state data
    state_daily_data.rename(axis=1, mapper={None: 'State'}, inplace=True)

    # Pivoting to reshape Status column values(Recovered, Confirmed, Deceased Cases) to columns
    state_daily_data = state_daily_data.pivot_table(index=['Date', 'State'], columns='Status', values='value')

    # Reset index to replicate stacked index Date to Date column before setting as index.
    state_daily_data = state_daily_data.reset_index().set_index('Date')

    state_daily_data.to_csv(file_loc)

    print(f"Downloaded Daily State Stats CSV at '{file_loc}'")


def get_test_dataframe(file_loc):
    """Gets ICMR Covid Testing samples data from Datameet dataset.
    Data starting - 2020-03-13. Has multiple entries for certain days.
    Args:
    Returns:
    DataFrame with Date, Number of samples collected on that day.
    """
    path_testing = 'https://raw.githubusercontent.com/datameet/covid19/master/data/icmr_testing_status.json'

    with urlopen(path_testing) as response:
        # Reading this json data
        source = response.read()
        # converting this json to
        data = json.loads(source)

    stat_list = []
    dates_list = []

    # Parsing Dates and Number of Samples Collected on day.
    # Converting Date string to Datetime

    for rows in data['rows']:
        try:
            date = rows['id'].split('T')[0]
            dates_list.append(datetime.datetime.strptime(date, '%Y-%m-%d'))
            stat_list.append(rows['value']['samples'])
        except ValueError:
            continue

    testing_data = pd.DataFrame(index=dates_list, data={'TestingSamples': stat_list})

    # Removing duplicate indexes
    testing_data = testing_data.loc[~testing_data.index.duplicated(keep='last')]

    # Renaming Index to be consistent with all other CSVs
    testing_data.rename_axis(index='Date', inplace=True)

    testing_data.to_csv(file_loc)

    print(f"Downloaded Testing Stats CSV at '{file_loc}'")


def upload_to_bucket(bucket, local_folder, bucket_folder):
    """ Uploads Extracted files from pipeline to GCS Bucket.
    """
    files = [f for f in listdir(local_folder) if isfile(join(local_folder, f))]
    for file in files:
        # local individual filenames
        file_name = join(local_folder, file)
        # Create a blob (target of file you want uploaded)
        blob = bucket.blob(join(bucket_folder, file))
        # Actually upload the file.
        blob.upload_from_filename(file_name)

    print(f'Uploaded {files} to "{bucket.id}" bucket.')


def main(request):
    """Endpoint for Google Cloud Function, Downloads files to temp
    request is just an unused parameter, HTTP request"""
    make_dataframe('/tmp/COVID_India_National.csv')
    make_state_dataframe('/tmp/COVID_India_State.csv')
    get_test_dataframe('/tmp/COVID_India_Test_data.csv')
    # Creating client
    storage_client = storage.Client()
    # Connecting to Bucket
    bucket = storage_client.get_bucket('covid19-india-analysis-bucket')
    # Upload all files in temp to bucket.
    upload_to_bucket(bucket=bucket, local_folder='/tmp/', bucket_folder='Data/Raw/')
