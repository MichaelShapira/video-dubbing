import json
import subprocess
import boto3
import stat
import os
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from datetime import datetime, timedelta
import time


s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')
s3_client = boto3.client('s3')
sns = boto3.client('sns')


bucket_name = os.environ.get('STAGING_BUCKET_NAME')

def generate_presigned_url(bucket_name, object_key, expiration=86400):
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key
            },
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print(f"Error generating pre-signed URL: {str(e)}")
        return None

def send_email(subject, content, recipient_email):
    
    
    # Your SNS topic ARN
    topic_arn = os.environ.get('SNS_EMAIL_TOPIC')

    # HTML content for the email
    
    # Prepare the message
    message = {
        "default": "This is the default message",
        "email": content
    }

    # Publish the message
    response = sns.publish(
        TopicArn=topic_arn,
        Message=json.dumps(message),
        Subject='Video Dubbing is ready',
        MessageStructure='json'
    )


def get_dubbing_polly_jobs(dubbing_job_id):
    
    table = dynamodb.Table(os.environ.get('DYNAMO_POLLY_JOBS_TABLE'))

    try:
        # Assuming the secondary index name is 'MediaIdIndex'
        # If it's different, replace 'MediaIdIndex' with the actual index name
        response = table.query(
            IndexName=os.environ.get('DYNAMO_POLLY_JOBS_INDEX'),
            KeyConditionExpression=Key('dubbing_job_id').eq(dubbing_job_id)
        )
        
        # Convert the result to a dictionary
        result_dict = {}
        for item in response['Items']:
            sequence = int(item.get('sequence', 0))  # Convert to int, default to 0 if not present
            output_path = item.get('polly_output_object', '')
            start_time = int(item.get('start_time', 0))
            result_dict[sequence] = {
                "mp3_path": output_path,
                "start_time": start_time
            } 

        # Sort the dictionary by key (sequence)
        #sorted_dict = dict(sorted(result_dict.items()))
        sorted_dict  = dict(sorted(result_dict.items(), key=lambda x: x[0],reverse=True))
        return sorted_dict

    except ClientError as e:
        print(f"An error occurred: {e.response['Error']['Message']}")
        return None

def parse_s3_url(s3_url):
    # Remove the "s3://" prefix if present
    s3_url = s3_url.replace("s3://", "")

    # Split the URL into bucket and key
    parts = s3_url.split('/')
    bucket_name = parts[0]
    object_key = '/'.join(parts[1:])  # Join the remaining parts as the object key

    return bucket_name, object_key

def lambda_handler(event, context):
    
    
    ffmpeg_path=os.environ.get('FFMPEG_PATH')
    """
    result = subprocess.run(f'{ffmpeg_path}', 
                            capture_output=True, 
                            text=True, 
                            check=True, shell=True)
    print("Standard Output:")
    print(result.stdout)
    
    # Print stderr (if any)
    if result.stderr:
        print("Standard Error:")
        print(result.stderr)    

    """

    function_start_time = time.time()
    print(f"Start time: {function_start_time}")
    print('Merging audio streams....')

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
 
    sqs_data = json.loads(sqs_msg)


   
    video_file = sqs_data['video_file']

    bucket_name, bucket_key = parse_s3_url(video_file)

    input_video = '/tmp/input_file.mp4'
    output_file = '/tmp/output_file.mp4'
    
    print(f"Downloading input video from : {bucket_name},{bucket_key} int {input_video}")
        # Download input files from S3
    s3_client.download_file(bucket_name, bucket_key, input_video)
        
        
  
        
    
    
    try:

        dubbing_job_id = sqs_data['dubbing_job_id']
        final_file=f'{dubbing_job_id}/merged_output.mp4'

        sorted_result = get_dubbing_polly_jobs(dubbing_job_id)

        bucket = None
        while sorted_result:
            sequence, metadata = sorted_result.popitem()
            mp3_path = metadata['mp3_path']
            start_time=metadata['start_time']

            # Read input streams
            
            bucket,bucketKey = parse_s3_url(mp3_path)
            
            s3_client.download_file(bucket, bucketKey, f'/tmp/{sequence}.mp3')
            input_audio = f'/tmp/{sequence}.mp3'
        
            cmd = f"{ffmpeg_path} -y -i {input_video} -i {input_audio} -filter_complex '[1:a]adelay={start_time}|{start_time},volume=3,compand[delayed_audio];[0:a][delayed_audio]amix=inputs=2:duration=longest:normalize=0' -c:v copy -c:a aac -b:a 192k {output_file}"
            print(cmd)
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            result = subprocess.run(f"mv {output_file} {input_video}", shell=True, check=True, capture_output=True, text=True)
            print("Standard Output:")
            print(result.stdout)
            
            # Print stderr (if any)
            if result.stderr:
                print("Standard Error:")
                print(result.stderr) 

            end_time = time.time()
            print(f"End time: {end_time}")
            #safeguard for Lambda 15 minutes max runtime
            elapsed_time =  end_time-function_start_time
            # stop after 14 minutes
            print(f'Elapsed time: {elapsed_time} seconds' )
            if elapsed_time > 840:
                print("Reached 14 minutes. Safeguard activated. Partial dubbing expected")
                break
 
        # Upload the result back to S3
        s3_client.upload_file(f"{input_video}", bucket, final_file)

        presigned_url = generate_presigned_url(bucket, final_file)

        if presigned_url:
            # Prepare email content
            expiration_time = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            subject = "Dubbing results"
            email_content = f"""
            You video dubbing for {video_file} is ready. Download it here {presigned_url}
            """
            recipient_email = "michshap@amazon.com"

            # Send the email
            send_email(subject, email_content, recipient_email)

        queue_url = sqs.get_queue_url(QueueName=record['eventSourceARN'].split(':')[-1])['QueueUrl']

        # Delete the message
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        print(f"Message deleted successfully")

    except subprocess.CalledProcessError as e:
        print(f"FFmpeg stderr: {e.stderr}")
       
 
