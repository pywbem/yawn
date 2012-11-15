# Copyright (C) 2012 Red Hat, Inc.  All rights reserved.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2 of the GNU General Public License
# as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Authors: Michal Minar <miminar@redhat.com>

"""
Decorators for yawn methods meant for request processing rendering html
as result.
"""

import json
import logging
import pywbem
from werkzeug.exceptions import BadRequest
from pywbem_yawn import render

log = logging.getLogger(__name__)

GET, POST, GET_AND_POST = 1, 2, 3
def html_view(
        http_method      = GET,
        require_url      = True,
        require_ns       = True,
        returns_response = False):

    """
    Decorator for Yawn methods representing views. A view function takes
    parameters from GET or POST http methods, renders (x)html and
    returns it.

    @param http_method defines, which httpd methods are accepted by function
    @param require_url says, whether to raise BadRequest error, when url
    argument is missing
    @param require_ns says, whether to raise BadRequest error, when ns
    argument is missing
    @param returns_response seys, whether function returns whole response
    object (in case of True), or just a rendered (x)html string

    @return wrapped function
    """

    def _form_val(f, k, pop=True):
        v =  f.pop(k) if pop else f[k]
        if isinstance(v, list):
            if not len(v): return None
            return v[0]
        return v

    def _store_var(storage, req, var_name, required, form, args, kwargs):
        """
        params form and kwargs may get modified by this function
        """
        if getattr(storage, var_name, None) is not None: return
        setattr(storage, var_name, kwargs.pop(var_name, None))
        if http_method & GET:
            try: setattr(storage, var_name, req.args[var_name])
            except KeyError: pass
        if getattr(storage, var_name) is None and http_method & POST:
            try: setattr(storage, var_name, _form_val(form, var_name))
            except KeyError: pass
        if required and getattr(storage, var_name) is None:
            raise BadRequest("missing '%s' argument"%var_name)
        return getattr(storage, var_name)

    def _deco(f):
        def _new_f(self, *args, **kwargs):
            """
            @param self is instance of Yawn handler
            """
            req = self._local.request
            form = req.form.copy()
            for k in kwargs:
                if k in form:
                    del form[k]
            for var_name, required in ( ('url', require_url)
                                      , ('ns', require_ns)):
                _store_var(self._local, req, var_name, required,
                        form, args, kwargs)
            if http_method & POST:
                for k, v in form.items():
                    if isinstance(v, list):
                        if not len(v): continue
                        v = v[0]
                    kwargs[k] = v
            res = f(self, *args, **kwargs)
            if returns_response is True:
                return res
            self.response.data = res
            return self.response
        return _new_f

    return _deco

def json_view(f):
    """
    This is a decorator for Yawn methods representing async json views.
    These accept only http GET method and returns json string.

    If any exception in wrapped f occurs, a jason value:
        { "exception": [code, code_str, message] }
    is returned. Where:
        code     - is a number representing pywbem.CIMError
        code_str - is its string representation
        message  - is a more detailed description

    @param f must return a json dumpable python object

    @return werkzeug.wrappers.Response object
    """
    def _new_f(self, *args, **kwargs):
        """
        @param self is instance of Yawn handler
        """
        req = self._local.request
        try:
            for var_name in ('url', 'ns'):
                if not var_name in req.args:
                    raise BadRequest("missing %s argument"%var_name)
                setattr(self._local, var_name, req.args[var_name])
            res = f(self, *args, **kwargs)
        except Exception as e:
            if isinstance(e, pywbem.CIMError):
                code_str = render.cim_error2text[e.args[0]]
                res = { "exception": (e.args[0], code_str, e.args[1]) }
            else:
                code_str = str(e)
                res = { "exception": (-1, code_str, "") }
            if hasattr(e, "args") and len(args) >= 2:
                err_dscr = '%d (%s) - %s' % (e.args[0], code_str, e.args[1])
            else:
                err_dscr = code_str
            log.error('%s in json view "%s": %s"' % (
                "CIMError" if isinstance(e, pywbem.CIMError) else "Exception",
                f.__name__, err_dscr))
        self.response.headers["content-type"] = "application/json"
        self.response.data = json.dumps(res)
        return self.response
    return _new_f

