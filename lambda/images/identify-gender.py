import boto3
import os
import json
import subprocess
import base64

s3_client = boto3.client('s3')
bedrock_runtime_client = boto3.client('bedrock-runtime')
ffmpeg_path=os.environ.get('FFMPEG_PATH')

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
    s3_client.download_file("michshap-transcribe", "Conversation.mp4", "/tmp/Conversation.mp4")
    input_file = '/tmp/Conversation.mp4'  # Replace with your input file path
    time = '00:00:10'  # Extract frame at 10 seconds

    try:
        base64_image = extract_frame_and_convert_to_base64(input_file, time)

        model_id = "anthropic.claude-3-haiku-20240307-v1:0"

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
                            "text": "What is the probablity of the person in the picture to be male or female (in percents)? Only return output as JSON without explanation in the following format { \"gender\": <gender>, \"probablity\": <probability> }. Example { \"gender\": \"female\", \"probablity\": 85 }. If you are not sure return \"probablity: 0\""
                        }
                    ]
                }
            ],
            "max_tokens": 10000,
            "anthropic_version": "bedrock-2023-05-31"
        }

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

        return {
            'statusCode': 200,
            'body': {
                'message': 'Frame extracted and converted successfully',
                'base64_image': output
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

  

    

