import aws_cdk as core
import aws_cdk.assertions as assertions

from amazon_inspector_findings_reporter_cdk.amazon_inspector_findings_reporter_cdk_stack import AmazonInspectorFindingsReporterCdkStack

# example tests. To run these tests, uncomment this file along with the example
# resource in amazon_inspector_findings_reporter_cdk/amazon_inspector_findings_reporter_cdk_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AmazonInspectorFindingsReporterCdkStack(app, "amazon-inspector-findings-reporter-cdk")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
