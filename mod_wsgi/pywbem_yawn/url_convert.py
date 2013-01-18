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
Custom URL converters to obtain information from parts of url.
"""

from pywbem_yawn import inputparse
from pywbem_yawn import render
from werkzeug.routing import BaseConverter

class IdentifierConverter(BaseConverter):
    """
    Used for identifier names in url.
    Example: CIM_ElementName
    """

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = r'[a-zA-Z_][a-zA-Z0-9_]*'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value

class Base64Converter(BaseConverter):
    """
    Used for encoded object in base64 format in url.
    """

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = (r'(?:[A-Za-z0-9_-]{4})*(?:[A-Za-z0-9_-]{2}'
                      r'==|[A-Za-z0-9_-]{3}=)?')

    def to_python(self, value):
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        return inputparse.decode_reference(value)

    def to_url(self, value):
        if isinstance(value, basestring):
            return value
        return render.encode_reference(value)

class QLangConverter(BaseConverter):
    """
    Used for names of query languages like WQL.
    """

    QLANG_WQL = 0
    query_languages = ["WQL"]

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = r'(?i)(?:WQL)'

    def to_python(self, value):
        return { 'wql' : QLangConverter.QLANG_WQL }[value.lower()]

    def to_url(self, value):
        return QLangConverter.query_languages[value]

