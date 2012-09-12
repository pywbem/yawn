#**************************************************************************
#|
#| Copyright (c) 2006 Novell, Inc.
#| All Rights Reserved.
#|
#| This program is free software; you can redistribute it and/or
#| modify it under the terms of version 2 of the GNU General Public License as
#| published by the Free Software Foundation.
#|
#| This program is distributed in the hope that it will be useful,
#| but WITHOUT ANY WARRANTY; without even the implied warranty of
#| MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#| GNU General Public License for more details.
#|
#| You should have received a copy of the GNU General Public License
#| along with this program; if not, contact Novell, Inc.
#|
#| To contact Novell about this file by physical or electronic mail,
#| you may find current contact information at www.novell.com
#|
#|*************************************************************************

# NOTE: yawn currently requires the latest pywbem from svn.
#   cd /usr/lib/python/site-packages
#   svn co https://svn.sourceforge.net/svnroot/pywbem/pywbem/trunk pywbem

# @author Bart Whiteley <bwhiteley@suse.de>
# @author Norm Paxton <npaxton@novell.com>
# @author Michal Minar <miminar@redhat.com>

import datetime
import logging
import traceback
import re
import bisect
import pywbem
import pywbem.cim_http
import types
import cPickle
import base64
import urlparse
import zlib
import inspect
import mako
import mako.lookup
import mako.exceptions
import pkg_resources
from collections import defaultdict
from itertools import chain
from werkzeug.wrappers import Response, Request
from werkzeug.routing import Map, Rule, BaseConverter, ValidationError
from werkzeug.exceptions import (
        HTTPException, NotFound, Unauthorized, BadRequest)
from werkzeug.local import Local, release_local
try:
    from pywbem.cim_provider2 import codegen
except ImportError:
    codegen = None

log = logging.getLogger(__name__)

# *****************************************************************************
# ERROR HANDLING HELPERS
# *****************************************************************************
_status_codes = [('', '')
  ,('FAILED'                      , 'A general error occurred')
  ,('ACCESS_DENIED'               , 'Resource not available')
  ,('INVALID_NAMESPACE'           , 'The target namespace does not exist')
  ,('INVALID_PARAMETER'           , 'Parameter value(s) invalid')
  ,('INVALID_CLASS'               , 'The specified Class does not exist')
  ,('NOT_FOUND'                   , 'Requested object could not be found')
  ,('NOT_SUPPORTED'               , 'Operation not supported')
  ,('CLASS_HAS_CHILDREN'          , 'Class has subclasses')
  ,('CLASS_HAS_INSTANCES'         , 'Class has instances')
  ,('INVALID_SUPERCLASS'          , 'Superclass does not exist')
  ,('ALREADY_EXISTS'              , 'Object already exists')
  ,('NO_SUCH_PROPERTY'            , 'Property does not exist')
  ,('TYPE_MISMATCH'               , 'Value incompatible with type')
  ,('QUERY_LANGUAGE_NOT_SUPPORTED', 'Query language not supported')
  ,('INVALID_QUERY'               , 'Query not valid')
  ,('METHOD_NOT_AVAILABLE'        , 'Extrinsic method not executed')
  ,('METHOD_NOT_FOUND'            , 'Extrinsic method does not exist')]

def _code2string(code):
    if code > len(_status_codes) -1:
        return (str(code), "UNKNOWN ERROR")
    return _status_codes[code]

# *****************************************************************************
# SORTING HELPERS
# *****************************************************************************
def _cmp_pnames(klass):
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

def _cmp_params(klass):
    _cmp_orig = _cmp_pnames(klass)
    def _cmp(a, b):
        if a['is_method'] and not b['is_method']:
            return -1
        if not a['is_method'] and b['is_method']:
            return 1
        return _cmp_orig(a['name'], b['name'])
    return _cmp

# *****************************************************************************
# CIM HIERARCHY TRAVERSAL FUNCTIONS
# *****************************************************************************
def getAllHierarchy(conn, url, ns, className):
    hierarchy = []

    hierarchy.append(className)
    classNameToCheck = className
    while classNameToCheck != None:
        subklass = conn.GetClass(classNameToCheck, LocalOnly = False,
                IncludeQualifiers=True)
        if subklass.superclass != None:
            classNameToCheck = subklass.superclass
            hierarchy.append(classNameToCheck)
        else:
            classNameToCheck = None
    return hierarchy;

# *****************************************************************************
# CIM OBJECTS TO PYTHON BASIC TYPES
# *****************************************************************************
def _get_property_details(prop, inst=None):
    """
    This should be used only by functions get_class_item_details
    and get_class_props
    """
    if not isinstance(prop, (pywbem.CIMProperty, pywbem.CIMParameter)):
        raise TypeError('prop must be either CIMProperty or CIMParameter')
    if (   inst is not None
       and not isinstance(inst, pywbem.CIMInstance)
       and not isinstance(inst, pywbem.CIMInstanceName)):
       raise TypeError('inst must be one of: CIMInstance,'
               ' CIMInstanceName, None')
    if inst is not None:
        if isinstance(inst, pywbem.CIMInstance):
            _has_prop  = lambda name: name in inst.properties
            _get_value = lambda name: inst.properties[name].value
        else: # CIMInstanceName
            _has_prop  = lambda name: name in inst
            _get_value = lambda name: inst[name]

    i = { 'valuemap'     : []
        # string represantations of values in valuemap
        , 'values'       : {}
        }
    i['is_key'] = prop.qualifiers.has_key('key')
    if prop.is_array:
        i['is_array'] = prop.is_array
        i['array_size'] = prop.array_size
    if prop.reference_class is None:
        i['type'] = prop.type
    else:
        i['type'] = {'className':prop.reference_class}
        if inst is not None and _has_prop(prop.name):
            i['type']['ns'] = _get_value(prop.name).namespace

    if inst is not None and _has_prop(prop.name):
        i['value_orig'] = _get_value(prop.name)
        if (   prop.qualifiers.has_key('values')
           and prop.qualifiers.has_key('valuemap')):
            i['value'] = _displayMappedValue(
                    _get_value(prop.name), prop.qualifiers)
        elif prop.reference_class is not None:
            i['value'] = _get_value(prop.name)
        else:
            i['value'] = _val2str(_get_value(prop.name))

    if prop.qualifiers.has_key('valuemap'):
        valmap_quals = prop.qualifiers['valuemap'].value
        values_quals = None
        if prop.qualifiers.has_key('values'):
            values_quals = prop.qualifiers['values'].value
        for ivq, val in enumerate(valmap_quals):
            try: pywbem.tocimobj(prop.type, val)
            except:
                # skip valuemap items that aren't valid values
                # such as the numeric ranges for DMTF Reserved and whatnot
                continue
            i['valuemap'].append(val)
            if values_quals and ivq < len(values_quals):
                i['values'][val] = [values_quals[ivq]]
            else:
                i['values'][val] = None

    if isinstance(prop, pywbem.CIMParameter):
        # TODO is IN assumed to be true if the IN qualifier is missing?
        i['in'] = (  not prop.qualifiers.has_key('in')
                  or prop.qualifiers['in'])
        i['out'] = (  prop.qualifiers.has_key('out')
                   and prop.qualifiers['out'])

    return i

def get_class_item_details(className, item, inst=None):
    """
    @param inst provides some additional info (if given)
    """
    if not isinstance(className, basestring):
        raise TypeError('className must be a string')
    if not isinstance(item, (pywbem.CIMProperty, pywbem.CIMMethod,
            pywbem.CIMParameter)):
        raise TypeError('item must be either CIMProperty, CIMParameter or CIMMethod')
    if (   inst is not None
       and not isinstance(inst, (pywbem.CIMInstanceName, pywbem.CIMInstance))):
        raise TypeError('inst must be one of CIMInstanceName'
            ', CIMInstance or None')

    i = { 'name'         : item.name
        , 'is_deprecated': item.qualifiers.has_key('deprecated')
        # whether the item is declared be current class or
        # by some parent class
        , 'is_local'     : False
        # class, that defines this item (may be None)
        , 'class_origin' : None
        , 'is_key'       : False
        , 'is_array'     : False
        , 'is_method'    : isinstance(item, pywbem.CIMMethod)
        , 'is_required'  : item.qualifiers.has_key('required')
        , 'is_valuemap'  : item.qualifiers.has_key('valuemap')
        , 'array_size'   : None
        , 'value'        : None
        , 'value_orig'   : None
        # only valid for method
        , 'args'         : []
        , 'type'         : "<Unknown>"
        # all less interesting qualifiers sorted by name
        , 'qualifiers'   : []
        }

    if hasattr(item, 'class_origin'):
        i['is_local'] = item.class_origin == className
        i['class_origin'] = item.class_origin
    if item.qualifiers.has_key('description'):
        i['description'] = item.qualifiers['description'].value
    else:
        i['description'] = None
    for q in sorted(item.qualifiers.values(), key=lambda v: v.name):
        if q.name.lower() in ('description', 'deprecated', 'key', 'required'): continue
        i['qualifiers'].append((q.name, _val2str(q.value)))
    if isinstance(item, (pywbem.CIMProperty, pywbem.CIMParameter)):
        i.update(_get_property_details(item, inst))

    elif isinstance(item, pywbem.CIMMethod): # CIMMethod
        i['type'] = item.return_type
        args = i['args']
        for p in item.parameters.values():
            args.append(get_class_item_details(className, p))
    return i

def get_class_props(klass=None, inst=None, include_all=False):
    """
    @param inst may be CIMInstance
        if given and include_all == False, then only properties
        defined by provider will be returned
        if None, then all properties declared be klass will be returned
    @param include_all if True, then all properties declared by klass
        and all defined by given instance will be returned
    @note properties declared by klass != propertied defined be instance,
        that's why include_all flag is provided
    @note qualifiers declared be class override those provided by instance
    @return props: [ { 'name'        : name
                     , 'type'        : type
                     , 'value'       : value
                     , 'description' : description
                     , 'is_key'      : bool
                     , 'is_required' : bool
                     , 'is_array'    : bool
                     , 'qualifiers'  : [(name, value), ...]
                     }
                   , ...
                   ]
    if property is not in schema, then type is None and the rest
        of fields are undefined
    if type of property is reference, then:
        type  = {ns : namespace, className: className}
        value = object_path object
    """
    if klass is not None and not isinstance(klass, pywbem.CIMClass):
        raise TypeError('klass must be object of CIMClass')
    if (  inst is not None
       and not isinstance(inst, (pywbem.CIMInstance, pywbem.CIMInstanceName))):
        raise TypeError('inst must be either CIMInstance,'
        ' CIMInstanceName or None')
    if klass is None and inst is None:
        raise ValueError('klass or inst argument must be given')

    keys = set()
    if inst is not None:
        keys = set(inst.keys())
        if include_all and klass is not None:
            keys.update(set(klass.properties.keys()))
    else:
        keys = klass.properties.keys()
    keys = sorted(keys, _cmp_pnames(klass))

    props = []
    for prop_name in keys:
        iprop = None
        if (  isinstance(inst, pywbem.CIMInstance)
           and prop_name in inst.properties):
            iprop = inst.properties[prop_name]
        cprop = (  klass.properties[prop_name]
                if klass and klass.properties.has_key(prop_name) else None)
        p = { 'name'        : prop_name
            , 'is_key'      : False
            , 'is_required' : False
            , 'is_array'    : False
            , 'description' : None
            , 'type'        : '<Unknown>'
            , 'value'       : None
            , 'value_orig'  : None
            , 'qualifiers'  : []
            , 'is_valuemap' : False
            }
        if cprop is not None:
            p.update(get_class_item_details(klass.classname, cprop, inst))
        elif iprop is not None:
            p.update(_get_property_details(iprop, inst))
        elif isinstance(inst, pywbem.CIMInstanceName):
            if prop_name in inst:
                value = inst[prop_name]
                p['is_key']     = True
                p['is_array']   = isinstance(inst[prop_name], list)
                p['value']      = value
                p['value_orig'] = value
                if isinstance(value, pywbem.CIMInstanceName):
                    p['type'] = { 'className' : value.classname
                                , 'ns'        : value.namespace }

        props.append(p)
    return props

def get_class_methods(klass):
    """
    @return { 'name' : method_name
            , 'args' : arguments (just names)
            }
    """
    if not isinstance(klass, pywbem.CIMClass):
        raise TypeError('klass must be a CIMClass object')
    methods = []
    for method in klass.methods.values():
        methods.append((method.name, method.parameters.keys()))
    return methods

def get_inst_info(inst, klass=None, include_all=False):
    """
    @return { 'className'  : className
            , 'ns'         : namespace
            , 'path'       : path
            , 'props'      : [ p1dict, ... ]
            , 'methods'    : [ m1dict, ... ]
            , ...
            }
    """
    pth = inst if isinstance(inst, pywbem.CIMInstanceName) else inst.path
    info = { 'className' : pth.classname
           , 'ns'        : pth.namespace
           , 'host'      : pth.host
           , 'props'     : get_class_props(klass, inst, include_all)
           , 'path'      : pth
           , 'methods'   : []
           }
    if klass is not None:
        info['methods'] = get_class_methods(klass)
    return info

def get_method_params(className, cimmethod):
    """
    @return (in_params, out_params)
    where both are list of dictionaries
    """
    in_params  = []
    out_params = []

    if not isinstance(cimmethod, pywbem.CIMMethod):
        raise TypeError('cimmethod must be instance of pywbem.CIMMethod')
    for param in cimmethod.parameters.values():
        details = get_class_item_details(className, param)
        if details['in']:  in_params.append(details)
        if details['out']: out_params.append(details)

    return (in_params, out_params)

# *****************************************************************************
# PYTHON BASIC TYPES TO CIM OBJECTS
# *****************************************************************************

# parses base64 encoded string to python object (used for CIMInstanceNames)
_decodeObject = lambda x: (cPickle.loads(
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
            return _decodeObject(str(val))
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

# *****************************************************************************
# RENDERING UTILITIES
# *****************************************************************************

# encodes python object to base64 encoding (used for CIMInstanceNames)
_encodeObject = lambda x: (base64.urlsafe_b64encode(
    zlib.compress(cPickle.dumps(x, cPickle.HIGHEST_PROTOCOL))))

class SafeString(unicode):
    """
    when this type of string is passed to template, it will be not escaped
    upon rendering if safe param is True
    """
    def __init__(self, text):
        unicode.__init__(self, text)
        self.safe = True

def _val2str(x):
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
                strItem = _val2str(item)
                if type(item) in types.StringTypes:
                    strItem = '"' + strItem + '"'
                rval+= strItem
        rval+= '}'
        return rval
    return unicode(x)

def _displayMappedValue(val, quals):
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
        propstr = _val2str(i)
        rval+= propstr
        if propstr in valmapQual:
            valIdx = valmapQual.index(propstr)
            if valIdx < len(valuesQual):
                rval+= ' ('+valuesQual[valIdx]+')'
    if isinstance(val, list):
        rval+= '}'
    return SafeString(rval)

# *****************************************************************************
# DECORATORS
# *****************************************************************************
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

# *****************************************************************************
# URL CONVERTERS
# *****************************************************************************
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
        return _decodeObject(str(value))

    def to_url(self, value):
        if isinstance(value, basestring):
            return value
        return _encodeObject(value)

QLANG_WQL = 0
query_languages = ["WQL"]
class QLangConverter(BaseConverter):

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = r'(?i)(?:WQL)'

    def to_python(self, value):
        return { 'wql' : QLANG_WQL }[value.lower()]

    def to_url(self, value):
        return query_languages[value]

AC_ASSOCIATORS, AC_ASSOCIATOR_NAMES, AC_REFERENCES, AC_REFERENCE_NAMES = \
        range(4)
assoc_calls = [ 'associators', 'associatornames'
              , 'references', 'referencenames' ]
assoc_call_labels = [ 'Associators', 'Associator Names'
                    , 'References', 'Reference Names' ]
class AssocCallConverter(BaseConverter):

    def __init__(self, url_map):
        BaseConverter.__init__(self, url_map)
        self.regex = r'(?i)(?:%s)'%'|'.join(assoc_calls)

    def to_python(self, value):
        if value.lower() not in assoc_calls:
            raise ValueError('association call must be one of: [%s]' %
                    ', '.join(AssocCallConverter._vals))
        return assoc_calls.index(value.lower())

    def to_url(self, value):
        return assoc_calls[value]

# *****************************************************************************
# URL AND HTML TOOLS
# *****************************************************************************
_re_url_func = re.compile(r'^[A-Z][a-z_A-Z0-9]+$')
def _base_script(request):
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

def _get_user_pw(request):
    if 'Authorization' not in request.headers:
        return (None, None)
    auth = request.authorization
    return (auth.username, auth.password)

url_map = Map([
    Rule('/', endpoint='index'),
    Rule('/AssociatedClasses/<id:className>',
        endpoint="AssociatedClasses"),
    Rule('/AssociatorNames/<base64:path>', endpoint="AssociatorNames"),
    Rule('/CMPIProvider/<id:className>', endpoint="CMPIProvider"),
    Rule('/CreateInstance/<id:className>', endpoint='CreateInstance'),
    Rule('/CreateInstancePrep/<id:className>',
        endpoint='CreateInstancePrep'),
    Rule('/DeleteClass/<id:className>', endpoint='DeleteClass'),
    Rule('/DeleteInstance/<base64:path>',
        endpoint='DeleteInstance'),
    Rule('/EnumClassNames', endpoint='EnumClassNames'),
    Rule('/EnumInstanceNames/<id:className>',
        endpoint='EnumInstanceNames'),
    Rule('/EnumInstances/<id:className>', endpoint='EnumInstances'),
    Rule('/EnumNamespaces', endpoint='EnumNamespaces'),
    Rule('/FiltereredReferenceNames/<base64:path>',
        endpoint='FilteredReferenceNames'),
    Rule('/FilteredReferenceNamesDialog/<base64:path>',
        endpoint="FilteredReferenceNamesDialog"),
    Rule('/GetClass/<id:className>', endpoint='GetClass'),
    Rule('/GetInstance/path/<base64:path>',
        endpoint='GetInstance'),
    Rule('/GetInstance/cn/<id:className>', endpoint='GetInstance'),
    Rule("/GetInstD/<id:className>", endpoint="GetInstD"),
    Rule("/InvokeMethod/<id:method>/cn/<id:className>",
        endpoint="InvokeMethod"),
    Rule("/InvokeMethod/<id:method>/path/<base64:path>",
        endpoint="InvokeMethod"),
    Rule('/Login', endpoint='Login'),
    Rule('/Logout', endpoint='Logout'),
    Rule("/ModifyInstance/<base64:path>",
        endpoint="ModifyInstance"),
    Rule("/ModifyInstPrep/<base64:path>",
        endpoint="ModifyInstPrep"),
    Rule("/MofComp", endpoint="MofComp"),
    Rule("/Pickle/<base64:path>", endpoint="Pickle"),
    Rule("/PrepMethod/<id:method>/cn/<id:className>",
        endpoint="PrepMethod"),
    Rule("/PrepMethod/<id:method>/path/<base64:path>",
        endpoint="PrepMethod"),
    Rule("/PrepMofComp", endpoint="PrepMofComp"),
    Rule("/PyProvider/<id:className>", endpoint="PyProvider"),
    Rule("/Query", endpoint="Query"),
    Rule("/Query/<qlang:lang>", endpoint="Query"),
    Rule('/QueryD', endpoint='QueryD'),
    Rule("/ReferenceNames/<base64:path>",
        endpoint="ReferenceNames"),
    ], converters =
        { 'id'     : IdentifierConverter
        , 'mode'   : ModeConverter
        , 'bool'   : BooleanConverter
        , 'base64' : Base64Converter
        , 'qlang'  : QLangConverter
        #, 'ac'     : AssocCallConverter
        })

# *****************************************************************************
# HANDLER
# *****************************************************************************
class Yawn(object):

    def __init__(self,
            templates     = None,
            modules       = None,
            static_prefix = None,
            debug         = False):
        
        if templates is None:
            templates = pkg_resources.resource_filename(__name__, 'templates')
            log.debug('templates directory: {}'.format(templates))
        self._lookup = mako.lookup.TemplateLookup(
                directories      = templates,
                module_directory = modules
        )
        self._static_prefix = static_prefix
        self._debug = debug
        self._local = Local()

    @property
    def response(self):
        try:
            return self._local.response
        except AttributeError:
            resp = Response(content_type="text/html")
            try:
                url = self._local.url
                resp.headers['WWW-Authenticate'] = (
                        ', '.join([ 'Basic realm="CIMOM at %s"'%url
                                  , 'qop="auth,auth-int"']))
            except AttributeError: pass
            self._local.response = resp
            return resp

    @property
    def static_prefix(self):
        try:
            return self._local.static_prefix
        except AttributeError:
            if self._static_prefix is None:
                self._local.static_prefix = (
                        _base_script(self._local.request) + '/static')
            else:
                self._local.static_prefix = self._static_prefix
            return self._local.static_prefix

    @property
    def urls(self):
        try:
            return self._local.urls
        except AttributeError:
            self._local.urls = url_map.bind_to_environ(
                    self._local.request.environ)
            return self._local.urls

    @property
    def conn(self):
        url = self._local.url
        ns  = self._local.ns
        if (   hasattr(self._local, 'connection')
           and self._local.connection.url == url
           and self._local.connection.default_namespace == ns):
            return self._local.connection

        req = self._local.request
        (user, pw) = _get_user_pw(req)
        if user is None:
            user = ''
        if pw is None:
            pw = ''
        if (   len(user) > 0
           and req.cookies.has_key('yawn_logout')):
            if req.cookies['yawn_logout'] in ['true', 'pending']:
                self.response.set_cookie('yawn_logout', 'false',
                        path=_base_script(req))
                user, pw = '', ''
        self._local.connection = pywbem.WBEMConnection(url, (user, pw))
        self._local.connection.default_namespace = ns
        self._local.connection.debug = True
        return self._local.connection

    def render(self, template, **kwargs):
        kwargs['urls']   = self.urls
        kwargs['static'] = self.static_prefix
        kwargs['conn']   = getattr(self._local, 'connection', None)
        kwargs['url']    = getattr(self._local, 'url', None)
        kwargs['ns']     = getattr(self._local, 'ns', None)
        try:
            return self._lookup.get_template(template).render(**kwargs)
        except:
            return mako.exceptions.html_error_template().render()

    def dispatch_request(self, request):
        self._local.request = request
        try:
            endpoint, values = self.urls.match()
            return getattr(self, 'on_' + endpoint)(**values)
        except HTTPException, e:
            return e

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        try:
            return self.wsgi_app(environ, start_response)
        except pywbem.cim_http.AuthError as arg:
            response = self.response
            unresp = Unauthorized().get_response(environ)
            response.status_code = unresp.status_code
            response.data = unresp.data
            return response(environ, start_response)

        except pywbem.CIMError as arg:
            errstr = arg[1]
            if errstr.startswith('cmpi:'):
                # we have a traceback from CMPI, that might have newlines
                # converted.  need to convert them back.
                errstr = errstr[5:].replace('<br>', '\n')
            elif 'cmpi:Traceback' in errstr:
                errstr = errstr.replace('cmpi:Traceback', 'Traceback')
                errstr = errstr.replace('<br>', '\n')
            self._local.request = Request(environ)
            output = self.render('cim_error.mako',
                error   = '%s: %s' % _code2string(arg[0]),
                details = errstr)
            response = self.response
            response.data = output
            return response(environ, start_response)

        except Exception:
            if not self._debug:
                output = traceback.format_exc()
                response = Response(output, content_type='text/plain')
                return response(environ, start_response)
            raise

        finally:
            release_local(self._local)

    def _createOrModifyInstance(self, className, path, **params):
        conn = self.conn
        klass = conn.GetClass(ClassName=className,
                LocalOnly=False, IncludeQualifiers=True)
        if path is not None:
            inst = conn.GetInstance(InstanceName=path, LocalOnly = False)
        else:
            inst = pywbem.CIMInstance(className)
            inst.path = pywbem.CIMInstanceName(
                    className, namespace=self._local.ns)

        for p in get_class_props(klass, inst=inst, include_all=True):
            value = formvalue2cimobject(p, 'PropName.', params, True)
            if p['is_key']:
                if path is None:
                    inst.path[p['name']] = value
                else: # do not allow key modification of existing instance 
                    continue
            if (  value is None
               or (isinstance(value, list) and len(value) == 0)):
                inst.update_existing([(p['name'], None)])
            else:
                inst[p['name']] = value
        log.debug("not handled formvalues: {}".format(params))
        if path:
            if path.namespace is None:
                path.namespace = self._local.ns
            inst.path = path
            conn.ModifyInstance(ModifiedInstance=inst)
        else:
            path = conn.CreateInstance(NewInstance=inst)
        inst = conn.GetInstance(InstanceName=path, LocalOnly = False)

        return self.render('modify_instance.mako',
                className = className,
                instance  = get_inst_info(inst, klass))

    def _enumInstrumentedClassNames(self):
        fetched_classes = []
        def get_class(cname):
            fetched_classes.append(cname)
            return conn.GetClass(ClassName=cname,
                       LocalOnly=True, PropertyList=[],
                       IncludeQualifiers=False, IncludeClassOrigin=False)
        conn = self.conn
        caps = conn.EnumerateInstances(
                        ClassName='PG_ProviderCapabilities',
                        namespace='root/PG_InterOp',
                        PropertyList=['Namespaces', 'ClassName'])
        start_class = '.'
        deepDict = {start_class:[]}
        for cap in caps:
            if self._local.ns not in cap['Namespaces']:
                continue
            if cap['ClassName'] in fetched_classes:
                continue
            klass = get_class(cap['ClassName'])
            if klass.superclass is None:
                deepDict[start_class].append(klass.classname)
            else:
                try:
                    deepDict[klass.superclass].append(klass.classname)
                except KeyError:
                    deepDict[klass.superclass] = [klass.classname]
                while klass.superclass is not None:
                    if klass.superclass in fetched_classes:
                        break
                    klass = get_class(klass.superclass)
                    if klass.superclass is None and \
                            klass.superclass not in deepDict[start_class]:
                        deepDict[start_class].append(klass.classname)
                    elif klass.superclass in deepDict:
                        if klass.classname not in deepDict[klass.superclass]:
                            deepDict[klass.superclass].append(klass.classname)
                        break
                    else:
                        deepDict[klass.superclass] = [klass.classname]

        return self.render('enum_instrumented_class_names.mako',
                mode      = 'deep',
                className = start_class,
                classes   = deepDict)

    def on_index(self):
        resp = self.response
        resp.data = self.render('index.mako')
        return resp

    @view()
    def on_AssociatedClasses(self, className):
        conn = self.conn
        classNames = None
        cns = conn.References(ObjectName=className, IncludeQualifiers=True)
        cns.sort()

        hierarchy = []
        hierarchy = getAllHierarchy(conn, url, ns, className)
        lastAssocClass = ''
        associations = []
        for cn in cns:
            klass = cn[1]
            assocClass = klass.classname
            resultClass = ''
            role = ''
            resultRole = ''
            roleDescription = ''
            resultRoleDescription = ''

            # to find the resultClass, I have to iterate the properties
            # to a REF that is not className
            for propname in klass.properties.keys():
                prop = klass.properties[propname]
                if prop.reference_class is not None:
                    refClass = prop.reference_class
                    description = ''
                    if prop.qualifiers.has_key('description'):
                        description = prop.qualifiers['description'].value

                    if refClass in hierarchy:
                        if assocClass==lastAssocClass:
                            if resultClass=='':
                                resultClass = refClass
                                resultRole = propname
                                resultRoleDescription = description
                            else:
                                role = propname
                                roleDescription = description
                        else:
                            if role=='' and refClass in hierarchy:
                                role = propname
                                roleDescription = description
                            else:
                                resultClass = refClass
                                resultRole = propname
                                resultRoleDescription = description
                    else:
                        if resultClass=='':
                            resultClass = refClass
                            resultRole = propname
                            resultRoleDescription = description
            associations.append(
                    ( resultClass
                    , assocClass
                    , role
                    , roleDescription
                    , resultRole
                    , resultRoleDescription
                    ))
            lastAssocClass = assocClass

        return self.render('associated_classes.mako',
                className = className,
                associations = associations)

    @view()
    def on_AssociatorNames(self, path):
        assocs = self.conn.AssociatorNames(ObjectName=path)
        groupedAssocs = {}
        for assoc in assocs:
            if assoc.classname not in groupedAssocs.keys():
                groupedAssocs[assoc.classname] = [assoc]
            else:
                groupedAssocs[assoc.classname].append(assoc)
        setkeys = groupedAssocs.keys()
        setkeys.sort()
        instances = []
        for setkey in setkeys:
            insts = groupedAssocs[setkey]
            if len(insts) < 1: continue
            infos = []
            for iname in insts:
                infos.append(get_inst_info(iname))
            instances.append((inst.classname, inst.namespace, infos))
        return self.render('associator_names.mako',
                className = path.classname,
                instances = instances)

    @view()
    def on_CMPIProvider(self, className):
        klass = self.conn.GetClass(ClassName = className, LocalOnly=False,
                    IncludeClassOrigin=True, IncludeQualifiers=True)
        return self.render('cmpi_provider.mako', className=className)

    @view(http_method=POST)
    def on_CreateInstance(self, className, **params):
        return self._createOrModifyInstance(className, None, **params)

    @view()
    def on_CreateInstancePrep(self, className):
        klass = self.conn.GetClass(ClassName=className,
                LocalOnly=False, IncludeQualifiers=True)
        items = sorted([ get_class_item_details(className, prop)
            for prop in klass.properties.values()], _cmp_params(klass))
        return self.render('modify_instance_prep.mako',
                new       = True,
                className = className,
                items     = items)

    @view()
    def on_DeleteClass(self, className):
        self.conn.DeleteClass(ClassName = className)
        return self.render('delete_class.mako',
                className  = className)

    @view()
    def on_DeleteInstance(self, path):
        self.conn.DeleteInstance(path)
        return self.render('delete_instance.mako',
                className = path.classname,
                iname     = get_inst_info(path))

    @view()
    def on_EnumClassNames(self, className=None, mode=None, instOnly=None):
        conn = self.conn
        req = self._local.request
        if mode is None:
            mode = req.args.get('mode', 'deep')
        if className is None:
            className = req.args.get('className', None)
        if instOnly is None:
            instOnly = req.args.get('instOnly', None)
            if instOnly is not None:
                instOnly = instOnly.lower() in ('true', 'yes', '1')
        if instOnly is not None:
            self.response.set_cookie('yawn_instOnly', str(instOnly).lower(),
                    path=_base_script(req))
        elif (  'yawn_instOnly' in req.cookies
             and req.cookies['yawn_instOnly'] == 'true'):
            instOnly = True

        if instOnly:
            return self._enumInstrumentedClassNames()

        lineage = []
        if className is not None:
            lineage = [className]
            klass = conn.GetClass(ClassName=className)
            while klass.superclass is not None:
                lineage.insert(0, klass.superclass)
                klass = conn.GetClass(ClassName=klass.superclass)

        kwargs = { 'DeepInheritance' : mode in ['flat', 'deep'] }
        if className is not None:
            kwargs['ClassName'] = className
        if mode == 'deep':
            kwargs['LocalOnly'] = True
            kwargs['IncludeQualifiers'] = False
            kwargs['IncludeClassOrigin'] = False
        klasses = conn.EnumerateClasses(**kwargs)

        start_class = className is None and 'None' or className
        classes = {start_class:[]}
        for klass in klasses:
            if mode == 'deep':
                if klass.superclass is None:
                    bisect.insort(classes[start_class], klass.classname)
                else:
                    if not klass.superclass in classes:
                        classes[klass.superclass] = [klass.classname]
                    else:
                        bisect.insort(classes[klass.superclass],
                                klass.classname)
            else:
                bisect.insort(classes[start_class], klass.classname)
                if mode != 'flat' and conn.EnumerateClassNames(
                        ClassName=klass.classname):
                    classes[klass.classname] = [True] # has kids

        return self.render('enum_class_names.mako',
                className  = className,
                lineage    = lineage,
                mode       = mode,
                classes    = classes)

    @view()
    def on_EnumInstanceNames(self, className):
        instNames = self.conn.EnumerateInstanceNames(ClassName = className)
        inameDict = pywbem.NocaseDict()
        for iname in instNames:
            if iname.classname not in inameDict:
                inameDict[iname.classname] = [iname]
            else:
                inameDict[iname.classname].append(iname)

        instances = []
        for cname, inames in sorted(inameDict.items(), key=lambda k: k[0]):
            infos = []
            for iname in inames:
                infos.append(get_inst_info(iname))
            instances.append((cname, iname.namespace, infos))

        return self.render('enum_instance_names.mako',
            className  = className,
            instances  = instances)

    @view()
    def on_EnumInstances(self, className):
        conn = self.conn
        insts = conn.EnumerateInstances(
                ClassName = className,
                LocalOnly = False)

        ccache = pywbem.NocaseDict()
        instances = []
        for inst in insts:
            i = {}
            try:
                klass = ccache[inst.path.classname]
            except KeyError:
                klass = conn.GetClass(inst.path.classname, LocalOnly=False)
                ccache[inst.path.classname] = klass
            i = get_inst_info(inst, klass)
            instances.append(i)

        return self.render('enum_instances.mako',
                className = className,
                instances = instances)

    @view(require_ns=False)
    def on_EnumNamespaces(self):
        conn = self.conn
        nsinsts = []
        for nsclass in ['CIM_Namespace', '__Namespace']:
            for interopns in ['root/cimv2', 'Interop', 'interop', 'root',
                    'root/interop']:
                try:
                    nsinsts = conn.EnumerateInstanceNames(nsclass,
                            namespace = interopns)
                except pywbem.CIMError, arg:
                    if arg[0] in [pywbem.CIM_ERR_INVALID_NAMESPACE,
                                  pywbem.CIM_ERR_NOT_SUPPORTED,
                                  pywbem.CIM_ERR_INVALID_CLASS]:
                        continue
                    else:
                        raise
                if len(nsinsts) == 0:
                    continue
                break
            if len(nsinsts) == 0:
                continue
            break

        if len(nsinsts) == 0:
            return self.render("enum_namespaces.mako", namespaces = [])
        nslist = [inst['Name'].strip('/') for inst in nsinsts]
        if interopns not in nslist:
        # Pegasus didn't get the memo that namespaces aren't hierarchical
        # This will fall apart if there exists a namespace
        # <interopns>/<interopns>
        # Maybe we should check the Server: HTTP header instead.
            nslist = [interopns+'/'+subns for subns in nslist]
            nslist.append(interopns)
        nslist.sort()
        if 'root/PG_InterOp' in nslist:
            nsd = dict([(x, 0) for x in nslist])
            caps = conn.EnumerateInstances('PG_ProviderCapabilities',
                    namespace='root/PG_InterOp',
                    PropertyList=['Namespaces'])
            for cap in caps:
                for _ns in cap['Namespaces']:
                    try:
                        nsd[_ns] += 1
                    except KeyError:
                        pass
        else:
            nsd = {}
        return self.render('enum_namespaces.mako',
                namespaces = nslist,
                nsd        = nsd)

    @view(http_method=GET_AND_POST)
    def on_FilteredReferenceNames(self, path,
            assocCall=None, assocClass="",
            resultClass="", role="", resultRole="", properties=""):
        conn = self.conn
        if assocCall is None:
            raise BadRequest('missing "assocCall" argument')
        if assocCall.lower() not in assoc_calls:
            raise BadRequest('assocCall must be one of: [%s]'%
                    ', '.join(assoc_calls))
        assocCall = assoc_calls.index(assocCall.lower())

        params = {}
        if assocClass:
            params['AssocClass'] = assocClass
        if resultClass:
            params['ResultClass'] = resultClass
        if role:
            params['Role'] = role
        if resultRole:
            params['ResultRole'] = resultRole
        if assocCall in (AC_ASSOCIATORS, AC_REFERENCES):
            params['IncludeQualifiers'] = True

        results = []
        funcs = { AC_ASSOCIATORS      : 'Associators'
                , AC_ASSOCIATOR_NAMES : 'AssociatorNames'
                , AC_REFERENCES       : 'References'
                , AC_REFERENCE_NAMES  : 'ReferenceNames' }
        objs = getattr(conn, funcs[assocCall])(ObjectName=path, **params)

        for o in objs:
            if assocCall in (AC_ASSOCIATORS, AC_REFERENCES):
                # o is CIMInstance
                klass = conn.GetClass(
                        ClassName=o.path.classname,
                        namespace=o.path.namespace,
                        LocalOnly=False, IncludeQualifiers=True)
                results.append(get_inst_info(o, klass))
            else:
                results.append(get_inst_info(o))

        return self.render('filtered_reference_names.mako',
                className        = path.classname,
                assoc_call       = assoc_calls[assocCall],
                assoc_call_label = assoc_call_labels[assocCall],
                assoc_class      = assocClass,
                result_class     = resultClass,
                role             = role,
                result_role      = resultRole,
                properties       = properties,
                results          = results)

    @view()
    def on_FilteredReferenceNamesDialog(self, path):
        return self.render('filtered_reference_names_dialog.mako',
                path       = path,
                className  = path.classname,
                iname      = get_inst_info(path))

    @view()
    def on_GetClass(self, className):
        klass = self.conn.GetClass(ClassName=className, LocalOnly=False,
                IncludeClassOrigin=True, IncludeQualifiers=True)
        kwargs = {
                'className'   : className,
                'super_class' : klass.superclass,
                'aggregation' : klass.qualifiers.has_key('aggregation'),
                'association' : klass.qualifiers.has_key('association')
        }
        if klass.qualifiers.has_key('description'):
            kwargs['description'] = klass.qualifiers['description'].value
        else:
            kwargs['description'] = None
        if klass.qualifiers:
            kwargs['qualifiers'] = [ (q.name, _val2str(q.value))
                    for q in klass.qualifiers.values()
                    if  q.name.lower() != 'description']
        else:
            kwargs['qualifiers'] = []

        items =  []
        for item in chain(klass.methods.values(), klass.properties.values()):
            items.append(get_class_item_details(className, item))
        kwargs['items'] = sorted(items, _cmp_params(klass))

        return self.render('get_class.mako', **kwargs)

    @view(http_method=GET_AND_POST)
    def on_GetInstance(self, className=None, path=None, **params):
        if className is None and path is None:
            raise ValueError("either className or path must be given")
        conn = self.conn
        if path is None:
            # Remove 'PropName.' prefix from param names.
            params = dict([(x[9:],y) for (x, y) in params.items()
                                     if x.startswith('PropName.')])
            path = pywbem.CIMInstanceName(className,
                    keybindings=params, namespace=self._local.ns)

        klass = conn.GetClass(ClassName=path.classname,
                LocalOnly=False, IncludeQualifiers=True)
        inst = conn.GetInstance(InstanceName=path, LocalOnly = False)

        return self.render('get_instance.mako',
                className = path.classname,
                instance = get_inst_info(inst, klass))

    @view()
    def on_GetInstD(self, className):
        klass = self.conn.GetClass(ClassName=className, LocalOnly=False,
                IncludeQualifiers=True)

        items = [   get_class_item_details(className, i)
            for i in sorted(klass.properties.values(), key=lambda a: a.name)
            if  i.qualifiers.has_key('key') ]
        return self.render('get_instance_dialog.mako',
                className = className,
                items     = items)

    @view(http_method=POST)
    def on_InvokeMethod(self, method, path=None, className=None, **params):
        if path is None and className is None:
            raise ValueError("either object path or className argument must"
                    " be given")
        conn = self.conn
        if className is None:
            className = path.classname
        if (   isinstance(path, pywbem.CIMInstanceName)
           and path.namespace is None):
            path.namespace = self._local.ns
        klass = conn.GetClass(ClassName = className, LocalOnly=False)
        cimmethod = klass.methods[method]

        in_values  = defaultdict(str)
        out_values = defaultdict(str)

        in_params = {}

        tmpl_in_params, tmpl_out_params = get_method_params(
                className, cimmethod)

        for p in tmpl_in_params:
            value = formvalue2cimobject(p, 'MethParam.', params)
            p['value'] = _val2str(value)
            if value is not None:
                in_params[p['name']] = value

        (rval, out_params) = conn.InvokeMethod(
                MethodName = method,
                ObjectName = className if path is None else path,
                **in_params)

        out_values = {}
        if out_params:
            for p in tmpl_out_params:
                value = formvalue2cimobject(p, '', out_params)
                p['value'] = _val2str(value)

        iname = None
        if path is not None:
            iname = get_inst_info(path, klass)

        return self.render('invoke_method.mako',
                className    = className,
                method_name  = method,
                iname        = iname,
                in_params    = tmpl_in_params,
                out_params   = tmpl_out_params,
                return_value = _val2str(rval))

    @view(http_method=POST, require_url=False, require_ns=False,
            returns_response=True)
    def on_Login(self, **kwargs):
        try:
            scheme, host, port = [kwargs[k] for k in (
                "scheme", "host", "port")]
        except KeyError:
            raise BadRequest(
                    "missing one of ['scheme', 'host', 'port'] arguments")
        ns = kwargs.get('ns', None)
        url = scheme+'://'+host
        if not (  (scheme == 'https' and port == '5989')
               or (scheme == 'http' and port == '5988')):
            url += ':'+port
        if host[0] == '/':
            url = host
        self._local.url = url
        self._local.ns = ns
        if ns:
            return self.on_EnumClassNames()
        return self.on_EnumNamespaces()

    @view(require_url=False, require_ns=False)
    def on_Logout(self):
        # Enable the client to reauthenticate, possibly as a new user
        self.response.set_cookie('yawn_logout', "true",
                path=_base_script(self._local.request))
        return self.render('logout.mako')

    @view(http_method=POST)
    def on_ModifyInstance(self, path, **params):
        return self._createOrModifyInstance(path.classname, path, **params)

    @view(http_method=GET_AND_POST)
    def on_ModifyInstPrep(self, path):
        conn = self.conn
        klass = conn.GetClass(ClassName=path.classname,
                LocalOnly=False, IncludeQualifiers=True)
        inst  = conn.GetInstance(InstanceName=path,
                LocalOnly=False, IncludeQualifiers=True)
        instance = get_inst_info(inst, klass) #, include_all=True

        return self.render('modify_instance_prep.mako',
            new       = False,
            className = path.classname,
            instance  = instance)

    @view(require_url=False, require_ns=False)
    def on_Pickle(self, path):
        return self.render('pickle.mako',
                className      = path.classname,
                str_obj        = str(path),
                compressed_obj = _encodeObject(path),
                xml_obj        = path.tocimxml().toprettyxml())

    @view()
    def on_PrepMethod(self, method, path=None, className=None):
        if path is None and className is None:
            raise ValueError("either object path or className argument must"
                    " be given")
        if className is None:
            className = path.classname
        klass = self.conn.GetClass(ClassName = className, LocalOnly=False,
                IncludeQualifiers=True)

        cimmethod = klass.methods[method]
        in_params, out_params = get_method_params(className, cimmethod)
        iname = None
        if path is not None:
            iname = get_inst_info(path, klass)

        return self.render('prep_method.mako',
                className   = className,
                method_name = method,
                iname       = iname,
                in_params   = in_params,
                out_params  = out_params,
                return_type = cimmethod.return_type)

    @view()
    def on_PyProvider(self, className):
        klass = self.conn.GetClass(ClassName = className, LocalOnly=False,
                    IncludeClassOrigin=True, IncludeQualifiers=True)
        code, mof = codegen(klass)
        return self.render('py_provider.mako',
                className = className,
                code      = code,
                mof       = mof)

    @view(http_method=POST)
    def on_Query(self, query=None, lang=QLANG_WQL):
        conn = self.conn
        if query is None:
            if "query" not in self._local.request.form:
                raise ValueError("missing query string argument")
            query = request.form["query"]
        if isinstance(lang, int):
            lang = query_languages[QLANG_WQL]
        elif isinstance(lang, basestring):
            if not lang in query_languages:
                raise ValueError("lang must be one of: {}".format(
                    query_languages))
        else:
            raise TypeError("lang must be either string or integer not: {}".
                    format(lang.__class__.__name__))

        insts = conn.ExecQuery(QueryLanguage=lang,
                Query=query, namespace=self._local.ns)
        results = []
        ccache = pywbem.NocaseDict()
        for inst in insts:
            cn = inst.path.classname
            try:
                klass = ccache[cn]
            except KeyError:
                klass = ccache[cn] = conn.GetClass(cn, LocalOnly=False)
            results.append(get_inst_info(inst, klass))
        return self.render('query.mako',
                qlang   = lang,
                query   = query,
                results = results)

    @view()
    def on_QueryD(self, className=''):
        return self.render('query_dialog.mako', className=className)

    @view()
    def on_ReferenceNames(self, path):
        """ The goal here is to list InstPaths to all related objects, grouped
        in the
         following manner:
         - Assoc Class Name
           - Role of related object
             - Type of object (its classname)
               - instPath1
               - instPath2
               - ...
             - Another type (classname)
               - instPaths
           - Another role
             - type
               - paths
         - Another Assoc Class Name
           - Role
             - ...
         Known bugs: if an assoc class has a key property of type other than
         REF, we'll probably blow up.  We also won't follow non-key REF
         properties (if there are such things)
        """
        oldns = path.namespace
        # TODO remove this namespace hack when pywbem is fixed
        path.namespace = None
        refs = self.conn.ReferenceNames(ObjectName=path)
        path.namespace = oldns is not None and oldns or self._local.ns

        refdict = {}
        for ref in refs:
            refInstPath = ref
            assocClassName = refInstPath.classname
            if assocClassName not in refdict.keys():
                refdict[assocClassName] = {}
            for role in refInstPath.keys():
                roleInstPath = refInstPath[role]
                if roleInstPath == path:
                    continue
                if role not in refdict[assocClassName]:
                    refdict[assocClassName][role] = {}
                roleClassName = roleInstPath.classname
                if roleClassName not in refdict[assocClassName][role]:
                    refdict[assocClassName][role][roleClassName] = []
                refdict[assocClassName][role][roleClassName].append(
                        roleInstPath)

        refmap = {}
        for assoc, roles in sorted(refdict.items(), key=lambda i: i[0]):
            rols = refmap[assoc] = []
            for role, refs in sorted(roles.items(), key=lambda i: i[0]):
                if not refs: continue
                rs = []
                for cls, ref_paths in sorted(refs.items(), key=lambda i: i[0]):
                    rfs = [ get_inst_info(p) for p in sorted(ref_paths) ]
                    rs.append((cls, p.namespace, rfs))
                rols.append((role, rs))

        return self.render('reference_names.mako',
                iname        = get_inst_info(path),
                associations = sorted(refdict.keys()),
                refmap       = refmap)

