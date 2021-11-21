#!/usr/bin/env python
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

from mod_python import Cookie, apache
import pywbem
import cgi
import types
import cPickle
import base64
import urlparse
import string
import zlib
import os
try:
    from pywbem.cim_provider2 import codegen
except ImportError:
    codegen = None


# Mostly I just wanted to be able to say that I've used lambda functions
#_val2str = lambda x: (type(x) == types.UnicodeType and x or str(x))
##############################################################################
# no need to cgi.urllib.unquote_plus().  mod_python does that for us.
_decodeObject = lambda x: (cPickle.loads(zlib.decompress(base64.b64decode(x))))
##############################################################################
_encodeObject = lambda x: (base64.b64encode(zlib.compress(cPickle.dumps(x, cPickle.HIGHEST_PROTOCOL))))
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
                if type(item) == str:
                    strItem = '"' + strItem + '"'
                rval+= strItem
        rval+= '}'
        return cgi.escape(rval)
    else:
        return cgi.escape(str(x))

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
            klassProp = (key in klass.properties) and klass.properties[key] or None
            return klassProp and 'key' in klassProp.qualifiers
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
def getAllHierarchy(req, url, ns, className):
    hierarchy = []

    conn = _getConn(req, url, ns)
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
def DeleteInstance(req, url, ns, instPath):
    conn = _frontMatter(req, url, ns)
    instName = _decodeObject(instPath)
    try:
        conn.DeleteInstance(instName)
    # TODO make this use _ex()
    except pywbem._cim_http.AuthError as arg:
        raise apache.SERVER_RETURN(apache.HTTP_UNAUTHORIZED)
    except pywbem.CIMError as arg:
        req.write( _printHead('Error Deleting instance of '+instName.classname))
        req.write( 'Deleting instance of '+instName.classname+
                   ' returned the following error:<br> <i>(' + repr(arg[0]) +
                   ') : ' + arg[1] + '</i>')
        req.write( '</body></html>')
        return;
    urlargs = {'ns':ns,'url':url,'className':instName.classname}
    req.write( _printHead('Deleted Instance of '+instName.classname, 
       urlargs=urlargs))
    req.write('Deleted Instance of ' + _makeHref(req, 'GetClass', 
       urlargs, instName.classname))
    _printInstanceNames(req, urlargs, [instName], omitGetLink=True)
    return '</body></html>'

##############################################################################
def ReferenceNames(req, url, ns, instPath):
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
 Known bugs: if an assoc class has a key property of type other than REF,
 we'll probably blow up.  We also won't follow non-key REF properties (if
 there are such things)
    """
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    instName = _decodeObject(instPath)
    oldns = instName.namespace
    # TODO remove this namespace hack when pywbem is fixed
    instName.namespace = None
    refs = _ex(req, conn.ReferenceNames,ObjectName=instName)
    instName.namespace = oldns is not None and oldns or ns

    class_urlargs = urlargs.copy()
    class_urlargs["className"] = instName.classname
    ht = 'Objects associated with instance of '
    ht+= _makeHref(req, 'GetClass', class_urlargs, instName.classname) 
    ht = _printHead('ReferenceNames '+instName.classname, ht, req, urlargs)
    req.write(ht)

    _printInstanceNames(req, urlargs, [instName])
    req.write('<hr>',0)
    refdict = {}
    for ref in refs:
        refInstPath = ref
        assocClassName = refInstPath.classname
        if assocClassName not in refdict.keys():
            refdict[assocClassName] = {}
        for role in refInstPath.keys():
            roleInstPath = refInstPath[role]
            if roleInstPath == instName:
                continue
            if role not in refdict[assocClassName].keys():
                refdict[assocClassName][role] = {}
            roleClassName = roleInstPath.classname
            if roleClassName not in refdict[assocClassName][role].keys():
                refdict[assocClassName][role][roleClassName] = []
            refdict[assocClassName][role][roleClassName].append(roleInstPath)
    assocClassNames = refdict.keys()
    assocClassNames.sort()
    req.write('<h2>Associations Available</h2><ul>')
    for assocClassName in assocClassNames:
        req.write('<li><a href="#' + assocClassName + '">'+assocClassName+'</a>')
    req.write('</ul>')
    for assocClassName in assocClassNames:
        class_urlargs["className"] = assocClassName
        assocLink = _makeHref(req, 'GetClass', class_urlargs, assocClassName)
        req.write(         '<a name="' + assocClassName + '"/>')
        req.write(         '\n<table border="1">\n',0)
        req.write(         '<tr>\n')
        req.write(         '  <td>\n')
        req.write(         '    <table>\n')
        req.write(         '      <tr>\n')
        req.write(         '        <td>\n')
        req.write(         '          <font size=+3>Association: '+assocLink+'</font>\n')
        req.write(         '        </td>\n')
        req.write(         '      </tr>\n')
        assocSet = refdict[assocClassName]
        roles = assocSet.keys()
        roles.sort()
        for role in roles:
            req.write(     '      <tr>\n')
            req.write(     '        <td>\n')
            req.write(     '          <table border="1">\n')
            req.write(     '            <tr>\n')
            req.write(     '              <td>\n')
            req.write(     '                <font size=+2>Role: '+role+'</font>\n')
            req.write(     '              </td>\n')
            req.write(     '            </tr>\n')
            classSet = assocSet[role]
            classNames = classSet.keys()
            classNames.sort()
            for className in classNames:
                class_urlargs["className"] = className
                typeLink = _makeHref(req, 'GetClass', class_urlargs, className)
                req.write( '            <tr>\n')
                req.write( '              <td>\n' )
                req.write( '                <table>\n')
                req.write( '                  <tr>\n')
                req.write( '                    <td>\n')
                req.write( '                      <font size=+1>Type: '+typeLink+'</font>\n')
                req.write( '                    </td>\n')
                req.write( '                  </tr>\n')
                req.write( '                  <tr>\n')
                req.write( '                    <td>\n')
                instPathSet = classSet[className]
                instPathSet.sort()
                _printInstanceNames(req, urlargs, instPathSet)
                req.write( '                    </td>\n')
                req.write( '                  </tr>\n')
                req.write( '                </table>\n')
                req.write( '              </td>\n')
                req.write( '            </tr>\n' )
            req.write(     '          </table>\n')
            req.write(     '        </td>\n')
            req.write(     '      </tr>\n')

        req.write(         '    </table>\n')
        req.write(         '  </td>\n')
        req.write(         '</tr>\n')
        req.write(         '</table>\n')
    return '</body></html>'

##############################################################################
def FilteredReferenceNames(req, url, ns, instPath, assocClass, resultClass, 
                           role, resultRole, assocCall, properties):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    instName = _decodeObject(instPath)
    refs = None
    req.write( _printHead(assocCall+' '+instName.classname,urlargs=urlargs))

    class_urlargs = urlargs.copy()
    class_urlargs["className"] = instName.classname
    ht = '<h1>Filtered Objects associated with instance of '
    ht+= _makeHref(req, 'GetClass', class_urlargs, instName.classname) +'</h1>'
    if assocCall=='Associators':
        ht+='<b>Associators ( AssocClass=' + assocClass + ', ResultClass=' + resultClass + ', Role=' + role + ', ResultRole=' + resultRole + ', Properties=' + properties + ' )</b><br><br>'
    elif  assocCall=='Associator Names':
        ht+='<b>AssociatorNames ( AssocClass=' + assocClass + ', ResultClass=' + resultClass + ', Role=' + role + ', ResultRole=' + resultRole + ', Properties=' + properties + ' )</b><br><br>'
    elif  assocCall=='References':
        ht+='<b>References ( ResultClass=' + resultClass + ', Role=' + role + ', Properties=' + properties + ' )</b><br><br>'
    elif  assocCall=='Reference Names':
        ht+='<b>ReferenceNames ( ResultClass=' + resultClass + ', Role=' + role + ', Properties=' + properties + ' )</b><br><br>'
    req.write(ht)

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

    try:
        if assocCall=='Associators':
            assocs = _ex(req, conn.Associators,ObjectName=instName, 
                         **params)#, properties)
            req.write('Showing ' + repr(len(assocs)) + ' resulting object(s). <br><br>')
            for assoc in assocs:
                assocInstPath = assoc.path
                assocInst = assoc
                assocClassName = assocInst.classname
                req.write('<hr><h2>Objects of Class: ' + assocClassName + '</h2>')
                _printInstanceNames(req, urlargs, [assocInstPath])

                klass = _ex(req, conn.GetClass,
                        ClassName=assocInstPath.classname, 
                        namespace=assocInstPath.namespace, LocalOnly=False, 
                        IncludeQualifiers=True)
                req.write(_displayInstance(req, assocInst, assocInstPath, klass, urlargs))
        elif  assocCall=='Associator Names':
            assocNames = _ex(req, conn.AssociatorNames, ObjectName=instName, 
                             **params)#, properties)
            req.write('Showing ' + repr(len(assocNames)) + ' resulting object(s). <br><br>')
            for assocName in assocNames:
                assocInstPath = assocName
                req.write('<hr><h2>Objects of Class: ' + assocInstPath.classname + '</h2>')
                _printInstanceNames(req, urlargs, [assocInstPath])
        elif  assocCall=='References':
            refs = _ex(req,conn.References,ObjectName=instName, 
                       **params)#, properties)
            req.write('Showing ' + repr(len(refs)) + ' resulting object(s). <br><br>')
            for ref in refs:
                assocInstPath = ref.path
                assocInst = ref
                assocClassName = assocInst.classname
                _printInstanceNames(req, urlargs, [assocInstPath])

                klass = _ex(req,conn.GetClass,ClassName=assocInstPath.classname,
                        LocalOnly=False, IncludeQualifiers=True)
                req.write(_displayInstance(req, assocInst, assocInstPath, klass, urlargs))
        elif  assocCall=='Reference Names':
            refNames = _ex(req, conn.ReferenceNames, ObjectName=instName, **params)#, properties)
            req.write('Showing ' + repr(len(refNames)) + ' resulting object(s). <br><br>')
            for refName in refNames:
                assocInstPath = refName
                req.write('<hr><h2>Objects of Class: ' + assocInstPath.classname + '</h2>')
                _printInstanceNames(req, urlargs, [assocInstPath])
    except pywbem._cim_http.AuthError as arg:
        raise apache.SERVER_RETURN(apache.HTTP_UNAUTHORIZED)

    return '</body></html>'

##############################################################################
def AssociatorNames(req, url, ns, instPath):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    instName = _decodeObject(instPath)
    assocs = _ex(req,conn.AssociatorNames,ObjectName=instName)
    ht = _printHead('AssociatorNames '+instName.classname, urlargs=urlargs)
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
        req.write(ht)
        assocList = groupedAssocs[setkey]
        _printInstanceNames(req, urlargs, assocList)
    return '</body></html>'

##############################################################################
def FilteredReferenceNamesDialog(req, url, ns, instPath):
    conn = _frontMatter(req, url, ns)
    instName = _decodeObject(instPath)
    class_urlargs = {}
    class_urlargs['ns'] = ns
    class_urlargs['url'] = url
    class_urlargs["className"] = instName.classname
    ht = _printHead('Filtered ReferenceNames Dialog... (Coming...)', urlargs=class_urlargs)
    ht+= '<h1>Filtered References on Class '+_makeHref(req, 'GetClass', class_urlargs, instName.classname)+'</h1>'
    req.write(ht)
    _printInstanceNames(req, class_urlargs, [instName])
    ht= '<br><br><br><form type=get action="'+_baseScript(req)+'/FilteredReferenceNames" METHOD=GET>'
    ht+= '<input type=hidden name="url" value="'+url+'">'
    ht+= '<input type=hidden name="ns" value="'+ns+'">'
    ht+= '<input type=hidden name="instPath" value="'+instPath+'">'
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
    req.write(ht)
    return '</body></html>'


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
def _displayInstance(req, inst, instName, klass, urlargs):
    class_urlargs = urlargs.copy()
    class_urlargs["className"] = klass.classname
    ht= '<h2>Instance of '+_makeHref(req, 'GetClass', class_urlargs, klass.classname)+'</h2>'
    ht+= '<h4>Host: <i><font color="#00AA00">' + _val2str(instName.host) + '</font></i>'
    ht+= '<br>Namespace: <i><font color="#00AA00">' + _val2str(instName.namespace) + '</font></i></h4>'
    ht+= '<align ="right">'
    urlargs['instPath'] = _encodeObject(instName)
    ht+= '</align>'
    keys = inst.keys()
    _sortkey(keys, klass)
    ht+= '<table border="1" cellpadding="2">'
    ht+= '<tr>'
    ht+= '<td>'+_makeHref(req, 'DeleteInstance', urlargs, 'Delete')
    ht+= '<br>'+_makeHref(req, 'ModifyInstPrep', urlargs, 'Modify')
    ht+= '</td>'
    ht+= '<td align="right" colspan=2>View '
    ht+= _makeHref(req, 'ReferenceNames', urlargs,'Objects Associated with this Instance')
    ht+= '<br>'
    ht+= _makeHref(req, 'FilteredReferenceNamesDialog', urlargs,'(With Filters)')
    ht+= '</td></tr>'
    ht+= '<tr bgcolor="CCCCCC"><th>Type</th><th>Name</th><th>Value</th>'
    haveRequiredProps = False
    for key in keys:
        prop = inst.properties[key]
        klassProp = (key in klass.properties) and klass.properties[key] or None
        propIsKey = klassProp and ('key' in klassProp.qualifiers)
        propIsRequired = klassProp and ('required' in klassProp.qualifiers)
        propTitle = ''
        if klassProp and ('description' in klassProp.qualifiers):
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
                ht+= '<td>'+_makeHref(req, "GetClass", link_urlargs, 
                        klassProp.reference_class) + ' <i>Ref</i>'
        else:
            ht+='<td><font color="red">PropNotInSchema</font>'
        ht+= '</td><td title="'+cgi.escape(propTitle)+'">'+_makeHref(req, 'GetClass', class_urlargs, key, '#'+key.lower())+'</td><td>'


        if klassProp and ('values' in klassProp.qualifiers) and ('valuemap' in klassProp.qualifiers):
            ht+= _displayMappedValue(prop.value, klassProp.qualifiers)
        elif klassProp and klassProp.reference_class is not None:
            ns = _val2str(inst[key].namespace)
            urlargs['ns'] = ns
            targetInstName = inst[key]
            targetObjectPath = _val2str(targetInstName)
            ht+= _makeGetInstLink(req, urlargs, targetInstName, targetObjectPath)
        else:
            propval = _val2str(prop.value)
            if key.lower().endswith("classname"):
                link_urlargs = class_urlargs.copy()
                link_urlargs["className"] = propval
                ht+= _makeHref(req, "GetClass", link_urlargs, propval)
            else:
                ht+= propval
        ht+= '</td></tr>'
    ht+= '<tr><td colspan=3><table border=0><tr><td nowrap bgcolor="#FFDDDD">'
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
            methUrlArgs['objPath'] = methUrlArgs['instPath']
            del methUrlArgs['instPath']
            methUrlArgs['method'] = method.name
            ht+= _makeHref(req, 'PrepMethod', methUrlArgs, method.name) + '('
            for param in method.parameters.keys():
                if param != method.parameters.keys()[0]:
                    ht+= ','
                ht+= param
            ht+=')'
            ht+= ' </td>'
            ht+= '</tr>'
        ht+= '</table>'
        ht+= '</td></tr>'
    purlargs = {'obj': _encodeObject(instName)}
    ht+= '<tr><td colspan=3>'
    ht+= 'Get the '+_makeHref(req, 'Pickle', purlargs, 'LocalInstancePath')
    ht+= ' for use as a Method Reference Parameter'
    ht+= '</td></tr>'
    ht+= '</table>'
    return ht


##############################################################################
def GetInstance(req, url, ns, instPath=None, className=None, **params):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    if instPath is not None:
        instName = _decodeObject(instPath)
    else:
        # Remove 'PropName.' prefix from param names.
        params = dict ([(x[9:],y) for (x, y) in params.items()])
        instName = pywbem.CIMInstanceName(className, 
                keybindings=params, namespace=ns)
    inst = None
    klass = _ex(req,conn.GetClass,ClassName=instName.classname, 
            LocalOnly=False, IncludeQualifiers=True)
    inst = _ex(req,conn.GetInstance,InstanceName=instName, LocalOnly = False)
    ht = _printHead('Instance of '+instName.classname, req=req, urlargs=urlargs)
    ht+= _displayInstance(req, inst, instName, klass, urlargs)
    return ht + '</body></html>'

##############################################################################
def _makeHref(req, func, dict, target, append=''):
    return '<a href="'+_baseScript(req)+'/'+func+'?'+cgi.urllib.urlencode(dict)+append+'">'+cgi.escape(target)+'</a>'


##############################################################################
def _makeHrefWithTags(req, func, dict, target, openTags, closeTags):
    return '<a href="'+_baseScript(req)+'/'+func+'?'+cgi.urllib.urlencode(dict)+'">'+openTags+cgi.escape(target)+closeTags+'</a>'


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

##############################################################################
def _makeGetInstLink(req, urlargs, instName, targetName):
    urlargs['instPath'] = _encodeObject(instName)
    return _makeHref(req, 'GetInstance', urlargs, targetName)

##############################################################################
def _printInstRow(req, urlargs, keys, inst, omitGetLink = False):
    lurlargs = urlargs.copy()
    if inst.namespace is not None:
        lurlargs['ns'] = inst.namespace
    ht =     '  <tr>\n'
    if not omitGetLink:
        ht+=     '    <td>\n'
        ht+= _makeGetInstLink(req, lurlargs, inst, 'get')+'\n'
        ht+=     '    </td>\n'
    for key in keys:
        keyval = inst[key]
        ht+= '    <td>\n'
        if isinstance(keyval, pywbem.CIMInstanceName):
            ns = keyval.namespace
            if ns is not None:
                lurlargs['ns'] = ns
            ht+= _makeGetInstLink(req, lurlargs, keyval, _val2str(keyval))+'\n'
            if ns is not None:
                ht+= '<br><i>In namespace: ' + ns + '</i>'
        else:
            ht+= _val2str(keyval)+'\n'
        ht+= '    </td>\n'
    if inst.namespace is not None:
        ht+= '    <td><i><font color="#00AA00">'+inst.namespace+'</font></i></td>\n'
    ht+=     '  </tr>\n'
    req.write(ht)

##############################################################################
def Pickle(req, obj):
    req.add_common_vars()
    req.content_type = "Text/HTML"
    ht = _printHead("Object", "Object Serialization", req)
    ht+= '<p><i>To pass the following object as a Parameter Reference to a method call, copy this string to your clipboard and paste it to the parameter field.</i><p>'
    ht+= '<hr>'+obj+'<hr>'
    lobj = _decodeObject(obj)
    ht+= '<p><pre>'+cgi.escape(lobj.tocimxml().toprettyxml())+'</pre>'
    ht+= str(lobj)
    return ht + '</body></head>'

##############################################################################
def _printInstanceNames(req, urlargs, instNames, omitGetLink=False):
    if len(instNames) > 0:
        ht = '\n<table border="1" cellpadding="2">\n'
        if instNames[0].namespace:
            keys = instNames[0].keys()
            keys.sort()
            ht+= _printInstHeading(keys, includeNS=True, omitGetLink=omitGetLink)
        else:
            keys = instNames[0].keys()
            keys.sort()
            ht+= _printInstHeading(keys, omitGetLink=omitGetLink)
        req.write(ht)
        instNames.sort()
        for instName in instNames:
            _printInstRow(req, urlargs, keys, instName, omitGetLink)
        req.write( '</table>\n')

##############################################################################
def EnumInstances(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    insts = _ex(req,conn.EnumerateInstances,ClassName = className, LocalOnly = False)
    ht = _printHead('Instances of '+className, 'Instances of '+className, req, urlargs=urlargs)
    numInsts = len(insts)
    msgStart = 'Showing '+repr(numInsts)+' Instances<br />'
    if numInsts == 0:
        msgStart = 'No Instances<br />'
    elif numInsts == 1:
        msgStart = ''
    ht+= msgStart
    req.write(ht)
    ccache = pywbem.NocaseDict()
    for inst in insts:
        instName = inst.path
        try:
            klass = ccache[instName.classname]
        except KeyError:
            klass = conn.GetClass(instName.classname, LocalOnly=False)
            ccache[instName.classname] = klass
        req.write(_displayInstance(req, inst, instName, klass, urlargs.copy()))
    return '</body></html>'

##############################################################################
def _createOrModifyInstance(req, conn, url, ns, className, instName, **params):
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    klass = _ex(req, conn.GetClass, ClassName=className, 
            LocalOnly=False, IncludeQualifiers=True)
    if instName is not None:
        inst = _ex(req, conn.GetInstance,InstanceName=instName, LocalOnly = False)
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
                    propVal = [pywbem.cimvalue(x, dt) for x in propVal]
                    inst.properties[propName] = propVal
                else:
                    inst.properties[propName] = pywbem.cimvalue(propVal, dt)
    if instName:
        if instName.namespace is None: 
            instName.namespace = ns
        inst.path = instName
        _ex(req, conn.ModifyInstance,ModifiedInstance=inst)
    else: 
        instName = _ex(req, conn.CreateInstance, NewInstance=inst)
    inst = _ex(req, conn.GetInstance,InstanceName=instName, LocalOnly = False)
    
    urlargs['instPath'] = _encodeObject(instName)
    refurl = _baseScript(req)+'/GetInstance?'+cgi.urllib.urlencode(urlargs)
    ht = '<HTML>'
    ht+= '<META HTTP-EQUIV="Refresh" CONTENT="1;URL='+refurl+'">'
    ht+= '<HEAD><TITLE>Saving Instance...</TITLE> </HEAD>'
    ht+= '<BODY>The Instance has been saved.  Refreshing...<br>'
    ht+= '<p>If your browser doesn&apos;t refresh to the new instance, '
    ht+= 'click '+  _makeGetInstLink(req, urlargs, instName, 'here.')
    return ht 

##############################################################################
def CreateInstance(req, url, ns, className, **params):
    conn = _frontMatter(req, url, ns)
    ht = _createOrModifyInstance(req, conn, url, ns, className, None, **params)
    return ht + '</body></html>'

##############################################################################
def ModifyInstance(req, url, ns, instPath, **params):
    conn = _frontMatter(req, url, ns)
    instName = _decodeObject(instPath)
    ht = _createOrModifyInstance(req, conn, url, ns, instName.classname, instName, **params)
    return ht + '</body></html>'

##############################################################################
def CreateInstancePrep(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    klass = _ex(req, conn.GetClass, ClassName=className, 
            LocalOnly=False, IncludeQualifiers=True)
    ht = _printHead('Create Instance of '+className,'Create Instance of '+className, req, urlargs={'ns':ns, 'url':url})
    ht+= _displayInstanceMod(req, conn, url, ns, klass)
    return ht + '</body></html>'

##############################################################################
def GetInstD(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    klass = _ex(req, conn.GetClass, ClassName=className, LocalOnly=False, 
            IncludeQualifiers=True)
    ht = _printHead('Get Instance of '+className,'Get Instance of '+className, req, urlargs={'ns':ns, 'url':url})
    ht+= _displayInstanceMod(req, conn, url, ns, klass, getInst=True)
    return ht + '</body></html>'

##############################################################################
def ModifyInstPrep(req, url, ns, instPath):
    conn = _frontMatter(req, url, ns)
    instPathDec = _decodeObject(instPath)
    klass = _ex(req,conn.GetClass,ClassName=instPathDec.classname, 
            LocalOnly=False, IncludeQualifiers=True)
    ht = _printHead('Modify Instance of '+instPathDec.classname,'Modify Instance of '+instPathDec.classname, req, urlargs={'ns':ns, 'url':url})
    ht+= _displayInstanceMod(req, conn, url, ns, klass, (instPath, instPathDec))
    return ht + '</body></html>'

##############################################################################
def _displayInstanceMod(req, conn, url, ns, klass, oldInstPathPair = None, getInst=False):
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    oldInstPath = None
    oldInstPathDec = None
    if oldInstPathPair is not None:
        oldInstPath = oldInstPathPair[0]
        oldInstPathDec = oldInstPathPair[1]
    className = klass.classname
    urlargs['className'] = className
    oldInst = None
    if oldInstPathDec is not None:
        oldInst = _ex(req,conn.GetInstance,InstanceName=oldInstPathDec, LocalOnly = False)
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
    ht+= '<form action="'+_baseScript(req)+'/'+method+'" METHOD='
    if getInst:
        ht+= 'GET>'
    else:
        ht+= 'POST>'
    ht+= '<input type=hidden name="url" value="'+url+'">'
    ht+= '<input type=hidden name="ns" value="'+ns+'">'
    if oldInstPathPair is None:
        ht+= '<input type=hidden name="className" value="'+className+'">'
    else:
        ht+= '<input type=hidden name="instPath" value="'+oldInstPath+'">'
    ht+= '<table border="1" cellpadding="2">'
    ht+= '<tr bgcolor="CCCCCC"><th>Type</th><th>Name</th><th>Value</th>'
    ht+= '</tr>'
    for propName in propNames:
        prop = klass.properties[propName]
        propIsKey = 'key' in prop.qualifiers
        propIsRequired = 'required' in prop.qualifiers
        propTitle = ''
        if 'description' in prop.qualifiers:
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
        ht+= '</td><td title="'+cgi.escape(propTitle)+'">'+_makeHref(req, 
                'GetClass', urlargs, propName, '#'+propName.lower())+'</td>'
        ht+= '<td>'
        fPropName = 'PropName.'+prop.name
        oldVal = None
        if oldInst is not None:
            if propName in oldInst.properties:
                oldVal = oldInst.properties[propName].value
        if 'valuemap' in prop.qualifiers:
            if type(oldVal) == list:
                oldVal = [str(x) for x in oldVal]
            needComboBox = True
            valmapQual = prop.qualifiers['valuemap'].value
            valuesQual = None
            if 'values' in prop.qualifiers:
                valuesQual = prop.qualifiers['values'].value

            # Disable the combobox for now, because it isn't working, and
            # we may not actually need it.  For example, perhaps any time
            # values from VendorReserved are used, the vendor's subclass
            # will override the method, and thus the qualifiers, and provide
            # specific valuemap extensions that would in turn show up in our
            # drop down.
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
                    pywbem.cimvalue(curVal, prop.type)
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

##############################################################################
def EnumInstanceNames(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    instNames = _ex(req,conn.EnumerateInstanceNames,ClassName = className)
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
    ht+= _makeHref(req, 'GetClass', class_urlargs, className) + '</h1>'
    ht = _printHead('Instances of '+className, ht, req, urlargs=urlargs)
    req.write(ht)
    if numInsts == 0:
        ht = _makeHref(req, 'CreateInstancePrep', class_urlargs, 
            'Create New Instance')
        req.write(ht)

    for cname, inames in inameDict.items():
        if len(inameDict) > 1:
            ht = '<h2>'
            ht+= '%s %s' % (len(inames), len(inames) == 1 and 'Instance' or 'Instances')
            class_urlargs["className"] = cname
            ht+= ' of '
            ht+= _makeHref(req, 'GetClass', class_urlargs, cname) + '</h2>'
            req.write(ht)
        _printInstanceNames(req, urlargs, inames)
        ht = '<p>'
        ht+= _makeHref(req, 'CreateInstancePrep', class_urlargs, 
            'Create New Instance')
        req.write(ht)

    return '</body></html>'

##############################################################################
def _frontMatter(req, url, ns):
    req.add_common_vars()
    req.content_type = 'Text/HTML'
    authHeader = 'Basic realm="CIMOM at '+url+'"'
    req.headers_out["WWW-Authenticate"] = authHeader
    req.err_headers_out["WWW-Authenticate"] = authHeader
    return _getConn(req, url, ns)

##############################################################################
def InvokeMethod(req, url, ns, objPath, method, **params):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    className = None
    lobjPath = _decodeObject(objPath)
    if isinstance(lobjPath, pywbem.CIMInstanceName) and lobjPath.namespace is None:
        lobjPath.namespace = ns
    className = lobjPath.classname
    urlargs['className'] = className
    # else lobjPath is a CIMInstanceName
    klass = _ex(req,conn.GetClass,ClassName = lobjPath.classname, 
            LocalOnly=False)
    ht = 'Invoked method '+_makeHref(req, 'GetClass', urlargs, className)
    ht+= '::'+_makeHref(req, 'GetClass', urlargs, method, '#'+method.lower())
    ht+= '()'
    ht = _printHead('Results of Method '+className+'::'+method, ht, req, urlargs=urlargs)

    cimmethod = klass.methods[method]
    inParms = {}

    def type_str (meta_parm):
        if meta_parm.reference_class is not None:
            urlargs['className'] = metaParm.reference_class
            dt = 'REF ' + _makeHref(req, 'GetClass', urlargs, 
                                    metaParm.reference_class)
        else:
            dt = metaParm.type
        if metaParm.is_array:
            dt+= '[]'
        return dt

    if params:
        # Remove 'MethParm.' prefix from param names.
        params = dict ([(x[9:],y) for (x, y) in params.items()])
        ht+= '<h3>With Input Parameters</h3>'
        ht+= '<table valign=top border=1>'
        ht+= ' <tr bgcolor="#CCCCCC"><th>Data Type</th><th>Param Name</th><th>Value</th></tr>'
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
                        paramVal = [_decodeObject(x) for x in paramVal]
                    else:
                        paramVal = [pywbem.cimvalue(x, dt[:-2]) for x in paramVal]
                    inParms[paramName] = paramVal
                else:
                    if metaParm.reference_class is not None:
                        inParms[paramName] = _decodeObject(paramVal)
                    else:
                        inParms[paramName] = pywbem.cimvalue(paramVal, dt)
        ht+= '</table>'

    (rval, outParms) = _ex(req,conn.InvokeMethod,MethodName=method, ObjectName=lobjPath, **inParms)

    if outParms:
        ht+= '<h3>Output Values</h3>'
        ht+= '<table border=1><tr bgcolor="#CCCCCC">'
        ht+= '<th>Data Type</th><th>Param Name</th><th>Value</th></tr>'
        for parmName, parm in outParms.items():
            metaParm = cimmethod.parameters[parmName]
            isRef = metaParm.reference_class is not None
            dt = type_str(metaParm)
            ht+= '<tr><td>'+dt+'</td><td>'+metaParm.name+'</td><td>'
            if 'values' in metaParm.qualifiers and 'valuemap' in metaParm.qualifiers:
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
                    ht+= _makeGetInstLink(req, urlargs, parm, _val2str(parm))
                else:
                    ht+= _val2str(parm)
            ht+= '</td></tr>'
        ht+= '</table>'

    ht+= '<font size=+1><b>Method returned:</b></font> ' + _val2str(rval)
    urlargs['className'] = className
    ht+= '<p>Return to class ' + _makeHref(req, 'GetClass', urlargs, className)
    if isinstance(lobjPath, pywbem.CIMInstanceName):
        del urlargs['className']
        ht+= ' or instance of '+className + ':'
        req.write(ht)
        _printInstanceNames(req, urlargs, [lobjPath])
        ht = ''

    return ht + '</body></html>'

##############################################################################
def Query(req, url, ns, lang, query):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    insts = _ex(req, conn.ExecQuery, QueryLanguage=lang, 
            Query=query, namespace=ns)
    ht = _printHead('Query Results', req=req, urlargs=urlargs)
    ht+= '<h2>Query Results</h2><hr>'
    ht+= 'Query Language = '+lang
    ht+= '<br>Query = '+query
    numInsts = len(insts)
    msgStart = 'Showing '+repr(numInsts)+' Instances<br />'
    if numInsts == 0:
        msgStart = 'No Instances<br />'
    elif numInsts == 1:
        msgStart = ''
    ht+= msgStart
    req.write(ht)
    ccache = pywbem.NocaseDict()
    for inst in insts:
        instName = inst.path
        try:
            klass = ccache[instName.classname]
        except KeyError:
            klass = conn.GetClass(instName.classname, LocalOnly=False)
            ccache[instName.classname] = klass
        req.write(_displayInstance(req, inst, instName, klass, urlargs.copy()))
    return '</body></html>'



    insts = _ex(req,conn.EnumerateInstances,ClassName = className, LocalOnly = False)
    ht = _printHead('Instances of '+className, 'Instances of '+className, req, urlargs=urlargs)
    numInsts = len(insts)
    msgStart = 'Showing '+repr(numInsts)+' Instances<br />'
    if numInsts == 0:
        msgStart = 'No Instances<br />'
    elif numInsts == 1:
        msgStart = ''
    ht+= msgStart
    req.write(ht)
    ccache = pywbem.NocaseDict()
    for inst in insts:
        instName = inst.path
        try:
            klass = ccache[instName.classname]
        except KeyError:
            klass = conn.GetClass(instName.classname, LocalOnly=False)
            ccache[instName.classname] = klass
        req.write(_displayInstance(req, inst, instName, klass, urlargs.copy()))
    return '</body></html>'

##############################################################################
def QueryD(req, url, ns, className=''):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    ht = _printHead('Query', req=req, urlargs=urlargs)
    ht+= '<h2>Execute Query</h2><hr>'
    ht+= '<form action="'+_baseScript(req)+'/Query" METHOD=GET>'
    ht+= '<input type=hidden name="url" value="'+url+'">'
    ht+= '<input type=hidden name="ns" value="'+ns+'">'
    ht+= '<table border=0>'
    ht+= '<tr><td>Query Language</td><td>'
    ht+= '<select name="lang">'
    ht+= '<option value="WQL">WQL'
    #ht+= '<option value="CQL">CQL'
    ht+= '</select></td></tr>'
    ht+= '<tr><td>Query</td>'
    ht+= '<td><input type=text value="SELECT * FROM %s WHERE" size=80 name="query"></td></tr>' % className
    ht+= '</table>'
    ht+= '<input type=submit value="Execute Query"></form>'
    return ht + '</body></html>'

##############################################################################
def PrepMethod(req, url, ns, objPath, method):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    lobjPath = _decodeObject(objPath)
    className = None
    className = lobjPath.classname
    klass = _ex(req,conn.GetClass,ClassName = className, LocalOnly=False,
            IncludeQualifiers=True)

    cimmethod = klass.methods[method]
    inParms = []
    outParms = []
    for param in cimmethod.parameters.values():
        # TODO is IN assumed to be true if the IN qualifier is missing?
        if not 'in' in param.qualifiers or param.qualifiers['in'].value:
            inParms.append(param)
        if 'out' in param.qualifiers and param.qualifiers['out'].value:
            outParms.append(param)


    classUrlArgs = urlargs.copy()
    classUrlArgs['className'] = className
    ht = 'Invoke method '+_makeHref(req, 'GetClass', classUrlArgs, className)
    ht+= '::'+_makeHref(req, 'GetClass', classUrlArgs, method, '#'+method.lower())+'()'
    # note, ht passed in as param. 
    ht = _printHead('Method '+className+'::'+method, ht, req, urlargs=urlargs)
    if isinstance(lobjPath, pywbem.CIMInstanceName):
        ht+= 'on instance'
        req.write(ht,0)
        _printInstanceNames(req, urlargs, [lobjPath])
        ht = ''
    ht+= '<form action="'+_baseScript(req)+'/InvokeMethod" METHOD=POST>'
    ht+= '<input type=hidden name="url" value="'+url+'">'
    ht+= '<input type=hidden name="ns" value="'+ns+'">'
    ht+= '<input type=hidden name="objPath" value="'+objPath+'">'
    ht+= '<input type=hidden name="method" value="'+method+'">'
    ht+= '<table border=0>'
    needComboBox = False
    if inParms:
        someRequired = False
        ht+= '<h3>Enter Input Parameters</h3>'
        ht+= '<tr><td><table valign=top border=1>'
        ht+= '<tr bgcolor="#CCCCCC"><th>Data Type</th><th>Param Name</th><th>Value</th></tr>'
        for param in inParms:
            ht+= '<tr valign=top'
            if 'required' in param.qualifiers and param.qualifiers['required'].value:
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
            if 'description' in param.qualifiers:
                ht+= ' title="'+cgi.escape(param.qualifiers['description'].value)+'"'
            ht+= '>'
            ht+= param.name
            ht+= '</td><td>'
            # avoid name collisions, in case some param is called ns, url, etc.
            parmName = 'MethParm.'+param.name
            if 'valuemap' in param.qualifiers:
                needComboBox = True
                valmapQual = param.qualifiers['valuemap'].value
                valuesQual = None
                if 'values' in param.qualifiers:
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
                        pywbem.cimvalue(curVal, param.type)
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
            if 'description' in param.qualifiers:
                ht+= ' title="'+cgi.escape(param.qualifiers['description'].value)+'"'
            ht+= '>'+param.name+'</td></tr>'
        ht+= '</table>'
    rtype = cimmethod.return_type is not None and cimmethod.return_type or 'void'
    ht+= '<h3>Method return type: '+rtype+'</h3>'

    if needComboBox:
        ht+= _comboBox_js

    req.write(ht)
    return '</body></html>'

##############################################################################
def PrepMofComp(req, url):
    conn = _frontMatter(req, url, 'root/cimv2')
    ht = _printHead("MOF", "MOF", req, {'url':url})
    ht+= '<form action="'+_baseScript(req)+'/MofComp" '
    ht+= 'enctype="multipart/form-data" METHOD=POST>'
    ht+= '<input type=hidden name="url" value="'+url+'"/>'
    ht+= '<input type=hidden name="ns" value="'+'root/cimv2'+'"/>'
    ht+= '<input id="file" name="file" size="70" type="file" />'
    ht+= '<p><textarea cols="80" id="text" name="text" rows="40">'
    ht+= '</textarea>'
    ht+= '<p><input name="commit" type="submit" value="Submit" />'
    ht+= '</form>'
    return ht + '</body></html>'

##############################################################################
def MofComp(req, url, ns, file, text):
    conn = _frontMatter(req, url, 'root/cimv2')
    ht = _printHead("MOF", "MOF", req, {'url':url})
    ht+= "file:<pre>"
    ht+= cgi.escape(file.value)
    ht+= '</pre>'
    ht+= 'text:<pre>'
    ht+= cgi.escape(text)
    ht+= '</pre>'
    return ht + '</body></html>'

##############################################################################
def _ex(req, method, **params):
    try:
        return method(**params)
    except pywbem._cim_http.AuthError as arg:
        raise apache.SERVER_RETURN(apache.HTTP_UNAUTHORIZED)
    except pywbem.CIMError as arg:
        ht = _printHead('Error')
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
        if req.conn.debug:
            if req.conn.last_request is not None:
                ht+= '<pre>'+cgi.escape(req.conn.last_request)+'</pre>'
            ht+= '<hr>'
            if req.conn.last_reply is not None:
                ht+= '<pre>'+cgi.escape(req.conn.last_reply)+'</pre>'
        ht+= '</body></html>'
        req.write(ht)
        # see http://tinyurl.com/jjwjz
        req.status = apache.HTTP_OK
        raise apache.SERVER_RETURN(apache.DONE)
    #except: 
        #fo = open('/tmp/yawn_dump', 'w')
        #fo.write(req.conn.last_reply)
        #fo.close()
        #raise
        

##############################################################################
def DeleteClass(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    _ex(req, conn.DeleteClass, ClassName = className)
    ht = _printHead('Deleted class '+ className, urlargs=urlargs)
    ht+= 'Deleted Class ' + className
    return ht + '</body></html>'

##############################################################################
def GetClass(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url
    klass = _ex(req, conn.GetClass, ClassName=className, LocalOnly=False, 
            IncludeClassOrigin=True, IncludeQualifiers=True)
    urlargs['className'] = className
    ht = _printHead('Class '+className, 'Class '+className, req, urlargs=urlargs)
    instUrlArgs = urlargs.copy()
    ht+= '<table border=0><tr><td>'
    ht+= '<div align=center>'
    ht+= _makeHref(req, 'DeleteClass', urlargs, 'Delete Class')
    del urlargs['className']
    ht+= '. ' + _makeHref(req, 'GetInstD', instUrlArgs, 'Get Instance')
    ht+= ' or view '+_makeHref(req, 'EnumInstanceNames', instUrlArgs, 'Instance Names')
    ht+= ' or '+_makeHref(req, 'EnumInstances', instUrlArgs, 'Instances')
    ht+= ' or '+_makeHref(req, 'AssociatedClasses', instUrlArgs, 'Associated Classes')
    ht+= ' of this class.'
    if codegen is not None:
        ht+= ' &nbsp;'+ _makeHref(req, 
                   'PyProvider', instUrlArgs, 'Python Provider')
    ht+= ' &nbsp;'+ _makeHref(req, 
               'CMPIProvider', instUrlArgs, 'CMPI Provider')
    ht+= '</div>'
    ht+= '<table border="1" cellpadding="2">'
    if 'aggregation' in klass.qualifiers:
        titleBGColor = "green"
    elif 'association' in klass.qualifiers:
        titleBGColor = "red"
    else:
        titleBGColor = "black"
    ht+= '<tr><td valign="middle" align="center" width="50%" bgcolor="'+titleBGColor+'"><b><font color="#FFFFFF">'
    ht+= '<a name="'+className+'">'+className+'</a></font></b></td>'
    ht+= '<td valign="middle" align="center" witdth="50%">'
    if klass.superclass is not None:
        gcUrlArgs = urlargs.copy()
        gcUrlArgs["className"] = klass.superclass
        ht+= '<b>Superclass: '+_makeHref(req, 'GetClass', gcUrlArgs, klass.superclass)+'</font></b>'
    ht+= '</td></tr>'
    ht+= '<tr><td colspan="2"><table width="100%">'
    if 'description' in klass.qualifiers:
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
            if qual.name not in ["Composition", "Association", "Aggregation"]:
                ht+= ' ("'+_val2str(qual.value)+'") '
        ht+= '</td></tr>'
    ht+= '<tr><td align="center" bgcolor="#C0C0C0" colspan="3"><b>'
    ht+= 'Parameters (local in grey)</b></td></tr>'
    ht+= '<td width="15"></td><td width="100%"><table width="100%" border="1">'
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
        if 'description' in item.qualifiers:
            desc = item.qualifiers['description'].value
            del item.qualifiers['description']
        deprecated = 'deprecated' in item.qualifiers
        key = 'key' in item.qualifiers
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
            type = item.return_type is not None and item.return_type or 'void'
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
            methUrlArgs['objPath'] = _encodeObject(pywbem.CIMClassName(className, namespace=ns))
            methUrlArgs['method'] = item.name
            ht+= _makeHref(req, 'PrepMethod', methUrlArgs, item.name)
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
                    if 'description' in param.qualifiers:
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
                            ht+= qual.name + ' ' + _val2str(qual.value) + '</td></tr>'
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
                            ht+= repr(param.array_size)
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
                ht+= '<i>Class Origin</i>: '+_makeHref(req, 'GetClass', coUrlArgs, item.class_origin)
        ht+= '</td></tr>'
    ht+= '</table></table></table></td></tr></table>'
    return ht + '</body></html>'

##############################################################################
def _getConn(req, url, ns):
    (user, pw) = _getUserPW(req)
    if user is None:
        user = ''
    if pw is None:
        pw = ''
    cookies = Cookie.get_cookies(req)
    if len(user) > 0 and 'yawn_logout' in cookies:
        if cookies['yawn_logout'].value in ['true','pending']:
            #
            # modpython.Cookie.add_cookie() only adds to req.headers_out
            #
            req.err_headers_out["Cache-Control"] = 'no-cache="set-cookie"'

            cookie = 'yawn_logout=false;path='+_baseScript(req)
            #if cookies['yawn_logout'].value == 'pending':
            #    cookie = 'yawn_logout=false;path='+_baseScript(req)
            #else:
            #    cookie = 'yawn_logout=pending;path='+_baseScript(req)

            #
            # The purpose of this is to make sure the user re-authenticates
            # in case they want to switch users (without closing their browser)
            #
            req.err_headers_out["Set-Cookie"] = cookie
            user = ' '
            pw = ' '
    conn = pywbem.WBEMConnection(url, (user, pw))
    conn.default_namespace = ns
    req.conn = conn
    conn.debug = True
    return conn

##############################################################################
def _printEnumDeep(req, curclass, dict, urlargs, level = 0):
    classNames = dict[curclass]
    classNames.sort()
    for className in classNames:
        hasKids = className in dict
        ht = '<tr'
        if req.color:
            req.color = False
            ht+= ' bgcolor="#EEFFEE"'
        else:
            req.color = True
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
            ht+= _makeHref(req, 'GetClass', urlargs, className)
        else:
            ht+= _makeHrefWithTags(req, 'GetClass', urlargs, className, '<font color="#7777ff">', '</font>')
        if not isCimSchema:
           ht+= '</i>'
        if level==0:
           ht+= '</b>'
        ht+= '</td><td>'
        ht+= _makeHref(req, 'EnumInstanceNames', urlargs, 'Instance Names')
        ht+= '</td><td>&nbsp;&nbsp;&nbsp;'
        ht+= _makeHref(req, 'EnumInstances', urlargs, 'Instances')
        ht+= '</td></tr>'
        req.write(ht,0)
        if hasKids:
            _printEnumDeep(req, className, dict, urlargs, level+1)

##############################################################################
def EnumInstrumentedClassNames(req, url, ns):
    fetched_classes = []
    def get_class(cname):
        fetched_classes.append(cname)
        return _ex(req, conn.GetClass, ClassName=cname,
                   LocalOnly=True, PropertyList=[],
                   IncludeQualifiers=False, IncludeClassOrigin=False)
    conn = _frontMatter(req, url, ns)
    caps = _ex(req, conn.EnumerateInstances,
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
    ht = _printHead('Classes in '+ns,'Classes in '+url+'/'+ns, req, urlargs)
    ht+= '<table border=0><tr><td></td>'
    req.write(ht)

    req.color = True
    _printEnumDeep(req, startClass, deepDict, urlargs)

    return '</table></body></html>'

##############################################################################
def EnumClassNames(req, url, ns, className=None, mode='deep', instOnly=None):
    conn = _frontMatter(req, url, ns)
    req.add_common_vars()
    if instOnly is not None:
        cookie = 'yawn_instOnly=%s;path=%s' % (instOnly, _baseScript(req))
        instOnly = instOnly == 'true'
        req.headers_out['Set-Cookie'] = cookie
    else:
        cookies = Cookie.get_cookies(req)
        if 'yawn_instOnly' in cookies and \
                cookies['yawn_instOnly'].value == 'true':
            instOnly = True

    if instOnly:
        return EnumInstrumentedClassNames(req, url, ns)

    lineage = []
    if className is not None: 
        lineage = [className]
        klass = _ex(req, conn.GetClass, ClassName=className)
        while klass.superclass is not None:
            lineage.insert(0, klass.superclass)
            klass = _ex(req, conn.GetClass, ClassName=klass.superclass)
    if mode == 'deep':
        if className is None:
            klasses = _ex(req, conn.EnumerateClasses, DeepInheritance=True, 
                          LocalOnly=True, IncludeQualifiers=False, 
                          IncludeClassOrigin=False)
        else:
            klasses = _ex(req, conn.EnumerateClasses, DeepInheritance=True, 
                          LocalOnly=True, IncludeQualifiers=False, 
                          IncludeClassOrigin=False,
                          ClassName=className)
    else:
        if className is not None: 
            classNames = _ex(req, conn.EnumerateClassNames, 
                             DeepInheritance = mode=='flat', 
                             ClassName=className)
        else:
            classNames = _ex(req, conn.EnumerateClassNames, 
                             DeepInheritance = mode=='flat') 

    urlargs = {'ns': ns, 'url': url}
    ht = _printHead('Classes in '+ns,'Classes in '+url+'/'+ns, req, urlargs)
    ecn_urlargs = urlargs.copy()
    ecn_urlargs['mode'] = mode
    req.write(ht) ; ht = ''
    ht+= '<table border=0><tr><td></td>'
    if lineage: 
        ht+= '<td>'+_makeHref(req, 'EnumClassNames', ecn_urlargs, '<root>')
        for cname in lineage: 
            ht+= '&nbsp;/&nbsp;'
            if cname != lineage[-1]:
                ecn_urlargs['className'] = cname
                ht+= _makeHref(req, 'EnumClassNames', ecn_urlargs, cname)
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
        ht+= _makeHref(req, 'EnumClassNames', ref_urlargs, 
                       'Deep') #  (With Hierarchy)')
        ht+= '</td>'
    if mode != 'shallow':
        ref_urlargs['mode'] = 'shallow'
        ht+= '<td>'
        ht+= _makeHref(req, 'EnumClassNames', ref_urlargs, 'Shallow')
        ht+= '</td>'
    if False: # mode != 'flat': # Disable since deep is faster now
        ref_urlargs['mode'] = 'flat'
        ht+= '<td>'
        ht+= _makeHref(req, 'EnumClassNames', ref_urlargs, 
                       'Deep (Without Hierarchy)')
        ht+= '</td>'
    #ht+= '</tr></table>'
    ht+= '</tr></table></td></tr></table>'

    ht+= '<hr>\n'
    req.write(ht); ht = ''

    ht+= '<table border=0>'
    req.write(ht); ht = ''
    req.color = True
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

        _printEnumDeep(req, startClass, deepDict, urlargs, len(lineage))

    else:
        #ht+= '<table border=0>'
        req.write(ht); ht = ''
        if classNames is None:
            classNames = []
        for cname in classNames:
            isCimSchema = cname.startswith("CIM_")
            ecn_urlargs['className'] = cname
            ht = '<tr'
            if req.color:
                req.color = False
                ht+= ' bgcolor="#EEFFEE"'
            else:
                req.color = True
            ht+= '><td>'
            hasKids = mode != 'flat' and _ex(req, conn.EnumerateClassNames, 
                                      ClassName=cname)
            if hasKids:
                ht+= _makeHref(req, 'EnumClassNames', ecn_urlargs, '+')
            ht+= '</td><td>'
            urlargs['className'] = cname
            if not isCimSchema:
                ht+= '<i>'
            if not hasKids:
                ht+= _makeHrefWithTags(req, 'GetClass', urlargs, cname,
                               '<font color="#05058f">','</font>')
            else:
                ht+= _makeHref(req, 'GetClass', urlargs, cname)
            if not isCimSchema:
                ht+= '</i>'
            ht+= '</td><td>&nbsp;&nbsp;&nbsp;'
            ht+= _makeHref(req, 'EnumInstanceNames', urlargs, 'Instance Names')
            ht+= '</td><td>&nbsp;&nbsp;&nbsp;'
            ht+= _makeHref(req, 'EnumInstances', urlargs, 'Instances')
            ht+= '</td></tr>\n'
            req.write(ht)
        ht = '</table>'
        req.write(ht); ht = ''
        
    return '</table></body></html>'

##############################################################################
##############################################################################
def AssociatedClasses(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    classNames = None
    cns = _ex(req, conn.References,ObjectName=className, IncludeQualifiers=True)
    cns.sort()
    urlargs = {}
    urlargs['ns'] = ns
    urlargs['url'] = url

    urlargs['className'] = className
    ht = _printHead('Classes Associated To ' + className + ' in Namespace: '+ns)
    ht+= '<h1>Classes Associated To ' + _makeHref(req, 'GetClass', urlargs, className) + ' in Namespace: '+ns+'</h1>'
    ht+= '<table border=1 cellpadding=2><tr bgcolor="CCCCCC"><th>Associated Class Name</th><th>Via Association Class</th><th>Role</th><th>Associated Role</th></tr>'

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
    hierarchy = getAllHierarchy(req, url, ns, className)
    lastAssocClass = ''
    for cn in cns:
        klass = cn[1]
        assocClass = klass.classname
        resultClass = ''
        role = ''
        resultRole = ''
        roleDescription = ''
        resultRoleDescription = ''

        # to find the resultClass, I have to iterate the properties to a REF that is not className

        for propname in klass.properties.keys():
            prop = klass.properties[propname]
            if prop.reference_class is not None:
                refClass = prop.reference_class
                description = ''
                if 'description' in prop.qualifiers:
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
        ht+= _makeHref(req, 'GetClass', urlargs, resultClass)
        ht+= '</td>'
        ht+= '<td>'
        urlargs['className'] = assocClass
        ht+= _makeHref(req, 'GetClass', urlargs, assocClass)
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
    req.write(ht)
    return "</table></body></html>"

##############################################################################
def _printHead(title = None, heading = None, req = None, urlargs = None):
    ht = '\n<html><head><title>YAWN: CIM'
    if title is not None:
        ht+= ' ' + title
    ht+= '</title></head><body link="#0000ff" >'
    table = False
    if req is not None:
        table = True
    if table:
        ht+= '<table border=0 cellpadding=0 cellspacing=0 vspace=0><tr><td nowrap width=100% valign=top>'
        if heading is not None:
            ht+= '<h1>'+heading+'</h1>'
        ht+= '</td>'
        if urlargs and 'ns' in urlargs and 'url' in urlargs:
            lurlargs = {'ns':urlargs['ns'], 'url':urlargs['url']}
            ht+= '<td valign=top nowrap align=right><font size=-1><i>'
            ht+= _makeHref(req, 'EnumClassNames', lurlargs, lurlargs['ns'])
            ht+= '&nbsp;&nbsp;&nbsp;</i></td>'
        if urlargs and 'url' in urlargs:
            ht+= '<td valign=top nowrap align=right><font size=-1><i>'
            ht+= _makeHref(req, 'EnumNamespaces', {'url':urlargs['url']},
                           'Namespaces')
            ht+= '&nbsp;&nbsp;&nbsp;</i></td>'
        if urlargs and 'ns' in urlargs and 'url' in urlargs:
            try:
                lurlargs['className'] = urlargs['className']
            except KeyError:
                pass
            ht+= '<td valign=top nowrap align=right><font size=-1><i>'
            ht+= _makeHref(req, 'QueryD', lurlargs, 'Query')
            ht+= '&nbsp;&nbsp;&nbsp;</i></td>'
        ht+= '<td valign=top nowrap align=right><font size=-1><i>'
        ht+= '<a href="'+_baseScript(req)+'/Logout">Logout &gt;&gt;</a></i>'
        ht+= '</td></tr></table>'
    return ht

##############################################################################
def _getUserPW(req):
    if 'Authorization' not in req.headers_in.keys():
        return (None, None)
    pair = base64.b64decode(string.split(req.headers_in['Authorization'])[1])
    return string.split(pair,':')

##############################################################################
def _baseScript(req):
    # req object doesn't seem to have this!!
    # TODO make this more robust
    # http://www.modpython.org/pipermail/mod_python/2006-March/020501.html
    drlen = len(req.subprocess_env['DOCUMENT_ROOT'])
    if os.path.basename(__file__)[:6] == 'index.':
        return os.path.dirname(__file__)[drlen:]
    else:
        return __file__[drlen:-3]

##############################################################################
def EnumNamespaces(req, url):
    conn = _frontMatter(req, url, '')
    nsinsts = []
    try:
        for nsclass in ['CIM_Namespace', '__Namespace']:
            for interopns in ['root/cimv2', 'Interop', 'interop', 'root', 'root/interop']:
                try:
                    nsinsts = conn.EnumerateInstanceNames(nsclass, namespace = interopns)
                except pywbem._cim_http.AuthError as arg:
                    raise apache.SERVER_RETURN(apache.HTTP_UNAUTHORIZED)
                except pywbem.CIMError as arg:
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
    except pywbem.CIMError as arg:
        ht = _printHead('Error')
        details = _code2string(arg[0])
        ht+= '<i>'+details[0]+': '+details[1]+': '+cgi.escape(arg[1])+'</i>'
        return ht + '</body></html>'

    ht = _printHead('Namespaces','CIM Namespaces in '+url, req)
    if len(nsinsts) == 0:
        ht+= '<h1>Error</h1>'
        ht+= 'Unable to enumerate Namespaces.  Return to the '
        ht+= '<a href="'+_baseScript(req)+'">Login page</a> and specify a '
        ht+= 'Namespace.'
        if req.conn.last_reply is not None:
            ht+= '<pre>'+cgi.escape(req.conn.last_reply)+'</pre>'
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
        ht+= '<tr><td>'+_makeHref(req, 'EnumClassNames', urlargs, nsname)
        ht+= '</td><td>&nbsp;&nbsp;'
        if nsd and nsd[nsname] > 0:
            urlargs['instOnly'] = 'true'
            ht+= _makeHref(req, 'EnumClassNames', urlargs, 
                           '%s Instrumented Classes' % nsd[nsname])
        ht+= '</td></tr>' 
    ht+= '</table>'
    return ht + '</body></html>'

##############################################################################
def Login(req, scheme, host, port, ns):
    url = scheme + '://'+host
    if not ((scheme == 'https' and port == '5989') or (scheme == 'http' and port == '5988')):
        url += ':'+port
    if host[0] == '/':
        url = host
    if ns:
        return EnumClassNames(req, url, ns)
    return EnumNamespaces(req, url)



##############################################################################
def Logout(req):
    req.add_common_vars()
    req.content_type = "Text/HTML"
    req.headers_out["Cache-Control"] = 'no-cache="set-cookie"'
    # Enable the client to reauthenticate, possibly as a new user
    # See corresponding code in _getConn()
    cookie = 'yawn_logout=true;path='+_baseScript(req)
    req.headers_out["Set-Cookie"] = cookie
    refurl = _baseScript(req)
    ht = '<HTML>'
    ht+= '<META HTTP-EQUIV="Refresh" CONTENT="1;URL='+refurl+'">'
    ht+= '<HEAD><TITLE>Logging out...</TITLE> </HEAD>'
    ht+= '<BODY>Logging out...<br>'
    return ht + '</body></html>'


##############################################################################
def index(req):
    req.add_common_vars()
    req.content_type = "Text/HTML"
    ht = _printHead('Login')
    ht+= '<h1><font color=red><b>Y</b></font>et '
    ht+= '<font color=red><b>A</b></font>nother '
    ht+= '<font color=red><b>W</b></font>BEM '
    ht+= '<font color=red><b>N</b></font>avigator (YAWN)</h1>'
    ht+= '<h3><i>&quot;All CIM Browsers suck. &nbsp;This one sucks less&quot;</i></h3>'
    ht+= '<hr>'
    ht+= '<FORM ACTION="'+req.uri+'/Login" METHOD=GET>'
    ht+= '<table border=0>'
    ht+= '<tr><td>URI Scheme: </td>'
    ht+= '  <td><select name="scheme">'
    ht+= '  <option value="https">https'
    ht+= '  <option value="http">http'
    ht+= '</select></td></tr>'
    ht+= '<tr><td>Host: </td><td><INPUT TYPE=TEXT NAME="host" size="50"></td></tr>'
    ht+= '<tr><td>Port: </td><td><INPUT TYPE=TEXT NAME="port" VALUE="5989"></td></tr>'
    ht+= '<tr><td>Namespace: </td><td><INPUT TYPE=TEXT NAME="ns"></td></tr>'
    ht+= '<tr><td></td><td><INPUT TYPE=SUBMIT VALUE="Login"></td></tr>'
    ht+= '</table>'
    ht+= '</FORM>'
    ht+= '<hr><center>Powered by<br><img src="http://www.modpython.org/mod_python.gif"></center>'
    ht+= '</body></html>'
    return ht

##############################################################################
##############################################################################
##############################################################################

def PyProvider(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    klass = _ex(req, conn.GetClass, ClassName = className, LocalOnly=False, 
                IncludeClassOrigin=True, IncludeQualifiers=True)
    code, mof = codegen(klass)
    title = 'Python Provider for %s' % className
    ht = _printHead(title, req)
    ht+= '<font size=+1><b>%s</b></font>' % title
    ht+= '<table bgcolor="#f9f9f9" cellspacing=0 cellpadding=10 border=1>'
    ht+= '<tr><td><pre>'+cgi.escape(code)+'</pre>'
    ht+= '</td></tr></table>'
    ht+= '<font size=+1><b>Provider Registration MOF</b></font>'
    ht+= '<table bgcolor="#f9f9f9" cellspacing=0 cellpadding=10 border=1>'
    ht+= '<tr><td><pre>'+cgi.escape(mof)+'</pre>'
    ht+= '</td></tr></table>'
    return ht + '</body></html>'


def CMPIProvider(req, url, ns, className):
    conn = _frontMatter(req, url, ns)
    klass = _ex(req, conn.GetClass, ClassName = className, LocalOnly=False, 
                IncludeClassOrigin=True, IncludeQualifiers=True)
    code = cmpi_codegen(klass)
    title = 'CMPI Provider for %s' % className
    ht = _printHead(title, req)
    ht+= '<font size=+1><b>%s</b></font>' % title
    ht+= '<table bgcolor="#f9f9f9" cellspacing=0 cellpadding=10 border=1>'
    ht+= '<tr><td><pre>'+cgi.escape(code)+'</pre>'
    ht+= '</td></tr></table>'
    #ht+= '<font size=+1><b>Provider Registration MOF</b></font>'
    #ht+= '<table bgcolor="#f9f9f9" cellspacing=0 cellpadding=10 border=1>'
    #ht+= '<tr><td><pre>'+cgi.escape(mof)+'</pre>'
    #ht+= '</td></tr></table>'
    return ht + '</body></html>'

##############################################################################
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


