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
from werkzeug.routing import BaseConverter, ValidationError

class URLConverter(BaseConverter):

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = r'(?i)https?%3A%2F%2F[a-zA-z0-9.-]+(?::[0-9]+)?'

    def to_python(self, value):
        try:
            o = urlparse.urlparse(value)
            if o.scheme not in ('http', 'https'):
                raise ValidationError(
                        'url scheme must be one of [http, https]')
            if not path:
                raise ValidationError('url path part must not be empty')
            return o.geturl()
        except ValidationError: raise
        except Exception as e:
            raise ValidationError(e)

    def to_url(self, value):
        return value

class IdentifierConverter(BaseConverter):

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = r'[a-zA-Z_][a-zA-Z0-9_]*'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value

class ModeConverter(BaseConverter):

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = r'(?i)(?:deep|flat|shallow)'

    def to_python(self, value):
        return value.lower()

    def to_url(self, value):
        return value.lower()

class BooleanConverter(BaseConverter):

    def __init__(self, url_map):
        super(BooleanConverter, self).__init__(url_map)
        self.regex = '(?i)(?:true|false|yes|no|1|0)'

    def to_python(self, value):
        if value.lower() in ('true', 'yes', '1'):
            return True
        return False

    def to_url(self, value):
        return 'true' if value is True else 'false'

class Base64Converter(BaseConverter):

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

    QLANG_WQL = 0
    query_languages = ["WQL"]

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = r'(?i)(?:WQL)'

    def to_python(self, value):
        return { 'wql' : QLANG_WQL }[value.lower()]

    def to_url(self, value):
        return query_languages[value]

