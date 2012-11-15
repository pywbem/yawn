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
Various utilities.
"""
import inspect
import re

def cmp_pnames(klass):
    """
    compare function for sorting property names placing keys before non-keys
    """
    def _cmp(a, b):
        is_key = lambda key: (
                    klass and klass.properties.has_key(key)
                and klass.properties[key].qualifiers.has_key('key'))
        is_key_a = is_key(a)
        is_key_b = is_key(b)
        if is_key_a and is_key_b:
            return cmp(a, b)
        if is_key_a and not is_key_b:
            return -1
        if not is_key_a and is_key_b:
            return 1
        return cmp(a, b)
    return _cmp

def cmp_params(klass):
    """
    compare function for class properties represented as python
    dictionaries
    """
    _cmp_orig = cmp_pnames(klass)
    def _cmp(a, b):
        if a['is_method'] and not b['is_method']:
            return -1
        if not a['is_method'] and b['is_method']:
            return 1
        return _cmp_orig(a['name'], b['name'])
    return _cmp

GET, POST, GET_AND_POST = 1, 2, 3
def view(
        http_method      = GET,
        require_url      = True,
        require_ns       = True,
        returns_response = False):

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

_re_url_func = re.compile(r'^[A-Z][a-z_A-Z0-9]+$')
def base_script(request):
    """
    @return base url of yawn application
    """
    global url_funcs
    path_parts = [p for p in
        request.environ['SCRIPT_NAME'].split('/') if p ]
    if len(path_parts) and  _re_url_func.match(path_parts[-1]):
        try:
            if inspect.isfunction(eval(path_parts[-1])):
                path_parts.pop(len(path_parts) - 1)
        except: pass
    if len(path_parts) and path_parts[-1].startswith('index.'):
        path_parts.pop(len(path_parts[-1]))
    return "/" + "/".join(path_parts)

def get_user_pw(request):
    if 'Authorization' not in request.headers:
        return (None, None)
    auth = request.authorization
    return (auth.username, auth.password)
