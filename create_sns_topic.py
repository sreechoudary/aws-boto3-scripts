import boto3
print(boto3.__version__)
session = boto3.Session(profile_name='default')
sns = session.resource('sns', region_name='us-east-1')

topic_arn = sns.create_topic(Name='demotopic').arn
response = sns.subscribe(TopicArn=sns_topic_arn, Protocol='email', Endpoint='sree.muppavarapu@gmail.com')

print(response)