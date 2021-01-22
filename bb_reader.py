"""
BitBucket org data reader

Note(s):
    1. Requires Python 3
    2. https://docs.atlassian.com/bitbucket-server/rest/5.7.0/bitbucket-rest.html

"""
import json
import sys
import time
from collections import defaultdict

import oauthlib.oauth2
import requests
import requests_oauthlib
import yaml
from requests.packages.urllib3.exceptions import InsecureRequestWarning

import parameters
from cacheobj import CacheObject
from logger import get_logger


class BBFileLoadFailure(Exception):
    """
    Reading / loading a bitbucket file failed.
    """


class BBRequestAuthFail(Exception):
    """
    Bitbucket request failed due to auth failure.
    """


class RequestNotOK(Exception):
    """
    REST request to Bitbucket returned a status other than 'ok' (200)
    """


class BBDirReader(object):  # pylint: disable=too-many-instance-attributes
    """
    Encapsulate Bitbucket org/director retrieval.
    """
    def __init__(self, context_list, verify=False):
        """
        Initialize the BBDirReader object.

        :param context_list: list of projects (foundation)
        :param verify: 'verify' parameter passed to http requests
        :return:
        """
        params = parameters.SysParams()
        self._client_id = params['BB_CLIENT_ID']
        self._client_secret = params['BB_CLIENT_SECRET']
        self._auth_url = params['BB_OAUTH_URL']
        self._bb_rest = params['BB_REST_URL']
        self._bb_proj = params['BB_PROJECTS_URL']
        self._verify = verify
        self.logger = get_logger()

        # We (may) issue unverified http requests.  Turn off warnings
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        # Get the (initial) oauth token
        self._auth_token = self._get_oauth_token(self._client_id,
                                                 self._client_secret,
                                                 self._auth_url)

        # Pre-populate the cache with the repo names for each context
        if isinstance(context_list, str):
            # if context list was supplied as a string then allow 2 types
            # of separators.
            context_list = context_list.replace(',', ':').split(':')
        self._contexts = context_list
        self._cache_timestamp = None
        self._cache = self._make_cache()

    @property
    def cache(self):
        """
        Property returning current cache object.
        """
        return self._cache

    @property
    def status(self):
        """
        Return status information.
        """
        return {'cache_timestamp': self._cache_timestamp}

    @property
    def _http_header(self):
        """
        Construct/return and auth header for passing to Bitbucket, using
        the current auth token.
        """
        return {"Authorization": "bearer {}".format(self._auth_token)
               }

    def _request(self, url, return_json=False, _retry_=False):
        """
        Issue an http request to the given url.

        :param url: url to 'get'
        :param return_json: json-ize the return value
        :param _retry_: internal (recursion) flag, do not use in external calls
        :return: raw text or json of the request response.
        """
        self.logger.debug('Bitbucket request: %s', url)
        try:
            rsp = requests.get(url,
                               headers=self._http_header,
                               verify=self._verify)
        except requests.exceptions.SSLError as exn:
            # If auth failure then repeat the request
            self.logger.info('Request SSL error')
            self.logger.debug('Request SSL error: %s', exn)
            if not _retry_:
                self.logger.info('Re-auth and retry')
                self._auth_token = self._get_oauth_token(self._client_id,
                                                         self._client_secret,
                                                         self._auth_url)
                return self._request(url, return_json=return_json,
                                     _retry_=True)
            self.logger.info('Request failed on auth error')
            raise BBRequestAuthFail
        except:
            self.logger.debug('Request error: URL (%s)', url)
            self.logger.error('URL[%s] (%s, %s)', url, rsp.status_code, rsp.reason)
            raise
        else:
            if rsp.status_code == requests.codes.ok:
                rtn = rsp.json() if return_json else rsp.text
            else:
                self.logger.info("Request status %d: %s",
                                 rsp.status_code, rsp.reason)
                raise RequestNotOK
        return rtn

    def _bb_get_file(self, proj, slug, filename):
        """
        Get a (raw) file from Bitbucket.

        :param proj: the "project" name
        :param slug: the bitbucket "slug" (org)
        :param filename:
        :return: the raw file
        """
        url = "{}/{}/repos/{}/raw/{}".format(self._bb_proj,
                                             proj,
                                             slug,
                                             filename)
        self.logger.debug("Requesting file url %s", url)
        rtn = None
        try:
            rtn = self._request(url)
        except BBRequestAuthFail:
            self.logger.warning("Auth failure fetching Bitbucket file")
        except RequestNotOK:
            self.logger.warning("Request did not return 'ok'")
        except Exception as exn:
            self.logger.error("Unknown error requesting Bitbucket file: %s", exn)
        return rtn or ''

    def _bb_rest_get(self, command):
        """
        Send the given command to the Bitbucket REST API and return the
        response as JSON.

        :param command: the Bitbucket REST API command portion
        :return: response payload 'values' JSON
        """
        base_url = '{}/{}'.format(self._bb_rest, command)
        rtn = None
        try:
            rsp = {'isLastPage': False, 'nextPageStart': 0}
            rtn = []
            while not rsp['isLastPage']:
                url = "{}?start={}".format(base_url, rsp['nextPageStart'])
                self.logger.debug('[BB] get: %s', url)
                rsp = self._request(url, return_json=True)
                rtn.extend(rsp['values'])
        except BBRequestAuthFail:
            self.logger.warning("Auth failure accessing Bitbucket REST")
        except RequestNotOK:
            self.logger.warning("Request did not return 'ok'")
        except Exception as exn:
            self.logger.error("Unknown error from Bitbucket REST request: %s",
                              exn)
        return rtn or []

    def _get_repo_names(self, proj):
        """
        Get the names of the repos under the given project

        :param proj: project name (foundation)
        :return: list of repos
        """
        self.logger.debug('BB get repo names for %s', proj)
        repo_vals = self._bb_rest_get('{}/repos'.format(proj))
        if repo_vals:
            repo_names = [v['slug'] for v in repo_vals if v['name'].endswith('-org')]
        else:
            repo_names = []
        self.logger.debug('[BB] %s repo names: %s', proj, ','.join(repo_names))
        return repo_names

    def _get_oauth_token(self, client_id=None, client_secret=None, oauth_url=None):
        """
        Get a (new) auth token

        :param client_id: client id passed to OAuth
        :param client_secret: client secret passed to OAuth
        :param oauth_url: url of OAuth server
        :return: access token

        TODO: handle refresh to avoid getting new token each time.
        """
        try:
            client = oauthlib.oauth2.BackendApplicationClient(client_id=client_id)
            oauth = requests_oauthlib.OAuth2Session(client=client)
            token = oauth.fetch_token(token_url=oauth_url or self._auth_url,
                                      client_id=client_id or self._client_id,
                                      client_secret=client_secret or self._client_secret,
                                      verify=False)
            access_token = token['access_token']
        except Exception:
            self.logger.error("Failed retrieving access token from url %s", oauth_url)
            raise
        return access_token

    def _file_list(self, context, slug):
        """
        Get a list of file names in the repo for the given context/slug

        /rest/api/1.0/projects/{projectKey}/repos/{repositorySlug}/files
        """
        self.logger.debug('BB get file names for %s/%s', context, slug)
        url = '{}/repos/{}/files'.format(context, slug)
        filenames = self._bb_rest_get(url)
        if filenames:
            self.logger.debug('[BB] %s/%s file names: %s',
                              context, slug, ','.join(filenames))
        else:
            self.logger.debug('[BB] %s/%s no file names', context, slug)
        return filenames

    def _load_bb_file(self, context, slug, filename, json_content=False):
        """
        Read a Bitbucket yaml file and load it into a dict.

        :param context:
        :param slug:
        :param filename:
        :returns:
        """
        file_content = self._bb_get_file(context, slug, filename)
        try:
            content_dict = json.loads(file_content) \
                           if json_content else yaml.load(file_content)
        except:
            raise BBFileLoadFailure
        if not isinstance(content_dict, (dict, list)):
            self.logger.warning("Dictionary load of file failed %s/%s/%s (json %s)",
                                context, slug, filename, "yes" if json_content else "no")
            raise BBFileLoadFailure
        return content_dict

    def _make_cache(self):
        """
        Pop off the cache top level keys, and then recreate the
        cache with contexts/repo-names.
        """
        term = '-org'
        cache_obj = CacheObject()
        for ctxt in self._contexts:
            cache_obj[ctxt] = {r.lower()[:-len(term)]:
                               defaultdict(dict) for r in self._get_repo_names(ctxt)
                               if r.endswith(term)}
        return cache_obj

    def refresh(self):
        """
        Refresh the org lookup cache.

        Note that 'repo' may also be referred to in Bitbucket terminology as
        'slug'.

        The cache is arranged as:
            cache[context][slug]['org'] = {org dict},
                                ['space'] = {'spaces', 'security', 'space_config'},
        """
        start_time = time.time()
        start_str = time.strftime("%H:%M:%S", time.gmtime(start_time))
        self.logger.info("Refreshing cache from Bitbucket (%s)", start_str)
        new_cache = self._make_cache()

        for context, repolist in new_cache.items():
            self.logger.debug("Refresh: context %s", context)
            # 'sluglist' is the list of all orgs in the context. For example
            # projects/PCF_NPE/Agile-Studio-org, altoros_sow-org, and so on.
            # In the dictionary keys the trailing '-org' is stripped off.
            #
            # Each org represents a subdirectory. The subdirectory is expected
            # to contain an 'orgConfig.yml' and 'spaces.yml' file, as well as a
            # subdirectory for each space named in 'spaces.yml'.
            #
            # Each space subdirectory is expected to contain 2 files:
            # 'spaceConfig.yml' and 'security-group.json'.
            #
            # See https://bitbucket.service.edp.t-mobile.com/projects/PCF_NPE
            sluglist = ["{}-org".format(r) for r in repolist]
            for slug in sluglist:
                self.logger.debug("Refresh: slug %s", slug)
                try:
                    odict = self._load_bb_file(context, slug, 'orgConfig.yml')
                    repo = odict['org'].lower()
                except BBFileLoadFailure:
                    self.logger.warning("Failed to load config files")
                    continue
                except KeyError:
                    self.logger.warning("No orgConfig.yml [%s] %s", context, slug)
                    continue

                try:
                    sdict = self._load_bb_file(context, slug, 'spaces.yml')
                except  BBFileLoadFailure:
                    self.logger.warning("Failed to load spaces file")
                    sdict = defaultdict(dict)

                new_cache[context][repo]['org'] = odict
                new_cache[context][repo]['space'] = sdict

                for space in new_cache[context][repo]['space']['spaces']:
                    sec_name = "{}/security-group.json".format(space)
                    spc_name = "{}/spaceConfig.yml".format(space)

                    try:
                        sec_dict = self._load_bb_file(context, slug, sec_name,
                                                      json_content=True)
                        spc_dict = self._load_bb_file(context, slug, spc_name)
                    except  BBFileLoadFailure:
                        self.logger.warning("Failed to load space "
                                            "config/security files "
                                            "from %s/%s/%s",
                                            context, slug, space)
                        sec_dict = None
                        spc_dict = None
                    new_cache[context][repo][space]['security'] = sec_dict
                    new_cache[context][repo][space]['space_config'] = spc_dict

        # There is a window of time here during which the cache is being copied
        # in to and so is in an indeterminate state.  It should be non-critical
        # and so is allowed.
        old_size = sys.getsizeof(self._cache)
        copy_start = time.time()
        self._cache = dict(new_cache)
        del new_cache
        copy_elapsed = time.strftime("%H:%M:%S",
                                     time.gmtime(time.time() - copy_start))
        self.logger.debug("Cache copy time %s", copy_elapsed)
        self._cache_timestamp = time.time()
        refresh_elapsed = self._cache_timestamp - start_time
        elapsed_str = time.strftime("%H:%M:%S", time.gmtime(refresh_elapsed))
        self.logger.info("Refreshing cache completed (%s refresh_elapsed)",
                         elapsed_str)
        self.logger.info("Cache size: previous (%d), new (%d)", old_size, sys.getsizeof(self._cache))
