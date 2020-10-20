import boto3
import string
import random

aws_profile = 'default'
zone_id = 'Z2UQP3S1OE1SII'
session = boto3.Session(profile_name=aws_profile)
route53_client = session.client('route53')
cloudwatch_client = boto3.client('cloudwatch')
paginator = route53_client.get_paginator('list_resource_record_sets')
dns_records = []

try:
    source_zone_records = paginator.paginate(HostedZoneId=zone_id)
    for record_set in source_zone_records:
        for record in record_set['ResourceRecordSets']:
            if record['Type'] == 'A':
                dns_records.extend(record['Name'])

except Exception as error:
    print('An error occurred getting source zone records:')
    print(str(error))
    raise

existing_health_records = []
healthCheckPaginator = route53_client.get_paginator('list_health_checks')
try:
    health_check_records = healthCheckPaginator.paginate()
    for health_set in health_check_records:
        for record in health_set['HealthChecks']:
            existing_health_records.extend(record['Name'])
            print(record['HealthCheckConfig']['FullyQualifiedDomainName'])
                

except Exception as error:
    print('An error occurred getting source zone records:')
    print(str(error))
    raise

