#!/usr/bin/env python

import argparse
import logging
import pkg_resources
from werkzeug.serving import run_simple
import pywbem_yawn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="Yawn standalone daemon.")
    parser.add_argument('-p', '--port',
            dest="port", default=80, type=int,
            help="port on which to serve")
    parser.add_argument('--hostname',
            dest='hostname', default='localhost',
            help='the host for the application')
    parser.add_argument('-t', '--templates-dir',
            help="directory with templates",
            dest='templates', default=None)
    parser.add_argument('-m', '--module-dir',
            dest="modules", default=None,
            help="directory to use as cache for compiled templates")
    parser.add_argument('-s', '--static-files',
            help='path to directory with static files',
            default=None, dest='static_files')
    parser.add_argument('-l', '--log-level',
            help='logging level', dest="log_level",
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            default='warning')
    parser.add_argument('-d', '--debug',
            help="enable debugging", dest="debug",
            action='store_true')
    ns = parser.parse_args()

    log = logging.getLogger('root')

    handler = logging.StreamHandler()
    handler.setLevel('DEBUG')
    formatter = logging.Formatter(
            "%(asctime)s:%(levelname)s:%(lineno)d - %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(ns.log_level.upper())
    log.debug('logging level set to: {}'.format(ns.log_level))

    ylog = logging.getLogger(pywbem_yawn.__name__)
    ylog.addHandler(handler)
    ylog.setLevel(ns.log_level.upper())

    if ns.templates is not None:
        log.debug('templates directory : {}'.format(ns.templates))
    if ns.modules is not None:
        log.debug('modules directory   : {}'.format(ns.modules))
    sf = ns.static_files
    if sf is None:
    # pkg_resources.resource_filename(pywbem_yawn.__name__, 'static')
        sf = (pywbem_yawn.__name__, 'static')
    log.debug('static files        : {}'.format(sf))
    log.debug('using debugger      : {}'.format(
        'yes' if ns.debug is True else 'no'))
    #app = Yawn(templates=ns.templates, modules=ns.modules)
    app = pywbem_yawn.Yawn(static_prefix='/static', debug=ns.debug)
    #log.debug('serving on {}:{}'.format(ns.hostname, ns.port))
    run_simple(ns.hostname, ns.port, app, static_files={ '/static': sf },
            use_debugger=ns.debug)

