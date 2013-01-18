#!/usr/bin/env python

"""
Wrapper for running YAWN application under web server like
apache.
"""

import pywbem_yawn
from werkzeug.wsgi import SharedDataMiddleware

application = SharedDataMiddleware(
        pywbem_yawn.Yawn(),
        { '/static' : (pywbem_yawn.__name__, 'static') })

