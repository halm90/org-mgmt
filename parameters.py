"""
bb_org application-wide parameters
"""
import os

DEFAULT_LOG_LEVEL = 'DEBUG'
DEFAULT_TOOL_PORT = 8080

DEFAULT_DBFILE = 'orginfo.db'
DEFAULT_REFRESH_PERIOD = 4 * 60 * 60

DEFAULT_BB_REST_VERSION = '1.0'
DEFAULT_BB_BASE_URL = 'https://bitbucket.service.edp.t-mobile.com'
DEFAULT_BB_PROJECTS = '{}/projects'.format(DEFAULT_BB_BASE_URL)
DEFAULT_BB_REST = '{}/rest/api/{}/projects'.format(DEFAULT_BB_BASE_URL,
                                                   DEFAULT_BB_REST_VERSION)

DEFAULT_CONTEXTS = ['PCF_NPE', 'PCF_PRD', 'PCF_CDE']

class Singleton(type):
    """
    Basic singleton type
    """
    def __call__(cls, *args, **kwargs):
        """
        Override the type 'call'
        """
        try:
            return cls.__instance
        except AttributeError:
            cls.__instance = super().__call__(*args, **kwargs)
            return cls.__instance

class SysParams(dict, metaclass=Singleton):
    """
    A utility class intended to hold all system-wide and configurable
    parameters.
    """
    _required_env = ['BB_CLIENT_ID', 'BB_CLIENT_SECRET', 'BB_OAUTH_URL']

    _overridable = {
        'LOG_LEVEL': DEFAULT_LOG_LEVEL,
        'REFRESH_PERIOD': DEFAULT_REFRESH_PERIOD,
        'DB_FILE': DEFAULT_DBFILE,
        'BB_PROJECTS_URL': DEFAULT_BB_PROJECTS,
        'BB_REST_URL': DEFAULT_BB_REST,
        'BB_REQUEST_VERIFY': False,
        'REST_PORT': DEFAULT_TOOL_PORT,
        'CONTEXTS': DEFAULT_CONTEXTS,
    }

    def __init__(self):
        #  Get required environment variables, fail if any are missing.
        missing = []
        for key in self._required_env:
            try:
                self[key] = os.environ[key]
            except KeyError:
                missing.append(key)
        if missing:
            print("ERROR: missing environment variable(s): {}".format(missing))
            exit(1)

        #  Get optional/overridable environment variables
        self.update({key: os.getenv(key, val) for
                     key, val in self._overridable.items()})
