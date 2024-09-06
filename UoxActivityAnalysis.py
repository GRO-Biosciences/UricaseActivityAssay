import pandas as pd
import matplotlib.pyplot as plt
import yaml


def read_yaml(yaml_path):
    # read the yaml file
    with open(yaml_path, 'r') as file:
        filedata = file.read()
    # replace all tabs with four spaces to avoid read in error
    filedata = filedata.replace('\t', '    ')
    # write the file again
    with open(yaml_path, 'w') as file:
        file.write(filedata)
    with open(yaml_path, 'r') as stream:
        yaml_dict = yaml.safe_load(stream)

    return yaml_dict


def read_ascii(filepath):
    read_lines = False
    lines = []

    with open(filepath, 'r', encoding='utf-16') as f:
        for line in f:
            # Start reading when we encounter "Raw data"
            if 'Raw data' in line.strip():
                read_lines = True
                continue

            # Stop reading when we encounter "Date of measurement"
            if 'Date of measurement' in line.strip():
                read_lines = False
                continue

            # If we should read a line, append it to the list
            if read_lines and "°C" in line:
                lines.append(line)

    # The lines that we read will be a list of strings. We will need to convert this to a dataframe
    # Assuming each line is a comma-separated list of values
    repeat_headers = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    headers = ['Relative Time', 'Temperature']
    for i in range(1, 13):
        headers += [f'{header}{i}' for header in repeat_headers]

    # Create empty DataFrame with headers
    df = pd.DataFrame([line.split(',')[:-1] for line in lines], columns=headers)
    return df


def remove_background(t0_data, kinetic_data):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in kinetic_data.columns if col not in headers_to_exclude]

    # Create subset dataframes
    t0_df_subset = t0_data.loc[:, headers_to_include].map(pd.to_numeric, errors='coerce')
    kinetic_df_subset = kinetic_data.loc[:, headers_to_include].map(pd.to_numeric, errors='coerce')

    # Perform subtraction
    result_df = kinetic_df_subset - t0_df_subset.values

    # Add back the excluded columns from df2 to the result dataframe
    result_df['Relative Time'] = kinetic_data['Relative Time'].str.replace('s', '').astype(int)
    result_df['Temperature'] = kinetic_data['Temperature']
    return result_df


def standardize_data(df):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in df.columns if col not in headers_to_exclude]
    result_df = df[headers_to_include].div(df.iloc[0]).div(0.01)
    result_df['Relative Time'] = df['Relative Time']
    result_df['Temperature'] = df['Temperature']
    return result_df


def scatterplot_wellnames_relative_abs(df, date_time, expt_id):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in df.columns if col not in headers_to_exclude]
    for n in range(1, 13):
        plt.figure(figsize=(10, 6))
        for column in headers_to_include:
            if str(n) in column:
                if n == 1 or n == 2:
                    if len(column) == 2:
                        plt.scatter(df['Relative Time'], df[column], label=column)
                else:
                    plt.scatter(df['Relative Time'], df[column], label=column)

        plt.xlabel('Relative Time (s)')
        plt.ylabel('Relative 292 Absorbance (% of t0s)')
        plt.title(f'Relative Absorbance Over Time \n Column {n}')
        plt.legend()  # to show labels of each scatter plot
        plt.ylim([0, 110])
        plt.tight_layout()
        plt.savefig(
            f"C:\\Users\\MarkCerutti\\PycharmProjects\\UricaseActivityAssay\\plots\\{date_time}_{expt_id}_Column{n}.png")
        plt.close()
        # plt.show()


def map_sample_names(df, samplemap_path):
    platemap = pd.read_excel(samplemap_path)
    # Create a dictionary from Well Name to Sample Name
    name_dict = platemap.set_index('Well Name')['Sample Name'].to_dict()

    # Replace column names
    df.columns = [name_dict.get(col, col) for col in df.columns]

    # Remove columns not in platemap
    df = df[[col for col in df.columns if col in name_dict.values() or col in ['Relative Time', 'Temperature']]]
    return df


def scatterplot_samplenames_relative_abs(df, date_time, expt_id):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in df.columns if col not in headers_to_exclude]
    plt.figure(figsize=(10, 6))
    for column in headers_to_include:
        plt.scatter(df['Relative Time'], df[column], label=column)
    plt.xlabel('Relative Time (s)')
    plt.ylabel('Relative 292 Absorbance (% of t0s)')
    plt.title(f'Relative Absorbance Over Time')
    plt.legend()  # to show labels of each scatter plot
    plt.ylim([0, 110])
    plt.tight_layout()
    plt.savefig(
        f"C:\\Users\\MarkCerutti\\PycharmProjects\\UricaseActivityAssay\\plots\\{date_time}_{expt_id}_SampleNames.png")
    plt.close()


def final_percentage_consumed(df):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in df.columns if col not in headers_to_exclude]

    # Create subset dataframes
    df_subset = df.loc[:, headers_to_include]

    # Perform subtraction
    difference_series = df_subset.iloc[0] - df_subset.iloc[-1]
    difference_series = difference_series.sort_values(ascending=False)
    difference_series.plot(kind='bar')
    plt.ylabel('15 minute % Consumed')
    plt.title('% of Uric Acid Consumed \nfrom First to Last Plate Read')
    plt.tight_layout()
    plt.show()
    # Perform subtraction
    difference_series = 100 - (df_subset.iloc[0] - df_subset.iloc[-1])
    difference_series = difference_series.sort_values(ascending=True)
    difference_series.plot(kind='bar')
    plt.ylabel('15 minute % Uric Acid Remaining')
    plt.title('% of Uric Acid Remaining \nfrom First to Last Plate Read')
    plt.tight_layout()
    plt.show()
    return


# todo make these variables tkinter gui popups
# for now these are just file names within the working directory but they can be full filepaths to point to
# other source directories
yaml_filepath = "2024-09-05_12-34-53_Donphan.yaml"
bg_filepath = "UoxBG_WCL-240905-005.asc"
kinetic_filepath = "UoxKinetic_WCL-240905-006.asc"
platemap_filepath = "platemap.xlsx"


# Read in YAML file
yaml_dict = read_yaml(yaml_filepath)
# Read ASCII files for background and kinetic reads
bg_df = read_ascii(bg_filepath)
kinetic_df = read_ascii(kinetic_filepath)
# Remove the background absorbance values
transformed_data = remove_background(bg_df, kinetic_df)
# Standardize the absorbance values by the kinetic read t0
standardized_data = standardize_data(transformed_data)
# Plot all standardized absorbance well data across 12 plots
scatterplot_wellnames_relative_abs(standardized_data, yaml_dict['Start'], yaml_dict['Input Plates'][0][0:4])
# Map the sample names to the well names based on an xlsx doc
sample_df = map_sample_names(standardized_data, platemap_filepath)
# Plot the standardized absorbance data using the sample names
scatterplot_samplenames_relative_abs(sample_df, yaml_dict['Start'], yaml_dict['Input Plates'][0][0:4])
# Create bar charts of % consumed and % remaining uric acid
final_percentage_consumed(sample_df)