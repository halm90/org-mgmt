"""
T-Mobile PCF team org_mgmt caching object

Note(s):
    1. Requires Python 3
    2. Agent/fetchers that need a cache object can instantiate the cache object
       to get a simple key/value pair dictionary cache.

TODO:
    1. The object is (currently) a basic Python dictionary.  When a
       better (persistent) type is decided on this object will represent
       the API.  So in other words if mySQL is used then this object can
       present a dictionary-like interface to it.  Current thinking is that
       a simple Python 'mdb' may suffice.
"""
from collections import defaultdict

from logger import get_logger

class CacheObject(defaultdict):
    """
    Class implementing org mgmt cache for the org_mgmt application.
    """
    def __init__(self, *args, **kwargs):
        """
        Basic initialization for the cache object
        """
        self.logger = get_logger()
        self.logger.debug("Creating CacheObject base")
        super().__init__(defaultdict, *args, **kwargs) #pylint: disable=missing-super-argument
