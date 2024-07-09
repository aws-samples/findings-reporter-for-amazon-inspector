import boto3
import json
import os

inspector2_client = boto3.client('inspector2')


def lambda_handler(event, context):
    # Call Inspector API to list findings

    report_bucket = os.getenv('BUCKET_NAME')
    inspector_report_cmk = os.getenv('KMS_KEY')
    response = inspector2_client.create_findings_report(
        reportFormat='CSV',
        s3Destination={
            'bucketName': report_bucket,
            'kmsKeyArn': inspector_report_cmk
        }
    )

    # Return report as JSON
    return {
        'statusCode': 200,
        'body': json.dumps(response)
    }
