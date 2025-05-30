"""
Stack-In-A-Box: Requests-Mock Support
"""
from __future__ import absolute_import

import contextlib
import functools
import io
import logging
import re
import sys
import threading
import types

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse
import requests_mock
import requests_mock.response
import six

from stackinabox.stack import StackInABox
from stackinabox.util import deprecator
from stackinabox.util.requests_mock import reqcallable

try:
    import requests_mock.compat
except ImportError:
    pass


logger = logging.getLogger(__name__)


def session_registration(uri, session):
    """Requests-mock registration with a specific Session.

    :param uri: base URI to match against
    :param session: Python requests' Session object

    :returns: n/a
    """
    # log the URI that is used to access the Stack-In-A-Box services
    logger.debug('Registering Stack-In-A-Box at {0} under Python Requests-Mock'
                 .format(uri))
    logger.debug('Session has id {0}'.format(id(session)))

    # tell Stack-In-A-Box what URI to match with
    StackInABox.update_uri(uri)

    # Create a Python Requests Adapter object for handling the session
    StackInABox.hold_onto('adapter', requests_mock.Adapter())
    # Add the Request handler object for the URI
    StackInABox.hold_out('adapter').add_matcher(
        reqcallable.RequestMockCallable(uri)
    )

    if not uri.endswith('/'):
        uri += '/'

    # Tell the session about the adapter and the URI
    session.mount('http://{0}'.format(uri), StackInABox.hold_out('adapter'))
    session.mount('https://{0}'.format(uri), StackInABox.hold_out('adapter'))


def registration(uri):
    """Requests-mock registrationn.

    :param uri: base URI to match against

    :returns: n/a
    """

    # Use a global session object, and then use the session variant
    requests_mock_session_registration(uri,
                                       local_sessions.session)


def requests_request(method, url, **kwargs):
    """Requests-mock requests.request wrapper."""
    session = local_sessions.session
    response = session.request(method=method, url=url, **kwargs)
    session.close()
    return response


def requests_get(url, **kwargs):
    """Requests-mock requests.get wrapper."""
    kwargs.setdefault('allow_redirects', True)
    return requests_request('get', url, **kwargs)


def requests_options(url, **kwargs):
    """Requests-mock requests.options wrapper."""
    kwargs.setdefault('allow_redirects', True)
    return requests_request('options', url, **kwargs)


def requests_head(url, **kwargs):
    """Requests-mock requests.head wrapper."""
    kwargs.setdefault('allow_redirects', False)
    return requests_request('head', url, **kwargs)


def requests_post(url, data=None, json=None, **kwargs):
    """Requests-mock requests.post wrapper."""
    return requests_request('post', url, data=data, json=json, **kwargs)


def requests_put(url, data=None, **kwargs):
    """Requests-mock requests.put wrapper."""
    return requests_request('put', url, data=data, **kwargs)


def requests_patch(url, data=None, **kwargs):
    """Requests-mock requests.patch wrapper."""
    return requests_request('patch', url, data=data, **kwargs)


def requests_delete(url, **kwargs):
    """Requests-mock requests.delete wrapper."""
    return requests_request('delete', url, **kwargs)


class requests_session(requests.sessions.SessionRedirectMixin):
    """Requests-mock requests.Session wrapper."""

    def __init__(self):
        logger.debug('Session wrapper has id {0}'.format(id(self)))

    def __enter__(self):
        """requests.session.Session context entry wrapper."""
        return local_sessions.session

    def __exit__(self, *args):
        """requests.session.Session context exit wrapper."""
        local_sessions.session.close()

    def prepare_request(self, request):
        """Pyton requests.session.Session.prepare_request wrapper."""
        return local_sessions.session.prepare_request(request)

    def request(self, *args, **kwargs):
        """requests.session.Session.request wrapper."""
        return local_sessions.session.request(*args, **kwargs)

    def get(self, *args, **kwargs):
        """requests.session.Session.get wrapper."""
        return local_sessions.session.get(*args, **kwargs)

    def options(self, *args, **kwargs):
        """requests.session.Session.options wrapper."""
        return local_sessions.session.options(*args, **kwargs)

    def head(self, *args, **kwargs):
        """requests.session.Session.head wrapper."""
        return local_sessions.session.head(*args, **kwargs)

    def post(self, *args, **kwargs):
        """requests.session.Session.post wrapper."""
        return local_sessions.session.post(*args, **kwargs)

    def put(self, *args, **kwargs):
        """requests.session.Session.put wrapper."""
        return local_sessions.session.put(*args, **kwargs)

    def patch(self, *args, **kwargs):
        """requests.session.Session.patch wrapper."""
        return local_sessions.session.patch(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """requests.session.Session.delete wrapper."""
        return local_sessions.session.delete(*args, **kwargs)

    def send(self, *args, **kwargs):
        """requests.session.Session.send wrapper."""
        return local_sessions.session.send(*args, **kwargs)

    def merge_environment_settings(self, *args, **kwargs):
        """requests.session.Session.merge_environment_settings wrapper."""
        return local_sessions.session.merge_environment_settings(*args,
                                                                **kwargs)

    def get_adapter(self, *args, **kwargs):
        """requests.session.Session.get_adapter wrapper."""
        return local_sessions.session.get_adapter(*args, **kwargs)

    def close(self, *args, **kwargs):
        """requests.session.Session.close wrapper."""
        return local_sessions.session.close(*args, **kwargs)

    def mount(self, *args, **kwargs):
        """requests.session.Session.mount wrapper."""
        return local_sessions.session.mount(*args, **kwargs)

    def __getstate__(self, *args, **kwargs):
        """requests.session.Session.__getstate__ wrapper."""
        return local_sessions.session.__getstate__(*args, **kwargs)

    def __setstate__(self, *args, **kwargs):
        """requests.session.Session.__setstate__ wrapper."""
        return local_sessions.session.__setstate__(*args, **kwargs)


def get_session():
    """Access the global session object."""
    return local_sessions.session


class activate(object):
    """Requests-mock context object for Stack-In-A-Box."""

    def __init__(self):
        # Keep track of all the original functions that will
        # get replaced during a context operation
        self.__replacements = {
            'requests.request': requests.request,
            'requests.get': requests.get,
            'requests.options': requests.options,
            'requests.head': requests.head,
            'requests.post': requests.post,
            'requests.put': requests.put,
            'requests.patch': requests.patch,
            'requests.delete': requests.delete,
            'requests.session': requests.session,
            'requests.Session': requests.Session,
            'requests.sessions.Session': requests.sessions.Session
        }

    def __enter__(self):
        """Setup the context to use the Stack-In-A-Box variants."""
        logger.debug('Using session with id {0}'
                     .format(id(local_sessions.session)))
        requests.request = requests_request
        requests.get = requests_get
        requests.options = requests_options
        requests.head = requests_head
        requests.post = requests_post
        requests.put = requests_put
        requests.patch = requests_patch
        requests.delete = requests_delete
        requests.session = local_sessions.session
        requests.Sesssion = requests_session
        requests.sessions.Sesssion = requests_session

    def __exit__(self, exc_type, exc_value, traceback):
        """Exiting the context and restore the originals"""
        logger.debug('Stopping session with id {0}'
                     .format(id(local_sessions.session)))
        requests.session = self.__replacements['requests.session']
        requests.Session = self.__replacements['requests.Session']
        requests.sessions.Session = self.__replacements[
            'requests.sessions.Session']

        requests.delete = self.__replacements['requests.delete']
        requests.patch = self.__replacements['requests.patch']
        requests.put = self.__replacements['requests.put']
        requests.post = self.__replacements['requests.post']
        requests.head = self.__replacements['requests.head']
        requests.options = self.__replacements['requests.options']
        requests.get = self.__replacements['requests.get']
        requests.request = self.__replacements['requests.request']

        # Create a new session for next time
        local_sessions.session = Session()


# the Global session data
local_sessions = threading.local()
local_sessions.session = Session()


@deprecator.DeprecatedInterface("requests_mock_registration", "registration")
def requests_mock_registration(uri):
    return registration(uri)


@deprecator.DeprecatedInterface(
    "requests_mock_session_registration", "session_registration"
)
def requests_mock_session_registration(uri, session):
    return session_registration(uri, session)
