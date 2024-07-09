import json
from botocore.exceptions import ClientError
import boto3
from botocore.client import Config
import os


def lambda_handler(event, context):
    sns_topic_arn = os.getenv('TOPIC_ARN')
    ses_sender = os.getenv('SES_SENDER')
    ses_recipients = os.getenv('SES_RECIPIENTS')

    s3_info = event['Records'][0]['s3']
    bucket_name = s3_info["bucket"]["name"]
    object_name = s3_info['object']["key"]
    email_subject = "Your Inspector Report is ready for Download"
    presigned_url = generate_presigned_url(
        bucket_name,
        object_name,
        expiration=3600)
    print(presigned_url)
    if ses_sender:
        send_presigned_url_via_ses(ses_sender, ses_recipients, presigned_url, email_subject)
    if sns_topic_arn:
        send_presigned_url_via_sns(sns_topic_arn, presigned_url, email_subject)

def generate_presigned_url(bucket_name, object_name, expiration):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """
    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))

    Params = {'Bucket': bucket_name, 'Key': object_name}
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params=Params,
            ExpiresIn=expiration)
    except ClientError as e:
        print(e)
        return None

    # The response contains the presigned URL
    return response


def send_presigned_url_via_sns(sns_topic_arn, presigned_url, subject):
    """Send an email with a pre-signed URL using Amazon SNS

    :param sns_topic_arn: string, The ARN of the SNS topic you're publishing to
    :param presigned_url: string, The pre-signed URL to be sent via email
    :param subject: string, The subject line of the email
    """
    sns_client = boto3.client('sns')

    # Construct the message that will be sent via email
    #  message = f'Hello,\n\nHere is your pre-signed URL to access the Amazon Inspector Findings Report: \n\n {presigned_url} \n\nBest regards.'
    # Create your message for email in HTML format
    html_email_content = f"""<html>
    <head></head>
    <body>
    <p>Here is your file:</p>
    <p>{presigned_url}</p>
    </body>
    </html>"""

    # Construct the JSON message
    message = {
        'default': 'Your Amazon Inspector findings report is ready for download. Please visit the following link: ' + presigned_url,
        'email': 'Your Amazon Inspector findings report is ready for download. \n \n' +
                 'Please copy (not click on) the entire URL and visit it in your browser: \n\n ' + presigned_url,
        'email-json': json.dumps({'html': html_email_content})
    }

    # Convert the message dictionary to a JSON string
    message_json = json.dumps(message)

    # Publish the message to the SNS topic
    try:
        response = sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=message_json,
            Subject=subject,
            MessageStructure='json'
        )
        print(f'Message sent! Message ID: {response["MessageId"]}')
    except Exception as e:
        print(f'Failed to send message: {e}')


def send_presigned_url_via_ses(sender_email, recipients, presigned_url, subject):
    """Generate a presigned URL to share an S3 object

        :param sender_email: string, Your verified sender email address
        :param recipients: list, The recipient email addresses
        :param presigned_url: Time in seconds for the presigned URL to remain valid
        :param subject: string, The subject line for the email
    """

    # Create a new SES resource instance
    ses_client = boto3.client('ses')  # Ensure you use the correct region

    # The recipient email address
    recipient_emails = json.loads(recipients)

    # HTML body with the presigned URL as a hyperlink
    html_body = f"""<html>
    <head></head>
    <body>
    <p>Your Amazon Inspector Findings Report is ready. Please click on the link below to download</p>
    <p>Here is your file:</p>
    <a href="{presigned_url}">Download File</a>
    <p>\n\n If above hyper link cannot be opened, please copy and paste the following URL into your browser and download the report:</p>
    <p>{presigned_url}</p>
    </body>
    </html>"""

    # The email body for recipients with non-HTML email clients
    text_body = f"Here is your file: {presigned_url}"

    try:
        # Provide the contents of the email
        response = ses_client.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': recipient_emails
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        print(f"Email sent! Message ID: {response['MessageId']}")
    except Exception as e:
        print(f"Failed to send email: {e}")
