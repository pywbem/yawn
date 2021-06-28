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
Utilities and functions for parsing user input obtained from html forms.
"""

import base64
import pickle
import pywbem
import re
import zlib
import six

class ReferenceDecodeError(ValueError):
    """
    Exception raised, when parsing of object path failed.
    """

    def __init__(self, key=None, path=None):
        msg = "Could not decode compressed object path%s%s!"
        if key is not None:
            key = ' for key "%s"' % key
        else:
            key = ''
        if path is not None:
            if isinstance(path, six.text_type):
                path = path.encode('utf-8')
            path = ' "%s"' % str(path)
        else:
            path = ''
        msg = msg % (path, key)
        ValueError.__init__(self, msg)

def decode_reference(encoded_text):
    """
    Decompress object path to python object.
    """
    try:
        return pickle.loads(zlib.decompress(base64.urlsafe_b64decode(
            encoded_text)))
    except Exception:
        raise ReferenceDecodeError(path=encoded_text)

RE_INAME = re.compile(r"^((?P<namespace>[^:.=]+):)?"
        r"((?P<classname>[a-zA-Z_0-9]+)\.)?(?P<keys>.*)")

# states of keybindings parser
# 
# possible transitions:
#     (KEY_NAME,     '=')  -> VALUE_START
#     (KEY_NAME,     ?)    -> KEY_NAME
#     (VALUE_START,  '"')  -> VALUE_STR
#     (VALUE_START,  ?)    -> VALUE_SIMPLE
#     (VALUE_SIMPLE, ',')  -> KEY_NAME
#     (VALUE_SIMPLE, ?)    -> VALUE_SIMPLE
#     (VALUE_STR,    '"')  -> VALUE_END
#     (VALUE_STR,    '\\') -> VALUE_ESC
#     (VALUE_STR,    ?)    -> VALUE_STR
#     (VALUE_ESC,    ?)    -> VALUE_STR
# 
# KEYS_END is a final state
KEY_NAME, VALUE_START, VALUE_SIMPLE, VALUE_STR, VALUE_ESC, VALUE_END, \
    NEXT_KEY, KEYS_END = range(8)

_RE_KEY_NAME = re.compile(r'([a-zA-Z_0-9]+)=')
_RE_VALUE = re.compile(r'([^"\\]+)')
_RE_VALUE_SIMPLE = re.compile(r'([-a-zA-Z_0-9.]+)')
_RE_INTEGER_TYPE = re.compile(r'^[su]int')

def value_str2pywbem(prop, value):
    """
    Used by iname_str2pywbem function for transforming key value
    to a pywbem object.

    @param prop may be None, in that case type will be guessed
    """
    if prop is not None:
        prop_type = prop['type']
        if (_RE_INTEGER_TYPE.match(prop_type) or prop_type == "boolean"):
            if value[0]  == '"':
                value = value[1:]
            if value[-1] == '"':
                value = value[:-1]
    else:
        prop_type = 'string'
        if value.lower() in {'true', 'false'}:
            prop_type = 'boolean'
        else:
            try:
                int(value)
                prop_type = 'uint16'
            except ValueError:
                try:
                    float(value)
                    prop_type = 'float'
                except ValueError:
                    pass
    return pywbem.tocimobj(prop_type, value)

def iname_str2pywbem(props, iname, classname=None, namespace=None):
    """
    Parse object path given as string in format:
        <namespace>:<classname>.<keybindings>
      where
        <namespace> and <classname> are optional
        <keybindings> is a sequance of strings: key="value"
                      separated by ','
    @props is a dictionary with format:
        { key_name, property_dictionary }
      with informations about referenced class key properties;
      preferrably it should be a NocaseDict
    @note does not handle embedded references to objects
    """
    match = RE_INAME.match(iname)
    if not match:
        raise ValueError("Invalid path!")
    kwargs = {'classname':classname, 'namespace':namespace}
    for k in ("namespace", "classname"):
        if match.group(k):
            kwargs[k] = match.group(k)

    res = pywbem.CIMInstanceName(**kwargs)

    state = KEY_NAME
    value = ''
    keybindings = match.group('keys')
    pos = 0
    letter = keybindings[pos] if len(keybindings) else None
    while state != KEYS_END:
        eol = pos >= len(keybindings)             # end of input
        letter = keybindings[pos] if not eol else None # current letter
        if state == KEY_NAME:
            if eol:
                state = KEYS_END
            else:
                match = _RE_KEY_NAME.match(keybindings, pos)
                if not match:
                    raise ValueError("Invalid path!")
                key = match.group(1)
                if props and not key in props:
                    raise ValueError(
                        "Invalid path: unknown key \"%s\""
                        " for instance of class \"%s\"!"%(
                            key, kwargs['classname']))
                state = VALUE_START
                pos = match.end()
        elif state == VALUE_START:
            if letter == '"':
                state = VALUE_STR
                pos += 1
            else:
                state = VALUE_SIMPLE
        elif state == VALUE_SIMPLE:
            match = _RE_VALUE_SIMPLE.match(keybindings, pos)
            if not match:
                raise ValueError("Invalid path!")
            res[key] = value_str2pywbem(props.get(key, None), match.group(1))
            pos = match.end()
            state = NEXT_KEY
        elif state == VALUE_STR:
            if letter == '"':
                res[key] = value_str2pywbem(props.get(key, None), value)
                value = ''
                state = VALUE_END
            elif letter == '\\':
                state = VALUE_ESC
                pos += 1
            else:
                match = _RE_VALUE.match(keybindings, pos)
                if not match:
                    raise ValueError("Invalid path:"
                    " expected '\"' or '\\'!")
                pos = match.end()
                value += match.group(1)
        elif state == VALUE_ESC:
            state = VALUE_STR
            value += letter
            pos += 1
        elif state == VALUE_END:
            if letter == '"':
                state = NEXT_KEY
                pos += 1
            else:
                raise ValueError("Invalid path: missing terminating '\"'!")
        elif state == NEXT_KEY:
            if eol:
                state = KEYS_END
            elif letter == ',':
                state = KEY_NAME
                pos += 1
            else:
                raise ValueError("Invalid path: expected ','!")
        else:
            assert False # something wrong in above code
    if state != KEYS_END:
        raise ValueError("Invalid path!")
    if not len(res.keybindings):
        raise ValueError("Invalid path: missing key-value pairs!")
    return res

def formvalue2iname(param, prefix, formdata, suffix='', pop_used=False,
        namespace=None):
    """
    Obtain a single object path from form inputs.
    Object path can be given as key values in separated input fields,
    as a compressed string or as an raw path string.
    @param suffix can be used to obtain the values from an item of
    array, which has name of fields composed like this:
        <prefix><param_name>-<item>.<key_name>
      where <item> is an index to array, counted from zero
            <key_name> is a name of key property of referenced class
    suffix in this case will be "-<item>"
    @param namespace is a namespace of referenced class
    """
    if not isinstance(param['type'], dict):
        raise ValueError("param must represent a reference to object")
    param_name = prefix.lower()+param['name'].lower()+suffix
    def get_value(name):
        """@return value from formdata and optionally remove it"""
        res = formdata[name]
        if pop_used:
            del formdata[name]
        return res
    if (   formdata.has_key(param_name+'-reftype')
       and formdata[param_name+"-reftype"] != 'compressed'):
        namespace = param['type'].get('ns', namespace)
        reftype = get_value(param_name+'-reftype')
        if reftype == 'keys':
            result = pywbem.CIMInstanceName(
                    classname=param['type']['className'],
                    namespace=namespace)
            for key, ref_param in param['type']['keys'].items():
                result[key] = formvalue2cimobject(ref_param,
                        param_name+'.', formdata, pop_used)
        else: # raw object path
            result = iname_str2pywbem(
                    param['type']['keys'], get_value(param_name),
                    classname=param['type']['className'],
                    namespace=namespace)
    else:
        if pop_used and formdata.has_key(param_name+'-reftype'):
            del formdata[param_name+'-reftype']
        value = get_value(param_name)
        if not value:
            return None
        # base64 decode does not properly handle unicode
        try:
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            result = decode_reference(value)
        except ReferenceDecodeError:
            raise ReferenceDecodeError(param_name, value)
    return result

def formvalue2cimobject(param, prefix, formdata, pop_used=False,
        namespace=None):
    """
    @param param is a dictionary created by get_class_item_details
    @param formdata should be a NocaseDict
    @param namespace is used as a fallback for reference types,
    where namespace of refered class could not be obtained
    @return value passable to pywbem methods
    """
    prefix = prefix.lower()
    param_name = param['name'].lower()
    def value(name):
        """@return value of form with optional removal"""
        res = formdata[prefix + name.lower()]
        if pop_used:
            del formdata[prefix + name.lower()]
        return res
    def process_simple_value(val):
        """@return value as a cim object"""
        return pywbem.tocimobj(param['type'], val)

    if param['is_array']:
        result = []
        if param['is_valuemap']:
            for val in param['valuemap']:
                if ("%s%s-%s"%(prefix, param_name, val)) in formdata:
                    result.append(process_simple_value(val))
        else:
            if not (prefix + param_name + '.size') in formdata:
                return
            if param['array_size'] is None:
                size = int(value(param_name + '.size'))
            else:
                size = param['array_size']
            for i in range(size):
                if isinstance(param['type'], dict):
                    pywbem_val = formvalue2iname(param, prefix, formdata,
                            suffix='-'+str(i), pop_used=pop_used,
                            namespace=namespace)
                else:
                    pywbem_val = process_simple_value(
                            value(param_name + '-' + str(i)))
                result.append(pywbem_val)
    else:
        if prefix + param_name + '-null' in formdata:
            return None
        if isinstance(param['type'], dict):
            result = formvalue2iname(param, prefix, formdata,
                    pop_used=pop_used, namespace=namespace)
        else:
            result = process_simple_value(value(param_name))

    return result

