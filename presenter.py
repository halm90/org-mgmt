"""
T-Mobile PCF team Cloud Foundry Org Management presentation

Note(s):
    1. Requires Python 3
    2. A separate 'fetcher' thread periodically pulls from BitBucket and
       refreshes a cache of org management data.  This application presents a
       REST API to that cache.

    3. <app>/v1/context/<context>/org/<org>/space/<space>
"""
from threading import Thread
import flask

from logger import get_logger
from restobj import RESTObject, Endpoint

ORG_MGMT_REST_VERSION = '1'

class V1MalformedURL(Exception):
    """
    V1 URL format is incorrect
    """

class RequestError(Exception):
    """
    context or org or space not found.
    """

class OrgMgmtREST(RESTObject):
    """
    The REST API: field incoming requests and dispatch to
    the appropriate handler.
    """
    version = ORG_MGMT_REST_VERSION

    def __init__(self, bb_reader,
                 service_name=None,
                 cache_refresh=None,
                 port=None):
        """
        Initialize the REST object.
        """
        self._v1_endpoints = [Endpoint('v1', self._version_1,
                                       show_help=self._show_help),
                             ]

        self.logger = get_logger()

        self.logger.debug("Initializing OrgMgmtREST object")
        super().__init__(port=port, service_name=service_name)
        self.logger.debug("Register endpoints")
        self.register_multiple_endpoints(self._v1_endpoints)

        self._bbreader = bb_reader
        self._cache_refresh = cache_refresh

    def _show_help(self):
        """
        Return the help message for all v1 queries
        """
        info = {"/contexts/<context>/[orgs/[<org_name>]]/[spaces/[<space_name>]]": "reports",
                "/contexts/<context>/orgs_metadata/[<org_name>]": "metadata",
                "/contexts/<context>/orgs/<org_name>/director": "org/director mapping",
                "/reader_status": "status of Bitbucket reader cache"}
        if self._cache_refresh:
            info['/refresh'] = "force cache refresh from BitBucket"
        return info

    def _refresh_cache(self):
        """
        Force the cache to refresh
        """
        if self._cache_refresh:
            Thread(target=self._cache_refresh).start()
            return "Cache refresh in progress"

    def _list_contexts(self):
        """
        Return a list of known contexts
        """
        return sorted(list(self._bbreader.cache.keys()))

    def _org_metadata(self, context, org_name=None):
        """
        Output all metadata for the given context.  Limit to the
        named org if one is given.
        """
        try:
            orgs = [org_name] if org_name \
                              else [nm for nm in self._bbreader.cache[context]]
            rtn = {org: self._bbreader.cache[context][org]['org'].get('metadata') \
                   for org in orgs}
        except KeyError:
            raise RequestError('No such context/org: {}/{}'.format(context, orgs))
        return rtn

    def _list_orgs(self, context):
        """
        Return a list of orgs in the given context and their last update time
        """
        try:
            rtn = {'context': context,
                   'orgs': sorted(list(self._bbreader.cache[context].keys()))}
        except KeyError:
            raise RequestError('Context {} not found'.format(context))
        return rtn

    def _list_spaces(self, context, org):
        """
        Return a list of space names in the given context/org
        """
        try:
            spaces = list(self._bbreader.cache[context][org]['space'].get('spaces', []))
            rtn = {'context': context,
                   'org': org,
                   'spaces': sorted(spaces)
                  }
        except KeyError:
            RequestError('No such context/org: {}/{}'.format(context, org))
        return rtn

    def _get_director(self, context, org):
        """
        Return the director for the given context/org.
        """
        try:
            dirnm = self._bbreader.cache[context][org]['org'].get('metadata',
                                                                  {}).get('director',
                                                                          'Unknown')
            rtn = {'org': org, 'director': dirnm}
        except KeyError:
            raise RequestError('No such context/org: {}/{}'.format(context, org))

        return rtn

    def _get_org(self, context, org):
        """
        Return orgConfig.yml contents for the given context/org.
        """
        try:
            rtn = {'context': context,
                   'org': org,
                   'space': self._bbreader.cache[context][org]['space'],
                   'org_config': self._bbreader.cache[context][org]['org'],
                  }
        except KeyError:
            raise RequestError('No such context/org: {}/{}'.format(context, org))

        return rtn

    def _get_space(self, context, org, space):
        """
        Return contents of the spaceConfig.yml and security-group.json for the
        specified space in the context/org
        """
        try:
            rtn = {'context': context,
                   'org': org,
                   'space': space,
                   'space_config': self._bbreader.cache[context][org][space]['space_config'],
                   'security_group': self._bbreader.cache[context][org][space]['security'],
                  }
        except KeyError:
            raise RequestError('No such context/org/space: {}/{}/{}'.format(context,
                                                                            org,
                                                                            space))
        return rtn

    def _version_1(self, rest_req=None, components=None, query=None, **kwargs):
        """
        Catch all v1 requests and dispatch to the appropriate handler.

        /contexts/<context>
        /contexts/<context>/orgs
        /contexts/<context>/orgs/org_name
        /contexts/<context>/orgs/org_name/spaces
        /contexts/<context>/orgs/org_name/spaces/space_name
        /contexts/<context]/orgs_metadata[/<org_name>]
        /refresh
        /reader_status

        Note: context is referred to elsewhere as foundation (PRD, NPE, CDE, ...)
        """
        context_name = None
        org_name = None
        space_name = None

        try:
            component = components.pop(0)
            if component == 'refresh' and not components:
                self.logger.info('Cache refresh explicitly requested')
                return flask.jsonify(self._refresh_cache())

            if component == 'reader_status' and not components:
                return flask.jsonify(self._bbreader.status)

            if component != 'contexts':
                raise V1MalformedURL
            if not components:
                # get all contexts and return (/contexts)
                self.logger.debug("Get all contexts")
                return flask.jsonify(self._list_contexts())
            context_name = components.pop(0)
            if not components:
                # list all orgs and return (/contexts/<name>)
                return flask.jsonify(self._list_orgs(context_name))

            component = components.pop(0)
            if component == 'orgs_metadata':
                # Send metadata for all orgs and return
                # (/contexts/<name>/org_metadata)
                if components:
                    org_name = components.pop(0).lower()
                else:
                    org_name = None
                return flask.jsonify(self._org_metadata(context_name, org_name))

            if component != 'orgs':
                raise V1MalformedURL
            if not components:
                # list all orgs and return (/contexts/<name>/orgs)
                self.logger.debug("List orgs for context %s", context_name)
                return flask.jsonify(self._list_orgs(context_name))
            org_name = components.pop(0).lower()
            if not components:
                #  get all orgs and return (/contexts/<name>/orgs/<org>)
                return flask.jsonify(self._get_org(context_name, org_name))

            component = components.pop(0)
            if component == 'director':
                # (/contexts/<name>/orgs/<org>/director)
                return flask.jsonify(self._get_director(context_name, org_name))

            if component != 'spaces':
                raise V1MalformedURL
            if not components:
                # list all spaces and return (/contexts/<name>/orgs/<org>/spaces)
                self.logger.debug("List spaces for context %s, org %s",
                                  context_name, org_name)
                return flask.jsonify(self._list_spaces(context_name, org_name))
            space_name = components.pop(0)
            # (/contexts/<name>/orgs/<org>/spaces/<spc>
            return flask.jsonify(self._get_space(context_name, org_name, space_name))

        except RequestError as exn:
            return flask.abort(400, exn.args)

        except (V1MalformedURL, IndexError):
            msg = 'Malformed URL API version {}'.format(self.version)
            if rest_req:
                msg += ": {}".format(rest_req)
            self.logger.info(msg)
            return flask.abort(400, msg)
