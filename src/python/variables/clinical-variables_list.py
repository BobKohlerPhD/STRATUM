import pandas as pd
import os
import difflib
from typing import List, Optional

def get_filtered_variable_names(
    search_keyword: Optional[str] = None, 
    search_column: str = 'generalized_variable_name', 
    output_column: str = 'original_variable_name', 
    fuzzy: bool = True
) -> List[str]:
    """
    Filters and returns variable names from the clinical registry.
    
    Args:
        search_keyword (Optional[str]): Keyword to search for.
        search_column (str): Column to search in.
        output_column (str): Column to return.
        fuzzy (bool): Whether to use fuzzy matching if strict matching fails.
        
    Returns:
        List[str]: A list of matched variable names.
    """
    try:
        dict_path = 'clinical_registry_master.csv'
        if not os.path.exists(dict_path):
            dict_path = os.path.join('data', 'processed', 'clinical_registry_master.csv')
            
        df_dict = pd.read_csv(dict_path, low_memory=False)
    except FileNotFoundError:
        return []
    
    if not search_keyword:
        return df_dict[output_column].drop_duplicates().tolist()

    # Strict filtering
    mask = df_dict[search_column].astype(str).str.contains(search_keyword, case=False, na=False)
    filtered_df = df_dict[mask]

    # Fuzzy logic if strict fails or if fuzzy is explicitly enabled
    if filtered_df.empty and fuzzy:
        all_names = df_dict[search_column].astype(str).tolist()
        matches = difflib.get_close_matches(search_keyword, all_names, n=5, cutoff=0.6)
        if matches:
            filtered_df = df_dict[df_dict[search_column].isin(matches)]
    
    return filtered_df[output_column].drop_duplicates().tolist()

