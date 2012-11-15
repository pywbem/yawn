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
Utilities and functions for template rendering.
"""
import base64
import cPickle
import datetime
from collections import defaultdict
import mako.lookup
import mako.exceptions
import pywbem
import types
import zlib

cim_error2text = defaultdict(lambda: "OTHER_ERROR", {
    1  : "FAILED",
    2  : "ACCESS_DENIED",
    3  : "INVALID_NAMESPACE",
    4  : "INVALID_PARAMETER",
    5  : "INVALID_CLASS",
    6  : "NOT_FOUND",
    7  : "NOT_SUPPORTED",
    8  : "CLASS_HAS_CHILDREN",
    9  : "CLASS_HAS_INSTANCES",
    10 : "INVALID_SUPERCLASS",
    11 : "ALREADY_EXISTS",
    12 : "NO_SUCH_PROPERTY",
    13 : "TYPE_MISMATCH",
    14 : "QUERY_LANGUAGE_NOT_SUPPORTED",
    15 : "INVALID_QUERY",
    16 : "METHOD_NOT_AVAILABLE",
    17 : "METHOD_NOT_FOUND"
})

def render_cim_error_msg(err):
    if not isinstance(err, pywbem.CIMError):
        raise TypeError("err must be a CIMError")
    errstr = err[1]
    if errstr.startswith('cmpi:'):
        errstr = errstr[5:]
    elif 'cmpi:Traceback' in errstr:
        errstr = errstr.replace('cmpi:Traceback', 'Traceback')
    errstr = errstr.replace('<br>', '\n').replace('&lt;br&gt;', '\n')
    return errstr

class Renderer:
    """
    A context manager used to encapsulate pywbem calls obtaining information
    for template rendering. If a pywbem CIMError occurs, it renders given
    template with error variable. Otherwise renders a template.

    Usage:
        with Renderer(lookup, "template_name.mako", **kwargs) as r:
           connection.GetInstance(...) # get informations
           ...
           r["var_name"] = val1        # set template variables
           r["var_name"] = val2
        return r.result                # rendered html (even in case
                                       # of exception)
    """

    def __init__(self, lookup, template, debug=False, **kwargs):
        if not isinstance(lookup, mako.lookup.TemplateLookup):
            raise TypeError("lookup must be an instance of"
                    " mako.lookup.TemplateLookup")
        if not isinstance(template, basestring):
            raise TypeError("template must be a string with the"
                    " name of template to render")
        self._debug = debug
        self._lookup = lookup
        self._template = template
        self._template_kwargs = kwargs
        # if any exception occurs within the render
        # context, this variable is set to (exc_type, exc_value, exc_tb)
        self._exception = None
        self._result = None

    @property
    def lookup(self):
        return self._lookup

    @property
    def template(self):
        return self._template

    @property
    def template_kwargs(self):
        return self._template_kwargs.copy()

    @template_kwargs.setter
    def template_kwargs(self, kwargs):
        self._template_kwargs = kwargs
        return kwargs

    @property
    def result(self):
        if self._result is None:
            template = self._lookup.get_template(self._template)
            if (  self._exception is not None
               and self._exception[0] is not pywbem.CIMError):
                self._result = mako.exceptions.html_error_template().render()
            else:
                ks = self._template_kwargs
                if self._exception is not None: # pywbem.CIMError
                    exc_type, exc_val, exc_tb = self._exception
                    ks["cim_error"] = "%d (%s)" % (exc_val.args[0],
                            cim_error2text[exc_val.args[0]])
                    ks["cim_error_msg"] = render_cim_error_msg(exc_val)
                self._result = template.render(**ks)
        return self._result

    def __enter__(self):
        self._exception = None
        self._result = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._exception = (exc_type, exc_val, exc_tb)
            if self._debug and exc_type is not pywbem.CIMError:
                # if debugger is turned on, let it do the job
                return False
            if exc_type == pywbem.cim_http.AuthError:
                # do not handle Authentication
                return False
        return True

    def __contains__(self, key): return key in self._template_kwargs
    def __len__(self): return len(self._template_kwargs)
    def __getitem__(self, key): return self._template_kwargs[key]
    def __setitem__(self, key, val):
        self._template_kwargs[key] = val
        return val

# encodes python object to base64 encoding (used for CIMInstanceNames)
encode_reference = lambda x: (base64.urlsafe_b64encode(
    zlib.compress(cPickle.dumps(x, cPickle.HIGHEST_PROTOCOL))))

class SafeString(unicode):
    """
    when this type of string is passed to template, it will be not escaped
    upon rendering if safe param is True
    """
    def __init__(self, text):
        unicode.__init__(self, text)
        self.safe = True

def val2str(x):
    if x is None:
        return SafeString('<span class="null_val">Null</span>')
    if isinstance(x, pywbem.CIMDateTime):
        x = x.timedelta if x.is_interval else x.datetime
    if isinstance(x, datetime.datetime):
        x = x.strftime("%Y/%m/%d %H:%M:%S.%f")
    elif isinstance(x, datetime.date):
        x = x.strftime("%Y/%m/%d")
    elif isinstance(x, datetime.time):
        x = x.strftime("%H:%M:%S.%f")
    if isinstance(x,list):
        rval = '{'
        if x:
            for i in range(0, len(x)):
                item = x[i]
                if i > 0:
                    rval+= ', '
                strItem = val2str(item)
                if type(item) in types.StringTypes:
                    strItem = '"' + strItem + '"'
                rval+= strItem
        rval+= '}'
        return rval
    return unicode(x)

def mapped_value2str(val, quals):
    rval = ''
    if isinstance(val, list):
        rval+= '{'
        valList = val
    else:
        valList = [val]
    valmapQual = quals['valuemap'].value
    valuesQual = quals['values'].value
    for i in valList:
        if i is not valList[0]:
            rval += ', '
        propstr = val2str(i)
        rval+= propstr
        if propstr in valmapQual:
            valIdx = valmapQual.index(propstr)
            if valIdx < len(valuesQual):
                rval+= ' ('+valuesQual[valIdx]+')'
    if isinstance(val, list):
        rval+= '}'
    return SafeString(rval)

