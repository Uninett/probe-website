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
        )
}
