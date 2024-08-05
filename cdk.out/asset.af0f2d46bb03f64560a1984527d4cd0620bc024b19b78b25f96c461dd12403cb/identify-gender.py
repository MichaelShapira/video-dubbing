import boto3
import os
import json
import cv2
import numpy as np

s3_client = boto3.client('s3')

def lambda_handler(event, context):
 
  s3_client.download_file("michshap-transcribe", "Conversation.mp4", "/tmp/Conversation.mp4")
  video = cv.VideoCapture('/tmp/Conversation.mp4')
  return 'OK'
    

