import os
import json
import boto3
from collections import defaultdict
session = boto3.Session(profile_name='default', region_name='us-east-1')
# Create CloudWatch client
cloudwatch = session.client('cloudwatch')
route53_client = session.client('route53')

DEBUG = os.getenv("DEBUG") is not None

def _create_metric(metric_name, dashboard_type):
    health_check_response = route53_client.get_health_check(
        HealthCheckId=metric_name['Dimensions'][0]['Value']
    )
    print(health_check_response['HealthCheck']['HealthCheckConfig']['FullyQualifiedDomainName'])
    labeljson = {}
    labeljson["label"] = health_check_response['HealthCheck']['HealthCheckConfig']['FullyQualifiedDomainName']
    metric = []
    metric.append("AWS/Route53")
    metric.append(metric_name['MetricName'])    
    metric.append('HealthCheckId')
    metric.append(metric_name['Dimensions'][0]['Value'])
    metric.append(labeljson)
    return metric

def _create_metrics(metric_names, dashboard_type):
    metrics = []
    for metric_name in metric_names['Metrics']:
        metrics.append(_create_metric(metric_name, dashboard_type))
    return metrics

def show(obj):
    rmd = "ResponseMetadata"
    if rmd in obj:
        del obj[rmd]
    print(json.dumps(obj, indent=4, default=str).replace('\n', "\n\u00A0"))

def create_dashboard(dashboard_name, metric_names, dashboard_type):
    widgets = []
    title = metric_names['Metrics'][0]['MetricName']
    metrics = _create_metrics(metric_names, dashboard_type)        
             
    widget = {
        'type': 'metric',
        'x': 0,
        'y': 0,
        'width': 24,
        'height': 6,
        'properties': {
            'title': f'{title}m',
            # multiple lambdas on each graph
            'metrics': metrics,
            'period': 5 * 60,
            'stat': 'Maximum',
            'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        }
    }
    widgets.append(widget)
    dashboard_body = {'widgets' : widgets}
    dashboard_body_j = json.dumps(dashboard_body)
    print(dashboard_body_j)
    response = cloudwatch.put_dashboard(DashboardName=dashboard_name, DashboardBody=dashboard_body_j)
    show(response)
    print('created!')

    if DEBUG:
        print(f'dashboard_body for {dashboard_name}')
        show(dashboard_body)

def delete_dashboard(dashboard_name):
    print("deleting", dashboard_name)
    response = cloudwatch.delete_dashboards(DashboardNames=[dashboard_name])
    show('delete_dashboards returns')
    show(response)

# List metrics through the pagination interface
paginator = cloudwatch.get_paginator('list_metrics')
metricinfo = defaultdict()
for response in paginator.paginate(
                MetricName='HealthCheckPercentageHealthy',
                Namespace='AWS/Route53'):
    #print(response)
    create_dashboard("UPTime", response, "route53")
