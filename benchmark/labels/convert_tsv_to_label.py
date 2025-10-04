
import pandas as pd
import os
import csv
import argparse

def convert_tsv_to_label(input_file, output_file):
    """
    Converts a TSV file from a specific format to a label.txt format.

    Input format (TSV):
    client_id\tpath\tsentence\t...

    Output format (TXT):
    filename.mp3\ttranscription

    Args:
        input_file (str): Path to the source TSV file.
        output_file (str): Path to the destination label.txt file.
    """
    try:
        print(f"Reading data from: {input_file}")
        # Read the TSV file using pandas, specifying the tab separator, python engine, and no quoting to handle quotes in sentences.
        df = pd.read_csv(input_file, sep='\t', engine='python', quoting=csv.QUOTE_NONE)

        # Ensure the required columns exist
        if 'path' not in df.columns or 'sentence' not in df.columns:
            raise ValueError("Input TSV must contain 'path' and 'sentence' columns.")

        print(f"Writing converted data to: {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for index, row in df.iterrows():
                original_filename = row['path']
                sentence = row['sentence']
                # Change the extension from .mp3 to .wav
                filename = os.path.splitext(original_filename)[0] + '.wav'
                # Write in the format: "filename.wav\tsentence"
                f_out.write(f"{filename}\t{sentence}\n")

        print(f"Conversion successful. {len(df)} lines written to {output_file}")

    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a Common Voice TSV file to a label.txt format for STT evaluation."
    )
    parser.add_argument(
        "input_file", type=str, help="Path to the source TSV file."
    )
    parser.add_argument(
        "output_file", type=str, help="Path for the destination label.txt file."
    )
    args = parser.parse_args()
    convert_tsv_to_label(args.input_file, args.output_file)
