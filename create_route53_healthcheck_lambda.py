import logging
import json
import os
import csv
import time
import string
import random
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

s3_bucket_name = ''
s3_bucket_region = ''
sns_arn = ''

try:
    s3_bucket_name = os.environ['s3_bucket_name']
    s3_bucket_region = os.environ['s3_bucket_region']
	sns_arn = os.environ['sns_arn']
except KeyError as e:
    print("Warning: Environmental variable(s) not defined")


# Create client objects

s3 = boto3.client('s3', region_name='us-east-1')
route53 = boto3.client('route53')
cloudwatch_client = boto3.client('cloudwatch', region_name='us-east-1')
sns_arn='arn:aws:sns:us-east-1:610786968339:AR-Service-Availability'
# Functions

def create_s3_bucket(bucket_name, bucket_region='us-east-1'):
    """Create an Amazon S3 bucket."""
    try:
        response = s3.head_bucket(Bucket=bucket_name)
        return response
    except ClientError as e:
        if(e.response['Error']['Code'] != '404'):
            print(e)
            return None
    # creating bucket in us-east-1 (N. Virginia) requires
    # no CreateBucketConfiguration parameter be passed
    if(bucket_region == 'us-east-1'):
        response = s3.create_bucket(
            ACL='private',
            Bucket=bucket_name
        )
    else:
        response = s3.create_bucket(
            ACL='private',
            Bucket=bucket_name,
            CreateBucketConfiguration={
                'LocationConstraint': bucket_region
            }
        )
    return response


def upload_to_s3(folder, filename, bucket_name, key):
    """Upload a file to a folder in an Amazon S3 bucket."""
    key = folder + '/' + key
    s3.upload_file(filename, bucket_name, key)


def get_route53_hosted_zones(next_zone=None):
    """Recursively returns a list of hosted zones in Amazon Route 53."""
    if(next_zone):
        response = route53.list_hosted_zones_by_name(
            DNSName=next_zone[0],
            HostedZoneId=next_zone[1]
        )
    else:
        response = route53.list_hosted_zones_by_name()
    hosted_zones = response['HostedZones']
    # if response is truncated, call function again with next zone name/id
    if(response['IsTruncated']):
        hosted_zones += get_route53_hosted_zones(
            (response['NextDNSName'],
            response['NextHostedZoneId'])
        )
    return hosted_zones


def get_route53_zone_records(zone_id, next_record=None):
    """Recursively returns a list of records of a hosted zone in Route 53."""
    if(next_record):
        response = route53.list_resource_record_sets(
            HostedZoneId=zone_id,
            StartRecordName=next_record[0],
            StartRecordType=next_record[1]
        )
    else:
        response = route53.list_resource_record_sets(HostedZoneId=zone_id)
    zone_records = response['ResourceRecordSets']
    # if response is truncated, call function again with next record name/id
    if(response['IsTruncated']):
        zone_records += get_route53_zone_records(
            zone_id,
            (response['NextRecordName'],
            response['NextRecordType'])
        )
    return zone_records


def get_record_value(record):
    """Return a list of values for a hosted zone record."""
    # test if record's value is Alias or dict of records
    try:
        value = [':'.join(
            ['ALIAS', record['AliasTarget']['HostedZoneId'],
            record['AliasTarget']['DNSName']]
        )]
    except KeyError:
        value = []
        for v in record['ResourceRecords']:
            value.append(v['Value'])
    return value


def try_record(test, record):
    """Return a value for a record"""
    # test for Key and Type errors
    try:
        value = record[test]
    except KeyError:
        value = ''
    except TypeError:
        value = ''
    return value


def write_zone_to_csv(zone, zone_records):
    """Write hosted zone records to a csv file in /tmp/."""
    zone_file_name = '/tmp/' + zone['Name'] + 'csv'
    # write to csv file with zone name
    with open(zone_file_name, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        # write column headers
        writer.writerow([
            'NAME', 'TYPE', 'VALUE',
            'TTL', 'REGION', 'WEIGHT',
            'SETID', 'FAILOVER', 'EVALUATE_HEALTH'
            ])
        # loop through all the records for a given zone
        for record in zone_records:
            csv_row = [''] * 9
            csv_row[0] = record['Name']
            csv_row[1] = record['Type']
            csv_row[3] = try_record('TTL', record)
            csv_row[4] = try_record('Region', record)
            csv_row[5] = try_record('Weight', record)
            csv_row[6] = try_record('SetIdentifier', record)
            csv_row[7] = try_record('Failover', record)
            csv_row[8] = try_record('EvaluateTargetHealth',
                try_record('AliasTarget', record)
            )
            value = get_record_value(record)
            # if multiple values (e.g., MX records), write each as its own row
            for v in value:
                csv_row[2] = v
                writer.writerow(csv_row)
    return zone_file_name


def write_zone_to_json(zone, zone_records):
    """Write hosted zone records to a json file in /tmp/."""
    zone_file_name = '/tmp/' + zone['Name'] + 'json'
    # write to json file with zone name
    with open(zone_file_name, 'w') as json_file:
        json.dump(zone_records, json_file, indent=4)
    return zone_file_name
    
def create_health_check(domain_name):
    logger = logging.getLogger()
    logger.info("Creating healthcheck for " + domain_name)
    response = route53.create_health_check(
        CallerReference=''.join(random.sample(string.ascii_lowercase, 9)),
        HealthCheckConfig={
            'Type': 'HTTPS',
            'Port': 443,
            'FullyQualifiedDomainName': domain_name,
            'RequestInterval': 10,
            'FailureThreshold': 3,
            'MeasureLatency': True,
            'EnableSNI': True
        }
    )
    
    route53.change_tags_for_resource(
        ResourceType='healthcheck',
        ResourceId=response['HealthCheck']['Id'],
        AddTags=[
            {
                'Key': 'Name',
                'Value': domain_name
            }
        ]
    )
    
    cloudwatch_client.put_metric_alarm(
        AlarmName=domain_name,
        ComparisonOperator='LessThanThreshold',
        EvaluationPeriods=1,
        MetricName='HealthCheckStatus',
        Namespace='AWS/Route53',
        Dimensions=[{'Name': 'HealthCheckId', 'Value': response['HealthCheck']['Id']}],
        Period=60,
        Statistic='Minimum',
        Threshold=1,
        ActionsEnabled=True,
        AlarmActions=[sns_arn],
        AlarmDescription='Alarm when site is unavailable')

def delete_health_check(domain_name):
    domain_name = domain_name[:-1]
    logger = logging.getLogger()
    logger.info("Deleting healthcheck for " + domain_name)
    health_check_paginator = route53.get_paginator('list_health_checks')
    try:
        health_check_records = health_check_paginator.paginate()
        for health_set in health_check_records:
            for record in health_set['HealthChecks']:
                if record['HealthCheckConfig']['FullyQualifiedDomainName'] == domain_name :
                    logger.info(record['Id'] + " : " + record['HealthCheckConfig']['FullyQualifiedDomainName'])
                    route53.delete_health_check(
                        HealthCheckId=record['Id']
                    )
                    cloudwatch_client.delete_alarms(
                        AlarmNames=[
                            domain_name
                        ]
                    )

    except Exception as error:
        print('An error occurred getting source zone records:')
        print(str(error))
        raise
     
def lambda_handler(event, context):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.debug(event['Records'][0]['Sns']['Message'])
    detailjson = json.loads(event['Records'][0]['Sns']['Message'])
    hostedzone_id = detailjson['detail']['requestParameters']['hostedZoneId']
    changes = detailjson['detail']['requestParameters']['changeBatch']['changes']
    for change in changes :
        action = change['action']
        domain_name = change['resourceRecordSet']['name']
        logger.info("hostedZoneId : " + hostedzone_id + " action : " + action + " DomainName : " + domain_name)
        if len(changes) == 1 and action == "DELETE" :
            delete_health_check(domain_name)
        if len(changes) == 1 and action == "CREATE" :
            create_health_check(domain_name)
    
    """Handler function for AWS Lambda"""
    time_stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ",
        datetime.utcnow().utctimetuple()
    )
    if(not create_s3_bucket(s3_bucket_name, s3_bucket_region)):
        return False
    #bucket_response = create_s3_bucket(s3_bucket_name, s3_bucket_region)
    #if(not bucket_response):
        #return False
    hosted_zones = get_route53_hosted_zones()
    for zone in hosted_zones:
        zone_folder = (time_stamp + '/' + zone['Name'][:-1])
        zone_records = get_route53_zone_records(zone['Id'])
        upload_to_s3(
            zone_folder,
            write_zone_to_csv(zone, zone_records),
            s3_bucket_name,
            (zone['Name'] + 'csv')
        )
        upload_to_s3(
            zone_folder,
            write_zone_to_json(zone, zone_records),
            s3_bucket_name,
            (zone['Name'] + 'json')
        )
    return True
