
# Video Dubbing Pipeline with AWS AIML Services

Creating video dubbing is a time-consuming and expensive operation. We can automate it with an AI-ML service. Specifically with speech-to-text and text-to-speech. The following project provides the pipeline that starts with uploading the video asset and ends with the user getting an email with a link to the translated asset.
The solution is tightly decoupled and very flexible due to the extensive usage of queues and notifications.

## Declamer

This project is done for educational purposes. It can be used as a POC, but you should not consider it as production ready deployment.

## Architecture
<img width="1112" alt="image" src="https://github.com/MichaelShapira/video-dubbing/assets/135519473/14853229-38aa-4911-912b-ef3559b40694">

## Architecture Explained

1. Upload your video asset to S3.
2. S3 Event invokes Lambda, which starts the transcription job.
3. When the transcription job ends, Amazon Transcribe sends the job-completed event to Amazon EvenBrigde.
4. Amazon Lambda is invoked by Amazoin Event-Bridge to convert the unstructured data from transcription data into JSON format.
5. The data is being placed into the Amazon Simple Queue Service (SQS) for further processing.
6. Another Lambda picks the message from the queue, stores metadata about the dubbing job in DynamoDB, and starts multiple text-to-speech jobs with Amazon Polly.
7. Each Polly job reports the completion of the job to the Amazon Simple Notification Service (SNS).
8. Amazon Lambda, which is subscribed to SNS, identifies that all polly jobs have been completed and updates the metadata in DynamoDB.
9. Once all polly jobs are completed, the message is put into another SQS queue for further processing.
10. Finally, all Polly job output files (MP3) are being merged into the original video asset by using the FFMPEG utility, and again, I used Amazon Lambda for this.
11. As the last step, I created a presigned url from the merged output, and this url was sent to the recipient that the user defined as part of the cdk deployment command.

## Prerequisites

You need to install AWS CDK following this instructions https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html.

## Deployment
```
cdk deploy --parameters snstopicemailparam=YOUR_EMAIL@dummy.com
```
Note the "snstopicemailparam" parameter. This is the email address that you will get link with translated asset. The link is valid for 24 hours only.
 
Also note that before actually getting the email with the link, you will get another email that asks you to verify your email.

## Quick Start

All you have to do is upload your video file to the S3 bucket. The name of the bucket appears in the output of the deployment process.
<img width="1022" alt="image" src="https://github.com/user-attachments/assets/6bacdd42-d325-4674-917d-e31db9838e9e">


## Current State of the project

Currently, only single speaker is supported. I plan to expand it to two speakers and also assign male voices to male actors and female voices to female actors. 

Also, the current process is not optimized. I do plan to optimize the performance. Specifically, since I use AWS Lambda, which is limited to 15 minutes of runtime, long videos will be translated only partially. This is not due to the limitations of the technology, but rather because of the Lambda timeout. Running the same process on EC2 or EKS/ECS will not have these limitations.
