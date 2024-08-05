import boto3
import os
import json
import subprocess
import base64

s3_client = boto3.client('s3')
ffmpeg_path=os.environ.get('FFMPEG_PATH')

def extract_frame_and_convert_to_base64(input_file, time, output_format='jpg'):
    # FFmpeg command to extract the frame and output to stdout
    ffmpeg_command = f'{ffmpeg_path} -ss {time} -i {input_file} -frames:v 1 -q:v 2 -update 1 /tmp/screenshot.png'
        
         # Run FFmpeg command
    subprocess.run(ffmpeg_command, shell=True, check=True, capture_output=True, text=True)

    # Read the temporary file and encode it to base64
    with open(temp_file, 'rb') as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    # Clean up the temporary file
    os.remove(temp_file)

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
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg stderr: {e.stderr}")    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': {
                'message': 'An error occurred',
                'error': str(e)
            }
        }

  

    

