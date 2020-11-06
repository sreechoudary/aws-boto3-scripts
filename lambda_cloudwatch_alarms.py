#=================================================================================================
# Function: CreateCloudWatchAlarmEC2Instances
# Purpose:  Lambda funtion used to provision cloudwatch alarms for EC2 instance CPU Utilization
# Author : Sreenivasa Rao M (sreenivasrao.m@autorabit.com)
# This function has the ability to provision CloudWatch alarms for any Ec2 instance
#==================================================================================================
import boto3
import datetime
import os
import time
import logging
from botocore.exceptions import ClientError
# Create CloudWatch client
cloudwatch = boto3.client('cloudwatch')
ec2 = boto3.resource('ec2')
ssm = boto3.client('ssm')
sns = boto3.client('sns')
client = boto3.client('ec2')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
DEFAULT_TOPIC_NAME="Systems-Monitor"
Email = os.environ.get('Email')
def lambda_handler(event, context):
  sns_topic_arn = ''
  if(event.get('detail') != None):
    detail = event.get('detail')
    if (detail.get('sns-topic')==None or detail['sns-topic']==''):
      logger.info("No sns topic passed, creating SNS topic with default name.")
      sns_topic_arn = get_sns_topic(DEFAULT_TOPIC_NAME)
    else:
      sns_topic_arn = get_sns_topic(detail['sns-topic'])

  if (event.get('detail') == None or event['detail']['instance-id'] == ''):
      logger.info("No instance id passed with the event.")
      create_alarms(None,sns_topic_arn)
  else:
      instance_id = event["detail"]["instance-id"]
      logger.info("installing and configuring Cloudwatch agents on the instance : " + instance_id)
      create_alarms(instance_id,sns_topic_arn)
 
def get_instance_name(instance):
  name = ''
  for tag in instance.tags:
      if 'Name'in tag['Key']:
          name = tag['Value']
  return name

def create_alarms(instance_id,sns_topic_arn):
  if (instance_id == None):
      logger.info("Creating cloudwatch alarms for all instances")
      all_instances = boto3.client('ec2').describe_instances(Filters=[{'Name': 'instance-state-name','Values': ['running']}])
      all_instance_ids = []
      linux_instance_ids=[]
      windows_instance_ids=[]
      for reservation in all_instances["Reservations"]:
          for instance in reservation["Instances"]:
            if (instance.get('Platform') == None):
              linux_instance_ids.append(instance["InstanceId"])
            else:
              windows_instance_ids.append(instance["InstanceId"])
            all_instance_ids.append(instance["InstanceId"])
            
      install_and_configure_cwagent(all_instance_ids)
      send_run_command(linux_instance_ids,"linux")
      send_run_command(windows_instance_ids,"windows")
      for instance in all_instances:
        create_alarms_for_instance(instance, get_instance_name(instance), sns_topic_arn)
     
  else:
    instance = ec2.Instance(instance_id)
    instance_id_list = [instance_id]
    install_and_configure_cwagent(instance_id_list)
    if(instance.platform == None):
      send_run_command(instance_id_list,"linux")
    else:
      send_run_command(instance_id_list,"windows")    
    create_alarms_for_instance(instance, get_instance_name(instance), sns_topic_arn)
 
def install_and_configure_cwagent(instance_id):
    logger.info('========== Instances to install Cloudwatch Agents:')
    logger.info(instance_id)
  # install cloudwatch agents using SSM automation
    ssm.send_command(
            InstanceIds=instance_id,
            DocumentName='AWS-ConfigureAWSPackage',
            Parameters={
                "action": ["Install"],
                "installationType":["Uninstall and reinstall"],
                "name":["AmazonCloudWatchAgent"]
            }
        )
    time.sleep(60)
    
def send_run_command(instance_ids, os):

    if(os=='windows'):
        commands = [
            "cd “C:\Program Files\Amazon\AmazonCloudWatchAgent\”", ".\\amazon-cloudwatch-agent-ctl.ps1 -a fetch-config -m ec2 -c ssm:AmazonCloudWatch-windows", ""
            ]
    if(os=='linux'):
        commands=["#!/bin/bash", "if [ $# = 1 ]", "then", " if [ $HOSTNAME = $1 ]", " then", " echo \"Hostname matched\"", " else", " echo \"Hostname not matched and updating the hostname\"", " sudo hostnamectl set-hostname $1", " fi", "else", " echo \"No arguments\"", "fi", "sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c ssm:infrastructure", "sleep 10", "sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a stop", "sudo sed -i 's/{instance_id}/'\"$HOSTNAME\"'/g' /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.d/ssm_infrastructure", "sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a start"]
     
    """
    Tries to queue a RunCommand job.  If a ThrottlingException is encountered
    recursively calls itself until success.
    """
    try:
        if(os=="windows"):
            ssm.send_command(
                InstanceIds=instance_ids,
                DocumentName='AWS-RunPowerShellScript',
                Parameters={
                    'commands': commands,
                    'executionTimeout': ['600'] # Seconds all commands have to complete in
                })
            logger.info('============RunCommand sent successfully')
            return True
        if(os=='linux'):
            ssm.send_command(
                InstanceIds=instance_ids,
                DocumentName='AWS-RunShellScript',
                Parameters={
                    'commands': commands,
                    'executionTimeout': ['600'] # Seconds all commands have to complete in
                })
    except ClientError as err:
            if 'ThrottlingException' in str(err):
                logger.info("RunCommand throttled, automatically retrying...")
                send_run_command(instance_ids, os)
            else:
                logger.info("Run Command Failed!\n%s", str(err))
                return False
 
def get_sns_topic(topic_name):
    topic = sns.create_topic(Name=topic_name)
    sns.subscribe(TopicArn=topic['TopicArn'], Protocol="email", Endpoint=Email)
    return (topic['TopicArn'])
 
def create_alarms_for_ebs_volumes(instance, instance_name, sns_topic_arn):
  paginator = cloudwatch.get_paginator('list_metrics')
  for response in paginator.paginate(Dimensions=[{'Name': 'InstanceId', 'Value': instance.id},{'Name': 'fstype','Value': 'ext4'}],
                                    MetricName='disk_used_percent',
                                    Namespace='CWAgent'):
            for metrics in response['Metrics']:
                cloudwatch.put_metric_alarm(
                    AlarmName='%s_Disk_Utilization_%s' % (instance_name, metrics['Dimensions'][0]['Value']),
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
                    AlarmName='%s_Disk_Inodes_Utilization_%s' % (instance_name, metrics['Dimensions'][0]['Value']),
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

def create_alarms_for_instance(instance, instance_name, sns_topic_arn):
    cloudwatch.put_metric_alarm(
      AlarmName= '%s_CPU_Utilization' % instance_name,
      ComparisonOperator='GreaterThanThreshold',
      EvaluationPeriods=1,
      MetricName='CPUUtilization',
      Namespace='AWS/EC2',
      Period=60,
      Statistic='Average',
      Threshold=70.0,
      ActionsEnabled=False,
      AlarmDescription='Alarm triggers when CPU Utilization  on this instance exceeds 70% utilization',
      TreatMissingData="missing",
      AlarmActions=[ sns_topic_arn ],
      Dimensions=[
          {
            'Name': 'InstanceId',
            'Value': instance.id
          }
      ],
    )
    cloudwatch.put_metric_alarm(
      AlarmName= '%s_Memory_Utilization' % instance_name,
      ComparisonOperator='GreaterThanThreshold',
      EvaluationPeriods=1,
      MetricName='mem_used_percent',
      Namespace='CWAgent',
      Period=60,
      Statistic='Average',
      Threshold=80.0,
      ActionsEnabled=True,
      AlarmDescription='Alarm triggers when memory utilization on this instance exceeds 80% utilization',
      TreatMissingData="notBreaching",
      AlarmActions=[ sns_topic_arn ],
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
      ],
    )
                 
    cloudwatch.put_metric_alarm(
          AlarmName='%s_StatusCheckFailed_System' % instance_name,
          ComparisonOperator='GreaterThanOrEqualToThreshold',
          EvaluationPeriods=1,
          MetricName='StatusCheckFailed_System',
          Namespace='AWS/EC2',
          Period=60,
          Statistic='Average',
          Threshold=1.0,
          ActionsEnabled=True,
          AlarmActions=[sns_topic_arn],
          AlarmDescription='Alarm triggers when system status check fails or when system is not reachable',
          Dimensions=[
              {
              'Name': 'InstanceId',
              'Value': instance.id
              },
          ]
    )
    cloudwatch.put_metric_alarm(
        AlarmName='%s_StatusCheckFailed_Instance' % instance_name,
        ComparisonOperator='GreaterThanOrEqualToThreshold',
        EvaluationPeriods=1,
        MetricName='StatusCheckFailed_Instance',
        Namespace='AWS/EC2',
        Period=60,
        Statistic='Average',
        Threshold=1.0,
        ActionsEnabled=True,
        AlarmActions=[sns_topic_arn],
        AlarmDescription='Alarm triggers when instance status check fails or when instance is not reachable',
        Dimensions=[
            {
            'Name': 'InstanceId',
            'Value': instance.id
            },
        ]
    )
    cloudwatch.put_metric_alarm(
        AlarmName='%s_StatusCheckFailed' % instance_name,
        ComparisonOperator='GreaterThanOrEqualToThreshold',
        EvaluationPeriods=1,
        MetricName='StatusCheckFailed',
        Namespace='AWS/EC2',
        Period=60,
        Statistic='Average',
        Threshold=1.0,
        ActionsEnabled=True,
        AlarmActions=[sns_topic_arn],
        AlarmDescription='Alarm triggers when status check fails or when instance is not reachable',
        Dimensions=[
            {
            'Name': 'InstanceId',
            'Value': instance.id
            },
        ]
    )
    time.sleep(10)
    create_alarms_for_ebs_volumes(instance, instance_name, sns_topic_arn)
    cpu_utilization_too_high = instance_name + '_CPU_Utilization'
    mem_utilization_too_high = instance_name + '_Memory_Utilization'
    alarm_rule = 'ALARM(' + '"' + cpu_utilization_too_high + '"' + ')' + ' AND ' + 'ALARM(' + '"' + mem_utilization_too_high + '"' + " )"
    logger.info(alarm_rule)
    cloudwatch.put_composite_alarm(AlarmName= instance_name + '- COMPOSITE ALARM MemCPU',
                        AlarmDescription='Alarm triggers when both CPU and Memory of giving instance is higher than 80%',
                        AlarmActions=[ sns_topic_arn ],
                        AlarmRule= alarm_rule ,
                        )