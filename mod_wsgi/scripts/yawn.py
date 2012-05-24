#!/usr/bin/env python

import argparse
import logging
from werkzeug.serving import run_simple
from pywbem_yawn import Yawn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="Yawn standalone daemon.")
#    parser.add_argument('-t', '--templates-dir',
#            help="directory with templates",
#            dest='templates', default='templates')
#    parser.add_argument('-m', '--module-dir',
#            dest="modules", default=None,
#            help="directory to use as cache for compiled templates")
    parser.add_argument('-p', '--port',
            dest="port", default=80, type=int,
            help="port on which to serve")
    parser.add_argument('--hostname',
            dest='hostname', default='localhost',
            help='the host for the application')
    parser.add_argument('-l', '--log-level',
            help='logging level', dest="log_level",
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            default='warning')
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

    ylog = logging.getLogger(Yawn.__module__)
    ylog.addHandler(handler)
    ylog.setLevel(ns.log_level.upper())

    #log.debug('templates directory : {}'.format(ns.templates))
    #log.debug('modules directory   : {}'.format(ns.modules))
    #app = Yawn(templates=ns.templates, modules=ns.modules)
    app = Yawn()
    #log.debug('serving on {}:{}'.format(ns.hostname, ns.port))
    run_simple(ns.hostname, ns.port, app)

