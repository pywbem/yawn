#!/usr/bin/env python
"""
Script for launching YAWN as a standalone web broswer.
Note that this is rather for testing purposes, then for production.
"""

import argparse
import logging
from werkzeug.serving import run_simple
import pywbem_yawn

def parse_args():
    """
    Parses command line arguments.
    """
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
    return parser.parse_args()

def run_yawn(hostname, port, log_level,
        templates=None,
        modules=None,
        static_files=None,
        debug=False):
    """
    Uses werkzeug's run_simple function to run YAWN application as a daemon.
    @param debug whether to turn on werkzeug's debugger upon exception
    handling
    TODO: use module directory for real
    """
    log = logging.getLogger('root')

    handler = logging.StreamHandler()
    handler.setLevel('DEBUG')
    formatter = logging.Formatter(
            "%(asctime)s:%(levelname)s:%(lineno)d - %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(log_level.upper())
    log.debug('logging level set to: {}'.format(log_level))

    ylog = logging.getLogger(pywbem_yawn.__name__)
    ylog.addHandler(handler)
    ylog.setLevel(log_level.upper())

    if templates is not None:
        log.debug('templates directory : {}'.format(templates))
    if modules is not None:
        log.debug('modules directory   : {}'.format(modules))
    if static_files is None:
        static_files = (pywbem_yawn.__name__, 'static')
    log.debug('static files        : {}'.format(static_files))
    log.debug('using debugger      : {}'.format(
        'yes' if debug is True else 'no'))
    app = pywbem_yawn.Yawn(static_prefix='/static', debug=debug)
    return run_simple(hostname,
            port,
            app,
            static_files = { '/static': static_files },
            use_debugger = debug)

if __name__ == "__main__":
    ARGS = parse_args()
    run_yawn(**vars(ARGS))
