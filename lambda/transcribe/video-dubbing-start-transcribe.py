import boto3
import uuid
import json
import os

def lambda_handler(event, context):


    
    record = event['Records'][0]
    
    s3bucket = record['s3']['bucket']['name']
    s3object = record['s3']['object']['key']
    
    s3Path = f's3://{s3bucket}/{s3object}'
    jobName = f'{s3object}--{str(uuid.uuid4())}'
    outputKey = f'transcripts/{s3object}-transcript.json'
    
    client = boto3.client('transcribe')
    
    response = client.start_transcription_job(
        TranscriptionJobName=jobName,
        LanguageCode=os.environ.get('AUDIO_LANGUAGE'),
        Media={'MediaFileUri': s3Path},
        OutputBucketName=s3bucket,
        OutputKey=outputKey,
        Settings={
                'ShowSpeakerLabels': True,
                'MaxSpeakerLabels': 10  # Adjust based on expected number of speakers
            },
        Subtitles={'Formats': ['srt']}
    )
    
 
    
    