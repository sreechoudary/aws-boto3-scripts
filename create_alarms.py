import boto3
from collections import defaultdict
from botocore.config import Config
regions = [
    'ca-central-1',
    'ap-southeast-2',
    'eu-central-1',
    'us-east-1',
    'us-east-2',
    'us-west-1',
    'us-west-2'
]
session = boto3.Session(profile_name='default')
for region in regions:
    print('Processing region : ' + region)
    ec2 = session.resource('ec2', region)
    cloudwatch = session.client('cloudwatch', region)
    sns = session.resource('sns', region)
    sns_topic_arn = sns.create_topic(Name='Systems-Monitor').arn
    #response = sns.subscribe(TopicArn=sns_topic_arn, Protocol='email', Endpoint='sree.muppavarapu@gmail.com')
    running_instances = ec2.instances.filter(Filters=[{
        'Name': 'instance-state-name',
        'Values': ['running']
    }])

    paginator = cloudwatch.get_paginator('list_metrics')
    
    ec2info = defaultdict()
    for instance in running_instances:
        for tag in instance.tags:
            if 'Name'in tag['Key']:
                name = tag['Value']
        print('Id: ' + instance.id)
        cloudwatch.put_metric_alarm(
            AlarmName='%s_CPU_Utilization' % name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=1,
            MetricName='CPUUtilization',
            Namespace='AWS/EC2',
            Period=60,
            Statistic='Average',
            Threshold=70.0,
            ActionsEnabled=True,
            AlarmActions=[sns_topic_arn],
            AlarmDescription='Alarm when server CPU exceeds 70%',
            Dimensions=[
                {
                'Name': 'InstanceId',
                'Value': instance.id
                },
            ]
        )
        cloudwatch.put_metric_alarm(
            AlarmName='%s_Memory_Utilization' % name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=1,
            MetricName='mem_used_percent',
            Namespace='CWAgent',
            Period=60,
            Statistic='Average',
            Threshold=80.0,
            ActionsEnabled=True,
            AlarmActions=[sns_topic_arn],
            AlarmDescription='Alarm when server RAM exceeds 80%',
            Dimensions=[
                {
                'Name': 'InstanceId',
                'Value': instance.id
                },
                {
                'Name': 'ImageId',
                'Value': instance.image_id
                },
                {
                'Name': 'InstanceType',
                'Value': instance.instance_type
                }
            ]
        )
        for response in paginator.paginate(Dimensions=[{'Name': 'InstanceId', 'Value': instance.id},{'Name': 'fstype','Value': 'ext4'}],
                                    MetricName='disk_used_percent',
                                    Namespace='CWAgent'):
            for metrics in response['Metrics']:
                cloudwatch.put_metric_alarm(
                    AlarmName='%s_Disk_Utilization_%s' % (name, metrics['Dimensions'][0]['Value']),
                    ComparisonOperator='GreaterThanThreshold',
                    EvaluationPeriods=1,
                    MetricName='disk_used_percent',
                    Namespace='CWAgent',
                    Period=60,
                    Statistic='Average',
                    Threshold=80.0,
                    ActionsEnabled=True,
                    AlarmActions=[sns_topic_arn],
                    AlarmDescription='Alarm when server DISK exceeds 80%',
                    Dimensions=metrics['Dimensions']
                )
                cloudwatch.put_metric_alarm(
                    AlarmName='%s_Disk_Inodes_Utilization_%s' % (name, metrics['Dimensions'][0]['Value']),
                    ComparisonOperator='LessThanThreshold',
                    EvaluationPeriods=1,
                    MetricName='disk_inodes_free',
                    Namespace='CWAgent',
                    Period=60,
                    Statistic='Average',
                    Threshold=1000,
                    ActionsEnabled=True,
                    AlarmActions=[sns_topic_arn],
                    AlarmDescription='Alarm when server Disk Inodes less than 1000',
                    Dimensions=metrics['Dimensions']
                )
        
        print("{0}: {1}".format('Name', name))
        print("------")
    