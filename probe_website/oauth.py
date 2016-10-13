from rauth import OAuth2Service
from flask import current_app, url_for, request, redirect, session
from probe_website import secret_settings
import json


class DataportenSignin():
    def __init__(self):
        self.service = OAuth2Service(
            name='dataporten',
            client_id=secret_settings.OAUTH_CREDENTIALS['id'],
            client_secret=secret_settings.OAUTH_CREDENTIALS['secret'],
            authorize_url='https://auth.dataporten.no/oauth/authorization',
            access_token_url='https://auth.dataporten.no/oauth/token',
            base_url='https://auth.dataporten.no/'
        )

    def get_callback_url(self):
        return url_for('oauth_callback', _external=True)

    def authorize(self):
        return redirect(self.service.get_authorize_url(
            scope='userid-feide profile email',
            response_type='code',
            redirect_uri=self.get_callback_url())
        )

    def callback(self):
        if 'code' not in request.args:
            return None
        try:
            oauth_session = self.service.get_auth_session(
                data={'code': request.args['code'],
                      'grant_type': 'authorization_code',
                      'redirect_uri': self.get_callback_url()},
                decoder=lambda x: json.loads(x.decode())
            )
        except KeyError:
            return None
        userinfo = oauth_session.get('userinfo').json()
        if ('user' in userinfo and
                'userid_sec' in userinfo['user'] and
                'name' in userinfo['user'] and
                'email' in userinfo['user']):
            return userinfo['user']
        return None
