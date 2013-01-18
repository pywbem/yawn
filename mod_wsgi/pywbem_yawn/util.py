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

def is_selinux_running():
    try:
        import selinux
        if selinux.security_getenforce() < 0:
            return False
    except (ImportError, OSError):
        return False
    return True
