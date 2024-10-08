import json
import boto3
from urllib.parse import urlparse
import json
import re
import uuid
import os
from botocore.config import Config

# import requests
transcribe_client = boto3.client("transcribe")
s3_client = boto3.client('s3')
sqs = boto3.client('sqs')
translate = boto3.client('translate')
polly = boto3.client('polly')

lambda_config = Config(
    read_timeout=900,  # Timeout for reading the response (in seconds)
    connect_timeout=5,  # Timeout for establishing connection (in seconds)
    retries={'max_attempts': 1}  # Disable retries for faster failure (optional)
)
lambda_client = boto3.client('lambda', config=lambda_config)

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
    
def convert_to_milliseconds(time_str):
    # Ensure the time_str is a float
    time_in_seconds = float(time_str)
    
    # Convert the time to milliseconds
    time_in_milliseconds = int(time_in_seconds * 1000)
    
    return time_in_milliseconds    

def get_speaker_label_in_time_range(json_data, start_time_ms, end_time_ms):
    segments = json_data['speaker_labels']['segments']
    
    for segment in segments:
        
        segment_start_time_ms = convert_to_milliseconds(segment['start_time'])
        segment_end_time_ms = convert_to_milliseconds(segment['end_time'])
        
        
        if start_time_ms>=segment_start_time_ms  and end_time_ms<=segment_end_time_ms :
            
            return segment['speaker_label']
    
    return None    
    
def parse_srt(srt_content,
              metadata_json,
              num_of_speakers,
              polly_voices,
              video_file):
    srt_pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\Z)', re.DOTALL)
    matches = srt_pattern.findall(srt_content)
    
    subtitles = []
    for match in matches:
        sequence = int(match[0])
        start_time = match[1]
        end_time = match[2]
        text = match[3].replace('\n', ' ').replace('"', '\\"')

        start_ms = srt_time_to_ms(start_time)
        end_ms = srt_time_to_ms(end_time)
        duration = calculate_duration(start_time, end_time)
        
        #speaker_id =get_speaker_label_in_time_range(metadata_json,start_ms,end_ms)\
        #if speaker_id is None:
        #    speaker_id='spk_0'
        
        speaker_id='spk_0'
         
        speaker_id_index = int(speaker_id[-1])
        
        voice_id=None
        
        try:
            voice_id = polly_voices[speaker_id_index]['Id']
        except IndexError:
            voice_id = polly_voices[0]['Id']
        
        subtitle = {
            "start_time": start_ms,
            "end_time": end_ms,
            "sequence": sequence,
            "duration": duration,
            "text": translate_text(text),
            "speaker": speaker_id,
            "voice_id":voice_id
        }
        
        subtitles.append(subtitle)


    payload = {
        "srt": subtitles,
        "num_of_speakers":num_of_speakers,
        "video_file":video_file
    }

    # Invoke Lambda A synchronously
    lambda_response = lambda_client.invoke(
        FunctionName='VideoDubbingIdentifyGender',  # Replace with the actual name of Lambda A
        InvocationType='RequestResponse',  # Synchronous invocation
        Payload=json.dumps(payload)
    )
    
    # Read the response from Lambda A
    response_payload = json.loads(lambda_response['Payload'].read().decode('utf-8'))
    
    
    data_json = json.loads(response_payload)

    # Extract the value of the "gender" key
    gender = data_json[0]["gender"]
    
    # Capitalize the first letter
    gender_capitalized = gender.capitalize()
    
    voice_name = next((item["Name"] for item in polly_voices if item["Gender"] == gender_capitalized), None)
    
    for item in subtitles:
      if "voice_id" in item:
        item["voice_id"] = voice_name
    
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

def send_to_sqs(subsitles,srt_file,uuid4,video_file,speakers):
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
        "speakers": speakers
        
    }
    # Convert the JSON object to a string
    message_body = json.dumps(json_object)
    #message_body = message_body.replace("\\'", "'")

    # Send the message to the SQS queue
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=message_body
    )

def parse_s3_url(s3_path):
    o = urlparse(s3_path, allow_fragments=False)
    s3WorkString =  o.path
    s3WorkString = s3WorkString[1:]
    
    s3WorkList = s3WorkString.split('/', 1)
    bucket = s3WorkList[0]
    bucketKey = s3WorkList[1]
    
    return bucket,bucketKey

def shrink_metadata_file(metadata_srt_content):
    data = json.loads(metadata_srt_content)

    # Extract the speaker_labels dictionary
    speaker_labels = data["results"]["speaker_labels"]
    
    # Remove the "items" arrays from the segments
    for segment in speaker_labels["segments"]:
        if "items" in segment:
            del segment["items"]
    
    # Create the new JSON with speaker_labels as the root element
    new_json = {"speaker_labels": speaker_labels}
    return new_json
    
def get_language_name(language_code):
   
    try:
        # Call the list_languages API
        response = translate.list_languages()

        # Search for the matching language code
        for language in response.get('Languages', []):
            if language['LanguageCode'] == language_code:
                return language['LanguageName']
        
        # If not found
        return f"Language name for code '{language_code}' not found"

    except Exception as e:
        return f"An error occurred: {str(e)}"
    
def lambda_handler(event, context):

    job_name = event['detail']['TranscriptionJobName']
    job = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
    video_file=job['TranscriptionJob']['Media']['MediaFileUri']
    
    
    
    mediaFile= job['TranscriptionJob']['Subtitles']['SubtitleFileUris'][0]
    metadata_data = job['TranscriptionJob']['Transcript']['TranscriptFileUri']
    
    # we need it to find voices in AWS Polly
    language_code = os.environ.get('AUDIO_LANGUAGE_TARGET')
    language_name = get_language_name(language_code)
    print(f"The language name for code '{language_code}' is: {language_name}")
    
    
    response = polly.describe_voices(
                Engine='standard'
                )
    
    

    # Extract elements where LanguageName is "Russian"
    polly_voices = [voice for voice in response["Voices"] if voice["LanguageName"] == language_name]


    #SRT file
    bucket,bucketKey =  parse_s3_url(mediaFile)
   

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
    
    
    #SRT metadata file
    bucket,bucketKey =  parse_s3_url(metadata_data)
    metadata_s3_object = s3_client.get_object(Bucket=bucket, Key=bucketKey)
    metadata_srt_content = metadata_s3_object['Body'].read().decode('utf-8')
    
    num_of_speakers =1 
    
    #new_json = shrink_metadata_file(metadata_srt_content)
    #num_of_speakers = new_json['speaker_labels']['speakers']
    #subtitles = parse_srt(srt_content,new_json,num_of_speakers,polly_voices,video_file)
    
    subtitles = parse_srt(srt_content,None,num_of_speakers,polly_voices,video_file)
    
    print(subtitles)

    send_to_sqs(subtitles, f"s3://{work_bucket}/{work_object}",uuid4,video_file,num_of_speakers)
    
    print(f"Message sent to SQS queue {os.environ.get('SQS_QUEUE_NAME')}")

   
