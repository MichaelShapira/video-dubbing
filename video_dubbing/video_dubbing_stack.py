from aws_cdk import (
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
    aws_sqs as sqs,
    CfnOutput,
    CfnParameter,
    aws_dynamodb as dynamo,
    aws_s3_notifications,
    aws_sns_subscriptions as subscriptions,
    aws_sns as sns,
    aws_events as events,
    aws_events_targets as targets,
    Stack,
    aws_lambda_event_sources as lambda_event_source
)
from constructs import Construct
import uuid
import subprocess
import aws_cdk as cdk
from aws_cdk.aws_iam import PolicyStatement

class VideoDubbingStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        
        
        transcribeLambdaRole = iam.Role(self, "TranscribeForDubbingLambdaRole",
                     assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
                                    )
        transcribeLambdaRole.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))
 
        functionAudionToText = _lambda.Function(self, "lambda_function",
                                    runtime=_lambda.Runtime.PYTHON_3_11,
                                    handler="video-dubbing-start-transcribe.lambda_handler",
                                    code=_lambda.Code.from_asset("./lambda/transcribe"),
                                    timeout=cdk.Duration.seconds(30),
                                    memory_size=256,
                                    environment={ # ADD THIS, FILL IT FOR ACTUAL VALUE 
                                                "AUDIO_LANGUAGE": "en-US"
                                            },
                                    role = transcribeLambdaRole
                                    )
        #Bucket to upload the video file
        sourceBucket = s3.Bucket(self, "VideoDubbingFilesSource", 
                                 versioned=False,
                                 removal_policy=RemovalPolicy.DESTROY,
                                 auto_delete_objects=True)
        
        
        #Staging bucket
        stagingBucket = s3.Bucket(self, "VideoDubbingStaging", 
                                 versioned=False,
                                 removal_policy=RemovalPolicy.DESTROY,
                                 auto_delete_objects=True)
        

        transcribeLambdaRole.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=["*"],
                actions=["transcribe:StartTranscriptionJob"]
                
            ))

        transcribeLambdaRole.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=[sourceBucket.bucket_arn+"/*"],
                actions=["s3:PutObject","s3:GetObject"]
                
            ))   

        # create s3 notification for lambda function
        notification = aws_s3_notifications.LambdaDestination(functionAudionToText)

        # assign notification for the s3 event type (ex: OBJECT_CREATED)
        sourceBucket.add_event_notification(s3.EventType.OBJECT_CREATED, notification)    

        table = dynamo.TableV2(self, "VideoDubbungStatus",
              partition_key=dynamo.Attribute(name="dubbing_job_id", type=dynamo.AttributeType.STRING),
              removal_policy= RemovalPolicy.DESTROY,
              
        )

        table_polly_job = dynamo.TableV2(self, "VideoDubbungPollyJobStatus",
              partition_key=dynamo.Attribute(name="polly_job_id", type=dynamo.AttributeType.STRING),
              removal_policy= RemovalPolicy.DESTROY,
              
        )
        dynamo_polly_job_index_name = 'dubbing_job_id_index'

        table_polly_job.add_global_secondary_index(
            index_name= dynamo_polly_job_index_name,
            partition_key= dynamo.Attribute(name="dubbing_job_id", type=dynamo.AttributeType.STRING)
        )
        

        transcribe_event = events.Rule(self, 'VideoDubbingTranscribeEvent',
                                           description='Completed Transcription Jobs',
                                           event_pattern=events.EventPattern(source=["aws.transcribe"],
                                                                             detail={
                                                                                 "TranscriptionJobStatus": ["COMPLETED"]
                                                                             }  
                               ))
        # Permissions for processTransactionResultLambda
        processTransactionResultLambdaRole = iam.Role(self, "SummarizeLambdaRole",
                     assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        processTransactionResultLambdaRole.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))

        s3CopySourcePolicy = iam.Policy(self, "S3CopySourcePolicy")  
        s3CopySourcePolicy.add_statements(PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:GetObject","s3:ListBucket"],
            resources=[sourceBucket.bucket_arn,sourceBucket.bucket_arn+"/*"]
        )) 
        processTransactionResultLambdaRole.attach_inline_policy(s3CopySourcePolicy)

        s3CopyTargetPolicy = iam.Policy(self, "S3CopyTargetPolicy")  
        s3CopyTargetPolicy.add_statements(PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:PutObject","s3:GetObject"],
            resources=[stagingBucket.bucket_arn,stagingBucket.bucket_arn+"/*"]
        )) 
        processTransactionResultLambdaRole.attach_inline_policy(s3CopyTargetPolicy)

        translateTextPolicy = iam.Policy(self, "TranslateTextPolicy")  
        translateTextPolicy.add_statements(PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["translate:TranslateText","translate:ListLanguages"],
            resources=["*"]
        )) 
        processTransactionResultLambdaRole.attach_inline_policy(translateTextPolicy)

        
        #End Permissions for processTransactionResultLambda

        
        dlq = sqs.Queue(self, "VideoDubbingDLQ",
            visibility_timeout=Duration.seconds(900)
        )

     
        queue = sqs.Queue(self, "SrtToPolly",
                visibility_timeout=Duration.seconds(120),
                receive_message_wait_time=Duration.seconds(20),
                dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,  # Number of retries before sending the message to the DLQ
                queue=dlq
            )
            )

        sqsPutMessagePolicy = iam.Policy(self, "SqsPutMessagePolicy")  
        sqsPutMessagePolicy.add_statements(PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["sqs:SendMessage","sqs:GetQueueUrl"],
            resources=[queue.queue_arn]
        )) 
        processTransactionResultLambdaRole.attach_inline_policy(sqsPutMessagePolicy)

        getTranscribeJobPolicy = iam.Policy(self, "getTranscribeJobPolicy")  
        getTranscribeJobPolicy.add_statements(PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["transcribe:GetTranscriptionJob"],
            resources=["*"]
        )) 
        processTransactionResultLambdaRole.attach_inline_policy(getTranscribeJobPolicy)
    
     
                                                                   
        # Lambda that is called when EventBridge identifies that Transcribe Job is over
        processTransactionResultLambda = _lambda.Function(self, "VideoDubbingTranscribeEventCompleted",
                                    runtime=_lambda.Runtime.PYTHON_3_11,
                                    handler="process-transcribe-result.lambda_handler",
                                    code=_lambda.Code.from_asset("./lambda/transcribe"),
                                    timeout=cdk.Duration.seconds(60),
                                    memory_size=512,
                                    role = processTransactionResultLambdaRole,
                                    environment={  
                                                "AUDIO_LANGUAGE_SOURCE": "en",
                                                "AUDIO_LANGUAGE_TARGET": "ru",
                                                "SQS_QUEUE_NAME": queue.queue_name,
                                                "STAGING_BUCKET_NAME": stagingBucket.bucket_name
                                            },
                                    )
        transcribe_event.add_target(targets.LambdaFunction(handler=processTransactionResultLambda)) 

        sns_topic = sns.Topic(self, "VideoDubbingPollyJobs")

        convertSubtitlesToPollyLambdaRole = iam.Role(self, "ConvertSubtitlesToPollyLambdaRole",
                     assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        convertSubtitlesToPollyLambdaRole.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))


        sqsPutMessagePolicy = iam.Policy(self, "SqsGetMessagePolicy")  
        sqsPutMessagePolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["sqs:SendMessage","sqs:GetQueueUrl","sqs:DeleteMessage"],
                    resources=[queue.queue_arn]
                )) 
        convertSubtitlesToPollyLambdaRole.attach_inline_policy(sqsPutMessagePolicy)

        pollyStartSpeechSynthesisTaskPolicy = iam.Policy(self, "PollyStartSpeechSynthesisTaskPolicy") 
        pollyStartSpeechSynthesisTaskPolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["polly:StartSpeechSynthesisTask"],
                    resources=["*"]
                )) 
        convertSubtitlesToPollyLambdaRole.attach_inline_policy(pollyStartSpeechSynthesisTaskPolicy)

        dynamoPutItemPolicy = iam.Policy(self, "DynamoPutItemPolicy") 
        dynamoPutItemPolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["dynamodb:PutItem"],
                    resources=[table.table_arn,table_polly_job.table_arn]
                )) 
        convertSubtitlesToPollyLambdaRole.attach_inline_policy(dynamoPutItemPolicy)


        snsPollyJobNotificationPolict = iam.Policy(self, "SnsPollyJobNotificationPolicy") 
        snsPollyJobNotificationPolict.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["sns:Publish"],
                    resources=[sns_topic.topic_arn]
                )) 
        convertSubtitlesToPollyLambdaRole.attach_inline_policy(snsPollyJobNotificationPolict)
        convertSubtitlesToPollyLambdaRole.attach_inline_policy(s3CopyTargetPolicy)

        # Lambda that is called when EventBridge identifies that Transcribe Job is over
        convertSubtitlesToPollyLambda = _lambda.Function(self, "VideoDubbingConvertSubsToPolly",
                                    runtime=_lambda.Runtime.PYTHON_3_11,
                                    handler="srt-to-polly.lambda_handler",
                                    code=_lambda.Code.from_asset("./lambda/polly"),
                                    timeout=cdk.Duration.seconds(60),
                                    memory_size=512,
                                    role = convertSubtitlesToPollyLambdaRole,
                                    environment={  
                                                "DYNAMO_DUBBING_STATUS_TABLE": table.table_name,
                                                "DYNAMO_POLLY_JOBS_TABLE": table_polly_job.table_name,
                                                "STAGING_BUCKET_NAME": stagingBucket.bucket_name,
                                                "POLLY_LANGUAGE_CODE": "ru-RU",
                                                "POLLY_VOICE_ID": "Tatyana",
                                                "POLLY_JOBS_SNS_ARN":sns_topic.topic_arn
                                            },
                                    )


        #Create an SQS event source for Lambda
        sqs_event_source = lambda_event_source.SqsEventSource(queue)

        #Add SQS event source to the Lambda function
        convertSubtitlesToPollyLambda.add_event_source(sqs_event_source)                              
  
        queueMergeAudio = sqs.Queue(self, "MergeAudio",
                visibility_timeout=Duration.seconds(950),
                receive_message_wait_time=Duration.seconds(20),
                dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,  # Number of retries before sending the message to the DLQ
                queue=dlq
            )
            )

        polyJobCompletedRole = iam.Role(self, "PolyJobCompletedRole",
                     assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        polyJobCompletedRole.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))

        dynamoPutGetItemPolicy = iam.Policy(self, "DynamoPutGetItemPolicy") 
        dynamoPutGetItemPolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["dynamodb:PutItem","dynamodb:GetItem","dynamodb:UpdateItem"],
                    resources=[table.table_arn,table_polly_job.table_arn]
                )) 
        polyJobCompletedRole.attach_inline_policy(dynamoPutGetItemPolicy)

        snsPollyJobNotificationPolicy = iam.Policy(self, "SnsPollyJobCompletedNotificationPolicy") 
        snsPollyJobNotificationPolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["sns:Receive","sns:GetTopicAttributes"],
                    resources=[sns_topic.topic_arn]
                )) 

        polyJobCompletedRole.attach_inline_policy(snsPollyJobNotificationPolicy)   

        sqsSendMessagePolicy = iam.Policy(self, "SqsSendMessagePolicy")  
        sqsPutMessagePolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["sqs:SendMessage","sqs:GetQueueUrl"],
                    resources=[queueMergeAudio.queue_arn]
                ))  

        polyJobCompletedRole.attach_inline_policy(sqsPutMessagePolicy)              

        # Lambda that is called when Amazon Polly job completed
        polyJobCompletedLambda = _lambda.Function(self, "PolyJobCompletedLambda",
                                    runtime=_lambda.Runtime.PYTHON_3_11,
                                    handler="process-polly-task-result.lambda_handler",
                                    code=_lambda.Code.from_asset("./lambda/polly"),
                                    timeout=cdk.Duration.seconds(60),
                                    memory_size=128,
                                    role = polyJobCompletedRole,
                                    environment={  
                                                "DYNAMO_DUBBING_STATUS_TABLE": table.table_name,
                                                "DYNAMO_POLLY_JOBS_TABLE": table_polly_job.table_name,
                                                "SQS_MERGE_AUDIO": queueMergeAudio.queue_name
                                            }
                                    )


        sns_topic.add_subscription(subscriptions.LambdaSubscription(polyJobCompletedLambda) )     

        sns_email_topic = sns.Topic(self, "VideoDubbingEmail")    
        email_address = CfnParameter(self, "sns-topic-email-param")

        sns_email_topic.add_subscription(subscriptions.EmailSubscription(email_address.value_as_string))    

        ffmpeg_layer = _lambda.LayerVersion(self, "FFmpegLayer",
                    code=_lambda.Code.from_asset("./lambda/ffmpeg/bin"),
                    compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
                    description="FFmpeg binary layer"
                    )


        mergeAudioRole = iam.Role(self, "MergeAudioRole",
                     assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        mergeAudioRole.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))
        # read mp3 and put merged content
        mergeAudioRole.attach_inline_policy(s3CopyTargetPolicy)


        sqsGetDeleteMessagePolicy = iam.Policy(self, "SqsGetDeleteMessagePolicy")  
        sqsGetDeleteMessagePolicy.add_statements(PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["sqs:GetQueueUrl","sqs:DeleteMessage"],
                            resources=[queue.queue_arn]
                        ))   
        mergeAudioRole.attach_inline_policy(sqsGetDeleteMessagePolicy)                

        dynamoGetItemPolicy = iam.Policy(self, "DynamoGetItemPolicy") 
        dynamoGetItemPolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["dynamodb:GetItem","dynamodb:Query"],
                    resources=[table.table_arn,table_polly_job.table_arn]
                )) 
        mergeAudioRole.attach_inline_policy(dynamoGetItemPolicy)


        dynamoQueryIndexItemPolicy = iam.Policy(self, "DynamoQueryIndexPolicy") 
        dynamoQueryIndexItemPolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["dynamodb:Query"],
                    resources=[table_polly_job.table_arn+f"/index/{dynamo_polly_job_index_name}"]
                )) 
        mergeAudioRole.attach_inline_policy(dynamoQueryIndexItemPolicy)


        snsEmailNotificationPolicy = iam.Policy(self, "SnsEmailNotificationPolicy") 
        snsEmailNotificationPolicy.add_statements(PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["sns:Publish"],
                    resources=[sns_email_topic.topic_arn]
                ))
        mergeAudioRole.attach_inline_policy(snsEmailNotificationPolicy)   

        s3GetSourceAssetPolicy = iam.Policy(self, "S3GetSourceAssetPolicy")  
        s3GetSourceAssetPolicy.add_statements(PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:GetObject"],
            resources=[sourceBucket.bucket_arn,sourceBucket.bucket_arn+"/*"]
        ))     
        mergeAudioRole.attach_inline_policy(s3GetSourceAssetPolicy) 

        # Lambda that is called when Amazon Polly job completed
        mergeAudioLambda = _lambda.Function(self, "MergeAudioLambda",
                                    runtime=_lambda.Runtime.PYTHON_3_11,
                                    handler="merge-audio.lambda_handler",
                                    code=_lambda.Code.from_asset("./lambda/ffmpeg"),
                                    timeout=cdk.Duration.seconds(900),
                                    memory_size=1024,
                                    role = mergeAudioRole,
                                    environment={  
                                                "DYNAMO_DUBBING_STATUS_TABLE": table.table_name,
                                                "DYNAMO_POLLY_JOBS_TABLE": table_polly_job.table_name,
                                                "DYNAMO_POLLY_JOBS_INDEX": dynamo_polly_job_index_name,
                                                "SNS_EMAIL_TOPIC": sns_email_topic.topic_arn,
                                                "FFMPEG_PATH": '/var/task/bin/ffmpeg',
                                                "EMAIL_ADDRESS": email_address.value_as_string
                                            },
                                     layers=[ffmpeg_layer]          
                                    ) 
       

        #Create an SQS event source for Lambda
        sqs_event_source = lambda_event_source.SqsEventSource(queueMergeAudio)

        #Add SQS event source to the Lambda function
        mergeAudioLambda.add_event_source(sqs_event_source)   

        CfnOutput(self, "Upload Audio File To This S3 bucket", value=sourceBucket.bucket_name)
        CfnOutput(self, "Staging files located here", value=stagingBucket.bucket_name)
        CfnOutput(self, "Start Transcribe Job Lambda", value=functionAudionToText.function_name)
        CfnOutput(self, "Polly Job Lambda", value=convertSubtitlesToPollyLambda.function_name)
        CfnOutput(self, "Process Transcribe Job Result Lambda", value=processTransactionResultLambda.function_name)
                                                                   
