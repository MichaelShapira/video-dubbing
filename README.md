
# Video Dubbing Pipeline with AWS AIML Services

## Declamer

This project is done for educational purposes. It can be used as a POC, but you should not consider it as production ready deployment.

## Architecture
<img width="1112" alt="image" src="https://github.com/MichaelShapira/video-dubbing/assets/135519473/14853229-38aa-4911-912b-ef3559b40694">

## Prerequisites

You need to install AWS CDK following this instructions https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html.

## Deployment
```
cdk deploy CallCenterPyStack -f  --parameters snstopicemailparam=YOUR_EMAIL@dummy.com
```
Note the "snstopicemailparam" parameter. This is the email address that you will get link with translated asset. The link is valid for 24 hours only.
 
Also note that before actually getting the email with the link, you will get another email that asks you to verify your email.
