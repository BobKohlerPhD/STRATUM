import pandas as pd
import subprocess
import argparse
import os
import numpy as np
import json

def get_filtered_variable_names(search_keyword=None, search_column='generalized_variable_name', output_column='original_variable_name'):
    """
    Loads clinical_registry_master.csv and filters variables based on a keyword in a specified column.
    """
    try:
        dict_path = 'clinical_registry_master.csv'
        if not os.path.exists(dict_path):
            dict_path = os.path.join('data', 'processed', 'clinical_registry_master.csv')
        
        if not os.path.exists(dict_path):
            print(f"Error: {dict_path} not found. Please ensure it has been generated.")
            return []
            
        df_dict = pd.read_csv(dict_path, low_memory=False)
    except Exception as e:
        print(f"Error loading data dictionary: {e}")
        return []

    if search_keyword:
        if search_column not in df_dict.columns:
            print(f"Error: Search column '{search_column}' not found in clinical_registry_master.csv.")
            return []
        
        mask = df_dict[search_column].astype(str).str.contains(search_keyword, case=False, na=False)
        filtered_df = df_dict[mask]
    else:
        filtered_df = df_dict

    if output_column not in filtered_df.columns:
        print(f"Error: Output column '{output_column}' not found in clinical_registry_master.csv.")
        return []

    return filtered_df[output_column].drop_duplicates().tolist()

def generate_fake_data(selected_variables, df_dict, output_file="harmonized_registry_data.rds", num_samples=1000):
    """
    Generates fake data with actual labels and saves it as an RDS file.
    """
    import tempfile
    
    print(f"Generating fake data for {len(selected_variables)} variables...")
    
    # Generic core columns for data orchestration
    data = {
        "participant_id": [f"sub-{i:04d}" for i in range(num_samples)],
        "session_label": np.random.choice(["Baseline", "Year 1", "Year 2", "Year 3"], num_samples),
        "subject_sex": np.random.choice([1, 2], num_samples)
    }
    
    for var_name in selected_variables:
        var_info = df_dict[df_dict['original_variable_name'] == var_name]
        if var_info.empty:
            continue
        
        datatype = var_info['datatype'].iloc[0]
        levels_str = var_info['levels'].iloc[0]
        
        label_map = {}
        try:
            if isinstance(levels_str, str) and levels_str.startswith('['):
                levels_list = json.loads(levels_str)
                for l in levels_list:
                    if '=' in l:
                        val, lbl = l.split('=', 1)
                        label_map[val.strip()] = lbl.strip()
        except Exception as e:
            print(f"Warning: Could not parse levels for {var_name}: {e}")

        if datatype in ['nominal', 'ordinal'] and label_map:
            choices = list(label_map.values())
            data[var_name] = np.random.choice(choices, num_samples)
        elif datatype in ['ratio', 'interval']:
            data[var_name] = np.random.uniform(0, 100, num_samples)
        else:
            data[var_name] = np.random.choice(["A", "B", "C"], num_samples)

    df_fake = pd.DataFrame(data)
    
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as tmp:
        df_fake.to_csv(tmp.name, index=False)
        r_cmd = f"suppressPackageStartupMessages(library(readr)); df <- read_csv('{tmp.name}', show_col_types = FALSE); saveRDS(df, '{output_file}')"
        subprocess.run(["Rscript", "-e", r_cmd], check=True)
        os.unlink(tmp.name)
    
    print(f"Fake data saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Orchestrates variable analysis and plotting.")
    parser.add_argument("--variables", nargs='*', help="List of specific variable names to plot.")
    parser.add_argument("--filter_keyword", type=str, help="Keyword to search for in variable names.")
    parser.add_argument("--filter_col", type=str, default="generalized_variable_name",
                        help="Column to search within when using --filter_keyword.")
    parser.add_argument("--output_dir", type=str, default="plots", help="Directory to save generated plots.")
    parser.add_argument("--fake_data", action="store_true", help="Generate fake data for testing plots.")
    parser.add_argument("--num_samples", type=int, default=1000, help="Number of samples for fake data.")

    args = parser.parse_args()

    dict_path = 'clinical_registry_master.csv'
    if not os.path.exists(dict_path):
        dict_path = os.path.join('data', 'processed', 'clinical_registry_master.csv')
    
    try:
        df_dict = pd.read_csv(dict_path, low_memory=False)
    except FileNotFoundError:
        print(f"Error: {dict_path} not found.")
        return

    selected_variables_to_plot = []
    if args.variables:
        selected_variables_to_plot = args.variables
    elif args.filter_keyword:
        selected_variables_to_plot = get_filtered_variable_names(
            search_keyword=args.filter_keyword,
            search_column=args.filter_col
        )
    else:
        print("Please provide variables or filter.")
        return

    if args.fake_data:
        generate_fake_data(selected_variables_to_plot, df_dict, num_samples=args.num_samples)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    for var_name in selected_variables_to_plot:
        var_info = df_dict[df_dict['original_variable_name'] == var_name]
        if var_info.empty: continue
        
        datatype = var_info.iloc[0]['datatype']
        plot_script = "src/r/plots/clinical-plots_unified.r"

        output_plot_path = os.path.join(args.output_dir, f"{var_name}_plot.png")
        print(f"Generating plot for '{var_name}' (Type: {datatype})...")
        try:
            subprocess.run(["Rscript", plot_script, var_name, output_plot_path, datatype], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error plotting '{var_name}': {e}")
    
    print("\nPlotting orchestration complete.")

if __name__ == "__main__":
    main()
