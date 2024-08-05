import boto3
import os
import json
import subprocess

s3_client = boto3.client('s3')
ffmpeg_path=os.environ.get('FFMPEG_PATH')

def extract_frame_and_convert_to_base64(input_file, time, output_format='jpg'):
    # FFmpeg command to extract the frame and output to stdout
    ffmpeg_command = [
        'ffmpeg',
        '-i', input_file,  # Input file
        '-ss', time,       # Seek to the specified time
        '-frames:v', '1',  # Extract only one frame
        '-q:v', '2',       # Quality (2 is high quality, lower number = higher quality)
        '-f', output_format,  # Force output format
        '-'                # Output to stdout
    ]

    # Run FFmpeg command and pipe the output to base64
    process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise Exception(f"FFmpeg error: {stderr.decode()}")

    # Encode the output to base64
    encoded_string = base64.b64encode(stdout).decode('utf-8')

    return encoded_string



def lambda_handler(event, context):
    s3_client.download_file("michshap-transcribe", "Conversation.mp4", "/tmp/Conversation.mp4")
    input_file = '/tmp/Conversation.mp4'  # Replace with your input file path
    time = '00:00:10'  # Extract frame at 10 seconds

    try:
        base64_image = extract_frame_and_convert_to_base64(input_file, time)
        return {
            'statusCode': 200,
            'body': {
                'message': 'Frame extracted and converted successfully',
                'base64_image': base64_image
            }
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': {
                'message': 'An error occurred',
                'error': str(e)
            }
        }

  

    

