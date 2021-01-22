"""
T-Mobile PCF team "Org Management" tool

Note(s):
    1. Requires Python 3
    2. A fetcher thread periodically pulls organization data from Bitbucket
       and refreshes a cache of org data.
    3. A REST thread presents a REST API to that cache.  It handles incoming
       REST requests and responds with data from the cache.
    4. <app>/v1/context/<context>/org/<org>/space/<space>
    5. Operation:
        - instantiate a cache object
        - instantiate a BBDirReader object
        - instantiate an OrgMgmtREST object
        - start the DirReader thread to fill the cache.  It will (re)schedule
          itself
        - start the REST object (which handles incoming REST requests
"""
import threading

from bb_reader import BBDirReader
from logger import get_logger
from presenter import OrgMgmtREST

#from parameters import SysParams
import parameters

LOGGER = None


def bb_thread_worker(bbreader):
    """
    Thread worker periodically wakes up to refresh org cache.
    :param bbreader: the reader object which reads from BB
    :param cache: the cache object which the reader updates
    :return:

    """
    LOGGER.info("BitBucket periodic (timed) gather")
    refresh_period = int(parameters.SysParams()['REFRESH_PERIOD'])
    try:
        bbreader.refresh()
    except Exception as exn:
        # TODO: capture exit-worthy errors (such as ctl-c) and raise/exit
        LOGGER.error("Refresh failed: %s", exn)

    if refresh_period > 0:
        threading.Timer(refresh_period,
                        bb_thread_worker,
                        args=(bbreader,)).start()


def main():
    """
    Main function: instantiate the Bitbucket reader and REST objects
    and then launch the worker thread.  The thread wakes up periodically
    and tells the reader to refresh its cache.
    """
    global LOGGER

    LOGGER = get_logger()
    params = parameters.SysParams()

    # Instantiate the necessary objects
    reader_obj = BBDirReader(params['CONTEXTS'],
                             verify=params['BB_REQUEST_VERIFY'] == 'True')
    rest_obj = OrgMgmtREST(reader_obj,
                           service_name=__name__,
                           cache_refresh=reader_obj.refresh,
                           port=params['REST_PORT'])

    threading.Timer(0, bb_thread_worker, args=(reader_obj,)).start()
    rest_obj.start()

if __name__ == "__main__":
    main()
