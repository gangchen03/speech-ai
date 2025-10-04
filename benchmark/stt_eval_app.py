import configparser
import os
import string
import pandas as pd
from jiwer import cer, wer
from whisper_normalizer.basic import BasicTextNormalizer

from google.cloud import speech_v2
from google.cloud import storage
from google.api_core.client_options import ClientOptions

def load_config(file_path='config.ini'):
    """Reads configuration from an INI file."""
    config = configparser.ConfigParser()
    config.read(file_path)
    return config

def list_gcs_audio_files(gcs_uri):
    """Lists all audio files in a GCS bucket directory."""
    storage_client = storage.Client()
    bucket_name, prefix = gcs_uri.replace("gs://", "").split("/", 1)
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    
    audio_files = [f"gs://{bucket_name}/{blob.name}" for blob in blobs if not blob.name.endswith('/')]
    print(f"Found {len(audio_files)} audio files in {gcs_uri}")
    return audio_files

def load_ground_truth(gcs_uri):
    """Loads ground truth from a GCS text file into a dictionary."""
    print(f"Loading ground truth from {gcs_uri}...")
    try:
        storage_client = storage.Client()
        bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        content = blob.download_as_text()
        
        ground_truth = {}
        for line in content.strip().split("\n"):
            # Expects format: "audio_file_name.wav\ttext transcription"
            parts = line.split("\t", 1)
            if len(parts) == 2:
                # Store just the filename as the key
                ground_truth[os.path.basename(parts[0])] = parts[1]
        print(f"Successfully loaded {len(ground_truth)} ground truth entries.")
        return ground_truth
    except Exception as e:
        print(f"Error loading ground truth file: {e}")
        return {}


def transcribe_gcs_uri_chirp(
    gcs_uri: str,
    project_id: str,
    location: str,
    language_code: str,
    model: str
) -> str:
    """
    Transcribes an audio file stored in GCS using the Chirp model.

    Args:
        gcs_uri (str): The GCS URI of the audio file.
        project_id (str): Your Google Cloud project ID.
        location (str): The GCP location for the recognizer.
        language_code (str): The language of the audio.
        model (str): The STT model to use (e.g., 'chirp').

    Returns:
        str: The transcribed text.
    """
    try:
        # Instantiates a client
        client = speech_v2.SpeechClient(
            client_options=ClientOptions(
                api_endpoint=f"{location}-speech.googleapis.com",
            )
        )

        config = speech_v2.RecognitionConfig(
            auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
            language_codes=[language_code],
            model=model,
        )

        request = speech_v2.RecognizeRequest(
            recognizer=f"projects/{project_id}/locations/{location}/recognizers/_",
            config=config,
            uri=gcs_uri,
        )

        # Transcribes the audio into text
        response = client.recognize(request=request)

        if response and response.results:
            return response.results[0].alternatives[0].transcript
        return ""
    except Exception as e:
        print(f"An error occurred during transcription for {gcs_uri}: {e}")
        return "ERROR_TRANSCRIPTION"


def main():
    """Main function to run the STT evaluation benchmark."""
    try:
        print("--- Starting Speech-to-Text Evaluation ---")
        print("Press Ctrl+C at any time to exit gracefully.")

        # 1. Read configuration
        config = load_config()
        gcp_config = config['gcp']
        stt_config = config['stt']
        data_config = config['data']
        output_config = config['output']

        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", gcp_config.get('project_id'))
        if not project_id:
            raise ValueError("Google Cloud project ID not found. Please set GOOGLE_CLOUD_PROJECT environment variable or in config.ini")

        batch_size = int(data_config['batch_size'])
        language_code = stt_config['language_code']
        
        # Create a 'results' directory if it doesn't exist
        results_dir = 'results'
        os.makedirs(results_dir, exist_ok=True)
        output_csv = os.path.join(results_dir, output_config['csv_file'])

        remove_space = stt_config.getboolean('remove_space', fallback=False)
        keep_punctuation = stt_config.getboolean('punctuation', fallback=True)
        metric_type = stt_config.get('metric', 'cer').lower()

        if metric_type not in ['cer', 'wer']:
            raise ValueError("Configuration error: 'metric' must be either 'cer' or 'wer'.")
        
        # Dynamically construct URIs
        gcs_bucket_uri = data_config['gcs_bucket_uri']
        # Ensure gcs_bucket_uri doesn't have a trailing slash for clean joining
        gcs_bucket_uri = gcs_bucket_uri.rstrip('/')
        gcs_audio_bucket_uri = f"{gcs_bucket_uri}/audio/{language_code}/audio/"
        gcs_ground_truth_uri = f"{gcs_bucket_uri}/audio/{language_code}/labels/labels_{language_code}.txt"

        # 2. Get list of audio files and load ground truth
        all_audio_files = list_gcs_audio_files(gcs_audio_bucket_uri)
        ground_truth_map = load_ground_truth(gcs_ground_truth_uri)
        
        if not all_audio_files:
            print("No audio files found. Exiting.")
            return
            
        if not ground_truth_map:
            print("Ground truth is empty. Cannot calculate CER. Exiting.")
            return

        # Load existing results to handle updates and skips
        results_df = pd.DataFrame()
        if os.path.exists(output_csv):
            try:
                # Read the existing CSV, filtering out any previous stats sections
                score_column = f'{metric_type}_score'
                temp_df = pd.read_csv(output_csv, dtype={score_column: str})
                # Convert score column to numeric, coercing errors will turn non-numeric strings (like 'max') into NaN
                temp_df[score_column] = pd.to_numeric(temp_df[score_column], errors='coerce')
                # Keep only the actual data rows where 'audio_file_name' is not NaN
                results_df = temp_df[temp_df['audio_file_name'].notna()].copy()
                print(f"Loaded {len(results_df)} existing results from {output_csv}.")
            except (pd.errors.EmptyDataError, KeyError):
                print(f"Warning: {output_csv} is empty or malformed. Starting fresh.")
        
        # Use 'audio_file_name' as the index for efficient lookups and updates
        if not results_df.empty:
            results_df.set_index('audio_file_name', inplace=True)

        # 3. Process files in batches
        files_to_process = all_audio_files[:batch_size]
        normalizer = BasicTextNormalizer()
        
        print(f"\nProcessing a batch of {len(files_to_process)} audio files...")
        for i, audio_uri in enumerate(files_to_process):
            audio_file_name = os.path.basename(audio_uri)
            print(f"  ({i+1}/{len(files_to_process)}) Processing: {audio_file_name}")

            # Check if the file has already been transcribed
            if audio_file_name in results_df.index and 'transcribed_text' in results_df.columns:
                print(f"    -> Transcription exists. Skipping API call.")
                transcribed_text = results_df.loc[audio_file_name, 'transcribed_text']
            else:
                # 4. Call transcription API if it's a new file
                print(f"    -> New file. Calling transcription API...")
                transcribed_text = transcribe_gcs_uri_chirp(
                    gcs_uri=audio_uri,
                    project_id=project_id,
                    location=gcp_config['location'],
                    language_code=language_code,
                    model=stt_config['model']
                )
                print(f"    -> Transcription result: {transcribed_text}")

            # 5. Always normalize text and calculate CER
            normalized_text = normalizer(transcribed_text)
            reference = ground_truth_map.get(audio_file_name)

            # Optionally remove punctuation from the reference text
            if not keep_punctuation and reference:
                # Create a translation table to remove all punctuation
                translator = str.maketrans('', '', string.punctuation + "。，、？！：；‘’“”—…")
                reference = reference.translate(translator)

            score = None
            if reference and normalized_text:
                # Prepare texts for CER calculation, optionally removing spaces
                hypothesis_for_cer = normalized_text
                reference_for_cer = reference
                if metric_type == 'cer':
                    if remove_space:
                        hypothesis_for_cer = hypothesis_for_cer.replace(" ", "")
                        reference_for_cer = reference_for_cer.replace(" ", "")
                    score = cer(reference_for_cer, hypothesis_for_cer) * 100
                else: # metric_type == 'wer'
                    score = wer(reference, normalized_text) * 100

            # 6. Update or add the row in the DataFrame
            score_column = f'{metric_type}_score'
            results_df.loc[audio_file_name, ['transcribed_text', 'normalized_text', 'ground_truth', score_column]] = [transcribed_text, normalized_text, reference, score]
            print(f"    -> Updated scores in memory.")

        # 7. Write the entire updated DataFrame back to the CSV file
        if not results_df.empty:
            # Reset index to turn 'audio_file_name' back into a column
            final_df = results_df.reset_index()
            score_column = f'{metric_type}_score'
            # Define column order for consistency
            final_df = final_df.rename(columns={'index': 'audio_file_name'})
            column_order = ['audio_file_name', 'transcribed_text', 'normalized_text', 'ground_truth', score_column]
            # Reorder columns, adding any missing ones
            final_df = final_df.reindex(columns=column_order)

            final_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
            print(f"\nMain transcription results saved to {output_csv}")
        else:
            print("\nNo results to write.")
            return

        # 8. Conduct final statistical calculation
        print("\nCalculating summary statistics...")
        score_column = f'{metric_type}_score'
        scores = results_df[score_column].dropna().astype(float)

        if scores.empty:
            print(f"Could not calculate statistics as there were no valid {metric_type.upper()} scores.")
        else:
            # Calculate Pooled CER
            # Concatenate all normalized and reference texts
            mega_hypothesis = " ".join(results_df['normalized_text'].dropna().astype(str))
            mega_reference = " ".join(results_df['ground_truth'].dropna().astype(str))

            pooled_score = None
            if metric_type == 'cer':
                if remove_space:
                    mega_hypothesis = mega_hypothesis.replace(" ", "")
                    mega_reference = mega_reference.replace(" ", "")
                pooled_score = cer(mega_reference, mega_hypothesis) * 100
            else: # metric_type == 'wer'
                pooled_score = wer(mega_reference, mega_hypothesis) * 100

            stats = {
                'mean': [scores.mean()],
                'median': [scores.median()],
                'min': [scores.min()],
                'max': [scores.max()],
                f'pooled_{metric_type}': [pooled_score]
            }
            stats_df = pd.DataFrame(stats)
            
            print(f"\n--- {metric_type.upper()} Score Statistics (%) ---")
            print(stats_df.to_string(index=False))

            # Append stats to the CSV file
            with open(output_csv, 'a', newline='', encoding='utf-8-sig') as f:
                f.write('\n\n--- Statistics ---\n')
                stats_df.to_csv(f, index=False)
            print(f"Statistics appended to {output_csv}")

    except KeyboardInterrupt:
        print("\n\n--- Program interrupted by user (Ctrl+C). Exiting. ---")
    finally:
        # 9. Exit
        print("\n--- Benchmark Program Finished ---")

if __name__ == "__main__":
    main()