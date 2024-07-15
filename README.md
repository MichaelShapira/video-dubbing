
# Video Dubbing Pipeline with AWS AIML Services

Creating video dubbing is a time-consuming and expensive operation. We can automate it with an AI-ML service. Specifically with speech-to-text and text-to-speech. The following project provides the pipeline that starts with uploading the video asset and ends with the user getting an email with a link to the translated asset.
The solution is tightly decoupled and very flexible due to the extensive usage of queues and notifications.

## Declamer

This project is done for educational purposes. It can be used as a POC, but you should not consider it as production ready deployment.

## Sample Files

Source: [JeffDay1.mp4](https://github.com/MichaelShapira/video-dubbing/blob/main/JeffDay1.mp4)
Target (Russian Translation): [JeffDay1Translated.mp4](https://github.com/MichaelShapira/video-dubbing/blob/main/JeffDay1Translated.mp4)

## Architecture
![image](https://github.com/user-attachments/assets/559a711f-3bbe-436f-a185-bec45c7174e7)


## Architecture Explained

1. Upload your video asset to S3.
2. S3 Event invokes Lambda, which starts the transcription job.
3. When the transcription job ends, Amazon Transcribe sends the job-completed event to Amazon EvenBrigde.
4. Amazon Lambda is invoked by Amazoin Event-Bridge to convert the unstructured data from transcription data into JSON format and translate the text with Amazon Translate service.
5. The data is being placed into the Amazon Simple Queue Service (SQS) for further processing.
6. Another Lambda picks the message from the queue, stores metadata about the dubbing job in DynamoDB, and starts multiple text-to-speech jobs with Amazon Polly.
7. Each Polly job reports the completion of the job to the Amazon Simple Notification Service (SNS).
8. Amazon Lambda, which is subscribed to SNS, identifies that all polly jobs have been completed and updates the metadata in DynamoDB.
9. Once all polly jobs are completed, the message is put into another SQS queue for further processing.
10. Finally, all Polly job output files (MP3) are being merged into the original video asset by using the FFMPEG utility, and again, I used Amazon Lambda for this.
11. As the last step, I created a presigned url from the merged output, and this url was sent to the recipient that the user defined as part of the cdk deployment command.

## Prerequisites

You need to install AWS CDK following this [instructions](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) .

## Deployment
```
cdk deploy --parameters snstopicemailparam=YOUR_EMAIL@dummy.com
```
Note the "snstopicemailparam" parameter. This is the email address that you will get link with translated asset. The link is valid for 24 hours only.
 
Also note that before actually getting the email with the link, you will get another email that asks you to verify your email.

## Quick Start

All you have to do is upload your video file to the S3 bucket. The name of the bucket appears in the output of the deployment process.
<img width="1022" alt="image" src="https://github.com/user-attachments/assets/6bacdd42-d325-4674-917d-e31db9838e9e">

## Language Setup

By default, the dubbing is done from English to Russian.
You can control the language setup in the following way:
1. Change the configuration of the Lambda that starts the transcription job. (Set the language of original video asset) 
   <img width="939" alt="image" src="https://github.com/user-attachments/assets/c7b3a673-3dfa-42ed-bbc7-cb7a407e94ae">

The name of the Lambda appears in the output of the deployment process.
  
   <img width="854" alt="image" src="https://github.com/user-attachments/assets/5f25bf6c-9fa5-4fbb-a901-dd243e9f2b53">

   Supported Languages: check [here](https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html).

2. Set the language to which to translate the transcription text. Transciption processing Lambda is responsible for setting the language of the text to translate.
   You need to provide both the source and the target languages.

   ![image](https://github.com/user-attachments/assets/441cdbb3-ed37-45e7-83fc-0e240543ca00)

   
The name of the Lambda appears in the output of the deployment process

   ![image](https://github.com/user-attachments/assets/9c47625c-f66f-43e6-a562-535431710fc5)

Supported languages for Amazon Translate: check [here](https://docs.aws.amazon.com/translate/latest/dg/what-is-languages.html).
   

3. Change the configuration of Lambda that converts text-to-speech by using Amazon Polly

   <img width="824" alt="image" src="https://github.com/user-attachments/assets/81819e1d-d79c-4503-a5a5-ba2f11b61c96">

The name of the Lambda appears in the output of the deployment process.

<img width="1140" alt="image" src="https://github.com/user-attachments/assets/ba86fc1c-f917-482e-a21e-337f45a1b2e2">

   Supported languages and voices: check [here](https://docs.aws.amazon.com/polly/latest/dg/supported-languages.html).


   


   



## Current State of the project

Currently, only single speaker is supported. I plan to expand it to two speakers and also assign male voices to male actors and female voices to female actors. 

Also, the current process is not optimized. I do plan to optimize the performance. Specifically, since I use AWS Lambda, which is limited to 15 minutes of runtime, long videos will be translated only partially. This is not due to the limitations of the technology, but rather because of the Lambda timeout. Running the same process on EC2 or EKS/ECS will not have these limitations.
