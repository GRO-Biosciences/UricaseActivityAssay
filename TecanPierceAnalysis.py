import pandas as pd
import matplotlib.pyplot as plt
import yaml
import tkinter as tk
from tkinter import filedialog
from Foundry import get_collaboration_path
from LabGuruAPI import Experiment, Protocol, SESSION
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
    line_counter = 0
    with open(filepath, 'r', encoding='utf-16') as f:
        for line in f:
            line_counter += 1
            if line_counter in [3, 4]:
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
    return df_raw


# Select Files
yaml_filepath = Path(select_file("YAML File Selection", "yaml"))
pierce_filepath1 = Path(select_file("Pierce1 A660 File Selection", "asc"))
pierce_filepath2 = Path(select_file("Pierce2 A660 File Selection", "asc"))
platemap_filepath = Path(select_file("Plate Map File Selection", "xlsx"))

# Read in YAML file
yaml_dict = read_yaml(yaml_filepath)
expt_id = int(yaml_dict['Input Plates'][0][0:4])
# Get Collaborations Path
p_base = get_collaboration_path(expt_id)
# Create folder in collabs path
work_dir = p_base / f"TecanPierce_{yaml_dict['Input Plates'][0]}_{yaml_dict['Start']}"
os.makedirs(work_dir, exist_ok=True)
# Read ASCII files for background and kinetic reads
# pierce_df = pd.concat([read_ascii(pierce_filepath1),read_ascii(pierce_filepath2)])
# pierce_df = pierce_df.reset_index()
pierce_df1 = read_ascii(pierce_filepath1)
pierce_df2 = read_ascii(pierce_filepath2)

# Create a three column Excel Doc of Well Name, DiluFactor*Conc, Sample Name
platemap = pd.read_excel(platemap_filepath)
# Create a dictionary from Well Name to Sample Name
name_dict = platemap.set_index('Well Name')['Sample Name'].to_dict()
control_dict = platemap.set_index('Well Name')['Control?'].to_dict()
# for col in pierce_df.columns:
#     (str(name_dict.get(col, col)) + ' (Control)' if isinstance(control_dict.get(col), str)
#      else name_dict.get(col, col))

data = []  # This list will hold the rows for the new DataFrame

for key in pierce_df1.columns:
    if len(key) > 3 or int(key[1]) in [1,2,3]:
        continue
    well_name = key[0] + str(int(key[1])-3)
    try:
        protein_concentration = float(pierce_df1.loc[1, key]) * yaml_dict['Metadata']['Dilution Factor']
    except:
        protein_concentration = ""
    dict_value = name_dict.get(well_name, None)

    # Populate a new row for the DataFrame
    row = {'Well Name': well_name, 'Protein Concentration (mg/mL)': protein_concentration, 'Sample Name': dict_value}
    data.append(row)
for key in pierce_df2.columns:
    if len(key) > 3 or int(key[1]) in [1,2,3]:
        continue
    well_name = key[0] + str(int(key[1])+3)
    try:
        protein_concentration = float(pierce_df2.loc[1, key]) * yaml_dict['Metadata']['Dilution Factor']  # Assuming the second row corresponds to index 1
    except:
        protein_concentration = ""
    dict_value = name_dict.get(well_name, None)  # Get the value from the dictionary, if it exists

    # Populate a new row for the DataFrame
    row = {'Well Name': well_name, 'Protein Concentration (mg/mL)': protein_concentration, 'Sample Name': dict_value}
    data.append(row)

# Create new DataFrame
new_df = pd.DataFrame(data)
new_df.to_excel(work_dir / f"TecanPierce_{yaml_dict['Input Plates'][0]}_{yaml_dict['Start']}.xlsx", index=False)

#LabGuru updates
if yaml_dict['Metadata']['Interferent'] == 'No':
    proto_stdcrv_string = "Standard Curve aliquots were stamped from a pre-made standard curve deep well plate into two Sample Dilution plates. The pre-made standard curve plate is made by hand via transferring solution from the Thermo - Pierce Bovine Serum Albumin Standard Pre-Diluted Set (23208) into the first three columns of a deep well plate, such that columns 1, 2, and 3 are triplicates of a standard curve composed of BSA at the following concentrations: 2.0, 1.5, 1.0, 0.75, 0.5, 0.125, 0.05, 0.0"
else:
    proto_stdcrv_string = "Interferent buffer was stamped into the first three columns of two Sample Dilution plates. Then Standard Curve aliquots were stamped from a pre-made standard curve deep well plate into those first three columns of both Sample Dilution plates, such that the protein concentrations of the standards and concentrations of the interferent were diluted 2-fold for each well. The pre-made standard curve plate is made by hand via transferring solution from the Thermo - Pierce Bovine Serum Albumin Standard Pre-Diluted Set (23208) into the first three columns of a deep well plate, such that columns 1, 2, and 3 are triplicates of a standard curve composed of BSA at the following concentrations: 2.0, 1.5, 1.0, 0.75, 0.5, 0.125, 0.05, 0.0. Those standard concentrations were all halved in this experiment via the interferent reagent. All standard protein concentration values are correctly set in the plate reader software to reflect the dilution."


# Create Section in LG
expt = Experiment.from_id(expt_id)
cur_section = expt.add_section(f"Tecan_PierceProteinQuant_{yaml_dict['Input Plates'][0]}_{yaml_dict['Start']}", -1)
# Use Pre-made LG Protocol
cur_protocol = Protocol.from_id(177)
# Add Text and Steps Elements to LG experiment section
cur_section.add_text_element(cur_protocol.sections[0].elements[0].format_data(
    input_plate=yaml_dict['Input Plates'][0]
))
sample_vol = 30/yaml_dict['Metadata']['Dilution Factor']
diluent_vol = str(30-sample_vol)
cur_section.add_steps_element(cur_protocol.sections[0].elements[1].format_data(
    standard_curve=proto_stdcrv_string,
    diluent_vol=diluent_vol,
    sample_vol=sample_vol
))

output_file_paths = [
    work_dir / f"TecanPierce_{yaml_dict['Input Plates'][0]}_{yaml_dict['Start']}.xlsx",
    yaml_filepath,
    pierce_filepath1,
    pierce_filepath2,
    platemap_filepath
]

# Get the instrument LG Token
SESSION.login()
cur_token = SESSION.token
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
            'item[section_id]': (None, cur_section.id),
            'item[element_id]': (None, attachments_element_resp.json()['id'])
        }
        response = requests.post(url, headers=headers, files=files)


