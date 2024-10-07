import boto3
import os
import json
import subprocess
import base64
import math
import re

s3_client = boto3.client('s3')
bedrock_runtime_client = boto3.client('bedrock-runtime')
ffmpeg_path=os.environ.get('FFMPEG_PATH')

def parse_s3_path(s3_path):
    # Regex pattern to match S3 paths
    pattern = r"s3://([^/]+)/(.+)"
    match = re.match(pattern, s3_path)
    
    if match:
        bucket_name = match.group(1)  # First capture group is the bucket name
        bucket_key = match.group(2)   # Second capture group is the bucket key (including folders)
        return bucket_name, bucket_key
    else:
        raise ValueError(f"Invalid S3 path: {s3_path}")

def conv_to_time(ms):
    
    seconds = ms // 1000
    minutes = (seconds // 60) % 60
    hours = seconds // 3600
    seconds = seconds % 60
    
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def extract_frame_and_convert_to_base64(input_file, time, output_format='jpg'):
    # FFmpeg command to extract the frame and output to stdout
    temp_file = '/tmp/screenshot.png'
    ffmpeg_command = f'{ffmpeg_path} -ss {time} -i {input_file} -frames:v 1 -q:v 2 -update 1 {temp_file}'
        
         # Run FFmpeg command
    subprocess.run(ffmpeg_command, shell=True, check=True, capture_output=True, text=True)

    # Read the temporary file and encode it to base64
    with open(temp_file, 'rb') as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    # Clean up the temporary file
    os.remove(temp_file)

    return encoded_string



def lambda_handler(event, context):

    str = event.get('srt')
    video_file = event.get('video_file')
    num_of_speakers = event.get('num_of_speakers')
    
    bucket,bucketKey = parse_s3_path(video_file)
    
    local_video_file="/tmp/video.mp4"

    s3_client.download_file(bucket, bucketKey, local_video_file)
    
    time = '00:00:10'  # Extract frame at 10 seconds
    
    speakers = []

    for i in range(num_of_speakers):
        total_male = 0
        total_female=0    
        for entry in str:
          
            if entry["speaker"] == f"spk_{i}":
                try:
                 
                    avg_time_ms = (entry["start_time"] + entry["end_time"]) / 2
                    
                    # Convert milliseconds to time format
                    time_val = conv_to_time(math.floor(avg_time_ms))
                    base64_image = extract_frame_and_convert_to_base64(local_video_file, time_val)
                    #model_id = "anthropic.claude-3-haiku-20240307-v1:0"
                    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
                  
                    payload = {
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/jpeg",
                                            "data": base64_image
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": "You are an AI assistant that should analyze the image and identify the gender of the person who is currently speaking. There are only three possible values that you should return: MALE, FEMALE, or NONE. It could be that the image doesn't contain persons or it is impossible to predict who the current speaker is. In this case, return NONE.No needto explain your response. Only return one of tree option: MALE,FEMALE,NONE "
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 10000,
                        "anthropic_version": "bedrock-2023-05-31"
                    }
                    try:
                        # we're ready to invoke the model!
                        response = bedrock_runtime_client.invoke_model(
                            modelId=model_id,
                            contentType="application/json",
                            body=json.dumps(payload)
                        )
                        # now we need to read the response. It comes back as a stream of bytes so if we want to display the response in one go we need to read the full stream first
                        # then convert it to a string as json and load it as a dictionary so we can access the field containing the content without all the metadata noise
                        output_binary = response["body"].read()
                        output_json = json.loads(output_binary)
                        output = output_json["content"][0]["text"]
                  
                        print(output)
                        
                        if output == "MALE": 
                            total_male+=1
                        if output == "FEMALE": 
                            total_female+=1

                        print(f'index: {i}')  
                        print(f'str: {entry}') 
                        print(total_male)  
                         
                        print(total_female) 
                        
                        '''
                        return {
                            'statusCode': 200,
                            'body': {
                                'message': 'Frame extracted and converted successfully',
                                'base64_image': output
                            }
                        }'''
                    except Exception as e:
                        print(e)    
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
        speakers.append({"speaker":f"spk_{i}","gender":("male" if total_male >= total_female else "female")})          
    
    print(speakers)
    return json.dumps(speakers)
  

    

