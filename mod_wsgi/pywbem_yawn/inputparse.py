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

import base64
import cPickle
import pywbem
import zlib

decode_reference = lambda x: (cPickle.loads(
    zlib.decompress(base64.urlsafe_b64decode(x))))

def formvalue2cimobject(param, prefix, formdata, pop_used=False):
    """
    @param is a dictionary created by get_class_item_details
    @return value passable to pywbem methods
    """
    def value(name):
        if pop_used:
            return formdata.pop(prefix + name)
        return formdata[prefix + name]
    def process_simple_value(val):
        dt = param['type']
        if isinstance(dt, dict): # reference
            if not val: return None
            # base64 decode does not properly handle unicode
            return decode_reference(str(val))
        return pywbem.tocimobj(dt, val)

    if param['is_array']:
        result = []
        if param['is_valuemap']:
            for val in param['valuemap']:
                if ("%s%s-%s"%(prefix, param['name'], val)) in formdata:
                    result.append(val)
        else:
            if not (prefix + param['name'] + '.size') in formdata:
                return
            if param['array_size'] is None:
                size = int(value(param['name'] + '.size'))
            else:
                size = param['array_size']
            for i in range(size):
                result.append(process_simple_value(
                    value(param['name'] + '-' + str(i))))
    else:
        result = process_simple_value(value(param['name']))
    return result

