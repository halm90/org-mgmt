"""
PCF team tool Custom exceptions
"""


"""
REST object errors.
"""
class AlreadyRegistered(Exception):
    """
    Exception raised attempting to register an endpoint already registered.
    """
    def __init__(self, msg):
        super().__init__('Endpoint "{}" is already registered'.format(msg))


class NoSuchEndpoint(Exception):
    """
    Exception raised attempting to de-register an unregistered endpoint.
    """
    def __init__(self, msg):
        super().__init__('No such registered endpoint "{}"'.format(msg))


class CannotUnregister(Exception):
    """
    Some endpoints cannot be unregistered.
    """
    def __init__(self, msg):
        super().__init__('Cannot unregister endpoint "{}"'.format(msg))


"""
Authorization and permission errors.
"""
class GetTokenFailedException(Exception):
    """
    Failure getting authorization access token.
    """

class RequestFailedAuthorization(Exception):
    """
    An HTTP request failed due to OATH token failure (expiration).
    """


"""
CloudFoundry related custom exceptions.
"""
class CFOrgException(Exception):
    """
    CloudFoundry error fetching org info.
    """

"""
Cache object errors.
"""
class CacheNotFound(Exception):
    """
    The requested item was not found in the cache.
    """

class SQLNoColumns(Exception):
    """
    A request for conversion of SQL query result to dictionary was
    made, but no mapping of column names was given.
    """

class SQLMissingParameter(Exception):
    """
    Attempted to create an SQL interface object, but missing
    required connection parameter(s).
    """
