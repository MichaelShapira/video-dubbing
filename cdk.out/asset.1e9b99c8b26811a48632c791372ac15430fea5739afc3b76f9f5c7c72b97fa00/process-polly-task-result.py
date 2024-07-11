import boto3
import os
import json
from botocore.exceptions import ClientError


dynamodb = boto3.resource('dynamodb')
# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

# DynamoDB table names
POLLY_JOBS_TABLE = os.environ.get('DYNAMO_POLLY_JOBS_TABLE')
DUBBING_STATUS_TABLE = os.environ.get('DYNAMO_DUBBING_STATUS_TABLE')

# SQS queue name
SQS_QUEUE_NAME = os.environ.get('SQS_MERGE_AUDIO')




def send_merge_message(task_id):
    try:
        
        
        
        # Query Dubbing_polly_jobs table
        polly_jobs_table = dynamodb.Table(POLLY_JOBS_TABLE)
        response = polly_jobs_table.get_item(Key={'polly_job_id': task_id})
        
        if 'Item' not in response:
            raise Exception(f"No item found in {POLLY_JOBS_TABLE} for polly_job_id: {task_id}")
        
        dubbing_job_id = response['Item']['dubbing_job_id']
        
        # Query Dubbing_status table
        dubbing_status_table = dynamodb.Table(DUBBING_STATUS_TABLE)
        response = dubbing_status_table.get_item(Key={'dubbing_job_id': dubbing_job_id})
        
        if 'Item' not in response:
            raise Exception(f"No item found in {DUBBING_STATUS_TABLE} for dubbing_job_id: {dubbing_job_id}")
        
        video_file = response['Item']['video_file']
        
        # Prepare message for SQS
        message = {
            "dubbing_job_id": dubbing_job_id,
            "video_file": video_file
        }
        
        # Get SQS queue URL
        queue_url = sqs.get_queue_url(QueueName=SQS_QUEUE_NAME)['QueueUrl']
        
        # Send message to SQS
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message)
        )
        print(f'Message sent to SQS {SQS_QUEUE_NAME}')
        
        return {
            'statusCode': 200,
            'body': json.dumps('Message sent to SQS successfully')
        }
    
    except ClientError as e:
        print(f"AWS service error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }

def decrease_counter( partition_key, partition_key_value):
    
    table = dynamodb.Table(DUBBING_STATUS_TABLE)

    try:
        response = table.update_item(
            Key={
                partition_key: partition_key_value
            },
            UpdateExpression='SET #counter = #counter - :decrement',
            ExpressionAttributeNames={
                '#counter': 'chunks_counter'
            },
            ConditionExpression='#counter > :zero',
            ExpressionAttributeValues={
                ':zero': 0,
                ':decrement': 1
            },
            ReturnValues='UPDATED_NEW'
        )
        return response['Attributes']['chunks_counter']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print("Counter is already at 0 or below.")
        else:
            print(f"An error occurred[decrease_counter]: {e.response['Error']['Message']}")
        return None

def update_polly_job_status(polly_job_id,task_status,polly_output_object):
    
    table = dynamodb.Table(POLLY_JOBS_TABLE)

    try:
        
        response = table.update_item(
            Key={
                'polly_job_id': polly_job_id
            },
            UpdateExpression="SET #status = :status, #polly_output_object = :polly_output_object",
            ExpressionAttributeNames={
                "#status": "status",
                "#polly_output_object": "polly_output_object"
            },
            ExpressionAttributeValues={
                ":status": task_status,
                ":polly_output_object": polly_output_object
            },
            ReturnValues="ALL_NEW"
        )

        updated_item = response.get('Attributes', {})
        dubbing_job_id = updated_item.get('dubbing_job_id')
        
        return dubbing_job_id

    except ClientError as e:
        print(f"An error occurred[update_polly_job_status]: {e.response['Error']['Message']}")
        return None

def lambda_handler(event, context):

     message = json.loads(event['Records'][0]['Sns']['Message'])
     

     
     task_id = message['taskId']
   

    
     task_status = message['taskStatus']  
     task_id = message['taskId']
     polly_output_object = message['outputUri']

     dubbing_job_id = update_polly_job_status(task_id,task_status,polly_output_object)
     if dubbing_job_id:
        print(f"Updated successfully. Media ID: {dubbing_job_id}")
     else:
        print("Failed to update or retrieve Media ID")    


     partition_key = 'dubbing_job_id'
     partition_key_value = dubbing_job_id

     new_counter_value = decrease_counter( partition_key, partition_key_value)
     if new_counter_value is not None:
        print(f"Counter decreased. New value: {new_counter_value}")     

     
     if new_counter_value == 0:
         send_merge_message(task_id)
     

