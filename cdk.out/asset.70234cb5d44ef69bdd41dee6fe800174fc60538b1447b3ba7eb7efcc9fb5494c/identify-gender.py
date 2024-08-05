import boto3
import os
import json
import subprocess

s3_client = boto3.client('s3')
ffmpeg_path=os.environ.get('FFMPEG_PATH')

def lambda_handler(event, context):
 
  result = subprocess.run(f'{ffmpeg_path} --version', shell=True, check=True, capture_output=True, text=True)
  output = result.stdout
  print(output)
  #s3_client.download_file("michshap-transcribe", "Conversation.mp4", "/tmp/Conversation.mp4")
  #video = cv.VideoCapture('/tmp/Conversation.mp4')
  return 'OK'
    

