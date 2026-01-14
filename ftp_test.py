# https://docs.paramiko.org/en/3.3/api/sftp.html
# https://stackoverflow.com/questions/39523216/paramiko-add-host-key-to-known-hosts-permanently



import paramiko

hostname = "example.com"
username = "user"
password = "pass"

# Establishing a connection

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.load_host_keys('./.known_hosts')

client.connect('192.168.0.149', username='camtrawl', password='pollock')
print("Connection successfully established with the server.")

sftp = paramiko.SFTPClient.from_transport(client.get_transport())



sftp.chdir('/camtrawl/image_data')
files = sftp.listdir()
print(files)
print()
sftp.close()
