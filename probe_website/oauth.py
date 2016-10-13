from rauth import OAuth2Service
from flask import current_app, url_for, request, redirect, session
from probe_website import secret_settings


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
        print(self.get_callback_url())
        return redirect(self.service.get_authorize_url(
            scope='userid-feide',
            response_type='code',
            redirect_uri=self.get_callback_url())
        )

    def callback(self):
        if 'code' not in request.args:
            return None
        oauth_session = self.service.get_auth_session(
            data={'code': request.args['code'],
                  'grant_type': 'authorization_code',
                  'redirect_uri': self.get_callback_url()}
        )
        me = oauth_session.get('me?fields=userid-feide,email').json()
        return me
