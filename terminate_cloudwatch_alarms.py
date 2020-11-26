#=================================================================================================
# Function: TerminateCloudWatchAlarmsForEc2Instance
# Purpose:  Lambda funtion used to delete cloudwatch alarms for terminated EC2 instances
# Author : Sreenivasa Rao M (sreenivasrao.m@autorabit.com)
# This function has the ability to delete CloudWatch alarms for any Ec2 instance
#==================================================================================================
import boto3
import datetime
import os
import logging
# Create CloudWatch client
cloudwatch = boto3.client('cloudwatch')
ec2 = boto3.resource('ec2')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
def lambda_handler(event, context):
    instance_id = event["detail"]["instance-id"]
    state = event["detail"]["state"]
    if (state == "terminated"):
      delete_alarms_for_instance(instance_id)

def get_instance_name(instance):
  instance_name = ''
  for tag in instance.tags:
      if (tag['Key']=="Name"):
        instance_name=(tag['Value'])
        return instance_name

def delete_alarms_for_instance(instance_id):
  instance_name = get_instance_name(ec2.Instance(instance_id))
  logger.info("Deleting cloudwatch alarms for instance : " + instance_name)
  response = cloudwatch.describe_alarms(AlarmNamePrefix = instance_name, AlarmTypes=[
        'CompositeAlarm','MetricAlarm',
    ])
  alarms = response['CompositeAlarms']
  alarm_names = [alarm['AlarmName'] for alarm in alarms]
  logger.info(alarm_names)
  cloudwatch.delete_alarms(AlarmNames = alarm_names)
  alarms = response['MetricAlarms']
  alarm_names = [alarm['AlarmName'] for alarm in alarms]
  logger.info(alarm_names)
  cloudwatch.delete_alarms(AlarmNames = alarm_names)