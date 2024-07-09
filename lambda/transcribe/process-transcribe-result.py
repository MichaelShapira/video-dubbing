import json
import boto3
from urllib.parse import urlparse
import json
import re
import uuid
import os

# import requests
transcribe_client = boto3.client("transcribe")
s3_client = boto3.client('s3')
sqs = boto3.client('sqs')
translate = boto3.client('translate')

def translate_text(text):
    
    # Translate the text to Russian
    result = translate.translate_text(
        Text=text,
        SourceLanguageCode=os.environ.get('AUDIO_LANGUAGE_SOURCE'),
        TargetLanguageCode=os.environ.get('AUDIO_LANGUAGE_TARGET')
    )
    
    # Get the translated text
    translated_text = result.get('TranslatedText')
    return translated_text
    
def parse_srt(srt_content):
    srt_pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\Z)', re.DOTALL)
    matches = srt_pattern.findall(srt_content)
    
    subtitles = []
    for match in matches:
        sequence = int(match[0])
        start_time = match[1]
        end_time = match[2]
        text = match[3].replace('\n', ' ').replace('"', '\\"')

        start_ms = srt_time_to_ms(start_time)
        duration = calculate_duration(start_time, end_time)
        
        subtitle = {
            "start_time": start_ms,
            "end_time": end_time,
            "sequence": sequence,
            "duration": duration,
            "text": translate_text(text)
        }
        
        subtitles.append(subtitle)
    
    return subtitles

def calculate_duration(start_time, end_time):
    start_ms = srt_time_to_ms(start_time)
    end_ms = srt_time_to_ms(end_time)
    return end_ms - start_ms

def srt_time_to_ms(time_str):
    hours, minutes, seconds = time_str.split(':')
    seconds, milliseconds = seconds.split(',')
    total_ms = (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(milliseconds)
    return total_ms

def send_to_sqs(subsitles,srt_file,uuid4,video_file):
    # Get the URL for the SQS queue
    queue_name = os.environ.get('SQS_QUEUE_NAME')
    response = sqs.get_queue_url(QueueName=queue_name)
    queue_url = response['QueueUrl']

    # Define the JSON object to send
    json_object = {
        "id": str(uuid4),
        "video_file": video_file,
        "srt_data": srt_file,
        "subs": subsitles,
        
    }
    # Convert the JSON object to a string
    message_body = json.dumps(json_object)
    #message_body = message_body.replace("\\'", "'")

    # Send the message to the SQS queue
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=message_body
    )

def lambda_handler(event, context):

    job_name = event['detail']['TranscriptionJobName']
    job = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
    video_file=job['TranscriptionJob']['Media']['MediaFileUri']

    
    mediaFile= job['TranscriptionJob']['Subtitles']['SubtitleFileUris'][0]

    o = urlparse(mediaFile, allow_fragments=False)
    s3WorkString =  o.path
    s3WorkString = s3WorkString[1:]
    
    s3WorkList = s3WorkString.split('/', 1)
    bucket = s3WorkList[0]
    bucketKey = s3WorkList[1]

   

    # Copy the object
    copy_source = {
        'Bucket': bucket,
        'Key': bucketKey
    }
    uuid4 = uuid.uuid4()
    
    work_bucket  = os.environ.get('STAGING_BUCKET_NAME')
    work_object= str(uuid4)+"/"+bucketKey


    s3_client.copy(copy_source, work_bucket,work_object)



    s3_object = s3_client.get_object(Bucket=work_bucket, Key=work_object)
    srt_content = s3_object['Body'].read().decode('utf-8')
    
    subtitles = parse_srt(srt_content)
    
    send_to_sqs(subtitles, f"s3://{work_bucket}/{work_object}",uuid4,video_file)
    
    print(f"Message sent to SQS queue {os.environ.get('SQS_QUEUE_NAME')}")

   
