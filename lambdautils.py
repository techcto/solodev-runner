import boto3,json
import os,time,shutil,subprocess
import paramiko

LAMBDA_TASK_ROOT = os.environ.get('LAMBDA_TASK_ROOT', os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(LAMBDA_TASK_ROOT, 'lib')
BIN_DIR = '/tmp/bin'
OPENSSL = '/usr/bin/openssl'

class LambdaUtils:
    def __init__(self):
        print("Init LambdaUtils Class")
        self.s3Client = boto3.resource('s3')
        print("Downloading RSA key from " + os.environ['Bucket'])
        self.s3Client.meta.client.download_file(os.environ['Bucket'], 'rsa.pem', '/tmp/rsa.pem')
        with open("/tmp/rsa.pem", "rb") as rsa:
            os.environ['instancePEM'] = rsa.read().decode("utf-8")

        self.key = paramiko.RSAKey.from_private_key_file("/tmp/rsa.pem")

    def _init_bin(self, executable_name):
        print("Init Bin:" + executable_name)

        start = time.clock()

        if not os.path.exists(BIN_DIR):
            print("Creating bin folder")
            os.makedirs(BIN_DIR)

        print("Copying binaries for "+executable_name+" in /tmp/bin")
        currfile = os.path.join(LAMBDA_TASK_ROOT, executable_name)
        newfile  = os.path.join(BIN_DIR, executable_name)
        copyResult = shutil.copyfile(currfile, newfile)
        print(copyResult)

        print("Giving new binaries permissions for " + executable_name)
        os.chmod(newfile, 0o755)
        elapsed = (time.clock() - start)
        print(executable_name+" ready in "+str(elapsed)+'s.')

    def _reindent(self, s, numSpaces):
        leading_space = numSpaces * ' '
        lines = [ leading_space + line.strip( )
                for line in s.splitlines( ) ]
        return '\n'.join(lines)

    def openssl(self, *args):
        cmdline = [OPENSSL] + list(args)
        subprocess.check_call(cmdline)

    def download_file(self, host, username, downloadFrom, downloadTo):
        c = paramiko.SFTPClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print("Connecting to " + host)
        c.connect( hostname = host, username = username, pkey = self.key )
        print("Connected to " + host)

        c.get(downloadFrom, downloadTo)

        return
        {
            'message' : "Script execution completed. See Cloudwatch logs for complete output"
        }

    def upload_file(self, host, username, downloadFrom, downloadTo):
        c = paramiko.SFTPClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print("Connecting to " + host)
        c.connect( hostname = host, username = username, pkey = self.key )
        print("Connected to " + host)

        #Upload file to homr dir
        tmpFilename = time.strftime("%Y%m%d-%H%M%S")
        downloadToTmp = "/home/" + username + "/" + tmpFilename
        print("Upload from " + downloadFrom + " to " + downloadToTmp)
        c.put(downloadFrom, downloadToTmp)

        #Clean out old file and replace with new file
        commands = [
            'rm -f  ' + downloadTo,
            'mv ' + downloadToTmp + ' ' + downloadTo,
            'ls -al ' + downloadTo
        ]
        self.execute_cmd(host, username, commands)

        return
        {
            'message' : "Script execution completed. See Cloudwatch logs for complete output"
        }

    def execute_cmd(self, host, username, commands):
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print("Connecting to " + host)
        c.connect( hostname = host, username = username, pkey = self.key )
        print("Connected to " + host)

        for command in commands:
            print("Executing {}".format(command))
            stdin, stdout, stderr = c.exec_command(command)
            output = stdout.read()
            if output:
                print(output.decode("utf-8"))
            errors = stderr.read()
            if errors:
                print(errors.decode("utf-8"))

        return
        {
            'message' : "Script execution completed. See Cloudwatch logs for complete output"
        }