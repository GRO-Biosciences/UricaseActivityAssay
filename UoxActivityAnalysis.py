import pandas as pd
import matplotlib.pyplot as plt
import yaml
import tkinter as tk
from tkinter import filedialog
from Foundry import get_collaboration_path
from LabGuruAPI import Experiment, Protocol
import os
import requests
from pathlib import Path
from AWSHelper import get_aws_secret

def select_file(title_str, filetype):
    root = tk.Tk()
    root.withdraw()
    if filetype == "yaml":
        file_path = filedialog.askopenfilename(title=title_str, filetypes=[('YAML Files', '*.yaml')])
    elif filetype == "asc":
        file_path = filedialog.askopenfilename(title=title_str, filetypes=[('ASC Files', '*.asc')])
    elif filetype == "xlsx":
        file_path = filedialog.askopenfilename(title=title_str, filetypes=[('Excel Files', '*.xlsx')])
    else:
        return
    return file_path


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
    result_df.insert(0, 'Relative Time', kinetic_data['Relative Time'].str.replace('s', '').astype(int))
    result_df.insert(0, 'Temperature', kinetic_data['Temperature'])
    return result_df


def standardize_data(df):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in df.columns if col not in headers_to_exclude]
    df[headers_to_include] = df[headers_to_include].div(df.iloc[0]).div(0.01)[headers_to_include]
    return df


def scatterplot_wellnames_relative_abs(df, date_time, expt_id, dest_dir):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in df.columns if col not in headers_to_exclude]
    for n in range(1, 13):
        plt.figure(figsize=(20, 12))
        for column in headers_to_include:
            if str(n) in column:
                if n == 1 or n == 2:
                    if len(column) == 2:
                        plt.scatter(df['Relative Time'], df[column], label=column)
                else:
                    plt.scatter(df['Relative Time'], df[column], label=column)

        plt.xlabel('Relative Time (s)')
        plt.ylabel('Relative A292 (% of t0s)')
        plt.title(f'Relative Absorbance Over Time \n Column {n}')
        plt.legend()  # to show labels of each scatter plot
        plt.ylim([0, 110])
        plt.tight_layout()
        plt.savefig(dest_dir / f"{date_time}_{expt_id}_Column{n}.png")
        plt.close()
        # plt.show()


def map_sample_names(df, samplemap_path):
    platemap = pd.read_excel(samplemap_path)
    # Create a dictionary from Well Name to Sample Name
    name_dict = platemap.set_index('Well Name')['Sample Name'].to_dict()
    control_dict = platemap.set_index('Well Name')['Control?'].to_dict()
    # Replace column names
    df.columns = [
        (str(name_dict.get(col, col)) + ' (Control)' if isinstance(control_dict.get(col), str)
         else name_dict.get(col, col))
        for col in df.columns
    ]
    df = df.loc[:, df.columns.notnull()]
    # Remove columns not in platemap
    df_raw = df[[col for col in df.columns if isinstance(col, str) and not col in ['Relative Time', 'Temperature']]]
    # If there are replicates, consolidate into a column of averages
    df_avg = df_raw.T.groupby(level=0).mean().T
    df_avg.insert(0, 'Relative Time', df['Relative Time'])
    df_avg.insert(0, 'Temperature', df['Temperature'])
    return df_avg


def scatterplot_samplenames_relative_abs(df, date_time, expt_id, dest_dir):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in df.columns if col not in headers_to_exclude]
    # separate control column names
    control_columns = [col for col in headers_to_include if '(Control)' in col]
    experiment_columns = [col for col in headers_to_include if '(Control)' not in col]
    num_cols = len(experiment_columns)
    if num_cols > 10:
        fig, axs = plt.subplots(3, 3, figsize=(25, 15))
        axs = axs.ravel()
        # Plot controls
        for i in range(0,9):
            ax = axs[i]
            for control_col in control_columns:
                ax.scatter(df['Relative Time'], df[control_col], label=control_col, zorder=3, marker='x')
        for i, column in enumerate(experiment_columns):
            ax = axs[i % 9]  # Determine the appropriate subplot for this plot
            ax.scatter(df['Relative Time'], df[column], label=column)
            ax.set_xlabel('Relative Time (s)')
            ax.set_ylabel('Relative A292 (% of t0s)')
            ax.set_title(f'Relative Absorbance Over Time')
            ax.legend()  # to show labels of each scatter plot
            ax.set_ylim([0, 110])

        plt.savefig(dest_dir / f"{date_time}_{expt_id}_SampleNames.png")
        # plt.show()
        plt.close()
    else:
        plt.figure(figsize=(10, 6))
        for column in headers_to_include:
            plt.scatter(df['Relative Time'], df[column], label=column)
        plt.xlabel('Relative Time (s)')
        plt.ylabel('Relative A292 (% of t0s)')
        plt.title(f'Relative Absorbance Over Time')
        plt.legend()  # to show labels of each scatter plot
        plt.ylim([0, 110])
        plt.tight_layout()
        plt.savefig(dest_dir / f"{date_time}_{expt_id}_SampleNames.png")
        plt.close()
    return dest_dir / f"{date_time}_{expt_id}_SampleNames.png"


def final_percentage_consumed(df, date_time, expt_id, dest_dir):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in df.columns if col not in headers_to_exclude]

    # Create subset dataframes
    df_subset = df.loc[:, headers_to_include]
    plt.figure(figsize=(30, 12))
    # Perform subtraction
    difference_series = df_subset.iloc[0] - df_subset.iloc[-1]
    difference_series = difference_series.sort_values(ascending=False)
    # Generate color array for plot
    colors = ['red' if "(Control)" in index else 'blue' for index in difference_series.index]
    difference_series.plot(kind='bar', color=colors)
    plt.ylabel('15 minute % Consumed')
    plt.title('% of Uric Acid Consumed \nfrom First to Last Plate Read')
    plt.tight_layout()
    plt.savefig(dest_dir / f"{date_time}_{expt_id}_PercentConsumed.png")
    # plt.show()
    plt.close()
    # Perform subtraction
    plt.figure(figsize=(30, 12))
    difference_series = 100 - (df_subset.iloc[0] - df_subset.iloc[-1])
    difference_series = difference_series.sort_values(ascending=True)
    difference_series.plot(kind='bar', color=colors)
    plt.ylabel('15 minute % Uric Acid Remaining')
    plt.title('% of Uric Acid Remaining \nfrom First to Last Plate Read')
    plt.tight_layout()
    plt.savefig(dest_dir / f"{date_time}_{expt_id}_PercentRemaining.png")
    # plt.show()
    plt.close()
    return


def final_overall_uric_acid(bg_removed_df, date_time, expt_id, dest_dir):
    headers_to_exclude = ['Relative Time', 'Temperature']
    headers_to_include = [col for col in bg_removed_df.columns if col not in headers_to_exclude]

    # Create subset dataframes
    df_subset = bg_removed_df.loc[:, headers_to_include]
    plt.figure(figsize=(30, 12))
    # Perform subtraction
    lastval_series = df_subset.iloc[-1].sort_values(ascending=True)
    colors = ['red' if "(Control)" in index else 'blue' for index in lastval_series.index]
    lastval_series.plot(kind='bar', color=colors)
    plt.ylabel('Background Subtracted Abs at 15 Min')
    plt.title('Uric Acid Remaining\nat Last Plate Read')
    plt.tight_layout()
    plt.savefig(dest_dir / f"{date_time}_{expt_id}_UricAcidRemaining.png")
    # plt.show()
    plt.close()
    return


# Select Files
yaml_filepath = Path(select_file("YAML File Selection", "yaml"))
bg_filepath = Path(select_file("Background Read File Selection", "asc"))
kinetic_filepath = Path(select_file("Kinetic Read File Selection", "asc"))
platemap_filepath = Path(select_file("Plate Map File Selection", "xlsx"))

# Read in YAML file
yaml_dict = read_yaml(yaml_filepath)
expt_id = int(yaml_dict['Input Plates'][0][0:4])
# Get Collaborations Path
p_base = get_collaboration_path(expt_id)
# Create folder in collabs path
work_dir = p_base / f"UoxActivity_{yaml_dict['Input Plates'][0]}_{yaml_dict['Start']}"
os.makedirs(work_dir, exist_ok=True)
# Read ASCII files for background and kinetic reads
bg_df = read_ascii(bg_filepath)
kinetic_df = read_ascii(kinetic_filepath)
# Remove the background absorbance values
transformed_data = remove_background(bg_df, kinetic_df)
# Map the sample names to the well names based on an xlsx doc
sample_df = map_sample_names(transformed_data, platemap_filepath)
# Standardize the absorbance values by the kinetic read t0
standardized_data = standardize_data(sample_df)
# Plot the standardized absorbance data using the sample names
scatterplot_path = scatterplot_samplenames_relative_abs(standardized_data, yaml_dict['Start'],
                                                        yaml_dict['Input Plates'][0][0:4], work_dir)
# Create bar charts of % consumed and % remaining uric acid
final_percentage_consumed(standardized_data, yaml_dict['Start'], yaml_dict['Input Plates'][0][0:4], work_dir)
# Create bar chart
sample_absolute_df = map_sample_names(transformed_data, platemap_filepath)
final_overall_uric_acid(sample_absolute_df, yaml_dict['Start'], yaml_dict['Input Plates'][0][0:4], work_dir)
# Export Dataframes into excel file in working directory
with pd.ExcelWriter(
        work_dir / f"UoxActivitySummary_{yaml_dict['Input Plates'][0]}_{yaml_dict['Start']}.xlsx") as writer:
    bg_df.to_excel(writer, sheet_name='RawBackground')
    kinetic_df.to_excel(writer, sheet_name='RawKinetic')
    standardized_data.to_excel(writer, sheet_name='Standardized')
# Create Section in LG
expt = Experiment.from_id(expt_id)
cur_section = expt.add_section(f"UoxActivity_{yaml_dict['Input Plates'][0]}_{yaml_dict['Start']}", -1)
# Use Pre-made LG Protocol
cur_protocol = Protocol.from_id(173)
# Set conditional LG experiment details
if yaml_dict['Metadata']['Lysis']:
    if yaml_dict['Metadata']['Lysis Buffer'] == "BPer":
        lysis_desc = f"Lysis was performed on the Tecan. The samples were resuspended in {yaml_dict['Metadata']['Lysis Volume']}μL of {yaml_dict['Metadata']['Lysis Buffer']} followed by a 30 minute shaking incubation at 37°C"
    else:
        lysis_desc = f"Lysis was performed on the Tecan. The samples were resuspended in {yaml_dict['Metadata']['Lysis Volume']}μL of {yaml_dict['Metadata']['Lysis Buffer']}"
else:
    lysis_desc = "Lysis was not performed on the Tecan."

if yaml_dict['Metadata']['Lysate Type'] == 'Clarified':
    lysate_desc = "After lysis, the plate was spun at 3000rcf for 10 minutes to pellet the lysate. Clarified lysate was used as the sample for the duration of the assay."
else:
    lysate_desc = "Whole cell lysate was used for the duration of the assay."

if yaml_dict['Metadata']['Assay Sample Dilution Factor'] == 1:
    dilution_desc = "Samples were taken directly from the lysis plate and were not further diluted before addition to the assay plate."
else:
    dil_sample_vol = 100 / yaml_dict['Metadata']['Assay Sample Dilution Factor']
    dil_buffer_vol = 100 - dil_sample_vol
    dilution_desc = (
        f"Samples were diluted by a factor of {yaml_dict['Metadata']['Assay Sample Dilution Factor']} with 100mM Sodium Phosphate buffer in a separate BioRad HardShell PCR Plate. "
        f"{dil_sample_vol}μL of sample was added to {dil_buffer_vol}μL of 100mM Sodium Phosphate buffer in the dilution plate, and the plate was pipet mixed.")
# Add Text and Steps Elements to LG experiment section
cur_section.add_text_element(cur_protocol.sections[0].elements[0].format_data(
    input_plate=yaml_dict['Input Plates'][0]
))
cur_section.add_steps_element(cur_protocol.sections[0].elements[1].format_data(
    lysis_description=lysis_desc,
    lysate_description=lysate_desc,
    dilution_description=dilution_desc,
    sodiumphos_vol=50 - yaml_dict['Metadata']['Assay Sample Volume'],
    sample_vol=yaml_dict['Metadata']['Assay Sample Volume']
))

# List out the input / output filepaths to be attached to the LG Experiment
output_file_paths = [
    work_dir / f"UoxActivitySummary_{yaml_dict['Input Plates'][0]}_{yaml_dict['Start']}.xlsx",
    yaml_filepath,
    bg_filepath,
    kinetic_filepath,
    platemap_filepath,
    scatterplot_path
]
# Get the instrument LG Token
cur_token = get_aws_secret('LGAPI_2024', 'us-east-1')
# Add attachment section
attachments_element_resp = requests.post(f'https://my.labguru.com/api/v1/elements', json={
    'token': cur_token,
    'item': {
        'container_id': cur_section.id,
        'container_type': 'ExperimentProcedure',
        'element_type': 'attachments',
        'name': 'Attachments',
        'data': '[]'
    }
})
# Add attachment
for cur_path in output_file_paths:
    url = 'https://my.labguru.com/api/v1/attachments'
    headers = {
        'accept': '*/*',
    }
    filepath = cur_path
    # make sure to open your file in binary mode
    with filepath.open('rb') as file:
        files = {
            'token': (None, cur_token),
            'item[attachment]': (filepath.name, file),
            'item[attach_to_uuid]': (None, expt.uuid),
            # 'item[title]': (None, ''),
            'item[section_id]': (None, cur_section.id),
            'item[element_id]': (None, attachments_element_resp.json()['id'])
        }
        response = requests.post(url, headers=headers, files=files)

jpg_name = str(scatterplot_path).split('\\')[-1].replace('.png', '.jpg')
img_html_path = f'{response.json()["id"]}/annotated/{jpg_name}'
std_curve_element_response = requests.post(f'https://my.labguru.com/api/v1/elements', json={
    'token': cur_token,
    'item': {
        'container_id': cur_section.id,
        'container_type': 'ExperimentProcedure',
        'element_type': 'text',
        'data': f'<img class="fancybox-image" src="/user_assets/415072/attachments/{img_html_path}" alt="">'
    }
})
