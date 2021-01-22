"""
bb_org logger functions.
"""
import logging
import os
import sys

DEFAULT_APPNAME = 'org_mgmt'
DEFAULT_LOG_LEVEL = 'INFO'


def get_logger(appname=None, level=None):
    """
    Get a logger object for application-wide use.
    """
    avail_levels = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO,
                    'WARNING': logging.WARNING, 'ERROR': logging.ERROR,
                    'CRITICAL': logging.CRITICAL}

    appname = appname or os.environ.get('APPNAME', DEFAULT_APPNAME)
    loglevel = str(level or os.environ.get('LOG_LEVEL', DEFAULT_LOG_LEVEL)).upper()

    logger = logging.getLogger(appname)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    if loglevel in avail_levels:
        logger.setLevel(avail_levels[loglevel])
    else:
        print("Can't set log level to {}".format(loglevel))
    return logger
