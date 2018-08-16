import boto3
import lambdautils

class Solodev:

    def __init__(self, instances, install_dir, cluster, instance_user):
        print("Init Solodev class")
        self.s3Client = boto3.resource('s3')
        self.lambdautils = lambdautils.LambdaUtils()
        self.instances = instances
        self.install_dir = install_dir
        self.cluster = cluster
        self.instance_user = instance_user
    
    def install(self):
        print("Perform fresh install of Solodev")
        print("Init Mongo cluster")
        self.initMongo()
        print("Install Solodev")
        self.updateSoftware()

    def update(self):
        print("Existing Solodev: Update cluster")
        print("Backup cluster")
        self.backup()
        print("Heal Mongo cluster")
        self.healMongo()
        print("Update Solodev")
        self.updateSoftware()

    def generateConfig(self, database_name, database_host, database_user, database_password, mongo_host):
        with open('templates/Client_Settings.xml', 'r') as settings :
            clientSettings = settings.read()

        clientSettings = clientSettings.replace('REPLACE_WITH_DATABASE', database_name)
        clientSettings = clientSettings.replace('REPLACE_WITH_DBHOST', database_host)
        clientSettings = clientSettings.replace('REPLACE_WITH_DBUSER', database_user)
        clientSettings = clientSettings.replace('REPLACE_WITH_DBPASSWORD', database_password)
        clientSettings = clientSettings.replace('REPLACE_WITH_MONGOHOST', mongo_host)

        print("Write Client_Settings.xml to /tmp/Client_Settings.xml")
        with open('/tmp/Client_Settings.xml', 'w') as settings:
            settings.write(clientSettings)

        print("Upload Client_Settings.xml to Instance")
        for instance in self.instances:
            try:
                print("Login to Solodev instance and copy Client_Settings.xml to install dir")
                self.lambdautils.upload_file(instance['PublicIpAddress'], self.instance_user, '/tmp/Client_Settings.xml', self.install_dir+'/Client_Settings.xml')
                break
            except BaseException as e:
                print(str(e))

    def backup(self):
        print("Init Duplicity")
        self.lambdautils._init_bin('bin/duplicity')

        commands = [
            '/tmp/duplicity'
        ]
        for instance in self.instances:
            try:
                print("Login to Solodev instance and execute backup scripts")
                self.lambdautils.execute_cmd(instance['PublicIpAddress'], self.instance_user, commands)
                break
            except BaseException as e:
                print(str(e))

    def restore(self):
        print("Restore Placeholder")

    def initMongo(self):
        print("Init Mongo")
        self.healMongo()

    def healMongo(self):
        print("Heal Mongo")
        self.lambdautils._init_bin('scripts/heal_mongo.sh')

        print("Get IP's of valid hosts")
        AWSHOSTS=""
        for instance in self.instances:
            AWSHOSTS += instance['PrivateIpAddress'] + '\n'
            
        print("Upload Valid Hosts and Stack Name to Instances")
        commands = [
            'echo "'+self.cluster+'" > '+self.install_dir+'/clients/solodev/stackname.txt',
            'echo "'+AWSHOSTS+'" > '+self.install_dir+'/clients/solodev/mongohosts.txt',
            'AWSHOSTS='+AWSHOSTS,
            '/tmp/heal_mongo.sh'
        ]
        for instance in self.instances:
            self.lambdautils.execute_cmd(instance['PublicIpAddress'], self.instance_user, commands)

        print("Execute Heal Mongo Bash Script")

    def installSoftware(self):
        print("Install Solodev")
        commands = [
        'mkdir -p '+self.install_dir+'/clients/solodev/Vhosts',
        'mkdir -p '+self.install_dir+'/clients/solodev/s.Vhosts',
        'mkdir -p '+self.install_dir+'/clients/solodev/Main',
        'mv '+self.install_dir+'/core/aws/Client_Settings.xml '+self.install_dir+'/clients/solodev/Client_Settings.xml',
		'mv '+self.install_dir+'/core/solodevX/www/htaccess.txt '+self.install_dir+'/core/solodevX/www/.htaccess',
        self.install_dir+'/core/update.php >> /root/phpinstall.log'
        ]
        for instance in self.instances:
            try:
                print("Login to Solodev instance and execute install script")
                self.lambdautils.execute_cmd(instance['PublicIpAddress'], self.instance_user, commands)
                break
            except BaseException as e:
                print(str(e))

    def updateSoftware(self):
        print("Update Solodev")
        commands = [
            'rm -Rf '+self.install_dir+'/old',
		    'mkdir '+self.install_dir+'/old',
		    'mv '+self.install_dir+'/modules '+self.install_dir+'/old/',
		    'mv '+self.install_dir+'/core '+self.install_dir+'/old/',
		    'mv '+self.install_dir+'/composer.json '+self.install_dir+'/old/',
		    'mv '+self.install_dir+'/composer.lock '+self.install_dir+'/old/',
		    'mv '+self.install_dir+'/vendor '+self.install_dir+'/old/',
		    'rm -Rf '+self.install_dir+'/license.php',
            self.install_dir+'/core/update.php >> /root/phpinstall.log'
        ]
        for instance in self.instances:
            try:
                print("Login to Solodev instance and execute update script")
                self.lambdautils.execute_cmd(instance['PublicIpAddress'], self.instance_user, commands)
                break
            except BaseException as e:
                print(str(e))
