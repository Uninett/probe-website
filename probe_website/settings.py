ANSIBLE_PATH = '/home/frestr/Ansible/wifi_probe/'
DATABASE_PATH = '/home/frestr/Projects/probe_website/database.db'
RELATIVE_IMAGE_PATH = '../image_generation/modified_kali-1.1.2-rpi2.img'

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
            'Please fill out the network credentials for {} before pushing configuration. '
            '(Click the Edit button to the right)'
        ),
        'fill_out_database_credentials': (
            'Please fill out the database credentials. '
            '(Under the \'Databases\' tab)'
        )
}

INFO_MESSAGE = {
        'ansible_already_running': (
            'Update is already in progress. Please wait for it to complete before '
            'trying to update again.'
        ),
        'shutdown_warning': (
            'It is important to shut the probes down properly, to avoid file '
            'corruption. The probes will also not start WiFi probing if an ethernet '
            'cable has been connected (to avoid doing probing over cable '
            'instead of WiFi). Therefore the probes need to be restarted before '
            'WiFi probing can begin. Go to the front page to read how to do that properly.'
        ),
        # This should not be a flash message, but rather a part of some kind of
        # documentation on the web site

        # 'shutdown_instructions': (
        #     'To shut a probe down, follow this procedure:'
        #     '   1. Pull out the ethernet cable.'
        #     '   2. Pull out the WiFi dongle. This will shut down the probe.'
        #     '   3. Wait until the green light on the Raspberry Pi stops blinking '
        #     '      (and is constantly green).'
        #     '   4. Pull out the power cable.'
        #     '   5. Insert the WiFi dongle again (but not the ethernet cable)'
        #     'The probe will now automatically start probing when power is reconnected.'
        # )
}

PROBE_ASSOCIATION_PERIOD = 20*60  # In seconds, i.e. 20*60 = 20 minutes
