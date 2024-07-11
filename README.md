
# Video Dubbing Pipeline with AWS AIML Services

Creating video dubbing is a time-consuming and expensive operation. We can automate it with an AI-ML service. Specifically with speech-to-text and text-to-speech. The following project provides the pipeline that starts with uploading the video asset and ends with the user getting an email with a link to the translated asset.

## Declamer

This project is done for educational purposes. It can be used as a POC, but you should not consider it as production ready deployment.

## Architecture
<img width="1112" alt="image" src="https://github.com/MichaelShapira/video-dubbing/assets/135519473/14853229-38aa-4911-912b-ef3559b40694">

## Prerequisites

You need to install AWS CDK following this instructions https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html.

## Deployment
```
cdk deploy --parameters snstopicemailparam=YOUR_EMAIL@dummy.com
```
Note the "snstopicemailparam" parameter. This is the email address that you will get link with translated asset. The link is valid for 24 hours only.
 
Also note that before actually getting the email with the link, you will get another email that asks you to verify your email.

## Current State of the project

Currently, only single speakers are supported. I plan to expand it to two speakers and also assign male voices to male actors and female voices to female actors. 

Also, the current process is not optimized. I do plan to optimize the performance. Specifically, since I use AWS Lambda, which is limited to 15 minutes of runtime, long videos will be translated only partially. This is not due to the limitations of the technology, but rather because of the Lambda timeout. Running the same process on EC2 or EKS/ECS will not have these limitations.
