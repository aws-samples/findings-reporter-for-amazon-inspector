import json
# Core constructs
from aws_cdk import Stack
from constructs import Construct

# AWS services
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_iam as iam
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_events as events
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk import aws_kms as kms


class InspectorFindingsReportStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create S3 bucket to store the report
        inspector_report_bucket = s3.Bucket(
            self, "InspectorReportBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL
        )
        # Define the service principal for Amazon Inspector2
        inspector_principal = iam.ServicePrincipal("inspector2.amazonaws.com")

        # Create a policy statement that allows 's3:PutObject' action from Inspector v2
        bucket_policy_statement = iam.PolicyStatement(
            actions=["s3:PutObject",
                     "s3:PutObjectAcl",
                     "s3:AbortMultipartUpload"],
            resources=[inspector_report_bucket.bucket_arn + "/*"],  # Grant access to the objects in the bucket
            principals=[inspector_principal]
        )

        # Attach the policy statement to the bucket
        inspector_report_bucket.add_to_resource_policy(bucket_policy_statement)

        # Get the account ID of the current account
        account_root_principal = iam.AccountRootPrincipal()

        # Create a KMS key used for Inspector report encryption
        inspector_report_cmk = kms.Key(self, "InspectorReportCmk",
                                       policy=iam.PolicyDocument(
                                           statements=[
                                               iam.PolicyStatement(
                                                   actions=["kms:*"],
                                                   principals=[iam.AccountRootPrincipal()],
                                                   resources=["*"],
                                               )
                                           ]
                                       ))

        # Define the Amazon Inspector service principal
        inspector_principal = iam.ServicePrincipal("inspector2.amazonaws.com")

        # Grant Amazon Inspector permissions to use the key
        inspector_report_cmk.grant_encrypt_decrypt(inspector_principal)

        # Create an IAM role for Lambda
        lambda_role = iam.Role(
            self, "InspectorLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonInspector2FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSNSFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSESFullAccess")
            ])

        inspector_report_cmk.grant_encrypt_decrypt(lambda_role)

        # Environment Variables initializations:
        TOPIC_ARN = ""
        SES_SENDER = ""
        SES_RECIPIENTS = ""

        notification_system = self.node.try_get_context('notificationSystem')
        if notification_system == 'SES':
            SES_SENDER = self.node.try_get_context('ses_sender')
            print(SES_SENDER)
            SES_RECIPIENTS = self.node.try_get_context('ses_receivers')
            print(SES_RECIPIENTS)
        elif notification_system == 'SNS':
            subscribed_emails = self.node.try_get_context('sns_subscribed_emails')
            # Create SNS topic to send the report
            inspector_report_topic = sns.Topic(self, "InspectorReportTopic")
            TOPIC_ARN = inspector_report_topic.topic_arn
            # Create SNS subscriptions to send the report
            for subscribed_email in subscribed_emails:
                inspector_report_topic.add_subscription(subscriptions.EmailSubscription(subscribed_email))
        else:
            print("please specify proper notification_system in cdk.json")

        # Create Lambda function to send the report

        inspector_report_generator_lambda = _lambda.Function(
            self, "InspectorReportFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="report_generator.lambda_handler",
            code=_lambda.Code.from_asset("./lambda/report_generator/"),
            environment={
                "BUCKET_NAME": inspector_report_bucket.bucket_name,
                "KMS_KEY": inspector_report_cmk.key_arn
            },
            role=lambda_role
        )

        report_sender_lambda = _lambda.Function(
            self, "ReportSenderFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="report_sender.lambda_handler",
            code=_lambda.Code.from_asset("./lambda/report_sender/"),
            environment={
                "TOPIC_ARN": TOPIC_ARN,
                "SES_SENDER": SES_SENDER,
                "SES_RECIPIENTS": json.dumps(SES_RECIPIENTS)
            },
            role=lambda_role
        )

        # Grant the Lambda function permissions to the bucket and the topic
        inspector_report_bucket.grant_read_write(inspector_report_generator_lambda)
        inspector_report_bucket.grant_put(inspector_report_generator_lambda)

        # Add an S3 event notification to trigger the Lambda function
        inspector_report_bucket.add_event_notification(s3.EventType.OBJECT_CREATED,
                                                       s3n.LambdaDestination(report_sender_lambda))

        # create an event bridge rule to trigger the lambda every 24 hours
        rule = events.Rule(
            self,
            "Rules",
            schedule=events.Schedule.cron(
                minute="05",
                hour="00",
                day="*",
                month="*",
                year="*")
        )

        # Add the Lambda function as a target
        rule.add_target(targets.LambdaFunction(inspector_report_generator_lambda))
