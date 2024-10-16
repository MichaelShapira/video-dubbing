import boto3
import json
import uuid
import os
from botocore.exceptions import ClientError



polly_client = boto3.client('polly')
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')


def insert_dubbing_polly_job(polly_job_id, dubbing_job_id,sequence,start_time):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table( os.environ.get('DYNAMO_POLLY_JOBS_TABLE'))

    try:
        response = table.put_item(
            Item={
                'polly_job_id': polly_job_id,
                'dubbing_job_id': dubbing_job_id,
                'status': 'STARTED',
                'polly_output_object': '',
                'sequence': sequence,
                'start_time': start_time
            }
        )
        
        return True
    except ClientError as e:
        print(f"An error occurred: {e.response['Error']['Message']}")
        return False



def run_polly_job(text, duration,unique_id,target_bucket,target_bucket_key):

    polly_text=f"<speak><prosody amazon:max-duration=\"{duration}ms\">{text}</prosody></speak>"
    
    
    # Start the asynchronous Polly job
    response = polly_client.start_speech_synthesis_task(
        Engine='standard',
        LanguageCode=os.environ.get('POLLY_LANGUAGE_CODE'),
        OutputFormat='mp3',
        OutputS3BucketName=target_bucket,
        OutputS3KeyPrefix=target_bucket_key,
        Text=polly_text,
        TextType='ssml',
        VoiceId=os.environ.get('POLLY_VOICE_ID'),
        SnsTopicArn=os.environ.get('POLLY_JOBS_SNS_ARN')
    )
    return response['SynthesisTask']['TaskId']

def insert_dubbing_status(unique_id, chunks_counter, media_output_bucket, media_output_prefix,video_file):
    
    table = dynamodb.Table(os.environ.get('DYNAMO_DUBBING_STATUS_TABLE'))

    try:
        response = table.put_item(
            Item={
                'dubbing_job_id': unique_id,
                'chunks_counter': chunks_counter,
                'media_output_bucket': media_output_bucket,
                'media_output_prefix': media_output_prefix,
                'video_file': video_file
            }
        )
        print("Insert successful")
        return True
    except ClientError as e:
        print(f"An error occurred: {e.response['Error']['Message']}")
        return False

def lambda_handler(event, context):
    # Initialize the SQS client

    sqs_msg = None
    

    # Check if there are any records in the event
    if 'Records' not in event or len(event['Records']) == 0:
        print("No records found in the event")
        return {
            'statusCode': 200,
            'body': json.dumps('No messages to process')
        }

    # Get the first (and only) record
    record = event['Records'][0]
    
    receipt_handle = record['receiptHandle']

    # Extract the message body
    sqs_msg = record['body']

   

    translated_srt = json.loads(sqs_msg)

    unique_id = translated_srt['id']
    video_file=translated_srt['video_file']
    chunks_counter = len(translated_srt['subs'])
    media_output_bucket = os.environ.get('STAGING_BUCKET_NAME')
    media_output_prefix = f'{unique_id}/polly_output/'

    success = insert_dubbing_status(unique_id, chunks_counter, media_output_bucket, unique_id,video_file)
    if success:
        print(f"Record inserted successfully into Dubbing_status table with id {unique_id}")
    else:
        print("Failed to insert record into Dubbing_status table")

    for srt in translated_srt['subs']:
        polly_job_id=run_polly_job(srt['text'], srt['duration'],unique_id,media_output_bucket,media_output_prefix)
        sequence = srt['sequence']
        start_time=srt['start_time']
        success = insert_dubbing_polly_job(polly_job_id, unique_id,sequence,start_time)
        if success:
            print(f"Record inserted successfully into Dubbing_polly_jobs table with polly_job_id {polly_job_id}")
        else:
            print("Failed to insert record into Dubbing_polly_jobs table")
            
            
            
    try:
        # Create SQS client
        
        # Get the queue URL
        queue_url = sqs.get_queue_url(QueueName=record['eventSourceARN'].split(':')[-1])['QueueUrl']

        # Delete the message
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        print(f"Message deleted successfully")
        
    except Exception as e:
        
        print(f"Error deleting message: {str(e)}")
        # Depending on your use case, you might want to raise an exception here
        # to prevent the Lambda from reporting success if message deletion fails
        
        
    