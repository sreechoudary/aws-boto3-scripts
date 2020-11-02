import boto3
import json
# Set environmental variables

# Create client objects

s3 = boto3.client('s3', region_name='us-west-2')

response = s3.list_buckets()

# Output the bucket names
print('Existing buckets:')
for bucket in response['Buckets']:
    bucketName = bucket["Name"]
    #if len(bucketName) == 12 and bucketName != "aralmuploads" and bucketName != "arinstallers" and bucketName != "aws-arserver" and bucketName != "6b50e9324392":
    #if bucketName.startswith("desktop-") or bucketName.startswith("ar-hyd-lap") :
    if bucketName.startswith("org1-20") or bucketName.startswith("org2-129") or bucketName.startswith("orgid") or bucketName.startswith("rabitauto-140") or bucketName.startswith("rameshm-016") :
        print(bucketName)
        objresponse = s3.list_objects_v2(
            Bucket=bucketName,
        )
        Objects = []
        if 'Contents' in response:
            for objName in objresponse["Contents"]:
                print(objName["Key"])
                d = {}
                d['Key']=objName["Key"]
                Objects.append(d)
            delobjresponse = s3.delete_objects(
                Bucket=bucketName,
                Delete={
                    'Objects': Objects
                }
            )
            delresponse = s3.delete_bucket(
                Bucket=bucketName
            )

 
def empty_s3_bucket(bucket_name):
  response = s3.list_objects_v2(Bucket=bucket_name)
  if 'Contents' in response:
    for item in response['Contents']:
      print('deleting file', item['Key'])
      s3.delete_object(Bucket=bucket_name, Key=item['Key'])
      while response['KeyCount'] == 1000:
        response = s3.list_objects_v2(
          Bucket=bucket_name,
          StartAfter=response['Contents'][0]['Key'],
        )
        for item in response['Contents']:
          print('deleting file', item['Key'])
          s3.delete_object(Bucket=bucket_name, Key=item['Key'])     
    #print(f'  {bucket}')
    #print(f'  {bucket["Name"]}')