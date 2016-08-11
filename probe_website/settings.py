ANSIBLE_PATH = '/home/frestr/Ansible/wifi_probe/'
DATABASE_PATH = '/home/frestr/Projects/probe_website/database.db'

CERTIFICATE_DIR = '/home/frestr/Ansible/wifi_probe/certs/'
ALLOWED_CERT_EXTENSIONS = set(['cer', 'cert', 'ca', 'pem'])

ERROR_MESSAGE = {
        'invalid_mac': (
            'The supplied MAC address was not valid or is already in use. '
        ),
        'invalid_settings': (
            'One or more of the configurations are invalid.'
        ),
        'invalid_certificate': (
            'The supplied certificate file is invalid, or something went wrong when uploading it.'
        ),
        'fill_out_network_credentials': (
            'Please fill out the network credentials for {} before pushing configuration.'
            '(Click the Edit button to the right)'
        )
}

INFO_MESSAGE = {
        'ansible_already_running': (
            'Update is already in progress. Please wait for it to complete before '
            'trying to update again.'
        )
}

PROBE_ASSOCIATION_PERIOD = 20*60  # In seconds, i.e. 20*60 = 20 minutes
