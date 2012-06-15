#!/usr/bin/env python

import pywbem_yawn
from werkzeug.wsgi import SharedDataMiddleware

app = pywbem_yawn.Yawn()

application = SharedDataMiddleware(
        app,
        { '/static' : (pywbem_yawn.__name__, 'static') })

