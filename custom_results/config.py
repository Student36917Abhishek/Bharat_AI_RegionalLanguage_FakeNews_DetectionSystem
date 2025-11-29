"""
Configuration file for Reddit data processing pipeline
"""

# Default 
DEFAULT_INPUT_FILE = "/home/abhi/Pictures/custom_results/reddit_search_output.json"
DEFAULT_EXTRACTED_FILE = "extracted_reddit_data.json"
DEFAULT_OUTPUT_FILE = "translated_reddit_data.json"

def get_file_paths():
    """
    Get input and output file paths.
    Can be modified to accept user input or command line arguments.
    """
    return DEFAULT_INPUT_FILE, DEFAULT_EXTRACTED_FILE, DEFAULT_OUTPUT_FILE

def set_file_paths(input_file=None, extracted_file=None, output_file=None):
    """
    Set custom input and output file paths.
    Returns paths to be used in the main script.
    """
    input_path = input_file if input_file else DEFAULT_INPUT_FILE
    extracted_path = extracted_file if extracted_file else DEFAULT_EXTRACTED_FILE
    output_path = output_file if output_file else DEFAULT_OUTPUT_FILE
    return input_path, extracted_path, output_path
