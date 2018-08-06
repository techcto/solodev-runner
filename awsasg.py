import boto3,json

class AwsAsg:
    def __init__(self, cluster):
        print("Init AwsAsg Class")
        self.cluster = cluster
        self.activeInstances = []
        self.newInstances = []
        self.status = "run"
        self.snsTopicArn = ""
        self.snsSubject = ""
        self.snsMessage = ""
        self.lifecycleHookName = ""
        self.lifecycleActionToken = ""
        self.autoscalingClient = boto3.client('autoscaling')
        self.ec2Client = boto3.client('ec2')

    def complete_lifecycle_action(self, lifecycleActionResult):
        try:
            response = self.autoscalingClient.complete_lifecycle_action(LifecycleHookName=self.lifecycleHookName,AutoScalingGroupName=self.cluster,LifecycleActionToken=self.lifecycleActionToken,LifecycleActionResult=lifecycleActionResult)
            if response:
                return response
        except BaseException as e:
            print(str(e))

    def check_instance_status(self):
        #Get all instances for an ASG
        filters = [{  
            'Name': 'tag:aws:autoscaling:groupName',
            'Values': [self.cluster]
        }]

        print("Print instances in autoscaling group")
        for reservation in self.ec2Client.describe_instances(Filters=filters)['Reservations']:
            # print(reservation['Instances'])

            for instance in reservation['Instances']:
                #Check to see if instance is healthy
                response = self.autoscalingClient.describe_auto_scaling_instances(
                    InstanceIds=[
                        instance['InstanceId']
                    ]
                )

                for asgInstance in response['AutoScalingInstances']:
                    #Pretty print json of instance from AWS autoscaling group
                    print(json.dumps(asgInstance, indent=4, sort_keys=True))

                    if (asgInstance['LifecycleState'] == 'InService'):   
                        print("This instance is good to go!")
                        self.activeInstances.append(instance)
                    elif (asgInstance['LifecycleState'] == 'Pending') or (asgInstance['LifecycleState'] == 'Pending:Wait') or (asgInstance['LifecycleState'] == 'Pending:Proceed'):
                        print("We have a new instance.  Welcome!")
                        self.newInstances.append(instance)

    def check_event_status(self, event, context):
        print("Test Event for type")
        self.event = event
        self.context = context
        eventStatus = "TEST"

        try:
            snsTopicArn=event['Records'][0]['Sns']['TopicArn']
            snsMessage=json.loads(event['Records'][0]['Sns']['Message'])
            try:
                snsEvent=snsMessage['Event']
                eventStatus = "ASG"
            except BaseException as e:
                print(str(e))
            eventStatus = "SNS"
        except BaseException as e:
            print(str(e))

        runStatus = "exit"
        if (eventStatus == "SNS") or (eventStatus == "ASG"):
            self.snsTopicArn=event['Records'][0]['Sns']['TopicArn']
            self.snsSubject=event['Records'][0]['Sns']['Subject']
            self.snsMessage=json.loads(event['Records'][0]['Sns']['Message'])
            
            if eventStatus == "ASG":
                self.snsEvent=snsMessage['Event']
                
                if self.snsEvent == "autoscaling:TEST_NOTIFICATION":
                    runStatus = "exit"
                else:
                    self.lifecycleHookName=snsMessage['LifecycleHookName']
                    self.lifecycleActionToken=snsMessage['LifecycleActionToken']
                    self.lifecycleTransition=snsMessage['LifecycleTransition']

                    if self.lifecycleTransition == "autoscaling:EC2_INSTANCE_TERMINATING":
                        runStatus = "backup"
                    elif self.lifecycleTransition == "autoscaling:EC2_INSTANCE_LAUNCHING":
                        runStatus = "retry"
                    else:
                        runStatus = "run"
        elif eventStatus == "TEST":
            runStatus = "run"

        self.status = runStatus;