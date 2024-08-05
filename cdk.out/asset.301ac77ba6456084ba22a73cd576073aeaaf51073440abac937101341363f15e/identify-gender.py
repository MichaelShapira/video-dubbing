import boto3
import os
import json

s3_client = boto3.client('s3')

def lambda_handler(event, context):
 
  s3.download_file("michshap-transcribe", "Conversation.mp4", "/tmp/Conversation.mp4")
  return 'OK'
    

