import boto3
import os
import json
#import cv2
import numpy as np
import subprocess

s3_client = boto3.client('s3')

def lambda_handler(event, context):
 
  result = subprocess.run('ls -la /opt', capture_output=True, text=True,shell=True)
  output = result.stdout
  print(output)
  s3_client.download_file("michshap-transcribe", "Conversation.mp4", "/tmp/Conversation.mp4")
  #video = cv.VideoCapture('/tmp/Conversation.mp4')
  return 'OK'
    

