import boto3
from collections import defaultdict
session = boto3.Session(profile_name='arvault')
ec2 = session.resource('ec2')

running_instances = ec2.instances.filter(Filters=[{
    'Name': 'instance-state-name',
    'Values': ['running']}])

ec2info = defaultdict()
for instance in running_instances:
    for tag in instance.tags:
        if 'Name'in tag['Key']:
            name = tag['Value']
    # Add instance info to a dictionary         
    ec2info[instance.id] = {
        'Name': name,
        'Type': instance.instance_type,
        'State': instance.state['Name'],
        'Private IP': instance.private_ip_address,
        'Public IP': instance.public_ip_address,
        'Image ID': instance.image_id,
        'block_device_mappings': instance.block_device_mappings,
        'Launch Time': instance.launch_time
        }

attributes = ['Name', 'Type', 'State', 'Private IP', 'Public IP', 'Image ID', 'block_device_mappings', 'Launch Time']
for instance_id, instance in ec2info.items():
    for key in attributes:
        print("{0}: {1}".format(key, instance[key]))
    print("------")