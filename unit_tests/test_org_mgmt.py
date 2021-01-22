"""
Unit tests for the org-mgmt (main) module.
"""
import unittest

from mock import patch, MagicMock

import org_mgmt

#pylint: disable=invalid-name, no-self-use

class TestThreadWorker(unittest.TestCase):
    """
    Test basic operation of the worker thread.
    """
    def testWorkerNoRefresh(self):
        """
        Test the worker thread with no refresh.
        """
        with patch('bb_reader.BBDirReader') as mock_reader, \
             patch('cacheobj.CacheObject') as mock_cache, \
             patch('threading.Timer') as mock_timer, \
             patch('parameters.SysParams', return_value={'REFRESH_PERIOD': 0}):
            org_mgmt.LOGGER = MagicMock()
            org_mgmt.bb_thread_worker(mock_reader)

        mock_reader.refresh.assert_called_once()
        mock_timer.assert_not_called()

    def testWorkerRefresh(self):
        """
        Test the worker thread with no refresh.
        """
        rfsh = 10
        with patch('bb_reader.BBDirReader') as mock_reader, \
             patch('cacheobj.CacheObject') as mock_cache, \
             patch('threading.Timer') as mock_timer, \
             patch('parameters.SysParams', return_value={'REFRESH_PERIOD': rfsh}):
            org_mgmt.LOGGER = MagicMock()
            org_mgmt.bb_thread_worker(mock_reader)

        mock_reader.refresh.assert_called_once()
        mock_timer.assert_called_once_with(rfsh,
                                           org_mgmt.bb_thread_worker,
                                           args=(mock_reader,))
