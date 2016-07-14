ANSIBLE_PATH = '/home/frestr/Ansible/wifi_probe/'
DATABASE_PATH = '/home/frestr/Projects/probe_website/database.db'

CERTIFICATE_DIR = '/home/frestr/Ansible/wifi_probe/certs/'
ALLOWED_CERT_EXTENSIONS = set(['cer', 'ca'])

ERROR_MESSAGE = {
        'invalid_mac': (
            'The supplied MAC address was not valid or is already in use. '
        ),
        'invalid_scripts': (
            'One or more of the script configurations are invalid.'
        ),
        'invalid_network_config': (
            'One or more of the network configurations are invalid.'
        ),
        'invalid_database_settings': (
            'One or more of the network configurations are invalid.'
        ),
        'invalid_certificate': (
            'The supplied certificate file is invalid, or something went wrong when uploading it.'
        )
}
