import boto3,json,os,subprocess,base64,time,shutil
from botocore.vendored import requests
import paramiko

import awsasg,awslambda,awss3,lambdautils,solodev

#Boot up modules
awsasg = awsasg.AwsAsg(os.environ['Cluster'])
awss3 = awss3.AwsS3()
awslambda = awslambda.AwsLambda(awsasg)
lambdautils = lambdautils.LambdaUtils()
solodev = solodev.Solodev(awsasg.activeInstances, os.environ['install_dir'], os.environ['cluster'], os.environ['instance_user'])

s3 = boto3.resource('s3')
s3Client = boto3.client('s3')

def run(event, context):
    print("Run App")
    print(event)
    print(context)
    print(os.environ)  

    #Set Event Status
    awsasg.check_event_status(event, context)

    #Set ASG Status
    awsasg.check_instance_status()

    #Check RKE Status
    appStatus = init()

    #Run Application
    dispatch(awsasg, appStatus);

    return True

def init():
    appStatus = awss3.file_exists(os.environ['bucket'], 'Client_Settings.xml')
    if appStatus == True:
        s3Client.download_file(os.environ['bucket'], 'config.yaml', '/tmp/Client_Settings.xml')
    else:
        print("Generate Solodev config with all active instances")
        solodev.healMongo()
        solodev.generateConfig(os.environ['database_name'], os.environ['database_host'], os.environ['database_user'], os.environ['database_password'], os.environ['mongo_host'])
    return appStatus

def dispatch(awsasg, appStatus):
    if awsasg.snsSubject == "update":
        update(awsasg)
    elif awsasg.status == "backup":
        backup(awsasg)
    elif awsasg.status == "restore":
        restore(awsasg)
    elif awsasg.status == "exit":
        exit(awsasg)
    elif awsasg.status == "retry":
        retry(awsasg)
    else:
        install(awsasg)
    return True

def install(awsasg):
    print("Install Solodev CMS")
    solodev.install()
    print("Upload Solodev generated configs")
    s3Client.upload_file('/tmp/Client_Settings.xml', os.environ['bucket'], 'Client_Settings.xml')
    print("Complete Lifecycle")
    awsasg.complete_lifecycle_action('CONTINUE')
    exit(awsasg)
    
def update(awsasg):
    print("Download Solodev generated config")
    s3Client.download_file(os.environ['bucket'], 'Client_Settings.xml', '/tmp/Client_Settings.xml')
    print("Update Solodev")
    solodev.update()
    exit(awsasg)
    
def backup(awsasg):
    print("Backup Solodev and upload externally to S3")
    solodev.backup()
    exit(awsasg)

def restore(awsasg):
    print("Restore Solodev latest backup")
    restoreStatus = solodev.restore()
    if restoreStatus == False:
        print("Restore failed!")
        exit(awsasg)
    else:
        print("Call Update Function via SNS")
        status = awslambda.publish_sns_message("update")
        if status == False:
            update(awsasg)

def exit(awsasg):
    print("Complete Lifecycle")
    awsasg.complete_lifecycle_action('CONTINUE')
    return True

def retry(awsasg):
    # time.sleep(60)
    # status = awslambda.publish_sns_message('')
    # if status == False:
    #     install(awsasg)
    return True