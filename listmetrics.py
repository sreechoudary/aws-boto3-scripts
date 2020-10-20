import boto3
from collections import defaultdict
session = boto3.Session(profile_name='arvault')
# Create CloudWatch client
cloudwatch = session.client('cloudwatch')

# List metrics through the pagination interface
paginator = cloudwatch.get_paginator('list_metrics')
metricinfo = defaultdict()
for response in paginator.paginate(Dimensions=[{'Name': 'InstanceId', 'Value': 'i-018d5e4a257fdcf65'},{
                'Name': 'fstype',
                'Value': 'ext4'
                }],
                MetricName='disk_used_percent',
                Namespace='CWAgent'):
    for metrics in response['Metrics']:
        metricinfo[metrics['Dimensions'][1]['Value']+"-"+metrics['Dimensions'][0]['Value']] = {
            'path': metrics['Dimensions'][0]['Value'],
            'InstanceId': metrics['Dimensions'][1]['Value'],
            'ImageId': metrics['Dimensions'][2]['Value'],
            'InstanceType': metrics['Dimensions'][3]['Value'],
            'device': metrics['Dimensions'][4]['Value'],
            'fstype': metrics['Dimensions'][5]['Value']
            }
        print("-----")
attributes = ['path', 'InstanceId', 'ImageId', 'InstanceType', 'device', 'fstype']
for instance_id, instance in metricinfo.items():
    for key in attributes:
        print("{0}: {1}".format(key, instance[key]))
    print("------")

