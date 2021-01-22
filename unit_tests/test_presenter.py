"""
Unit tests for the org-mgmt presenter module.
"""
import unittest

from collections import defaultdict
from mock import patch, MagicMock

import presenter

#pylint: disable=protected-access, invalid-name

class TestOrgMgmtREST(unittest.TestCase):
    """
    Test basic operation of the OrgMgmtREST subclass of RESTObject.
    """
    def setUp(self):
        """
        Test setups: patch out functions across all tests.
        """
        self._cache = defaultdict(dict)
        self.mock_logger = patch('logger.get_logger').start()
        self.mock_register = patch('restobj.RESTObject.register_multiple_endpoints').start()
        self.mock_jsonify = patch('flask.jsonify').start()
        self.mock_reader = patch('bb_reader.BBDirReader').start()

    def tearDown(self):
        """
        Test teardowns: clean up test-wide patches.
        """
        patch.stopall()

    def testObjectInit(self):
        """
        Validate the object initialization.
        """
        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        self.mock_register.assert_called_once()

    def testShowHelp(self):
        """
        Validate the object 'show_help' function.
        """
        om_rest = presenter.OrgMgmtREST(self._cache)
        info = om_rest._show_help()
        help = {"/contexts/<context>/[orgs/[<org_name>]]/[spaces/[<space_name>]]": "reports",
                "/contexts/<context>/orgs_metadata/[<org_name>]": "metadata",
                "/contexts/<context>/orgs/<org_name>/director": "org/director mapping",
                "/reader_status": "status of Bitbucket reader cache"}
        self.assertEqual(info, help)

    def testRefresh(self):
        """
        Validate the object cache refresh functionality.
        """
        mock_refresh = MagicMock()

        om_rest = presenter.OrgMgmtREST(self._cache)
        om_rest._cache_refresh = mock_refresh
        rtn = om_rest._refresh_cache()
        mock_refresh.assert_called_once()
        self.assertEqual(rtn, 'Cache refresh in progress')

    def testListContexts(self):
        """
        Validate the object context listing functionality.
        """
        contexts = ['a', 'b', 'c', 'd']
        self.mock_reader.cache = {k: n for n, k in enumerate(contexts)}
        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        rtn = om_rest._list_contexts()
        self.assertEqual(rtn, contexts)

    def testOrgsMetadataSingle(self):
        """
        Validate the org metadata (bulk download) functionality.
        """
        context = 'my_context'
        org = 'org1'
        director = 'george lucas'
        self.mock_reader.cache = {context: {org: {'org':
                                                  {'metadata':
                                                   {'director': director}}}}}
        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        rtn = om_rest._org_metadata(context, org)
        desired_rtn = {org: {'director': director}}
        self.assertEqual(rtn, desired_rtn)

    def testOrgsMetadataAll(self):
        """
        Validate the org metadata (bulk download) functionality.
        """
        context = 'my_context'
        orgs = ['org1', 'org2']
        director = 'george lucas'
        self.mock_reader.cache = {context:
                                  {o: {'org':
                                       {'metadata': {'director':
                                                     director}}} for o in orgs}}
        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        rtn = om_rest._org_metadata(context)
        desired_rtn = {o: {'director': director} for o in orgs}
        self.assertEqual(rtn, desired_rtn)

    def testListOrgs(self):
        """
        Validate the object org listing functionality.
        """
        context = 'my_context'
        orgs = ['org1', 'org2']
        self.mock_reader.cache = {context: {o: n for n, o in enumerate(orgs)}}
        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        rtn = om_rest._list_orgs(context)
        desired_rtn = {'context': context,
                       'orgs': orgs}
        self.assertEqual(rtn, desired_rtn)

    def testListSpaces(self):
        """
        Validate the object space listing functionality.
        """
        context = 'my_context'
        org = 'my_org'
        spaces = ['space1', 'space2']
        self.mock_reader.cache = {context: {org: {'space': {'spaces': spaces}}}}

        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        rtn = om_rest._list_spaces(context, org)
        desired_rtn = {'context': context,
                       'org': org,
                       'spaces': spaces}
        self.assertEqual(rtn, desired_rtn)

    def testGetDirector(self):
        """
        Validate the object 'get_director' functionality.
        """
        context = 'my_context'
        org = 'my_org'
        director = 'george lucas'
        self.mock_reader.cache = {context:
                                  {org: {'org':
                                         {'metadata': {'director': director}}}}}
        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        rtn = om_rest._get_director(context, org)
        desired_rtn = {'org': org, 'director': director}
        self.assertEqual(rtn, desired_rtn)

    def testGetOrg(self):
        """
        Validate the object 'get_org' functionality.
        """
        context = 'my_context'
        org = 'my_org'
        spaces = ['space1', 'space2']
        self.mock_reader.cache = {context: {org: {'space': {'spaces': spaces},
                                                  'org': "some org data"}}}

        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        rtn = om_rest._get_org(context, org)
        desired_rtn = {'context': context,
                       'org': org,
                       'space': {'spaces': spaces},
                       'org_config': "some org data",
                      }
        self.assertEqual(rtn, desired_rtn)

    def testGetSpace(self):
        """
        Validate the object 'get_space' functionality.
        """
        context = 'my_context'
        org = 'my_org'
        space = 'my_space'
        spc_config = 'my space config'
        spc_secy = 'some space security'
        self.mock_reader.cache = {context: {org: {space: {'space_config': spc_config,
                                                          'security': spc_secy}}}}

        om_rest = presenter.OrgMgmtREST(self.mock_reader)
        rtn = om_rest._get_space(context, org, space)
        desired_rtn = {'context': context,
                       'org': org,
                       'space': space,
                       'space_config': spc_config,
                       'security_group': spc_secy,
                      }
        self.assertEqual(rtn, desired_rtn)

    def testV1Refresh(self):
        """
        Validate the rest endpoint: /v1/refresh
        """
        om_rest = presenter.OrgMgmtREST(self._cache)
        value = "some value"
        with patch('presenter.OrgMgmtREST._refresh_cache',
                   return_value=value) as mock_refresh:
            om_rest._version_1(components=["refresh"])

        mock_refresh.assert_called_once()
        self.mock_jsonify.assert_called_once_with(value)

    def testV1Contexts(self):
        """
        Validate the rest endpoint: /v1/contexts
        """
        om_rest = presenter.OrgMgmtREST(self._cache)
        value = "some value"
        with patch('presenter.OrgMgmtREST._list_contexts',
                   return_value=value) as mock_list_contexts:
            om_rest._version_1(components=["contexts"])

        mock_list_contexts.assert_called_once()
        self.mock_jsonify.assert_called_once_with(value)

    def testV1ContextsOrgs(self):
        """
        Validate the rest endpoint: /v1/contexts/<ctxt>/orgs
        """
        om_rest = presenter.OrgMgmtREST(self._cache)
        value = "some value"
        with patch('presenter.OrgMgmtREST._list_orgs',
                   return_value=value) as mock_list_orgs:
            om_rest._version_1(components=["contexts",
                                           "ctxt_name",
                                           "orgs"])

        mock_list_orgs.assert_called_once_with('ctxt_name')
        self.mock_jsonify.assert_called_once_with(value)

    def testV1ContextsOrg(self):
        """
        Validate the rest endpoint: /v1/contexts/<ctxt>/orgs/<org>
        """
        om_rest = presenter.OrgMgmtREST(self._cache)
        value = "some value"
        with patch('presenter.OrgMgmtREST._get_org',
                   return_value=value) as mock_get_org:
            om_rest._version_1(components=["contexts",
                                           "ctxt_name",
                                           "orgs",
                                           "org_name"])

        mock_get_org.assert_called_once_with("ctxt_name", "org_name")
        self.mock_jsonify.assert_called_once_with(value)

    def testV1Director(self):
        """
        Validate the rest endpoint: /v1/contexts/<ctxt>/orgs/<org>/director
        """
        om_rest = presenter.OrgMgmtREST(self._cache)
        value = "some value"
        with patch('presenter.OrgMgmtREST._get_director',
                   return_value=value) as mock_get_director:
            om_rest._version_1(components=["contexts",
                                           "ctxt_name",
                                           "orgs",
                                           "org_name",
                                           "director"])

        mock_get_director.assert_called_once_with("ctxt_name", "org_name")
        self.mock_jsonify.assert_called_once_with(value)

    def testV1ContextsOrgsSpaces(self):
        """
        Validate the rest endpoint: /v1/contexts/<ctxt>/orgs/<org>/spaces
        """
        om_rest = presenter.OrgMgmtREST(self._cache)
        value = "some value"
        with patch('presenter.OrgMgmtREST._list_spaces',
                   return_value=value) as mock_list_spaces:
            om_rest._version_1(components=["contexts",
                                           "ctxt_name",
                                           "orgs",
                                           "org_name",
                                           "spaces"])

        mock_list_spaces.assert_called_once_with("ctxt_name", "org_name")
        self.mock_jsonify.assert_called_once_with(value)

    def testV1ContextsOrgsSpace(self):
        """
        Validate the rest endpoint: /v1/contexts/<ctxt>/orgs/<org>/spaces/<space>
        """
        om_rest = presenter.OrgMgmtREST(self._cache)
        value = "some value"
        with patch('presenter.OrgMgmtREST._get_space',
                   return_value=value) as mock_get_space:
            om_rest._version_1(components=["contexts",
                                           "ctxt_name",
                                           "orgs",
                                           "org_name",
                                           "spaces",
                                           "space_name"])

        mock_get_space.assert_called_once_with("ctxt_name", "org_name",
                                               "space_name")
        self.mock_jsonify.assert_called_once_with(value)

    def testV1Malformed(self):
        """
        Validate the malformed rest endpoints.
        This could also use the pytest.mark.parametrize() decorator.
        """
        bad_urls = ["foo", "contexts/nm/foo",
                    "contexts/nm/orgs/nm/foo"]
        om_rest = presenter.OrgMgmtREST(self._cache)

        for url in bad_urls:
            with patch('flask.abort') as mock_abort:
                om_rest._version_1(components=url.split('/'))
            mock_abort.assert_called_once_with(400, "Malformed URL API version 1")
