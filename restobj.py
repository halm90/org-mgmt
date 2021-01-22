"""
T-Mobile PCF team generic REST object.

Note(s):
    1. Requires Python 3
    2. For Flask API see: http://flask.pocoo.org/docs/0.11/api
"""
import threading
from datetime import datetime
from sortedcontainers import SortedDict

from flask import Flask, jsonify, request

from excepts import AlreadyRegistered, NoSuchEndpoint, CannotUnregister
from logger import get_logger

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'

class Endpoint(object):
    """
    Constructor for defining REST endpoint(s).

    :param name: endpoint
    :param handler: handler function
    :param description: endpoint description
    :param filters: filters recognized by endpoint handler
    :param show_help: function to return endpoint specific help
    """
    def __init__(self, name, handler, description=None, filters=None,
                 show_help=None):
        """
        Setup the endpoint object internal variables.
        """
        self._name = name
        self._handler = handler
        self._filters = filters
        self._descr = description
        self._helper = show_help
        if filters:
            filter_str = "(filter(s): {})".format(', '.join(filters))
            self._descr = "{} {}".format(description, filter_str)
        super().__init__()

    @property
    def name(self):
        """
        Endpoint name (url extension)
        """
        return self._name

    @property
    def description(self):
        """
        Description of the endpoint used for 'help'
        """
        return self._descr

    @property
    def handler(self):
        """
        Function called for handling the endpoint.
        """
        return self._handler

    @property
    def show_help(self):
        """
        Function to return endpoint specific help
        """
        return self._helper


class RESTObject(object):
    """
    This class is meant to be a base (or mixin) class.  It provides
    a general REST interface which allows the subclass to register any
    enpoint and handler that it wishes.
    """
    _commands = {}
    _flaskapp = None

    def __init__(self, port=None, service_name=None, autostart=False,
                 name='endpoints'):
        """
        Register endpoints and start up the flask listening thread.
        """
        self._default_endpoints = [
            #  Basic command enpoints
            Endpoint('/', self._cmd_status),
            Endpoint('status', self._cmd_status, 'service status'),
            Endpoint('__empty', self._cmd_status),
            Endpoint('showall', self._cmd_show_all, 'show registered commands'),
            Endpoint('help', self._cmd_show_all, 'show registered commands'),
        ]
        self._default_epoint_names = [ep.name for ep in self._default_endpoints]
        self.logger = get_logger()

        self.logger.debug("Creating RESTObject")
        self._service_name = service_name
        self._flask_port = port
        self._host_ip = '0.0.0.0'
        self._name = name
        self._start_time = datetime.now().strftime(DATE_FORMAT)

        # See: http://flask.pocoo.org/docs/0.11/api/#url-route-registrations
        self._flaskapp = Flask(__name__)

        self.logger.debug("RESTObject registering default endpoints")
        for epoint in self._default_endpoints:
            self._flaskapp.add_url_rule('/{}'.format(epoint.name),
                                        epoint.name,
                                        view_func=epoint.handler)

        self.logger.debug("RESTObject adding flask rules")
        self._flaskapp.add_url_rule('/',
                                    view_func=self._service_request,
                                    defaults={'rest_request': '__empty'})
        self._flaskapp.add_url_rule('/<path:rest_request>',
                                    view_func=self._service_request)
        if autostart:
            self.logger.debug("RESTObject create thread object")
            self._flask_thread = threading.Thread(target=self.start,
                                                  args=(),
                                                  kwargs={})
            self.logger.debug("RESTObject starting background thread and flask app")
            self._flask_thread.start()

    def start(self, *args, **kwargs):   #pylint: disable=unused-argument
        """
        Run the flask thread.
        """
        hostaddr = kwargs.get('host', self._host_ip)
        portnum = kwargs.get('port', self._flask_port)
        self.logger.debug("RESTObject starting flask app on %s:%s", hostaddr, str(portnum))
        self._flaskapp.run(host=hostaddr, port=portnum)

    def register_multiple_endpoints(self, endpoints):
        """
        Register several endpoints.
        """
        for epoint in endpoints:
            self.register_endpoint(epoint)

    def register_endpoint(self, endpoint):
        """
        Register a (new) monitoring endpoint.
        """
        if endpoint.name in self._commands.keys():
            raise AlreadyRegistered(endpoint.name)

        self.logger.debug("RESTObject register endpoint %s", endpoint.name)
        self._commands[endpoint.name] = endpoint

    def unregister_endpoint_by_name(self, endpoint_name):
        """
        Unregister a monitoring endpoint (by name).
        """
        if endpoint_name in [ep.name for ep in self._default_endpoints]:
            raise CannotUnregister(endpoint_name)

        if endpoint_name not in self._commands:
            raise NoSuchEndpoint(endpoint_name)

        self.logger.debug('RESTObject unregister endpoint "%s"', endpoint_name)
        self._commands.pop(endpoint_name)

    # # #
    # The following commands are used by this base class and are
    # not to be called by inheriting (child) classes.
    def _cmd_status(self, *args):     #  pylint: disable=unused-argument
        """
        Default/builtin command: service state.
        """
        rtn_dict = {'state': 'up',
                    'start_time': self._start_time,
                    'current_time': datetime.now().strftime(DATE_FORMAT)
                   }
        if hasattr(self, 'version'):
            rtn_dict['version'] = self.version
        if hasattr(self, 'status'):
            status = self.status() if callable(self.status) else self.status
            if status:
                rtn_dict['status'] = self.status() if callable(self.status) else self.status
        return jsonify(rtn_dict)

    def _cmd_show_all(self, *args):  #  pylint: disable=unused-argument
        """
        command: show all registered commands.
        """
        showlist = SortedDict({'default': {ep.name:ep.description \
                                           for ep \
                                           in self._default_endpoints if ep.description}})

        showlist[self._name] = SortedDict({nm:ep.show_help() if ep.show_help \
                                              else ep.description \
                                           for nm, ep in self._commands.items()})
        return jsonify(showlist)

    @staticmethod
    def _unknown_request(rest_req, **kwargs):
        """
        Handle requests to unregistered endpoint(s).
        """
        return jsonify('No such endpoint: <{}>'.format(rest_req))

    def _service_request(self, rest_request):
        """
        Generic request handler: intercept all http requests and dispatch
        to the handler registered for that endpoint.
        """
        try:
            components = rest_request.rstrip('/').split('/')
            cmd = components.pop(0)
            handler = self._commands[cmd].handler
        except KeyError:
            handler = self._unknown_request

        return handler(rest_req=rest_request,
                       components=components,
                       query=request.args,
                      )
