import boto3
from collections import defaultdict
from botocore.config import Config
my_config = Config(
    region_name = 'us-east-1'
)
ec2 = boto3.resource('ec2', config=my_config)
cloudwatch = boto3.client('cloudwatch', config=my_config)
sns = boto3.resource('sns', config=my_config)
sns_topic_arn = sns.create_topic(Name='demotopic').arn
#response = sns.subscribe(TopicArn=sns_topic_arn, Protocol='email', Endpoint='sree.muppavarapu@gmail.com')
running_instances = ec2.instances.filter(Filters=[{
    'Name': 'instance-state-name',
    'Values': ['running']
}])

ec2info = defaultdict()
for instance in running_instances:
    for tag in instance.tags:
        if 'Name'in tag['Key']:
            name = tag['Value']
    # Add instance info to a dictionary         
    ec2info[instance.id] = {
        'Name': name,
    }

attributes = ['Name']
for instance_id, instance in ec2info.items():
    print('Id: ' + instance_id)
    for key in attributes:
        cloudwatch.put_metric_alarm(
            AlarmName='%s_CPU_Utilization' % instance[key],
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
                'Value': instance_id
                },
            ]
        )
        print("{0}: {1}".format(key, instance[key]))
    print("------")