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

import logging
import traceback
import re
import pywbem
import pywbem.cim_http
import cgi
import types
import cPickle
import base64
import urlparse
import string
import zlib
import os
import sys
import inspect
#import mako
#import mako.lookup
from werkzeug.wrappers import Response, Request
from werkzeug.routing import Map, Rule, BaseConverter, ValidationError
from werkzeug.exceptions import (
        HTTPException, NotFound, Unauthorized, BadRequest)
try:
    from pywbem.cim_provider2 import codegen
except ImportError:
    codegen = None

log = logging.getLogger(__name__)

# Mostly I just wanted to be able to say that I've used lambda functions
#_val2str = lambda x: (type(x) == types.UnicodeType and x or str(x))
##############################################################################
# no need to cgi.urllib.unquote_plus().  mod_python does that for us.
_decodeObject = lambda x: (cPickle.loads(
    zlib.decompress(base64.urlsafe_b64decode(x))))
##############################################################################
_encodeObject = lambda x: (base64.urlsafe_b64encode(
    zlib.compress(cPickle.dumps(x, cPickle.HIGHEST_PROTOCOL))))
##############################################################################
def _val2str(x):
    #if type(x) == types.UnicodeType:
    #    return x
    if x is None:
        return '<font color="#999999"><i>Null</i></font>'
    elif isinstance(x,list):
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
        return cgi.escape(rval)
    else:
        return cgi.escape(unicode(x))

##############################################################################
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

##############################################################################
def _sortkey(keylist, klass):
    """Sort a list of property names, but bubble the key classes first
    in the sorted results."""

    def keycmp(a, b):
        def is_key(key):
            klassProp = klass.properties.has_key(key) and klass.properties[key] or None
            return klassProp and klassProp.qualifiers.has_key('key')
        is_key_a = is_key(a)
        is_key_b = is_key(b)
        if is_key_a and is_key_b:
            return cmp(a, b)
        if is_key_a and not is_key_b:
            return -1
        if not is_key_a and is_key_b:
            return 1
        return cmp(a, b)
    
    keylist.sort(keycmp)

##############################################################################
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

##############################################################################
def isSubClass(req, url, ns, subClassName, parentClassName):
    conn = _getConn(req, url, ns)

    #first the easy case:  are they the same
    req.write('<br>is ' + subClassName + ' a subclass of ' + parentClassName)
    if subClassName == parentClassName:
        return True
    #now, get the class object for subClassName, see if its parent class is parentClassName
    classNameToCheck = subClassName
    while classNameToCheck != None:
#        req.write('<br>is ' + subClassName + ' a subclass of ' + parentClassName)
#        req.write('<br>classNameToCheck: ' + classNameToCheck)
        subklass = conn.GetClass(classNameToCheck, LocalOnly=False, 
                IncludeQualifiers=True)
#        req.write('<br>subklass: ' + `subklass`)
#        req.write('<br>parentClassName: ' + parentClassName)

        if subklass.superclass != None:
#            req.write('<br>subklass.superclass: ' + subklass.superclass)
            classNameToCheck = subklass.superclass
            if subklass.superclass == parentClassName:
                req.write('<br><b>Yes! Returning True</b><br><br>')
                return True
#            req.write('<br>new classNameToCheck: ' + classNameToCheck)
#            req.write('<br><br>')
        else:
            classNameToCheck = None
    req.write('<br><b>Didn\'t find it... returning False</b><br><br>')
    return False;

##############################################################################
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
    return rval

##############################################################################
def _printInstHeading(keys, includeNS=False, omitGetLink = False):
    ht =     '  <tr bgcolor="CCCCCC">\n'
    if not omitGetLink:
        ht+=     '    <th></th>\n'
    for key in keys:
        ht+= '    <th>'+key+'</th>\n'
    if includeNS:
        ht+= '<th><i><font color="#00AA00">Namespace</font></i></th>'
    ht+=     '  </tr>\n'
    return ht
_re_url_func = re.compile(r'^[A-Z][a-z_A-Z0-9]+$')

##############################################################################
def _baseScript(request):
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

##############################################################################
# TODO
"""
- Make GetClass links on REF type fields for properties and parameters.
- Refactor some of the code to display properties and parameters to
  decrease code duplication (such as handling of valuemaps)
- Fix the javascript combobox to actually send typed values instead of
  just look cute.
- Beautify the error screens
- Fix various code that is not case insensitive
- Display property/method/parameter names from the class instead of the
  instance, as they will be more likely to be pretty (mixed-case), whereas
  providers sometimes will have all lowercase property names that don't
  look as good.
- Mark properties on instances that aren't in the schema (it's been known
  to happen).


"""

##############################################################################
# Older stuff
##############################################################################
# Combobox support from
# http://particletree.com/features/upgrade-your-select-element-to-a-combo-box/
# This isn't currently working (typed values aren't sent).
# http://particletree.com/features/upgrade-your-select-element-to-a-combo-box/#6606
_comboBox_js = """
<!-- Removed combobox script for now.  If we need it, go get it (and get it working) -->
"""



def cmpi_codegen(klass):
    code = '''/* <Insert License Here> */

#include <stdio.h>
#include <stdarg.h>

#include <cmpi/cmpidt.h>
#include <cmpi/cmpift.h>
#include <cmpi/cmpimacs.h>

/* A simple stderr logging/tracing facility. */
#ifndef _CMPI_TRACE
#define _CMPI_TRACE(tracelevel,args) _logstderr args 
static void _logstderr(char *fmt,...)
{
   va_list ap;
   va_start(ap,fmt);
   vfprintf(stderr,fmt,ap);
   va_end(ap);
   fprintf(stderr,"\\n");
}
#endif

/* Global handle to the CIM broker. This is initialized by the CIMOM when the provider is loaded */
static const CMPIBroker * _broker = NULL;

static CMPIStatus %(cname)sCleanup(CMPIInstanceMI * self,
                                   const CMPIContext * ctx,
                                   CMPIBoolean terminating)
{
    CMPIStatus st = { CMPI_RC_OK, NULL }; 
    return st; 
}

static CMPIStatus %(cname)sEnumInstanceNames(CMPIInstanceMI * self,
                                             const CMPIContext * ctx,
                                             const CMPIResult * rslt,
                                             const CMPIObjectPath * op)
{
    _CMPI_TRACE(1,("%(cname)sEnumInstanceNames() called, ctx %%p, result %%p, op %%p", ctx, rslt, op));
    CMPIStatus status = {CMPI_RC_OK, NULL};

    CMPIString* cns = CMGetNamespace(op, &status); 
    char* ns = CMGetCharsPtr(cmstr, &status); 
    CMPIString* ccname = CMGetClassName(op, &status); 
    char* cname = CMGetCharsPtr(ccname, &status); 
    CMPIObjectPath* cop = CMNewObjectPath(_broker, ns, cname, &status); 
    CMReturnObjectPath(rslt, cop);
    CMReturnDone(rslt); 
    status.rc = CMPI_RC_OK; 
    status.msg = NULL; 

    _CMPI_TRACE(1,("%(cname)sEnumInstanceNames() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
    return status;
}

static CMPIStatus %(cname)sEnumInstances(
        CMPIInstanceMI * self,
		const CMPIContext * ctx,
		const CMPIResult * rslt,
		const CMPIObjectPath * op,
		const char ** properties)
{
   CMPIStatus status = {CMPI_RC_OK, NULL};	

    _CMPI_TRACE(1,("%(cname)sEnumInstances() called, ctx %%p, rslt %%p, op %%p, properties %%p", ctx, rslt, op, properties));

	//CMReturnInstance(rslt, getSSHServiceInstance(&status)); 
	CMReturnDone(rslt); 

   status.rc = CMPI_RC_OK; 
   status.msg = NULL; 

   _CMPI_TRACE(1,("%(cname)sEnumInstances() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

static CMPIStatus %(cname)sGetInstance(
		CMPIInstanceMI * self,
		const CMPIContext * ctx,
		const CMPIResult * rslt,
		const CMPIObjectPath * op,
		const char ** properties)
{
   CMPIStatus status = {CMPI_RC_OK, NULL};

    _CMPI_TRACE(1,("%(cname)sGetInstance() called, ctx %%p, rslt %%p, op %%p, properties %%p", ctx, rslt, op, properties));

	//CMReturnInstance(rslt, getSSHServiceInstance(&status)); 
	CMReturnDone(rslt); 

   status.rc = CMPI_RC_OK; 
   status.msg = NULL; 

   _CMPI_TRACE(1,("%(cname)sGetInstance() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

static CMPIStatus %(cname)sCreateInstance(
		CMPIInstanceMI * self,
		const CMPIContext * ctx,
		const CMPIResult * rslt,
		const CMPIObjectPath * op,
		const CMPIInstance * inst)
{
   CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};
   
    _CMPI_TRACE(1,("%(cname)sCreateInstance() called, ctx %%p, rslt %%p, op %%p, inst %%p", ctx, rslt, op, inst));
   _CMPI_TRACE(1,("%(cname)sCreateInstance() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}


// ----------------------------------------------------------------------------

#ifdef CMPI_VER_100
#define %(cname)sSetInstance %(cname)sModifyInstance
#endif

static CMPIStatus %(cname)sSetInstance(
		CMPIInstanceMI * self,
		const CMPIContext * ctx,
		const CMPIResult * rslt,
		const CMPIObjectPath * op,
		const CMPIInstance * inst,
		const char ** properties)
{
   CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};
   
    _CMPI_TRACE(1,("%(cname)sSetInstance() called, ctx %%p, rslt %%p, op %%p, inst %%p, properties %%p", ctx, rslt, op, inst, properties));
   _CMPI_TRACE(1,("%(cname)sSetInstance() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

// ----------------------------------------------------------------------------


/* DeleteInstance() - delete/remove the specified instance. */
static CMPIStatus %(cname)sDeleteInstance(
		CMPIInstanceMI * self,	
		const CMPIContext * ctx,
		const CMPIResult * rslt,	
		const CMPIObjectPath * op)
{
   CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};

    _CMPI_TRACE(1,("%(cname)sDeleteInstance() called, ctx %%p, rslt %%p, op %%p", ctx, rslt, op));
   _CMPI_TRACE(1,("%(cname)sDeleteInstance() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

// ----------------------------------------------------------------------------


static CMPIStatus %(cname)sExecQuery(
		CMPIInstanceMI * self,
		const CMPIContext * ctx,
		const CMPIResult * rslt,
		const CMPIObjectPath * op,
		const char * query,
		const char * lang)
{
   CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};	/* Return status of CIM operations. */
   
    _CMPI_TRACE(1,("%(cname)sExecQuery() called, ctx %%p, rslt %%p, op %%p, query %%s, lang %%s", ctx, rslt, op, query, lang));
   _CMPI_TRACE(1,("%(cname)sExecQuery() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

//  associatorMIFT
//

CMPIStatus %(cname)sAssociatorNames(
		CMPIAssociationMI* self,
		const CMPIContext* ctx,
		const CMPIResult* rslt,
		const CMPIObjectPath* op,
		const char* assocClass,
		const char* resultClass,
		const char* role,
		const char* resultRole)
{
   	CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};
   
    _CMPI_TRACE(1,("associatorNames() called, ctx %%p, rslt %%p, op %%p, assocClass %%s, resultClass %%s, role %%s, resultRole %%s", ctx, rslt, op, assocClass, resultClass, role, resultRole));

   _CMPI_TRACE(1,("associatorNames() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

/***************************************************************************/
CMPIStatus %(cname)sAssociators(
		CMPIAssociationMI* self,
		const CMPIContext* ctx,
		const CMPIResult* rslt,
		const CMPIObjectPath* op,
		const char* assocClass,
		const char* resultClass,
		const char* role,
		const char* resultRole,
		const char** properties)
{
   	CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};
   
    _CMPI_TRACE(1,("associators() called, ctx %%p, rslt %%p, op %%p, assocClass %%s, resultClass %%s, role %%s, resultRole %%s", ctx, rslt, op, assocClass, resultClass, role, resultRole));

   _CMPI_TRACE(1,("associators() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

/***************************************************************************/
CMPIStatus %(cname)sReferenceNames(
		CMPIAssociationMI* self,
		const CMPIContext* ctx,
		const CMPIResult* rslt,
		const CMPIObjectPath* op,
		const char* resultClass,
		const char* role)
{
   	CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};
   
    _CMPI_TRACE(1,("referenceNames() called, ctx %%p, rslt %%p, op %%p, resultClass %%s, role %%s", ctx, rslt, op, resultClass, role));

   _CMPI_TRACE(1,("referenceNames() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}


/***************************************************************************/
CMPIStatus %(cname)sReferences(
		CMPIAssociationMI* self,
		const CMPIContext* ctx,
		const CMPIResult* rslt,
		const CMPIObjectPath* op,
		const char* resultClass,
		const char* role,
		const char** properties)
{
   	CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};
   
    _CMPI_TRACE(1,("references() called, ctx %%p, rslt %%p, op %%p, resultClass %%s, role %%s, properties %%p", ctx, rslt, op, resultClass, role, properties));

   _CMPI_TRACE(1,("references() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

/***************************************************************************/
CMPIStatus %(cname)sInvokeMethod(
		CMPIMethodMI* self,
		const CMPIContext* ctx,
		const CMPIResult* rslt,
		const CMPIObjectPath* op,
		const char* method,
		const CMPIArgs* in,
		CMPIArgs* out)
{
   	CMPIStatus status = {CMPI_RC_ERR_NOT_SUPPORTED, NULL};
   
    _CMPI_TRACE(1,("invokeMethod() called, ctx %%p, rslt %%p, op %%p, method %%s, in %%p, out %%p", ctx, rslt, op, method, in, out));

   _CMPI_TRACE(1,("invokeMethod() %%s", (status.rc == CMPI_RC_OK)? "succeeded":"failed"));
   return status;
}

/***************************************************************************/


CMMethodMIStub( %(cname)s, %(cname)s, _broker, CMNoHook); 
CMInstanceMIStub( %(cname)s, %(cname)s, _broker, CMNoHook); 
CMAssociationMIStub( %(cname)s, %(cname)s, _broker, CMNoHook); 


''' % {'cname':klass.classname} 
    return code

GET, POST, GET_AND_POST = 1, 2, 3
def view(
        http_method=GET,
        require_url=True,
        require_ns=True,
        returns_response=False):
    def _form_val(f, k, pop=True):
        v =  f.pop(k) if pop else f[k]
        if isinstance(v, list):
            if not len(v): return None
            return v[0]
        return v
    def _deco(f):
        def _new_f(self, request, *args, **kwargs):
            form = request.form.copy()
            for k in kwargs:
                if k in form:
                    del form[k]
            if require_url and ("url" not in kwargs or kwargs['url'] is None):
                kwargs['url'] = None
                if not 'ns' in kwargs:
                    kwargs['ns'] = None
                if http_method & GET:
                    try:
                        kwargs['url'] = request.args['url']
                        if kwargs['ns'] is None:
                            kwargs['ns'] = request.args['ns']
                    except KeyError: pass
                if kwargs['url'] is None and http_method & POST:
                    try:
                        kwargs['url'] = _form_val(form, 'url')
                        if kwargs['ns'] is None:
                            kwargs['ns'] = _form_val(form, 'ns')
                    except KeyError: pass
                if require_url is True and kwargs['url'] is None:
                    raise BadRequest("missing url argument")
                if require_ns is True and kwargs['ns'] is None:
                    raise BadRequest("missing namespace argument")
            if not require_url and 'url' in kwargs and not kwargs['url']:
                del kwargs['url']
            if not require_ns and 'ns' in kwargs and not kwargs['ns']:
                del kwargs['ns']
            if http_method & POST:
                for k, v in form.items():
                    if isinstance(v, list):
                        if not len(v): continue
                        v = v[0]
                    kwargs[k] = v
            res = f(self, request, *args, **kwargs)
            if returns_response is True:
                return res
            self.response.data = res
            return self.response
        return _new_f
    return _deco

def _getUserPW(request):
    if 'Authorization' not in request.headers:
        return (None, None)
    auth = request.authorization
    return (auth.username, auth.password)

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

class Yawn(object):

    def __init__(self, templates="templates", modules=None):
        self.url_map = Map([
            Rule('/', endpoint='index'),
            Rule('/AssociatedClasses/<id:className>',
                endpoint="AssociatedClasses"),
            Rule('/AssociatorNames/<base64:obj>', endpoint="AssociatorNames"),
            Rule('/CMPIProvider/<id:className>', endpoint="CMPIProvider"),
            Rule('/CreateInstance/<id:className>', endpoint='CreateInstance'),
            Rule('/CreateInstancePrep/<id:className>',
                endpoint='CreateInstancePrep'),
            Rule('/DeleteClass/<id:className>', endpoint='DeleteClass'),
            Rule('/DeleteInstance/<base64:obj>',
                endpoint='DeleteInstance'),
            Rule('/EnumClassNames', endpoint='EnumClassNames'),
            Rule('/EnumInstanceNames/<id:className>',
                endpoint='EnumInstanceNames'),
            Rule('/EnumInstrumentedClassNames',
                endpoint='EnumInstrumentedClassNames'),
            Rule('/EnumInstances/<id:className>', endpoint='EnumInstances'),
            Rule('/EnumNamespaces', endpoint='EnumNamespaces'),
            Rule('/FiltereredReferenceNames',
                endpoint='FilteredReferenceNames'),
            Rule('/FilteredReferenceNamesDialog/<base64:obj>',
                endpoint="FilteredReferenceNamesDialog"),
            Rule('/GetClass/<id:className>', endpoint='GetClass'),
            Rule('/GetInstance/inst/<base64:obj>',
                endpoint='GetInstance'),
            Rule('/GetInstance/cn/<id:className>', endpoint='GetInstance'),
            Rule("/GetInstD/<id:className>", endpoint="GetInstD"),
            Rule("/InvokeMethod/<base64:obj>/<id:method>",
                endpoint="InvokeMethod"),
            Rule('/Login', endpoint='Login'),
            Rule('/Logout', endpoint='Logout'),
            Rule("/ModifyInstance/<base64:obj>",
                endpoint="ModifyInstance"),
            Rule("/ModifyInstPrep/<base64:obj>",
                endpoint="ModifyInstPrep"),
            Rule("/MofComp", endpoint="MofComp"),
            Rule("/Pickle/<base64:obj>", endpoint="Pickle"),
            Rule("/PrepMethod/<base64:obj>/<id:method>",
                endpoint="PrepMethod"),
            Rule("/PrepMofComp", endpoint="PrepMofComp"),
            Rule("/PyProvider/<id:className>", endpoint="PyProvider"),
            Rule("/Query", endpoint="Query"),
            Rule("/Query/<qlang:lang>", endpoint="Query"),
            Rule('/QueryD', endpoint='QueryD'),
            Rule("/ReferenceNames/<base64:obj>",
                endpoint="ReferenceNames"),
            ], converters =
                { 'id'     : IdentifierConverter
                , 'mode'   : ModeConverter
                , 'bool'   : BooleanConverter
                , 'base64' : Base64Converter
                , 'qlang'  : QLangConverter })

#        self._lookup = mako.lookup.TemplateLookup(
#                directories=templates,
#                module_directory=modules
#        )
        self.urls = None
        self._connection = None
        self._response = None
        self._color = True

    @property
    def response(self):
        if self._response is None:
            self._response = Response(content_type="text/html")
        return self._response

    @property
    def color(self):
        return self._color

    def _toggle_color(self):
        self._color = not self._color
        return self._color

    def conn(self, request, url, ns):
        if (   self._connection
           and self._connection.url == url
           and self._connection.default_namespace == ns):
            return self._connection

        (user, pw) = _getUserPW(request)
        if user is None:
            user = ''
        if pw is None:
            pw = ''
        if len(user) > 0 and request.cookies.has_key('yawn_logout'):
            if request.cookies['yawn_logout'] in ['true', 'pending']:
                self.response.set_cookie('yawn_logout', 'false',
                        path=_baseScript(request))
                user, pw = '', ''
        self._connection = pywbem.WBEMConnection(url, (user, pw))
        self._connection.default_namespace = ns
        self._connection.debug = True
        return self._connection

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, 'on_' + endpoint)(request, **values)
        except HTTPException, e:
            return e

    def wsgi_app(self, environ, start_response):
        if self.urls is None:
            self.urls = self.url_map.bind_to_environ(environ)
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
            ht = self._printHead('Error')
            details = _code2string(arg[0])
            ht+= '<p><i>'+details[0]+': ' + details[1]+'</i>'
            errstr = arg[1]
            if errstr.startswith('cmpi:'):
                # we have a traceback from CMPI, that might have newlines
                # converted.  need to convert them back. 
                errstr = errstr[5:].replace('<br>', '\n')
            elif 'cmpi:Traceback' in errstr:
                errstr = errstr.replace('cmpi:Traceback', 'Traceback')
                errstr = errstr.replace('<br>', '\n')
            ht+= '<pre>'+cgi.escape(errstr)+'</pre>'
            ht+= '<hr>'
            if self._connection is not None and self._connection.debug is True:
                if self._connection.last_request is not None:
                    ht+= '<pre>'+cgi.escape(self._connection.last_request)
                    ht+= '</pre>'
                ht+= '<hr>'
                if self._connection.last_reply is not None:
                    ht+= '<pre>'+cgi.escape(self._connection.last_reply)
                    ht+= '</pre>'
            ht+= '</body></html>'
            response = Response(ht, content_type="text/html")
            return response(environ, start_response)
        except Exception:
            output = traceback.format_exc()
#        output = traceback.format_exc()
#        log.error(output)
#        output += """\nThe env dictionary:\n%s""" % (
#                "\n".join("%s: %s"%(k, v) for k, v in env.items()))
            response = Response(output, content_type='text/plain')
            return response(environ, start_response)
        finally:
            self._connection = None
            self._response = None
            self._color = True

    def _frontMatter(self, request, url, ns):
        """ @return (response, pywbem connection) """
        resp = self.response
        resp.headers['WWW-Authenticate'] = (
                ', '.join([ 'Basic realm="CIMOM at {}"'.format(url)
                          , 'qop="auth,auth-int"']))
        return self.conn(request, url, ns)

    def _makeHref(self, request, func, dict, target, append=''):
        return ( '<a href="'+self.urls.build(func, dict)
               + append + '">'+cgi.escape(target)+'</a>')

    def _makeHrefWithTags(self, env, func, dict, target, openTags, closeTags):
        return ( '<a href="'+self.urls.build(func, dict)
               +'">'+openTags+cgi.escape(target) + closeTags+'</a>')

    def _printHead(self, title = None, heading = None,
            req = None, urlargs = None):
        ht = '\n<html><head><title>YAWN: CIM'
        if title is not None:
            ht+= ' ' + title
        ht+= '</title></head><body link="#0000ff" >'
        table = False
        if req is not None:
            table = True
        if table:
            ht+= '<table border=0 cellpadding=0 cellspacing=0 vspace=0>'
            ht+= '<tr><td nowrap width=100% valign=top>'
            if heading is not None:
                ht+= '<h1>'+heading+'</h1>'
            ht+= '</td>'
            if urlargs and 'ns' in urlargs and 'url' in urlargs:
                lurlargs = {'ns':urlargs['ns'], 'url':urlargs['url']}
                ht+= '<td valign=top nowrap align=right><font size=-1><i>'
                ht+= self._makeHref(req, 'EnumClassNames', lurlargs,
                        lurlargs['ns'])
                ht+= '&nbsp;&nbsp;&nbsp;</i></td>'
            if urlargs and 'url' in urlargs:
                ht+= '<td valign=top nowrap align=right><font size=-1><i>'
                ht+= self._makeHref(req, 'EnumNamespaces',
                        {'url':urlargs['url']}, 'Namespaces')
                ht+= '&nbsp;&nbsp;&nbsp;</i></td>'
            if urlargs and 'ns' in urlargs and 'url' in urlargs:
                try:
                    lurlargs['className'] = urlargs['className']
                except KeyError:
                    pass
                ht+= '<td valign=top nowrap align=right><font size=-1><i>'
                ht+= self._makeHref(req, 'QueryD', lurlargs, 'Query')
                ht+= '&nbsp;&nbsp;&nbsp;</i></td>'
            ht+= '<td valign=top nowrap align=right><font size=-1><i>'
            ht+= '<a href="'+self.urls.build('Logout')
            ht+= '">Logout &gt;&gt;</a></i>'
            ht+= '</td></tr></table>'
        return ht

    def _printEnumDeep(self, request, curclass, dict, urlargs, level = 0):
        classNames = dict[curclass]
        classNames.sort()
        ht = ''
        for className in classNames:
            hasKids = dict.has_key(className)
            ht+= '<tr'
            if self.color:
                ht+= ' bgcolor="#EEFFEE"'
            self._toggle_color()
            ht+= '><td>'
            for i in range(level-1):
               ht+= '|&nbsp;&nbsp;&nbsp;&nbsp;'
            if (level > 0):
                ht+= '|---'
            urlargs["className"] = className
            if level==0:
               ht+= '<b>'
            isCimSchema = className.startswith("CIM_")
            if not isCimSchema:
               ht+= '<i>'
            if not hasKids:
                ht+= self._makeHref(request, 'GetClass', urlargs, className)
            else:
                ht+= self._makeHrefWithTags(request, 'GetClass', urlargs,
                        className, '<font color="#7777ff">', '</font>')
            if not isCimSchema:
               ht+= '</i>'
            if level==0:
               ht+= '</b>'
            ht+= '</td><td>'
            ht+= self._makeHref(request, 'EnumInstanceNames', urlargs,
                    'Instance Names')
            ht+= '</td><td>&nbsp;&nbsp;&nbsp;'
            ht+= self._makeHref(request, 'EnumInstances', urlargs, 'Instances')
            ht+= '</td></tr>'
            if hasKids:
                ht += self._printEnumDeep(request, className,
                        dict, urlargs, level+1)
        return ht

    def _printInstanceNames(self, request, urlargs, instNames,
            omitGetLink=False):
        if len(instNames) > 0:
            ht = '\n<table border="1" cellpadding="2">\n'
            if instNames[0].namespace:
                keys = instNames[0].keys()
                keys.sort()
                ht+= _printInstHeading(keys, includeNS=True,
                        omitGetLink=omitGetLink)
            else:
                keys = instNames[0].keys()
                keys.sort()
                ht+= _printInstHeading(keys, omitGetLink=omitGetLink)
            instNames.sort()
            for instName in instNames:
                ht += self._printInstRow(request, urlargs, keys, instName,
                        omitGetLink)
            return ht + '</table>\n'

    def _printInstRow(self, request, urlargs, keys, inst, omitGetLink = False):
        lurlargs = urlargs.copy()
        lurlargs['obj'] = inst
        if inst.namespace is not None:
            lurlargs['ns'] = inst.namespace
        ht =     '  <tr>\n'
        if not omitGetLink:
            ht+=     '    <td>\n'
            ht+= self._makeHref(request, 'GetInstance', lurlargs, 'get')+'\n'
            ht+=     '    </td>\n'
        for key in keys:
            keyval = inst[key]
            ht+= '    <td>\n'
            if isinstance(keyval, pywbem.CIMInstanceName):
                ns = keyval.namespace
                if ns is not None:
                    lurlargs['ns'] = ns
                lurlargs['obj'] = keyval
                ht+= self._makeHref(request, 'GetInstance', lurlargs,
                        _val2str(keyval))+'\n'
                if ns is not None:
                    ht+= '<br><i>In namespace: ' + ns + '</i>'
            else:
                ht+= _val2str(keyval)+'\n'
            ht+= '    </td>\n'
        if inst.namespace is not None:
            ht+= '    <td><i><font color="#00AA00">'+inst.namespace
            ht+= '</font></i></td>\n'
        ht+=     '  </tr>\n'
        return ht

    def _displayInstanceMod(self, request, url, ns, klass,
            oldInstPathPair = None, getInst=False):
        conn = self._connection
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        oldInstPathDec = None
        if oldInstPathPair is not None:
            oldInstPathDec = oldInstPathPair[1]
        className = klass.classname
        urlargs['className'] = className
        oldInst = None
        if oldInstPathDec is not None:
            oldInst = conn.GetInstance(InstanceName=oldInstPathDec,
                    LocalOnly = False)
        haveRequiredProps = False
        if getInst:
            propNames = [p.name for p in klass.properties.values()
                    if 'Key' in p.qualifiers]
            propNames.sort()
        else:
            propNames = klass.properties.keys()
            _sortkey(propNames, klass)
        ht = '<table border=0><tr><td>'
        if getInst:
            method = 'GetInstance'
        elif oldInst is not None:
            method = 'ModifyInstance'
        else:
            method = 'CreateInstance'
        if oldInstPathPair is None:
            kwargs = { 'className' : className }
        else:
            kwargs = { 'obj' : oldInstPathDec }
        ht+= '<form action="'+self.urls.build(method, kwargs)+'" METHOD='
        if getInst:
            ht+= 'GET>'
        else:
            ht+= 'POST>'
        ht+= '<input type=hidden name="url" value="'+url+'">'
        ht+= '<input type=hidden name="ns" value="'+ns+'">'
        ht+= '<table border="1" cellpadding="2">'
        ht+= '<tr bgcolor="CCCCCC"><th>Type</th><th>Name</th><th>Value</th>'
        ht+= '</tr>'
        for propName in propNames:
            prop = klass.properties[propName]
            propIsKey = prop.qualifiers.has_key('key')
            propIsRequired = prop.qualifiers.has_key('required')
            propTitle = ''
            if prop.qualifiers.has_key('description'):
                propTitle = prop.qualifiers['description'].value
            ht+= '<tr'
            if propIsKey:
                ht+= ' bgcolor="#FFDDDD"'
            elif propIsRequired:
                ht+= ' bgcolor="#FFaaaa"'
                haveRequiredProps = True
            ht+= '>'
            if prop.reference_class is None:
                ht+= '<td>'+prop.type
                if prop.is_array:
                    ht+= ' [ ]'
            else:
                ht+= '<td>'+prop.reference_class + ' <i>Ref</i>'
            ht+= ( '</td><td title="'+cgi.escape(propTitle)+'">'
                 + self._makeHref(request, 'GetClass', urlargs, propName,
                     '#'+propName.lower())+'</td>')
            ht+= '<td>'
            fPropName = 'PropName.'+prop.name
            oldVal = None
            if oldInst is not None:
                if oldInst.properties.has_key(propName):
                    oldVal = oldInst.properties[propName].value
            if prop.qualifiers.has_key('valuemap'):
                if type(oldVal) == list:
                    oldVal = [str(x) for x in oldVal]
                needComboBox = True
                valmapQual = prop.qualifiers['valuemap'].value
                valuesQual = None
                if prop.qualifiers.has_key('values'):
                    valuesQual = prop.qualifiers['values'].value

                # Disable the combobox for now, because it isn't working, and
                # we may not actually need it.  For example, perhaps any time
                # values from VendorReserved are used, the vendor's subclass
                # will override the method, and thus the qualifiers, and
                # provide specific valuemap extensions that would in turn show
                # up in our drop down.
                #ht+= '<select name="'+fPropName+'" class="comboBox">'
                ht+= '<select name="'+fPropName+'"'
                if prop.is_array:
                    ht+= ' MULTIPLE SIZE=4'
                ht+= '>'
                if not prop.is_array:
                    ht+= '<option value='""'>'
                for i in range(0, len(valmapQual)):
                    curVal = valmapQual[i]
                    # skip valuemap items that aren't valid values
                    # such as the numeric ranges for DMTF Reserved and whatnot
                    try:
                        pywbem.tocimobj(prop.type, curVal)
                    except:
                        continue
                    ht+= '<option value="'+curVal+'"'
                    if oldVal is not None:
                        if type(oldVal) == list:
                            if curVal in oldVal:
                                ht+= ' SELECTED'
                        elif str(oldVal) == curVal:
                            ht+= ' SELECTED'
                    ht+= '>'+curVal
                    if valuesQual and i < len(valuesQual):
                        ht+= ' ('+valuesQual[i]+')'
                ht+= '</select>'

            else:
                if oldVal is not None and propIsKey:
                    ht+= _val2str(oldVal)
                elif prop.type == 'boolean' and not prop.is_array:
                    ht+= '<select name="'+fPropName+'">'
                    ht+= '<option value='""'>'
                    ht+= '<option value="True"'
                    if oldVal is not None and oldVal:
                        ht+= ' SELECTED'
                    ht+= '>True'
                    ht+= '<option value="False"'
                    if oldVal is not None and not oldVal:
                        ht+= ' SELECTED'
                    ht+= '>False'
                    ht+= '</select>'
                else:
                    ht+= '<input type=text size=50 name="'+fPropName+'"'
                    if oldVal is not None:
                        strValue = _val2str(oldVal)
                        if isinstance(oldVal,list):
                            strValue = strValue.replace('"','&quot;')
                        ht+= ' value="'+strValue+'"'
                    ht+= '>'
            ht+= '</td></tr>'

        ht+= '</table></td></tr>'
        ht+= '<tr><td colspan=3><table border=0><tr><td nowrap bgcolor="#FFDDDD">'
        ht+= '<i>Key Property</i></td>'
        if haveRequiredProps == True:
            ht+= '<td></td><td nowrap bgcolor="#FFaaaa">'
            ht+= '<i>Required (non-key) Property</i></td>'
        ht+= '<td width="100%" align="right">'
        if getInst:
            button = 'Get Instance'
        else:
            button = 'Save Instance'
        ht+= '<input type=submit value="%s"></td></table></td></tr>' % button
        ht+= '</form>'
        ht+= '</table>'
        return ht

    def _displayInstance(self, request, inst, obj, klass, urlargs):
        class_urlargs = urlargs.copy()
        class_urlargs["className"] = klass.classname
        ht= '<h2>Instance of '+self._makeHref(request, 'GetClass',
                class_urlargs, klass.classname)+'</h2>'
        ht+= '<h4>Host: <i><font color="#00AA00">' + _val2str(obj.host)
        ht+= '</font></i>'
        ht+= '<br>Namespace: <i><font color="#00AA00">'
        ht+= _val2str(obj.namespace) + '</font></i></h4>'
        ht+= '<align ="right">'
        urlargs['obj'] = obj
        ht+= '</align>'
        keys = inst.keys()
        _sortkey(keys, klass)
        ht+= '<table border="1" cellpadding="2">'
        ht+= '<tr>'
        ht+= '<td>'+self._makeHref(request, 'DeleteInstance', urlargs,
                'Delete')
        ht+= '<br>'+self._makeHref(request, 'ModifyInstPrep', urlargs,
                'Modify')
        ht+= '</td>'
        ht+= '<td align="right" colspan=2>View '
        ht+= self._makeHref(request, 'ReferenceNames', urlargs,
                'Objects Associated with this Instance')
        ht+= '<br>'
        ht+= self._makeHref(request, 'FilteredReferenceNamesDialog',
                urlargs,'(With Filters)')
        ht+= '</td></tr>'
        ht+= '<tr bgcolor="CCCCCC"><th>Type</th><th>Name</th><th>Value</th>'
        haveRequiredProps = False
        for key in keys:
            prop = inst.properties[key]
            klassProp = (  klass.properties.has_key(key)
                        and klass.properties[key] or None)
            propIsKey = klassProp and klassProp.qualifiers.has_key('key')
            propIsRequired = (   klassProp
                             and klassProp.qualifiers.has_key('required'))
            propTitle = ''
            if klassProp and klassProp.qualifiers.has_key('description'):
                propTitle = klassProp.qualifiers['description'].value
            ht+= '<tr'
            if propIsKey:
                ht+= ' bgcolor="#FFDDDD"'
            elif propIsRequired:
                ht+= ' bgcolor="#FFaaaa"'
                haveRequiredProps = True
            ht+= '>'
            if klassProp: 
                if klassProp.reference_class is None:
                    ht+= '<td>'+prop.type
                    if prop.is_array:
                        ht+= ' [ ]'
                else:
                    link_urlargs = class_urlargs.copy()
                    link_urlargs["className"] = klassProp.reference_class
                    ht+= '<td>'+self._makeHref(request, "GetClass",
                            link_urlargs, klassProp.reference_class)
                    ht+= ' <i>Ref</i>'
            else:
                ht+='<td><font color="red">PropNotInSchema</font>'
            ht+= '</td><td title="'+cgi.escape(propTitle)+'">'
            ht+= self._makeHref(request, 'GetClass', class_urlargs, key,
                    '#'+key.lower())+'</td><td>'


            if (   klassProp and klassProp.qualifiers.has_key('values')
               and klassProp.qualifiers.has_key('valuemap')):
                ht+= _displayMappedValue(prop.value, klassProp.qualifiers)
            elif klassProp and klassProp.reference_class is not None:
                ns = _val2str(inst[key].namespace)
                urlargs['ns'] = ns
                targetInstName = inst[key]
                urlargs['obj'] = targetInstName
                targetObjectPath = _val2str(targetInstName)
                ht+= self._makeHref(request, 'GetInstance', urlargs,
                        targetObjectPath)
            else:
                propval = _val2str(prop.value)
                if key.lower().endswith("classname"):
                    link_urlargs = class_urlargs.copy()
                    link_urlargs["className"] = propval
                    ht+= self._makeHref(request, "GetClass", link_urlargs,
                            propval)
                else:
                    ht+= propval
            ht+= '</td></tr>'
        ht+= '<tr><td colspan=3>'
        ht+= '<table border=0><tr><td nowrap bgcolor="#FFDDDD">'
        ht+= '<i>Key Property</i></td>'
        if haveRequiredProps == True:
            ht+= '<td></td><td nowrap bgcolor="#FFaaaa">'
            ht+= '<i>Required (non-key) Property</i></td>'
        ht+= '<td width="100%" align="right"></table></td></tr>'
        if klass.methods:
            ht+= '<tr><td colspan=3>'
            ht+= '<table>'
            ht+= '<tr><td>'
            ht+= '<font size=+1><center><b>Methods</b></center></font>'
            ht+= '</td></tr>'
            for method in klass.methods.values():
                ht+= '<tr>'
                ht+= ' <td>'
                methUrlArgs = urlargs.copy()
                methUrlArgs['obj'] = methUrlArgs['obj']
                methUrlArgs['method'] = method.name
                ht+= self._makeHref(request, 'PrepMethod', methUrlArgs,
                        method.name) + '('
                for param in method.parameters.keys():
                    if param != method.parameters.keys()[0]:
                        ht+= ','
                    ht+= param
                ht+=')'
                ht+= ' </td>'
                ht+= '</tr>'
            ht+= '</table>'
            ht+= '</td></tr>'
        purlargs = {'obj': obj}
        ht+= '<tr><td colspan=3>'
        ht+= 'Get the '+self._makeHref(request, 'Pickle',
                purlargs, 'LocalInstancePath')
        ht+= ' for use as a Method Reference Parameter'
        ht+= '</td></tr>'
        ht+= '</table>'
        return ht

    def _createOrModifyInstance(self, request, url, ns, className, obj,
            **params):
        conn = self._connection
        klass =  conn.GetClass(ClassName=className, 
                LocalOnly=False, IncludeQualifiers=True)
        if obj is not None:
            inst = conn.GetInstance(InstanceName=obj, LocalOnly = False)
        else:
            inst = pywbem.CIMInstance(className)
        inst.path = pywbem.CIMInstanceName(className, namespace=ns)
        # Remove 'PropName.' prefix from param names.
        params = dict ([(x[9:],y) for (x, y) in params.items()])
        for propName, propVal in params.items():
            metaProp = klass.properties[propName]
            if metaProp.reference_class is not None:
                dt = metaProp.reference_class
            else:
                dt = metaProp.type
            if not propVal:
                inst.update_existing([(propName,None)])
            else:
                if metaProp.reference_class is not None:
                    inst.properties[propName] = _decodeObject(propVal)
                else:
                    if metaProp.is_array:
                        if type(propVal) is not list:
                            propVal = propVal.strip()
                            propVal = propVal.strip('{}[]')
                            propVal = propVal.strip()
                            if len(propVal) > 2 and dt == 'string' \
                               and propVal[0] == '"' and propVal[-1] == '"' :
                                propVal = '['+propVal+']'
                                propVal = eval(propVal)
                            else:
                                propVal = propVal.split(",")
                                propVal = [x.strip() for x in propVal]
                        propVal = [pywbem.tocimobj(dt, x) for x in propVal]
                        inst.properties[propName] = propVal
                    else:
                        inst.properties[propName] = pywbem.tocimobj(
                                dt, propVal)
        if obj:
            if obj.namespace is None: 
                obj.namespace = ns
            inst.path = obj
            conn.ModifyInstance(ModifiedInstance=inst)
        else: 
            obj =  conn.CreateInstance(NewInstance=inst)
        inst = conn.GetInstance(InstanceName=obj, LocalOnly = False)
        
        urlargs = { 'ns' : ns, 'url' : url, 'obj' : obj }
        refurl = self.urls.build('GetInstance', urlargs)
        ht = '<HTML>'
        ht+= '<META HTTP-EQUIV="Refresh" CONTENT="1;URL='+refurl+'">'
        ht+= '<HEAD><TITLE>Saving Instance...</TITLE> </HEAD>'
        ht+= '<BODY>The Instance has been saved.  Refreshing...<br>'
        ht+= '<p>If your browser doesn&apos;t refresh to the new instance, '
        ht+= 'click '+self._makeHref(request, 'GetInstance', urlargs, 'here.')
        return ht

    def on_index(self, request):
        ht = self._printHead('Login')
        ht+= '<h1><font color=red><b>Y</b></font>et '
        ht+= '<font color=red><b>A</b></font>nother '
        ht+= '<font color=red><b>W</b></font>BEM '
        ht+= '<font color=red><b>N</b></font>avigator (YAWN)</h1>'
        ht+= '<h3><i>&quot;All CIM Browsers suck. &nbsp;This one sucks less&quot;</i></h3>'
        ht+= '<hr>'
        ht+= '<FORM ACTION="'+self.urls.build('Login')+'" METHOD=POST>'
        ht+= '<table border=0>'
        ht+= '<tr><td>URI Scheme: </td>'
        ht+= '  <td><select name="scheme">'
        ht+= '  <option value="https">https'
        ht+= '  <option value="http">http'
        ht+= '</select></td></tr>'
        ht+= '<tr><td>Host: </td><td><INPUT TYPE=TEXT NAME="host" size="50"></td></tr>'
        ht+= '<tr><td>Port: </td><td><INPUT TYPE=TEXT NAME="port" VALUE="5989"></td></tr>'
        #ht+= '<tr><td>User: </td><td><INPUT TYPE=TEXT NAME="user" size="50"></td></tr>'
        #ht+= '<tr><td>Password: </td><td><INPUT TYPE=TEXT NAME="password" size="50"</td></tr>'
        ht+= '<tr><td>Namespace: </td><td><INPUT TYPE=TEXT NAME="ns"></td></tr>'
        ht+= '<tr><td></td><td><INPUT TYPE=SUBMIT VALUE="Login"></td></tr>'
        ht+= '</table>'
        ht+= '</FORM>'
        ht+= '<hr><center>Powered by<br><img src="http://www.modpython.org/mod_python.gif"></center>'
        ht+= '</body></html>'
        return Response(ht, mimetype="text/html")

    @view()
    def on_AssociatedClasses(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        classNames = None
        cns = conn.References(ObjectName=className, IncludeQualifiers=True)
        cns.sort()
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url

        urlargs['className'] = className
        ht = _printHead( 'Classes Associated To ' + className
                       + ' in Namespace: '+ns)
        ht+= '<h1>Classes Associated To '
        ht+= self._makeHref(request, 'GetClass', urlargs, className)
        ht+= ' in Namespace: '+ns+'</h1>'
        ht+= '<table border=1 cellpadding=2><tr bgcolor="CCCCCC">'
        ht+= '<th>Associated Class Name</th><th>Via Association Class</th>'
        ht+= '<th>Role</th><th>Associated Role</th></tr>'

        #ht+= '<tr><td colspan=4>'
        #ht+= '<br><br><b>Properties</b>'
        #ht+= '<br>' + `cns[0][1].properties`
        #ht+= '<br><br><b>Superclass</b>'+ cns[0][1].superclass
        #ht+= '<br><br><b>Property Names</b>'+`cns[0][1].properties.keys()`
        #ht+= '<br><br><b>Qualifiers</b>'+`cns[0][1].qualifiers`
        #ht+= '<br><br><b>Description of Antecedent</b>'+`cns[0][1].properties['Antecedent'].qualifiers['Description'].value`
        #if 'Description' in cns[0][1].properties['Antecedent'].qualifiers.keys():
        #    ht+= '<br><br><b>Description of Antecedent</b>'+`cns[0][1].properties['Antecedent'].qualifiers['Description'].value`
        #ht+= '<br><br><b>Qualifiers of Dependent</b>'+`cns[0][1].properties['Dependent'].qualifiers`
        #ht+= '<br><br><b>Value of Antecedent</b>'+`cns[0][1].properties['Antecedent']`
        #ht+= '<br><br><b>Value of Antecedent</b>'+`cns[0][1].properties['Dependent']`
        #ht+= '<br><br><b>Methods</b>'+`cns[0][1].methods`
        #ht+= '</td></tr>'


        hierarchy = []
        hierarchy = getAllHierarchy(conn, url, ns, className)
        lastAssocClass = ''
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

            ht+= '<tr><td>'
            urlargs['className'] = resultClass
            ht+= self._makeHref(request, 'GetClass', urlargs, resultClass)
            ht+= '</td>'
            ht+= '<td>'
            urlargs['className'] = assocClass
            ht+= self._makeHref(request, 'GetClass', urlargs, assocClass)
            ht+= '</td>'
            ht+= '<td title="'+roleDescription+'">'
            ht+= role
            ht+= '</td>'
            ht+= '<td title="'+resultRoleDescription+'">'
            ht+= resultRole
            ht+= '</td>'
            ht+= '</tr>'

            lastAssocClass = assocClass
        ht+= '</table>'
        return ht + "</table></body></html>"

    @view()
    def on_AssociatorNames(self, request, obj, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        instName = _decodeObject(instPath)
        assocs = conn.AssociatorNames(ObjectName=instName)
        ht = self._printHead('AssociatorNames '+instName.classname,
                urlargs=urlargs)
        groupedAssocs = {}
        for assoc in assocs:
            if assoc.classname not in groupedAssocs.keys():
                groupedAssocs[assoc.classname] = [assoc]
            else:
                groupedAssocs[assoc.classname].append(assoc)
        setkeys = groupedAssocs.keys()
        setkeys.sort()
        for setkey in setkeys:
            ht+= '<h2>'+setkey+'</h2>'
            assocList = groupedAssocs[setkey]
            ht+= self._printInstanceNames(request, urlargs, assocList)
        return ht + '</body></html>'

    @view()
    def on_CMPIProvider(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        klass = conn.GetClass(ClassName = className, LocalOnly=False, 
                    IncludeClassOrigin=True, IncludeQualifiers=True)
        code = cmpi_codegen(klass)
        title = 'CMPI Provider for %s' % className
        ht = self._printHead(title, request)
        ht+= '<font size=+1><b>%s</b></font>' % title
        ht+= '<table bgcolor="#f9f9f9" cellspacing=0 cellpadding=10 border=1>'
        ht+= '<tr><td><pre>'+cgi.escape(code)+'</pre>'
        ht+= '</td></tr></table>'
        #ht+= '<font size=+1><b>Provider Registration MOF</b></font>'
        #ht+= '<table bgcolor="#f9f9f9" cellspacing=0 cellpadding=10 border=1>'
        #ht+= '<tr><td><pre>'+cgi.escape(mof)+'</pre>'
        #ht+= '</td></tr></table>'
        return ht + '</body></html>'

    @view(http_method=POST)
    def on_CreateInstance(self, request, className, url=None, ns=None,
            **params):
        conn = self._frontMatter(request, url, ns)
        ht = self._createOrModifyInstance(request,  url, ns, className,
                None, **params)
        return ht + '</body></html>'

    @view()
    def on_CreateInstancePrep(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        klass = conn.GetClass(ClassName=className, 
                LocalOnly=False, IncludeQualifiers=True)
        ht = self._printHead('Create Instance of '+className,
                'Create Instance of '+className, request,
                urlargs={'ns':ns, 'url':url})
        ht+= self._displayInstanceMod(request, url, ns, klass)
        return ht + '</body></html>'

    @view()
    def on_DeleteClass(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        conn.DeleteClass(ClassName = className)
        ht = self._printHead('Deleted class '+ className, urlargs=urlargs)
        ht+= 'Deleted Class ' + className
        return ht + '</body></html>'

    @view()
    def on_DeleteInstance(self, request, obj, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        try:
            conn.DeleteInstance(obj)
        # TODO make this use _ex()
        except pywbem.CIMError, arg:
            ht = self._printHead('Error Deleting instance of '+
                    obj.classname)
            ht+= 'Deleting instance of '+obj.classname
            ht+= ' returned the following error:<br> <i>('
            ht+= `arg[0]` + ') : ' + arg[1] + '</i>'
            ht+= '</body></html>'
            return ht
        urlargs = {'ns':ns,'url':url,'className':obj.classname}
        ht = self._printHead('Deleted Instance of '+obj.classname, urlargs=urlargs)
        ht+= r'Deleted Instance of '
        ht+= self._makeHref(request, 'GetClass', urlargs,
                obj.classname)
        ht+= self._printInstanceNames(request, urlargs, [obj],
                omitGetLink=True)
        return ht + '</body></html>'

    @view()
    def on_EnumClassNames(self, request, className=None, mode=None,
            instOnly=None, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        if mode is None:
            mode = request.args.get('mode', 'deep')
        if className is None:
            className = request.args.get('className', None)
        if instOnly is None:
            instOnly = request.args.get('instOnly', None)
            if instOnly is not None:
                instOnly = instOnly.lower() in ('true', 'yes', '1')
        if instOnly is not None:
            self.response.set_cookie('yawn_instOnly', str(instOnly).lower(),
                    path=_baseScript(request))
        elif (  'yawn_instOnly' in request.cookies
             and request.cookies['yawn_instOnly'] == 'true'):
            instOnly = True

        if instOnly:
            return self.on_EnumInstrumentedClassNames(request, url, ns)

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
        else:
            classNames = conn.EnumerateClassNames(**kwargs)

        urlargs = {'ns': ns, 'url': url}
        ht = self._printHead('Classes in '+ns,'Classes in '+url+'/'+ns,
                request, urlargs)
        ecn_urlargs = urlargs.copy()
        ecn_urlargs['mode'] = mode
        ht+= '<table border=0><tr><td></td>'
        if lineage: 
            ht+= '<td>'+self._makeHref(request, 'EnumClassNames',
                    ecn_urlargs, '<root>')
            for cname in lineage: 
                ht+= '&nbsp;/&nbsp;'
                if cname != lineage[-1]:
                    ecn_urlargs['className'] = cname
                    ht+= self._makeHref(request, 'EnumClassNames',
                            ecn_urlargs, cname)
                else:
                    ht+= cname
            ht+= '</td>'
        ref_urlargs = urlargs.copy()
        if className is not None: 
            ref_urlargs['className'] = className
        ht+= '<td width="100%" align="right">'
        ht+= '<table border=0><tr>'
        ht+= '<td align=center colspan=2>Reload listing:</td>'
        #if len(lineage) > 5:
        #    ht+= '</tr><tr>'
        #ht+= '<table border=1><tr>'
        if mode != 'deep':
            ref_urlargs['mode'] = 'deep'
            ht+= '<td>'
            ht+= self._makeHref(request, 'EnumClassNames', ref_urlargs, 
                           'Deep') #  (With Hierarchy)')
            ht+= '</td>'
        if mode != 'shallow':
            ref_urlargs['mode'] = 'shallow'
            ht+= '<td>'
            ht+= self._makeHref(request, 'EnumClassNames', ref_urlargs,
                    'Shallow')
            ht+= '</td>'
        if False: # mode != 'flat': # Disable since deep is faster now
            ref_urlargs['mode'] = 'flat'
            ht+= '<td>'
            ht+= self._makeHref(request, 'EnumClassNames', ref_urlargs, 
                           'Deep (Without Hierarchy)')
            ht+= '</td>'
        #ht+= '</tr></table>'
        ht+= '</tr></table></td></tr></table>'

        ht+= '<hr>\n'
        ht+= '<table border=0>'
        if mode == 'deep':
            startClass = className is None and 'None' or className
            deepDict = {startClass:[]}
            for klass in klasses:
                if klass.superclass is None:
                    deepDict[startClass].append(klass.classname)
                else:
                    try:
                        deepDict[klass.superclass].append(klass.classname)
                    except KeyError:
                        deepDict[klass.superclass] = [klass.classname]

            ht += self._printEnumDeep(request, startClass, deepDict, urlargs,
                    len(lineage))

        else:
            #ht+= '<table border=0>'
            if classNames is None:
                classNames = []
            for cname in classNames:
                isCimSchema = cname.startswith("CIM_")
                ecn_urlargs['className'] = cname
                ht+= '<tr'
                if self.color:
                    ht+= ' bgcolor="#EEFFEE"'
                self._toggle_color()
                ht+= '><td>'
                hasKids = (   mode != 'flat'
                          and conn.EnumerateClassNames(ClassName=cname))
                if hasKids:
                    ht+= self._makeHref(request, 'EnumClassNames',
                            ecn_urlargs, '+')
                ht+= '</td><td>'
                urlargs['className'] = cname
                if not isCimSchema:
                    ht+= '<i>'
                if not hasKids:
                    ht+= self._makeHrefWithTags(request, 'GetClass',
                            urlargs, cname,
                                   '<font color="#05058f">','</font>')
                else:
                    ht+= self._makeHref(request, 'GetClass', urlargs, cname)
                if not isCimSchema:
                    ht+= '</i>'
                ht+= '</td><td>&nbsp;&nbsp;&nbsp;'
                ht+= self._makeHref(request, 'EnumInstanceNames', urlargs,
                        'Instance Names')
                ht+= '</td><td>&nbsp;&nbsp;&nbsp;'
                ht+= self._makeHref(request, 'EnumInstances',
                        urlargs, 'Instances')
                ht+= '</td></tr>\n'
            ht += '</table>'

        return ht + '</table></body></html>'

    @view()
    def on_EnumInstanceNames(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        instNames = conn.EnumerateInstanceNames(ClassName = className)
        numInsts = len(instNames)
        inameDict = pywbem.NocaseDict()
        for iname in instNames:
            if iname.classname not in inameDict:
                inameDict[iname.classname] = [iname]
            else:
                inameDict[iname.classname].append(iname)

        ht = '%s %s' %(numInsts, numInsts == 1 and 'Instance' or 'Instances')

        class_urlargs = urlargs.copy()
        class_urlargs["className"] = className
        ht+= ' of '
        ht+= self._makeHref(request, 'GetClass',
                class_urlargs, className) + '</h1>'
        ht = self._printHead('Instances of '+className,
                ht, request, urlargs=urlargs)
        if numInsts == 0:
            ht += self._makeHref(request, 'CreateInstancePrep', class_urlargs, 
                'Create New Instance')

        for cname, inames in inameDict.items():
            if len(inameDict) > 1:
                ht+= '<h2>'
                ht+= '%s %s'%( len(inames)
                             , len(inames) == 1 and 'Instance' or 'Instances')
                class_urlargs["className"] = cname
                ht+= ' of '
                ht+= self._makeHref(request, 'GetClass',
                        class_urlargs, cname) + '</h2>'
            ht += self._printInstanceNames(request, urlargs, inames)
            ht += '<p>'
            ht+= self._makeHref(request, 'CreateInstancePrep', class_urlargs, 
                'Create New Instance')
        return ht + '</body></html>'

    @view()
    def on_EnumInstrumentedClassNames(self, request, url=None, ns=None):
        fetched_classes = []
        def get_class(cname):
            fetched_classes.append(cname)
            return conn.GetClass(ClassName=cname,
                       LocalOnly=True, PropertyList=[],
                       IncludeQualifiers=False, IncludeClassOrigin=False)
        conn = self._frontMatter(request, url, ns)
        caps = conn.EnumerateInstances(
                        ClassName='PG_ProviderCapabilities', 
                        namespace='root/PG_InterOp',
                        PropertyList=['Namespaces', 'ClassName'])
        startClass = '.'
        deepDict = {startClass:[]}
        for cap in caps:
            if ns not in cap['Namespaces']: 
                continue
            if cap['ClassName'] in fetched_classes:
                continue
            klass = get_class(cap['ClassName'])
            if klass.superclass is None:
                deepDict[startClass].append(klass.classname)
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
                            klass.superclass not in deepDict[startClass]:
                        deepDict[startClass].append(klass.classname)
                    elif klass.superclass in deepDict:
                        if klass.classname not in deepDict[klass.superclass]:
                            deepDict[klass.superclass].append(klass.classname)
                        break 
                    else:
                        deepDict[klass.superclass] = [klass.classname]
                                

        urlargs = {'ns': ns, 'url': url}
        ht = self._printHead('Classes in '+ns,'Classes in '+url+'/'+ns,
                req, urlargs)
        ht+= '<table border=0><tr><td></td>'
        ht+= self._printEnumDeep(request, startClass, deepDict, urlargs)
        return ht + '</table></body></html>'

    @view()
    def on_EnumInstances(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        insts = conn.EnumerateInstances(ClassName = className,
                LocalOnly = False)
        ht = self._printHead('Instances of '+className,
                'Instances of '+className, request, urlargs=urlargs)
        numInsts = len(insts)
        msgStart = 'Showing '+`numInsts`+' Instances<br />'
        if numInsts == 0:
            msgStart = 'No Instances<br />'
        elif numInsts == 1:
            msgStart = ''
        ht+= msgStart

        ccache = pywbem.NocaseDict()
        for inst in insts:
            instName = inst.path
            try:
                klass = ccache[instName.classname]
            except KeyError:
                klass = conn.GetClass(instName.classname, LocalOnly=False)
                ccache[instName.classname] = klass
            ht += self._displayInstance(request, inst, instName,
                    klass, urlargs.copy())
        return ht + '</body></html>'

    @view(require_ns=False)
    def on_EnumNamespaces(self, request, url=None):
        conn = self._frontMatter(request, url, '')
        nsinsts = []
        try:
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
        except pywbem.CIMError, arg:
            ht = self._printHead('Error')
            details = _code2string(arg[0])
            ht+= '<i>'+details[0]+': '+details[1]
            ht+=': '+cgi.escape(arg[1])+'</i>'
            return ht + '</body></html>'

        ht = self._printHead('Namespaces','CIM Namespaces in '+url, request)
        if len(nsinsts) == 0:
            ht+= '<h1>Error</h1>'
            ht+= 'Unable to enumerate Namespaces.  Return to the '
            ht+= '<a href="'+_baseScript(request)
            ht+= '">Login page</a> and specify a '
            ht+= 'Namespace.'
            if conn.last_reply is not None:
                ht+= '<pre>'+cgi.escape(conn.last_reply)+'</pre>'
            return ht + '</body></html>'
        urlargs = {}
        urlargs['url'] = url
        nslist = [inst['Name'].strip('/') for inst in nsinsts]
        if interopns not in nslist:
        # Pegasus didn't get the memo that namespaces aren't hierarchical
        # This will fall apart if there exists a namespace 
        # <interopns>/<interopns>
        # Maybe we should check the Server: HTTP header instead. 
            nslist = [interopns+'/'+subns for subns in nslist]
            nslist.append(interopns)
        nslist.sort()
        nsd = None
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
        ht+= '<table border=0>'
        for nsname in nslist:
            urlargs['ns'] = nsname
            urlargs['instOnly'] = 'false'
            ht+= '<tr><td>'+self._makeHref(request, 'EnumClassNames', urlargs,
                    nsname)
            ht+= '</td><td>&nbsp;&nbsp;'
            if nsd and nsd[nsname] > 0:
                urlargs['instOnly'] = 'true'
                ht+= self._makeHref(request, 'EnumClassNames', urlargs, 
                               '%s Instrumented Classes' % nsd[nsname])
            ht+= '</td></tr>' 
        ht+= '</table>'
        return ht + '</body></html>'

    @view()
    def on_FilteredReferenceNames(self, request, instPath, assocClass,
            resultClass, role, resultRole, assocCall, properties,
            url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        instName = _decodeObject(instPath)
        refs = None
        ht = self._printHead(assocCall+' '+instName.classname,
                urlargs=urlargs)

        class_urlargs = urlargs.copy()
        class_urlargs["className"] = instName.classname
        ht+= '<h1>Filtered Objects associated with instance of '
        ht+= self._makeHref(request, 'GetClass', class_urlargs,
                instName.classname) +'</h1>'
        if assocCall=='Associators':
            ht+='<b>Associators ( AssocClass=' + assocClass + ', ResultClass='
            ht+= resultClass + ', Role=' + role + ', ResultRole=' + resultRole
            ht+= ', Properties=' + properties + ' )</b><br><br>'
        elif  assocCall=='Associator Names':
            ht+='<b>AssociatorNames ( AssocClass=' + assocClass
            ht+= ', ResultClass=' + resultClass + ', Role=' + role
            ht+= ', ResultRole=' + resultRole + ', Properties=' + properties
            ht+= ' )</b><br><br>'
        elif  assocCall=='References':
            ht+='<b>References ( ResultClass=' + resultClass + ', Role='
            ht+= role + ', Properties=' + properties + ' )</b><br><br>'
        elif  assocCall=='Reference Names':
            ht+='<b>ReferenceNames ( ResultClass=' + resultClass + ', Role='
            ht+= role + ', Properties=' + properties + ' )</b><br><br>'

        refdict = {}
        params = {}

        if len(assocClass) > 0:
            params['AssocClass'] = assocClass
        if len(resultClass) > 0:
            params['ResultClass'] = resultClass
        if len(role) > 0:
            params['Role'] = role
        if len(resultRole) > 0:
            params['ResultRole'] = resultRole
        if assocCall=='Associators' or assocCall=='References':
            params['IncludeQualifiers'] = True

        if assocCall=='Associators':
            assocs = conn.Associators(ObjectName=instName, **params)
            ht += 'Showing ' + `len(assocs)`
            ht += ' resulting object(s). <br><br>'
            for assoc in assocs:
                assocInstPath = assoc.path
                assocInst = assoc
                assocClassName = assocInst.classname
                ht += '<hr><h2>Objects of Class: '
                ht += assocClassName + '</h2>'
                ht += _printInstanceNames(request, urlargs,
                        [assocInstPath])

                klass = conn.GetClass(ClassName=assocInstPath.classname, 
                        namespace=assocInstPath.namespace,
                        LocalOnly=False, IncludeQualifiers=True)
                ht += self._displayInstance(request,
                        assocInst, assocInstPath, klass, urlargs)
        elif  assocCall=='Associator Names':
            assocNames = conn.AssociatorNames(ObjectName=instName,
                    **params)#, properties)
            ht += 'Showing ' + `len(assocNames)`
            ht += ' resulting object(s). <br><br>'
            for assocName in assocNames:
                assocInstPath = assocName
                ht += '<hr><h2>Objects of Class: '
                ht += assocInstPath.classname + '</h2>'
                ht += self._printInstanceNames(request, urlargs,
                        [assocInstPath])
        elif  assocCall=='References':
            refs = conn.References(ObjectName=instName, **params)
            ht += 'Showing ' + `len(refs)`
            ht += ' resulting object(s). <br><br>'
            for ref in refs:
                assocInstPath = ref.path
                assocInst = ref
                assocClassName = assocInst.classname
                ht += self._printInstanceNames(request, urlargs,
                        [assocInstPath])

                klass = conn.GetClass(ClassName=assocInstPath.classname,
                        LocalOnly=False, IncludeQualifiers=True)
                ht += self._displayInstance(request,
                        assocInst, assocInstPath, klass, urlargs)
        elif  assocCall=='Reference Names':
            refNames = conn.ReferenceNames(ObjectName=instName, **params)
            ht += 'Showing ' + `len(refNames)`
            ht += ' resulting object(s). <br><br>'
            for refName in refNames:
                assocInstPath = refName
                ht += '<hr><h2>Objects of Class: '
                ht += assocInstPath.classname + '</h2>'
                ht += self._printInstanceNames(request, urlargs,
                        [assocInstPath])

        return ht + '</body></html>'

    @view()
    def on_FilteredReferenceNamesDialog(self, request, obj, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = { 'ns' : ns, 'url' : url }
        class_urlargs = urlargs.copy()
        class_urlargs["className"] = obj.classname
        ht = self._printHead('Filtered ReferenceNames Dialog... (Coming...)',
                urlargs=class_urlargs)
        ht+= '<h1>Filtered References on Class '
        ht+= self._makeHref(request, 'GetClass', class_urlargs,
                obj.classname)+'</h1>'
        ht+= self._printInstanceNames(request, class_urlargs, [obj])
        ht+= '<br><br><br><form type=get action="'
        ht+= self.urls.build("FilteredReferenceNames", urlargs)
        ht+= '" METHOD=GET>'
        ht+= '<table border=1>'
        ht+= '<tr><td>Association Class<br><i>Not applicable for Reference/ReferenceNames</i></td><td><input type=text name="assocClass"></td></tr>'
        ht+= '<tr><td>Result Class</td><td><input type=text name="resultClass"></td></tr>'
        ht+= '<tr><td>Role</td><td><input type=text name="role"</td></tr>'
        ht+= '<tr><td>Result Role<br><i>Not applicable for Reference/ReferenceNames</i></td><td><input type=text name="resultRole"></td></tr>'
        ht+= '<tr><td>Properties<br><i>Comma-separated</i></td><td><input type=text name="properties"></td></tr>'
        ht+= '<tr><td valign=top>Call Type</td><td><select name="assocCall"><option value="Associators">Associator<br>'
        ht+= '<option value="Associator Names">Associator Names<br>'
        ht+= '<option value="References">References<br>'
        ht+= '<option value="Reference Names">Reference Names</select></td></tr>'
        ht+= '<tr><td colspan=2 align=right><input type=submit value="Submit"></td></tr>'
        ht+= '</table>'
        ht+= '</form>'
        return ht + '</body></html>'

    @view()
    def on_GetClass(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        klass = conn.GetClass(ClassName=className, LocalOnly=False, 
                IncludeClassOrigin=True, IncludeQualifiers=True)
        urlargs['className'] = className
        ht = self._printHead('Class '+className, 'Class '+className, request,
                urlargs=urlargs)
        instUrlArgs = urlargs.copy()
        ht+= '<table border=0><tr><td>'
        ht+= '<div align=center>'
        ht+= self._makeHref(request, 'DeleteClass', urlargs, 'Delete Class')
        del urlargs['className']
        ht+= '. ' + self._makeHref(request, 'GetInstD', instUrlArgs,
                'Get Instance')
        ht+= ' or view '+self._makeHref(request, 'EnumInstanceNames',
                instUrlArgs, 'Instance Names')
        ht+= ' or '+self._makeHref(request, 'EnumInstances',
                instUrlArgs, 'Instances')
        ht+= ' or '+self._makeHref(request, 'AssociatedClasses',
                instUrlArgs, 'Associated Classes')
        ht+= ' of this class.'
        if codegen is not None:
            ht+= ' &nbsp;'+ self._makeHref(request, 
                       'PyProvider', instUrlArgs, 'Python Provider')
        ht+= ' &nbsp;'+ self._makeHref(request, 
                   'CMPIProvider', instUrlArgs, 'CMPI Provider')
        ht+= '</div>'
        ht+= '<table border="1" cellpadding="2">'
        if klass.qualifiers.has_key('aggregation'):
            titleBGColor = "green"
        elif klass.qualifiers.has_key('association'):
            titleBGColor = "red"
        else:
            titleBGColor = "black"
        ht+= '<tr><td valign="middle" align="center" width="50%" bgcolor="'
        ht+= titleBGColor+'"><b><font color="#FFFFFF">'
        ht+= '<a name="'+className+'">'+className+'</a></font></b></td>'
        ht+= '<td valign="middle" align="center" witdth="50%">'
        if klass.superclass is not None:
            gcUrlArgs = urlargs.copy()
            gcUrlArgs["className"] = klass.superclass
            ht+= '<b>Superclass: '+self._makeHref(request, 'GetClass',
                    gcUrlArgs, klass.superclass)+'</font></b>'
        ht+= '</td></tr>'
        ht+= '<tr><td colspan="2"><table width="100%">'
        if klass.qualifiers.has_key('description'):
            ht+= '<tr><td colspan="3">'
            ht+= cgi.escape(klass.qualifiers['description'].value)
            ht+= '</td></tr>'
            del klass.qualifiers['description']
        if klass.qualifiers:
            ht+= '<tr><td colspan="3"><b>Qualifiers:</b>'
            firstTime = True
            for qual in klass.qualifiers.values():
                if firstTime:
                    firstTime = False
                else:
                    ht+= ', '
                ht+= qual.name
                if qual.name not in ["Composition", "Association",
                        "Aggregation"]:
                    ht+= ' ("'+_val2str(qual.value)+'") '
            ht+= '</td></tr>'
        ht+= '<tr><td align="center" bgcolor="#C0C0C0" colspan="3"><b>'
        ht+= 'Parameters (local in grey)</b></td></tr>'
        ht+= '<td width="15"></td><td width="100%">'
        ht+= '<table width="100%" border="1">'
        localItems = []
        nonLocalItems = []

        for method in klass.methods.values():
            if method.class_origin == className:
                localItems.append(method)
            else:
                nonLocalItems.append(method)

        for prop in klass.properties.values():
            if prop.class_origin == className:
                localItems.append(prop)
            else:
                nonLocalItems.append(prop)

        for item in localItems + nonLocalItems:
            desc = None
            if item.qualifiers.has_key('description'):
                desc = item.qualifiers['description'].value
                del item.qualifiers['description']
            deprecated = item.qualifiers.has_key('deprecated')
            key = item.qualifiers.has_key('key')
            if 'class_origin' in dir(item):
                local = item.class_origin == className
            else:
                local = True
            ht+= '<tr><td width="100%"'
            if local:
                ht+= ' bgcolor="#CCCCCC"'
            ht+= '>'
            ht+= '<a name="'+item.name.lower()+'"/>'
            for qual in item.qualifiers.values():
                ht+= qual.name + ' ' + _val2str(qual.value) + '<br />'
            if isinstance(item, pywbem.CIMProperty):
                if item.reference_class is not None:
                    type = item.reference_class
                else:
                    type = item.type
            elif isinstance(item, pywbem.CIMMethod):
                type = (   item.return_type is not None
                       and item.return_type or 'void')
            else:
                type = "&lt;Unknown&gt;"  # TODO is there anything else?
            ht+= type
            if deprecated:
                ht+= '<strike>'
            if key:
                ht+= '<font color="#FF0000">'
            ht+= ' <b>'
            if isinstance(item, pywbem.CIMMethod):
                methUrlArgs = urlargs.copy()
                methUrlArgs['obj'] = pywbem.CIMClassName(
                        className, namespace=ns)
                methUrlArgs['method'] = item.name
                ht+= self._makeHref(request, 'PrepMethod', methUrlArgs,
                        item.name)
            else:
                ht+= item.name
            ht+= '</b>'
            if isinstance(item, pywbem.CIMProperty) and item.is_array:
                ht+= '[ ]'
            if deprecated:
                ht+= '</strike>'
            if isinstance(item, pywbem.CIMMethod):
                ht += '('
                if len(item.parameters) > 0:
                    ht+= '<table cellpadding="0" 0="1" width="100%">'
                    for param in item.parameters.values():
                        pdesc = None
                        if param.qualifiers.has_key('description'):
                            pdesc = param.qualifiers['description'].value
                            del param.qualifiers['description']
                        ht+= '<tr>'
                        ht+= '<td width="32" /> <td width="32" />'
                        ht+= '<td>'
                        if deprecated:
                            ht+= '<strike>'
                        if pdesc is not None:
                            ht+= '<i>'+cgi.escape(pdesc)+'</i>'
                            ht+= '<br />'
                        if deprecated:
                            ht+= '</strike>'

                        if param.qualifiers:
                            ht+= '<table><tr><td>Qualifiers:</td>'
                            first = True
                            for qual in param.qualifiers.values():
                                if first:
                                    first = False
                                else:
                                    ht+= '<tr><td></td>'
                                ht+= '<td>'
                                ht+= qual.name + ' ' + _val2str(qual.value)
                                ht+= '</td></tr>'
                            ht+= '</table>'
                        ht+= '</td>'
                        ht+= '</tr>'
                        ht+= '<tr>'
                        ht+= '<td width="32" />'
                        ht+= '<td colspan="2">'
                        if deprecated:
                            ht+= '<strike>'
                        if param.reference_class is not None:
                            ht+= param.reference_class
                            ht+= ' REF'
                        else:
                            ht+= param.type
                        ht+= ' <b>'+param.name+'</b>'
                        if param.is_array:
                            ht+= ' [ '
                            if param.array_size is not None:
                                ht+= `param.array_size`
                            else:
                                ht+= ' '
                            ht+= ']'
                        if deprecated:
                            ht+= '</strike>'
                        ht+= '</td>'
                        ht+= '</tr>'
                    ht+= '</table>'
                ht+= ')'
                ht+= '<br />'
            else:
                ht+= ';<br />'
            if key:
                ht+= '</font>'
            if desc is not None:
                if deprecated:
                    ht+= '<strike>'
                ht+= '<i>'+cgi.escape(desc)+'</i><br />'
                if deprecated:
                    ht+= '</strike>'
            if not local:
                coUrlArgs = urlargs.copy()
                coUrlArgs["className"] = item.class_origin
                if item.class_origin is not None:
                    ht+= '<i>Class Origin</i>: '+self._makeHref(
                            request, 'GetClass', coUrlArgs, item.class_origin)
            ht+= '</td></tr>'
        ht+= '</table></table></table></td></tr></table>'
        return ht + '</body></html>'

    @view(http_method=GET_AND_POST)
    def on_GetInstance(self, request, className=None, obj=None,
            url=None, ns=None, **params):
        if className is None and obj is None:
            raise ValueError("either className or obj must be given")
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        if obj is None:
            # Remove 'PropName.' prefix from param names.
            params = dict ([(x[9:],y) for (x, y) in params.items()])
            obj = pywbem.CIMInstanceName(className, 
                    keybindings=params, namespace=ns)
        inst = None
        klass = conn.GetClass(ClassName=obj.classname, 
                LocalOnly=False, IncludeQualifiers=True)
        inst = conn.GetInstance(InstanceName=obj, LocalOnly = False)
        ht = self._printHead('Instance of '+obj.classname,
                req=request, urlargs=urlargs)
        ht+= self._displayInstance(request, inst, obj, klass, urlargs)
        return ht + '</body></html>'

    @view()
    def on_GetInstD(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        klass = conn.GetClass(ClassName=className, LocalOnly=False, 
                IncludeQualifiers=True)
        ht = self._printHead('Get Instance of '+className,
                'Get Instance of '+className, request,
                urlargs={'ns':ns, 'url':url})
        ht+= self._displayInstanceMod(request, url, ns, klass, getInst=True)
        return ht + '</body></html>'

    @view(http_method=POST)
    def on_InvokeMethod(self, request, obj, method,
            url=None, ns=None, **params):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        className = None
        if (   isinstance(obj, pywbem.CIMInstanceName)
           and obj.namespace is None):
            obj.namespace = ns
        className = obj.classname
        urlargs['className'] = className
        # else obj is a CIMInstanceName
        klass = conn.GetClass(ClassName = obj.classname, 
                LocalOnly=False)
        ht = 'Invoked method '+self._makeHref(request, 'GetClass',
                urlargs, className)
        ht+= '::'+self._makeHref(request, 'GetClass', urlargs,
                method, '#'+method.lower())
        ht+= '()'
        ht = self._printHead('Results of Method '+className+'::'+method, ht,
                request, urlargs=urlargs)

        cimmethod = klass.methods[method]
        inParms = {}

        def type_str (meta_parm):
            if meta_parm.reference_class is not None:
                urlargs['className'] = metaParm.reference_class
                dt = 'REF ' + self._makeHref(request, 'GetClass', urlargs, 
                                        metaParm.reference_class)
            else:
                dt = metaParm.type
            if metaParm.is_array:
                dt+= '[]'
            return dt

        if params:
            # Remove 'MethParm.' prefix from param names.
            params = dict ([(x[9:],y) for (x, y) in params.items()
                if x.startswith('MethParm.')])
            ht+= '<h3>With Input Parameters</h3>'
            ht+= '<table valign=top border=1>'
            ht+= ' <tr bgcolor="#CCCCCC"><th>Data Type</th>'
            ht+= '<th>Param Name</th><th>Value</th></tr>'
            for paramName, paramVal in params.items():
                metaParm = cimmethod.parameters[paramName]
                dt = type_str(metaParm)
                ht+= ' <tr><td>'+dt+'</td>'
                ht+= ' <td>'+paramName+'</td>'
                ht+= ' <td>'+_val2str(paramVal)+'</td></tr>'
                if paramVal:
                    if metaParm.is_array:
                        if type(paramVal) is not list:
                            paramVal = paramVal.strip()
                            paramVal = paramVal.strip('{}[]')
                            paramVal = paramVal.strip()
                            if len(paramVal) > 2 and dt == 'string' \
                               and paramVal[0] == '"' and paramVal[-1] == '"' :
                                paramVal = '['+paramVal+']'
                                paramVal = eval(paramVal)
                            else:
                                paramVal = paramVal.split(",")
                                paramVal = [x.strip() for x in paramVal]
                        if metaParm.reference_class is not None:
                            paramVal = [x for x in paramVal]
                        else:
                            paramVal = [   pywbem.tocimobj(dt[:-2], x)
                                       for x in paramVal]
                        inParms[paramName] = paramVal
                    else:
                        if metaParm.reference_class is not None:
                            inParms[paramName] = paramVal
                        else:
                            inParms[paramName] = pywbem.tocimobj(dt, paramVal)
            ht+= '</table>'

        (rval, outParms) = conn.InvokeMethod(MethodName=method,
                ObjectName=obj, **inParms)

        if outParms:
            ht+= '<h3>Output Values</h3>'
            ht+= '<table border=1><tr bgcolor="#CCCCCC">'
            ht+= '<th>Data Type</th><th>Param Name</th><th>Value</th></tr>'
            for parmName, parm in outParms.items():
                metaParm = cimmethod.parameters[parmName]
                isRef = metaParm.reference_class is not None
                dt = type_str(metaParm)
                ht+= '<tr><td>'+dt+'</td><td>'+metaParm.name+'</td><td>'
                if (   metaParm.qualifiers.has_key('values')
                   and metaParm.qualifiers.has_key('valuemap')):
                    display = str(parm)
                    valmapQual = metaParm.qualifiers['valuemap'].value
                    valuesQual = metaParm.qualifiers['values'].value
                    if display in valmapQual:
                        valIdx = valmapQual.index(display)
                        if valIdx < len(valuesQual):
                            display = display + ' ('+valuesQual[valIdx]+')'
                    ht+= display
                else:
                    if isRef and parm is not None:
                        urlargs['obj'] = parm
                        ht+= self._makeHref(request, 'GetInstance',
                                urlargs, _val2str(parm))
                    else:
                        ht+= _val2str(parm)
                ht+= '</td></tr>'
            ht+= '</table>'

        ht+= '<font size=+1><b>Method returned:</b></font> ' + _val2str(rval)
        urlargs['className'] = className
        ht+= '<p>Return to class ' + self._makeHref(request, 'GetClass',
                urlargs, className)
        if isinstance(obj, pywbem.CIMInstanceName):
            del urlargs['className']
            ht+= ' or instance of '+className + ':'
            ht+=self._printInstanceNames(request, urlargs, [obj])

        return ht + '</body></html>'

    @view(http_method=POST, require_url=False, require_ns=False,
            returns_response=True)
    def on_Login(self, request, **kwargs):
        """ @return (url, ns) """
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
        #if 'user' in request.form and request.form['user']:
            #resp = self.response
            #resp.cookies['user'] = request.form['user']
            #resp.cookies['password'] = request.form['pass
        if host[0] == '/':
            url = host
        if ns:
            return self.on_EnumClassNames(request, url=url, ns=ns)
        return self.on_EnumNamespaces(request, url=url)

    @view(require_url=False, require_ns=False)
    def on_Logout(self, request):
        # Enable the client to reauthenticate, possibly as a new user
        self.response.set_cookie('yawn_logout', "true", path=_baseScript(request))
        refurl = _baseScript(request)
        ht = '<HTML>'
        ht+= '<META HTTP-EQUIV="Refresh" CONTENT="1;URL='+refurl+'">'
        ht+= '<HEAD><TITLE>Logging out...</TITLE> </HEAD>'
        ht+= '<BODY>Logging out...<br>'
        return ht + '</body></html>'

    @view(http_method=POST)
    def on_ModifyInstance(self, request, obj, url=None, ns=None,
            **params):
        conn = self._frontMatter(request, url, ns)
        ht = self._createOrModifyInstance(request, url, ns, obj.classname,
                obj, **params)
        return ht + '</body></html>'

    @view(http_method=GET_AND_POST)
    def on_ModifyInstPrep(self, request, obj, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        instPath = _encodeObject(obj)
        klass = conn.GetClass(ClassName=obj.classname, 
                LocalOnly=False, IncludeQualifiers=True)
        ht = self._printHead('Modify Instance of '+obj.classname,
                'Modify Instance of '+obj.classname,
                request, urlargs={'ns':ns, 'url':url})
        ht+= self._displayInstanceMod(request, url, ns, klass, (instPath, obj))
        return ht + '</body></html>'

    @view()
    def on_MofComp(self, request, file, text, url=None, ns=None):
        conn = self._frontMatter(request, url, 'root/cimv2')
        ht = self._printHead("MOF", "MOF", request, {'url':url})
        ht+= "file:<pre>"
        ht+= cgi.escape(file.value)
        ht+= '</pre>'
        ht+= 'text:<pre>'
        ht+= cgi.escape(text)
        ht+= '</pre>'
        return ht + '</body></html>'

    @view(require_url=False, require_ns=False)
    def on_Pickle(self, request, obj):
        ht = self._printHead("Object", "Object Serialization", request)
        ht+= '<p><i>To pass the following object as a Parameter Reference'
        ht+= ' to a method call, copy this string to your clipboard and paste'
        ht+= ' it to the parameter field.</i><p>'
        ht+= '<hr>'+_encodeObject(obj)+'<hr>'
        lobj = obj
        ht+= '<p><pre>'+cgi.escape(lobj.tocimxml().toprettyxml())+'</pre>'
        ht+= str(lobj)
        return ht + '</body></head>'

    @view()
    def on_PrepMethod(self, request, obj, method, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        className = None
        className = obj.classname
        klass = conn.GetClass(ClassName = className, LocalOnly=False,
                IncludeQualifiers=True)

        cimmethod = klass.methods[method]
        inParms = []
        outParms = []
        for param in cimmethod.parameters.values():
            # TODO is IN assumed to be true if the IN qualifier is missing?
            if (  not param.qualifiers.has_key('in')
               or param.qualifiers['in'].value):
                inParms.append(param)
            if (   param.qualifiers.has_key('out')
               and param.qualifiers['out'].value):
                outParms.append(param)

        classUrlArgs = urlargs.copy()
        classUrlArgs['className'] = className
        ht = 'Invoke method '+self._makeHref(request, 'GetClass',
                classUrlArgs, className)
        ht+= '::'+self._makeHref(request, 'GetClass', classUrlArgs, method,
                '#'+method.lower())+'()'
        # note, ht passed in as param. 
        ht = self._printHead('Method '+className+'::'+method, ht, request,
                urlargs=urlargs)
        if isinstance(obj, pywbem.CIMInstanceName):
            ht+= 'on instance'
            ht+= self._printInstanceNames(request, urlargs, [obj])
        ht+= '<form action="'+self.urls.build("InvokeMethod",
            { 'obj' : obj, 'method' : method }) + '" METHOD=POST>'
        ht+= '<input type=hidden name="url" value="'+url+'">'
        ht+= '<input type=hidden name="ns" value="'+ns+'">'
        ht+= '<table border=0>'
        needComboBox = False
        if inParms:
            someRequired = False
            ht+= '<h3>Enter Input Parameters</h3>'
            ht+= '<tr><td><table valign=top border=1>'
            ht+= '<tr bgcolor="#CCCCCC"><th>Data Type</th>'
            ht+= '<th>Param Name</th><th>Value</th></tr>'
            for param in inParms:
                ht+= '<tr valign=top'
                if (   param.qualifiers.has_key('required')
                   and param.qualifiers['required'].value):
                    ht+= ' bgcolor="#FFDDDD"'
                    someRequired = True

                if param.reference_class is not None:
                    ht+= '><td>'+param.reference_class
                    ht+= ' REF'
                else:
                    ht+= '><td>'+param.type
                if param.is_array:
                    ht+= ' [ ]'
                ht+= '</td>'
                ht+= '<td'
                if param.qualifiers.has_key('description'):
                    ht+= ' title="'+cgi.escape(param.qualifiers['description'].value)+'"'
                ht+= '>'
                ht+= param.name
                ht+= '</td><td>'
                # avoid name collisions, in case some param is called ns, url, etc.
                parmName = 'MethParm.'+param.name
                if param.qualifiers.has_key('valuemap'):
                    needComboBox = True
                    valmapQual = param.qualifiers['valuemap'].value
                    valuesQual = None
                    if param.qualifiers.has_key('values'):
                        valuesQual = param.qualifiers['values'].value

                    # Disable the combobox for now, because it isn't working, and
                    # we may not actually need it.  For example, perhaps any time
                    # values from VendorReserved are used, the vendor's subclass
                    # will override the method, and thus the qualifiers, and provide
                    # specific valuemap extensions that would in turn show up in our
                    # drop down.
                    #ht+= '<select name="'+parmName+'" class="comboBox">'
                    ht+= '<select name="'+parmName+'"'
                    if param.is_array:
                        ht+= ' MULTIPLE SIZE=4'
                    ht+= '>'
                    if not param.is_array:
                        ht+= '<option value="">'
                    for i in range(0, len(valmapQual)):
                        curVal = valmapQual[i]
                        # skip valuemap items that aren't valid values
                        # such as the numeric ranges for DMTF Reserved and whatnot
                        try:
                            pywbem.tocimobj(param.type, curVal)
                        except:
                            continue
                        ht+= '<option value="'+curVal+'">'+curVal
                        if valuesQual and i < len(valuesQual):
                            ht+= ' ('+valuesQual[i]+')'
                    ht+= '</select>'

                elif param.type == 'boolean':
                    ht+= '<select name="'+parmName+'">'
                    ht+= '<option value='""'>'
                    ht+= '<option value="True">True'
                    ht+= '<option value="False">False'
                    ht+= '</select>'
                else:
                    ht+= '<input type=text size=50 name="'+parmName+'">'
                ht+= '</td></tr>'
            ht+= '</table></td></tr>'
            ht+= '<tr>'
            if someRequired:
                ht+= '<td><table border=0><tr><td nowrap bgcolor="#FFDDDD">'
                ht+= '<i>Required Parameter</i></td><td width="100%" align="right">'
            else:
                ht+= '<td align="right">'
            ht+= '<input type=submit value="Invoke Method"></td></tr>'
            if someRequired:
                ht+= '</table></td></tr>'
            ht+= '</table>'
        else:
            ht+= '<input type=submit value="Invoke Method">'
        ht+= '</form>'
        if outParms:
            ht+= '<h3>Output Parameters</h3>'
            ht+= '<table valign=top border=1><tr bgcolor="#CCCCCC">'
            ht+= '<th>Data Type</th><th>Param Name</th></tr>'
            for param in outParms:
                ht+= '<tr valign=top><td>'
                if param.reference_class is not None:
                    ht+= param.reference_class
                    ht+= ' REF'
                else:
                    ht+= param.type
                if param.is_array:
                    ht+= ' [ ]'
                ht+= '</td><td'
                if param.qualifiers.has_key('description'):
                    ht+= ' title="'+cgi.escape(
                            param.qualifiers['description'].value)+'"'
                ht+= '>'+param.name+'</td></tr>'
            ht+= '</table>'
        rtype = (  cimmethod.return_type is not None
                and cimmethod.return_type or 'void')
        ht+= '<h3>Method return type: '+rtype+'</h3>'

        if needComboBox:
            ht+= _comboBox_js

        return ht +'</body></html>'

    @view(require_ns=False)
    def on_PrepMofComp(self, request, url=None):
        conn = self._frontMatter(request, url, 'root/cimv2')
        ht = self._printHead("MOF", "MOF", request, {'url':url})
        ht+= '<form action="'+self.urls.build('MofComp') + '" '
        ht+= 'enctype="multipart/form-data" METHOD=POST>'
        ht+= '<input type=hidden name="url" value="'+url+'"/>'
        ht+= '<input type=hidden name="ns" value="'+'root/cimv2'+'"/>'
        ht+= '<input id="file" name="file" size="70" type="file" />'
        ht+= '<p><textarea cols="80" id="text" name="text" rows="40">'
        ht+= '</textarea>'
        ht+= '<p><input name="commit" type="submit" value="Submit" />'
        ht+= '</form>'
        return ht + '</body></html>'

    @view()
    def on_PyProvider(self, request, className, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        klass = conn.GetClass(ClassName = className, LocalOnly=False, 
                    IncludeClassOrigin=True, IncludeQualifiers=True)
        code, mof = codegen(klass)
        title = 'Python Provider for %s' % className
        ht = self._printHead(title, request)
        ht+= '<font size=+1><b>%s</b></font>' % title
        ht+= '<table bgcolor="#f9f9f9" cellspacing=0 cellpadding=10 border=1>'
        ht+= '<tr><td><pre>'+cgi.escape(code)+'</pre>'
        ht+= '</td></tr></table>'
        ht+= '<font size=+1><b>Provider Registration MOF</b></font>'
        ht+= '<table bgcolor="#f9f9f9" cellspacing=0 cellpadding=10 border=1>'
        ht+= '<tr><td><pre>'+cgi.escape(mof)+'</pre>'
        ht+= '</td></tr></table>'
        return ht + '</body></html>'

    @view(http_method=POST)
    def on_Query(self, request, query=None, lang=QLANG_WQL, url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        if query is None:
            if "query" not in request.form:
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
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        insts = conn.ExecQuery(QueryLanguage=lang, Query=query, namespace=ns)
        ht = self._printHead('Query Results', req=request, urlargs=urlargs)
        ht+= '<h2>Query Results</h2><hr>'
        ht+= 'Query Language = '+lang
        ht+= '<br>Query = '+query
        numInsts = len(insts)
        msgStart = 'Showing '+`numInsts`+' Instances<br />'
        if numInsts == 0:
            msgStart = 'No Instances<br />'
        elif numInsts == 1:
            msgStart = ''
        ht+= msgStart
        ccache = pywbem.NocaseDict()
        for inst in insts:
            instName = inst.path
            try:
                klass = ccache[instName.classname]
            except KeyError:
                klass = conn.GetClass(instName.classname, LocalOnly=False)
                ccache[instName.classname] = klass
            ht += self._displayInstance(request, inst, instName,
                    klass, urlargs.copy())
        return ht + '</body></html>'


    @view()
    def on_QueryD(self, request, className='', url=None, ns=None):
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        ht = self._printHead('Query', req=request, urlargs=urlargs)
        ht+= '<h2>Execute Query</h2><hr>'
        ht+= '<form action="'+self.urls.build('Query')+'" METHOD=POST>'
        ht+= '<input type=hidden name="url" value="'+url+'">'
        ht+= '<input type=hidden name="ns" value="'+ns+'">'
        ht+= '<table border=0>'
        ht+= '<tr><td>Query Language</td><td>'
        ht+= '<select name="lang">'
        ht+= '<option value="WQL">WQL'
        #ht+= '<option value="CQL">CQL'
        ht+= '</select></td></tr>'
        ht+= '<tr><td>Query</td>'
        ht+= ('<td><input type="text" value="SELECT * FROM %s WHERE"'
              ' size=80 name="query"></td></tr>')% className
        ht+= '</table>'
        ht+= '<input type=submit value="Execute Query"></form>'
        return ht + '</body></html>'

    @view()
    def on_ReferenceNames(self, request, obj, url=None, ns=None):
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
        conn = self._frontMatter(request, url, ns)
        urlargs = {}
        urlargs['ns'] = ns
        urlargs['url'] = url
        oldns = obj.namespace
        # TODO remove this namespace hack when pywbem is fixed
        obj.namespace = None
        refs = conn.ReferenceNames(ObjectName=obj)
        obj.namespace = oldns is not None and oldns or ns

        class_urlargs = urlargs.copy()
        class_urlargs["className"] = obj.classname
        ht = 'Objects associated with instance of '
        ht+= self._makeHref(request, 'GetClass', class_urlargs,
                obj.classname) 
        ht = self._printHead('ReferenceNames '+obj.classname, ht, request,
                urlargs)

        ht += self._printInstanceNames(request, urlargs, [obj])
        ht += '<hr>'

        refdict = {}
        for ref in refs:
            refInstPath = ref
            assocClassName = refInstPath.classname
            if assocClassName not in refdict.keys():
                refdict[assocClassName] = {}
            for role in refInstPath.keys():
                roleInstPath = refInstPath[role]
                if roleInstPath == obj:
                    continue
                if role not in refdict[assocClassName].keys():
                    refdict[assocClassName][role] = {}
                roleClassName = roleInstPath.classname
                if roleClassName not in refdict[assocClassName][role].keys():
                    refdict[assocClassName][role][roleClassName] = []
                refdict[assocClassName][role][roleClassName].append(
                        roleInstPath)
        assocClassNames = refdict.keys()
        assocClassNames.sort()
        ht+= '<h2>Associations Available</h2><ul>'
        for assocClassName in assocClassNames:
            ht += '<li><a href="#' + assocClassName + '">'+assocClassName
            ht += '</a>'
        ht += '</ul>'
        for assocClassName in assocClassNames:
            class_urlargs["className"] = assocClassName
            assocLink = self._makeHref(request, 'GetClass', class_urlargs,
                    assocClassName)
            ht +=          '<a name="' + assocClassName + '"/>'
            ht +=          '\n<table border="1">\n'
            ht +=          '<tr>\n'
            ht +=          '  <td>\n'
            ht +=          '    <table>\n'
            ht +=          '      <tr>\n'
            ht +=          '        <td>\n'
            ht +=          '          <font size=+3>Association: '+assocLink+'</font>\n'
            ht +=          '        </td>\n'
            ht +=          '      </tr>\n'
            assocSet = refdict[assocClassName]
            roles = assocSet.keys()
            roles.sort()
            for role in roles:
                ht +=      '      <tr>\n'
                ht +=      '        <td>\n'
                ht +=      '          <table border="1">\n'
                ht +=      '            <tr>\n'
                ht +=      '              <td>\n'
                ht +=      '                <font size=+2>Role: '+role+'</font>\n'
                ht +=      '              </td>\n'
                ht +=      '            </tr>\n'
                classSet = assocSet[role]
                classNames = classSet.keys()
                classNames.sort()
                for className in classNames:
                    class_urlargs["className"] = className
                    typeLink = self._makeHref(request, 'GetClass',
                            class_urlargs, className)
                    ht +=  '            <tr>\n'
                    ht +=  '              <td>\n' 
                    ht +=  '                <table>\n'
                    ht +=  '                  <tr>\n'
                    ht +=  '                    <td>\n'
                    ht +=  '                      <font size=+1>Type: '+typeLink+'</font>\n'
                    ht +=  '                    </td>\n'
                    ht +=  '                  </tr>\n'
                    ht +=  '                  <tr>\n'
                    ht +=  '                    <td>\n'
                    instPathSet = classSet[className]
                    instPathSet.sort()
                    ht += self._printInstanceNames(request, urlargs,
                            instPathSet)
                    ht +=  '                    </td>\n'
                    ht +=  '                  </tr>\n'
                    ht +=  '                </table>\n'
                    ht +=  '              </td>\n'
                    ht +=  '            </tr>\n' 
                ht +=      '          </table>\n'
                ht +=      '        </td>\n'
                ht +=      '      </tr>\n'

            ht +=          '    </table>\n'
            ht +=          '  </td>\n'
            ht +=          '</tr>\n'
            ht +=          '</table>\n'
        return ht + "</body></html>"

