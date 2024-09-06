import pandas as pd

file_path = r"C:\Users\simon\Desktop\webstack\New folder\UK_local_authority_housing_data.xlsx"


def stage_data(file_path):
    try:
        # Load the Excel file and skip the first few rows that contain irrelevant data
        file = pd.read_excel(file_path, sheet_name='UK_Starts', skiprows=5)
        print("File loaded successfully!")
        print(f"Data types of columns: {file.dtypes}")
        print(f"\nFirst few rows of the DataFrame: {file.head()}")
        return file
    except Exception as e:
        print(f"Operation Failed: {e}")

file = stage_data(file_path)

def data_cleaner(file):
    """This function cleans data by removing unnecessary columns
    and renaming columns to make data easier to understand
    """
    try:
        # Remove columns where all values are NaN
        file = file.dropna(axis=1, how='all')

        # Check the current columns before renaming
        print(f"Original columns: {file.columns}")

        # If there are 19 columns, we need to provide 19 new names.
        file.columns = [
            'Region Type', 'Region or Country Name', 'Local Authority Code', 'Local Authority Name',
            '2009-2010', '2010-2011', '2011-2012', '2012-2013', '2013-2014', '2014-2015',
            '2015-2016', '2016-2017', '2017-2018', '2018-2019', '2019-2020', '2020-2021',
            '2021-2022', '2022-2023', '2023-2024'
        ]

        # Remove any rows where all values are NaN
        file = file.dropna(how='all')

        # Print the cleaned data structure
        print(f"\nColumn names after renaming: {file.columns}")
        print(f"\nDataFrame info: ")
        file.info()  # Corrected this to display DataFrame info
        return file

    except Exception as e:
        print(f"File not cleaned: {e}")

file = data_cleaner(file)