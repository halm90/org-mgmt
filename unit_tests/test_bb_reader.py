"""
Unit tests for the org-mgmt Bitbucket interface module.
"""
from collections import defaultdict

import json
import logging
import unittest
import pytest
import requests
import yaml

from mock import patch, MagicMock, call
from testfixtures import LogCapture

import bb_reader

#pylint: disable=protected-access, invalid-name

class TestDirReader(unittest.TestCase):
    """
    Test basic operation of the BBDirReader class object.
    """
    _env_dict = {'BB_CLIENT_ID': 'client id',
                 'BB_CLIENT_SECRET': 'cient secret',
                 'BB_OAUTH_URL': 'oauth url',
                 'BB_REST_URL': 'rest url',
                 'BB_PROJECTS_URL': 'projects url',
                }
    _context = ['this', 'is', 'a', 'context']
    _names = ['namea-org', 'nameb-org', 'namec-org']

    def setUp(self):
        """
        Test setups: patch out functions across all tests.
        """
        patch('bb_reader.BBDirReader._get_repo_names',
              return_value=self._names).start()
        patch('parameters.SysParams', return_value=self._env_dict).start()

    def tearDown(self):
        """
        Test teardowns: clean up test-wide patches.
        """
        patch.stopall()

    @patch('bb_reader.BBDirReader._get_oauth_token')
    @patch('logger.get_logger')
    def testInitListContext(self, _, mock_auth):
        """
        Test the init function with CONTEXT as a list of strings.
        """
        with patch('cacheobj.CacheObject') as mock_cache, \
             patch('parameters.SysParams', return_value=self._env_dict):

            bb_reader.BBDirReader(self._context, mock_cache)

        mock_auth.assert_called_once_with(self._env_dict['BB_CLIENT_ID'],
                                          self._env_dict['BB_CLIENT_SECRET'],
                                          self._env_dict['BB_OAUTH_URL'])

    @patch('bb_reader.BBDirReader._get_oauth_token')
    @patch('logger.get_logger')
    def testInitStringContext(self, _, mock_auth):
        """
        Test the init function with CONTEXT as a string.
        """
        context = "a_string_context"

        with patch('cacheobj.CacheObject') as mock_cache, \
             patch('parameters.SysParams', return_value=self._env_dict):

            bb_reader.BBDirReader(context, mock_cache)

        mock_auth.assert_called_once_with(self._env_dict['BB_CLIENT_ID'],
                                          self._env_dict['BB_CLIENT_SECRET'],
                                          self._env_dict['BB_OAUTH_URL'])

    @patch('bb_reader.BBDirReader._get_oauth_token')
    @patch('logger.get_logger')
    def testHeader(self, _, mock_auth):
        """
        Test the 'header' property.
        """
        token = "this is a token"
        with patch('parameters.SysParams', return_value=self._env_dict):
            reader = bb_reader.BBDirReader(self._context, MagicMock())
            reader._auth_token = token
            header = reader._http_header
        self.assertEqual(header, {"Authorization": "bearer {}".format(token)})

    @patch('bb_reader.BBDirReader._get_oauth_token')
    @patch('logger.get_logger')
    def testGetFile(self, _, mock_auth):
        """
        Test the "get_file" function.
        """
        proj = 'project'
        slug = 'slug'
        fname = 'filename'
        desired_url = "{}/{}/repos/{}/raw/{}".format(self._env_dict['BB_PROJECTS_URL'],
                                                     proj,
                                                     slug,
                                                     fname)

        with patch('bb_reader.BBDirReader._request') as mock_request:
            reader = bb_reader.BBDirReader(self._context, MagicMock())
            reader._bb_get_file(proj, slug, fname)

        mock_request.assert_called_once_with(desired_url)

    @patch('logger.get_logger')
    def testGetOauthTokenOK(self, _):
        """
        Test the _get_auth_token function.
        """
        appclient = "app client"
        mock_oauth = MagicMock()
        with patch('oauthlib.oauth2.BackendApplicationClient',
                   return_value=appclient) as mock_back, \
             patch('requests_oauthlib.OAuth2Session',
                   return_value=mock_oauth) as mock_auth2:
            bb_reader.BBDirReader(self._context, MagicMock())

        mock_auth2.assert_called_once_with(client=appclient)
        mock_back.assert_called_once_with(client_id=self._env_dict['BB_CLIENT_ID'])

        mock_oauth.fetch_token.assert_called_once_with(
                    client_id=self._env_dict['BB_CLIENT_ID'],
                    client_secret=self._env_dict['BB_CLIENT_SECRET'],
                    token_url=self._env_dict['BB_OAUTH_URL'],
                    verify=False)

    @patch('bb_reader.BBDirReader._get_oauth_token')
    @patch('logger.get_logger')
    def testMakeCache(self, _, mock_auth):
        """
        Test the _make_cache function.
        """
        context = 'Context'
        orgs = ['orgA-org', 'orgB-org', 'orgC-org', 'not_an_org']
        with patch('cacheobj.CacheObject') as mock_cache, \
             patch('parameters.SysParams', return_value=self._env_dict), \
             patch('bb_reader.BBDirReader._get_repo_names',
                   return_value=orgs):
            reader = bb_reader.BBDirReader(context)
            returned_cache = reader._make_cache()

        trm = '-org'
        desired_cache = defaultdict(defaultdict,
                                    {context:
                                     {o.lower()[:-len(trm)]: defaultdict(dict)
                                     for o in orgs if o.endswith(trm)}})
        self.assertEqual(desired_cache, returned_cache)

    @patch('bb_reader.BBDirReader._get_oauth_token')
    @patch('logger.get_logger')
    def testRefresh(self, _, mock_auth):
        """
        Test the _refresh function.
        """
        test_cache = defaultdict(dict)
        context = 'Context'
        contexts = {'context1': ['repo1']}
        for ctxt, repos in contexts.items():
            test_cache[ctxt] = {r: defaultdict(dict) for r in repos}

        orgyml = yaml.load("repo1orgtag1: true\n" +
                           "repo1orgtag2: someval\n" +
                           "org: repo1\n")
        spcyml = yaml.load("org: repo1\n" +
                           "spaces:\n" +
                           "- r1space1\n" +
                           "- r1space2\n")

        spc1secjson = json.loads('[{"dest": "dest1",\n' +
                                 '  "proto": "all"},\n' +
                                 ' {"dest": "dest2",\n' +
                                 '  "proto": "all"}\n' +
                                 ']')
        spc2secjson = json.loads('[{"dest": "dest3",\n' +
                                 '  "proto": "some"},\n' +
                                 ' {"dest": "dest4",\n' +
                                 '  "proto": "some"}\n' +
                                 ']')


        spc1cfgyml = yaml.load("sometag2: false\n" +
                               "sometag3: whatever\n" +
                               "org: tst-org\n")

        spc2cfgyml = yaml.load("sometag4: false\n" +
                               "sometag5: whatever\n" +
                               "org: tst-org\n")

        get_files = [orgyml, spcyml,
                     spc1secjson, spc1cfgyml,
                     spc2secjson, spc2cfgyml]

        with patch('bb_reader.BBDirReader._load_bb_file') as mock_load_file, \
             patch('parameters.SysParams', return_value=self._env_dict):
            mock_load_file.side_effect = get_files
            reader = bb_reader.BBDirReader(context)
            reader._make_cache = MagicMock(return_value=test_cache)
            reader.refresh()

        gf_calls = [call('context1', 'repo1-org', 'orgConfig.yml'),
                    call('context1', 'repo1-org', 'spaces.yml'),
                    call('context1', 'repo1-org', 'r1space1/security-group.json',
                         json_content=True),
                    call('context1', 'repo1-org', 'r1space1/spaceConfig.yml'),
                    call('context1', 'repo1-org', 'r1space2/security-group.json',
                         json_content=True),
                    call('context1', 'repo1-org', 'r1space2/spaceConfig.yml')]
        mock_load_file.assert_has_calls(gf_calls)

        desired_cache = {'context1':
                            {'repo1':
                                {'space':
                                    {'spaces': ['r1space1', 'r1space2'],
                                     'org': 'repo1'},
                                 'org': {'repo1orgtag1': True,
                                         'repo1orgtag2': 'someval',
                                         'org': 'repo1'},
                                 'r1space1': {'space_config': {'org': 'tst-org',
                                                               'sometag2': False,
                                                               'sometag3': 'whatever'},
                                              'security': [{'proto': 'all',
                                                            'dest': 'dest1'},
                                                           {'proto': 'all',
                                                            'dest': 'dest2'}]},
                                 'r1space2': {'space_config': {'sometag4': False,
                                                               'sometag5': 'whatever',
                                                               'org': 'tst-org'},
                                              'security': [{'proto': 'some',
                                                            'dest': 'dest3'},
                                                           {'proto': 'some',
                                                            'dest': 'dest4'}]
                                             }
                                }
                            }
                        }
        self.assertEqual(reader._cache, desired_cache)


class TestReaderRequest(unittest.TestCase):
    """
    Test 'request' method.
    """
    _env_dict = {'BB_CLIENT_ID': 'client id',
                 'BB_CLIENT_SECRET': 'cient secret',
                 'BB_OAUTH_URL': 'oauth url',
                 'BB_REST_URL': 'rest url',
                 'BB_PROJECTS_URL': 'projects url',
                }
    _names = ['name1', 'name2', 'name3']
    _context = ['a', 'b', 'c', 'd']
    _token = 'dummy token'

    def setUp(self):
        """
        Test setups: patch out functions across all tests.
        """
        patch('bb_reader.BBDirReader._get_oauth_token',
              return_value=self._token).start()
        patch('parameters.SysParams', return_value=self._env_dict).start()
        patch('bb_reader.BBDirReader._get_repo_names',
              return_value=self._names).start()

    def tearDown(self):
        """
        Test teardowns: clean up test-wide patches.
        """
        patch.stopall()

    def testResponseOK(self):
        """
        Test the happiest path through the _request function
        """
        req_url = "this/is/a/test"
        rsp_text = 'some text'
        rsp_reason = 'no excuses'
        class RespObj():
            status_code = 200
            text = rsp_text
            reason = rsp_reason
        get_resp = RespObj()
        with patch('requests.get', return_value=get_resp) as mock_get:
            reader = bb_reader.BBDirReader(self._context)
            resp = reader._request(req_url)
        self.assertEqual(resp, rsp_text)

    def testResponseSimpleNOK(self):
        """
        Test the _request function: simple non-ok response
        """
        req_url = "this/is/a/test"
        rsp_text = 'some text'
        rsp_reason = 'no excuses'
        class RespObj():
            status_code = 400
            text = rsp_text
            reason = rsp_reason
        get_resp = RespObj()
        with patch('requests.get', return_value=get_resp) as mock_get, \
             pytest.raises(bb_reader.RequestNotOK), \
             LogCapture(level=logging.INFO) as info_log:
            reader = bb_reader.BBDirReader(self._context)
            reader._request(req_url)
        desired_msg = 'Request status 400: {}'.format(rsp_reason)
        info_log.check(('org_mgmt', 'INFO', desired_msg),)

    def testRequestException(self):
        """
        Test the _request function: request raises general exception

        Note that because the exception is raised in the mock there is
        no response and no valid log message we can test against.
        """
        req_url = "this/is/a/test"
        rsp_text = 'some text'
        rsp_reason = 'no excuses'
        class RespObj():
            status_code = 400
            text = rsp_text
            reason = rsp_reason
        RespObj()
        with patch('requests.get') as mock_get:
            reader = bb_reader.BBDirReader(self._context)
            mock_get.side_effect = Exception
            with pytest.raises(Exception):
                reader._request(req_url)

    def testRequestAuthFail(self):
        """
        Test the _request function: request raises SSL/auth exception twice
        """
        req_url = "this/is/a/test"
        rsp_text = 'some text'
        rsp_reason = 'no excuses'
        class RespObj():
            status_code = 400
            text = rsp_text
            reason = rsp_reason
        RespObj()
        with patch('requests.get') as mock_get, \
             patch('requests.codes.unauthorized'), \
             LogCapture(level=logging.INFO) as info_log:
            reader = bb_reader.BBDirReader(self._context)
            mock_get.side_effect = requests.exceptions.SSLError
            with pytest.raises(bb_reader.BBRequestAuthFail):
                reader._request(req_url)

        info_log.check(('org_mgmt', 'INFO', 'Request SSL error'),
                       ('org_mgmt', 'INFO', 'Re-auth and retry'),
                       ('org_mgmt', 'INFO', 'Request SSL error'),
                       ('org_mgmt', 'INFO', 'Request failed on auth error'))


class TestBBApi(unittest.TestCase):
    """
    Test the Bitbucket API facing functions.
    """
    _env_dict = {'BB_CLIENT_ID': 'client id',
                 'BB_CLIENT_SECRET': 'cient secret',
                 'BB_OAUTH_URL': 'oauth url',
                 'BB_REST_URL': 'rest url',
                 'BB_PROJECTS_URL': 'projects url',
                }
    _names = ['name1', 'name2', 'name3']
    _context = ['a', 'b', 'c', 'd']

    def setUp(self):
        """
        Test setups: patch out functions across all tests.
        """
        patch('bb_reader.BBDirReader._get_oauth_token').start()
        patch('parameters.SysParams', return_value=self._env_dict).start()

    def tearDown(self):
        """
        Test teardowns: clean up test-wide patches.
        """
        patch.stopall()

    def testRestGetOnePage(self):
        """
        Test the rest request with 1 page response.
        """
        command = 'test command'
        rtn_vals = [1, 2, 3]
        req_resp = {'isLastPage': True, 'nextPageStart': 0, 'values': rtn_vals}
        with patch('bb_reader.BBDirReader._request',
                   return_value=req_resp) as mock_request, \
             patch('bb_reader.BBDirReader._get_repo_names',
                   return_value=self._names):
            reader = bb_reader.BBDirReader(self._context)
            retn = reader._bb_rest_get(command)

        self.assertEqual(retn, rtn_vals)
        url = '{}/{}?start=0'.format(self._env_dict['BB_REST_URL'], command)
        mock_request.assert_called_once_with(url, return_json=True)


    def testRestGetTwoPages(self):
        """
        Test the rest request with 2 page response.
        """
        command = 'test command'
        rtn_vals1 = [1, 2, 3]
        rtn_vals2 = [4, 5, 6]
        req_resp = [{'isLastPage': False, 'nextPageStart': 10, 'values': rtn_vals1},
                    {'isLastPage': True, 'nextPageStart': 0, 'values': rtn_vals2}]
        with patch('bb_reader.BBDirReader._request',
                   side_effect=req_resp) as mock_request, \
             patch('bb_reader.BBDirReader._get_repo_names',
                   return_value=self._names):
            reader = bb_reader.BBDirReader(self._context)
            retn = reader._bb_rest_get(command)

        self.assertEqual(retn, rtn_vals1 + rtn_vals2)
        url = '{}/{}?start='.format(self._env_dict['BB_REST_URL'], command)
        mock_request.assert_has_calls([call(url + '0', return_json=True),
                                       call(url + '10', return_json=True)],
                                      any_order=True)

    def testGetRepo(self):
        """
        Test the _get_repo_names function.
        """
        badnames = ['name1', 'name2', 'name3']
        goodnames = ['name4-org', 'name5-org', 'name6-org']
        names = badnames + goodnames
        rest_rtn = [{'slug': v, 'name': v} for v in names]
        with patch('bb_reader.BBDirReader.__init__', return_value=None), \
             patch('bb_reader.BBDirReader._bb_rest_get', return_value=rest_rtn):
            reader = bb_reader.BBDirReader(self._context)
            reader.logger = MagicMock()
            retn = reader._get_repo_names('project name')

        self.assertEqual(retn, goodnames)
