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

_LOG = logging.getLogger(__name__)

GET, POST, GET_AND_POST = 1, 2, 3

def _convert(val, to=str):
    """
    Convert value given as string to particular python data type.

    @param val: Value to convert.
    @param to: Type factory.
    """
    if to is bool:
        return (   isinstance(val, (str, bytes))
               and val.lower() in ('1', 'true', 'y', 'yes', 'on'))
    if to is str:
        if isinstance(val, str):
            return val
        elif isinstance(val, bytes):
            return val.decode()
        else:
            return str(val)
    return to(val)

COMMON_ARGUMENTS = (
            ('url', 'url', True, str, None),
            ('ns', 'namespace', True, str, None),
            ('verify', 'verify', False, bool, False)
)

def html_view(
        http_method      = GET,
        require_url      = True,
        require_namespace= True,
        returns_response = False):
    """
    Decorator for Yawn methods representing views. A view function takes
    parameters from GET or POST http methods, renders (x)html and
    returns it.

    @param http_method defines, which httpd methods are accepted by function
    @param require_url says, whether to raise BadRequest error, when url
    argument is missing
    @param require_namespace says, whether to raise BadRequest error, when
    ns argument is missing
    @param returns_response seys, whether function returns whole response
    object (in case of True), or just a rendered (x)html string

    @return wrapped function
    """

    def _form_val(form, key, pop=True):
        """
        @return value from form and optionally removes it
        """
        value = form.pop(key) if pop else form[key]
        if isinstance(value, list):
            if not len(value):
                return None
            return value[0]
        return value

    def _store_var(storage, req, var_name, store_as,
            required, as_type, default, form, kwargs):
        """
        Params form and kwargs may get modified by this function.
        """
        if getattr(storage, store_as, None) is not None:
            return
        val = kwargs.pop(var_name, None)
        setattr(storage, store_as,
                _convert(val, as_type) if val is not None else val)
        if http_method & GET and var_name in req.args:
            setattr(storage, store_as, _convert(req.args[var_name], as_type))
        if      (   getattr(storage, store_as) is None
                and http_method & POST
                and var_name in form):
            setattr(storage, store_as,
                    _convert(_form_val(form, var_name), as_type))
        if getattr(storage, store_as) is None:
            if required:
                raise BadRequest("missing '%s' argument" % var_name)
            setattr(storage, store_as, default)
        return getattr(storage, store_as)

    def _deco(func):
        """
        This is a wrapper, that calls function func.
        """

        def _new_f(self, *args, **kwargs):
            """
            @param self is instance of Yawn handler
            """
            req = self._local.request
            form = req.form.copy()
            for k in kwargs:
                if k in form:
                    del form[k]
            for var_name, store_as, required, as_type, default in \
                    COMMON_ARGUMENTS:
                if var_name == 'url':
                    required = require_url
                elif var_name == 'ns':
                    required = require_namespace
                _store_var(self._local, req, var_name, store_as,
                        required, as_type, default, form, kwargs)
            if http_method & POST:
                for k, value in form.items():
                    if isinstance(value, list):
                        if not len(value):
                            continue
                        value = value[0]
                    kwargs[k] = value
            assert isinstance(self._local.namespace, str), "_new_f"
            res = func(self, *args, **kwargs)
            if returns_response is True:
                return res
            self.response.data = res
            return self.response
        return _new_f

    return _deco

def json_view(func):
    """
    This is a decorator for Yawn methods representing async json views.
    These accept only http GET method and returns json string.

    If any exception in wrapped func occurs, a jason value:
        { "exception": [code, code_str, message] }
    is returned. Where:
        code     - is a number representing pywbem.CIMError
        code_str - is its string representation
        message  - is a more detailed description

    @param func must return a json dumpable python object

    @return werkzeug.wrappers.Response object
    """
    def _new_f(self, *args, **kwargs):
        """
        @param self is instance of Yawn handler
        """
        req = self._local.request
        try:
            for var_name, store_as, required, as_type, default in \
                    COMMON_ARGUMENTS:
                if required and var_name not in req.args:
                    raise BadRequest("missing '%s' argument" % var_name)
                setattr(self._local, store_as, req.args.get(var_name, default))
            res = func(self, *args, **kwargs)
        except Exception as exc:  #pyling: disable=W0703
            if isinstance(exc, pywbem.CIMError):
                code_str = render.CIM_ERROR2TEXT[exc.args[0]]
                res = { "exception": (exc.args[0], code_str, exc.args[1]) }
            else:
                code_str = str(exc)
                res = { "exception": (-1, code_str, "") }
            if hasattr(exc, "args") and len(args) >= 2:
                err_dscr = '%d (%s) - %s' % (exc.args[0], code_str, exc.args[1])
            else:
                err_dscr = code_str
            _LOG.error('%s in json view "%s": %s"' % (
                "CIMError" if isinstance(exc, pywbem.CIMError) else "Exception",
                func.__name__, err_dscr))
        self.response.headers["content-type"] = "application/json"
        self.response.data = json.dumps(res)
        return self.response

    return _new_f

