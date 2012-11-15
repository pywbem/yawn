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
import bisect
import pywbem
import pywbem.cim_http
import mako
import mako.lookup
import pkg_resources
from collections import defaultdict
from itertools import chain
from werkzeug.wrappers import Response, Request
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import (
        HTTPException, NotFound, Unauthorized, BadRequest)
from werkzeug.local import Local, release_local
try:
    from pywbem.cim_provider2 import codegen
except ImportError:
    codegen = None
from pywbem_yawn import cim_insight
from pywbem_yawn import inputparse
from pywbem_yawn import render
from pywbem_yawn import util
from pywbem_yawn.url_convert import (
        IdentifierConverter, Base64Converter, QLangConverter)

log = logging.getLogger(__name__)

AC_ASSOCIATORS, AC_ASSOCIATOR_NAMES, AC_REFERENCES, AC_REFERENCE_NAMES = \
        range(4)
assoc_calls = [ 'associators', 'associatornames'
              , 'references', 'referencenames' ]
assoc_call_labels = [ 'Associators', 'Associator Names'
                    , 'References', 'Reference Names' ]

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
        , 'base64' : Base64Converter
        , 'qlang'  : QLangConverter
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
                        util.base_script(self._local.request) + '/static')
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
        (user, pw) = util.get_user_pw(req)
        if user is None:
            user = ''
        if pw is None:
            pw = ''
        if (   len(user) > 0
           and req.cookies.has_key('yawn_logout')):
            if req.cookies['yawn_logout'] in ['true', 'pending']:
                self.response.set_cookie('yawn_logout', 'false',
                        path=util.base_script(req))
                user, pw = '', ''
        self._local.connection = pywbem.WBEMConnection(url, (user, pw))
        self._local.connection.default_namespace = ns
        self._local.connection.debug = True
        return self._local.connection

    def renderer(self, template, **kwargs):
        ks = {
                'urls' : self.urls,
                'static' : self.static_prefix,
                'conn'   : getattr(self._local, 'connection', None),
                'url'    : getattr(self._local, 'url', None),
                'ns'     : getattr(self._local, 'ns', None)
              }
        ks.update(kwargs)
        return render.Renderer(self._lookup, template,
                debug=self._debug, **ks)

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

        except Exception:
            # this is a fallback for any unhandled exception
            if not self._debug:
                output = traceback.format_exc()
                response = Response(output, content_type='text/plain')
                return response(environ, start_response)
            raise

        finally:
            release_local(self._local)

    def _createOrModifyInstance(self, className, path, **params):
        conn = self.conn
        with self.renderer('modify_instance.mako', className=className) as r:
            klass = conn.GetClass(ClassName=className,
                    LocalOnly=False, IncludeQualifiers=True)
            if path is not None:
                inst = conn.GetInstance(InstanceName=path, LocalOnly = False)
            else:
                inst = pywbem.CIMInstance(className)
                inst.path = pywbem.CIMInstanceName(
                        className, namespace=self._local.ns)

            for p in cim_insight.get_class_props(
                    klass, inst=inst, include_all=True):
                value = inputparse.formvalue2cimobject(
                        p, 'PropName.', params, True)
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
            r['instance'] = cim_insight.get_inst_info(inst, klass)
        return r.result

    def _enumInstrumentedClassNames(self):
        fetched_classes = []
        def get_class(cname):
            fetched_classes.append(cname)
            return conn.GetClass(ClassName=cname,
                       LocalOnly=True, PropertyList=[],
                       IncludeQualifiers=False, IncludeClassOrigin=False)
        conn = self.conn
        start_class = '.'
        with self.renderer('enum_instrumented_class_names.mako',
                mode='deep', className=start_class) as r:
            caps = conn.EnumerateInstances(
                            ClassName='PG_ProviderCapabilities',
                            namespace='root/PG_InterOp',
                            PropertyList=['Namespaces', 'ClassName'])
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
                            if (  klass.classname
                               not in deepDict[klass.superclass]):
                                deepDict[klass.superclass].append(
                                        klass.classname)
                            break
                        else:
                            deepDict[klass.superclass] = [klass.classname]
            r['classes'] = deepDict
        return r.result

    def on_index(self):
        resp = self.response
        resp.data = self.renderer('index.mako').result
        return resp

    @util.view()
    def on_AssociatedClasses(self, className):
        conn = self.conn
        classNames = None
        with self.renderer('associated_classes.mako',
                className=className) as r:
            cns = conn.References(ObjectName=className, IncludeQualifiers=True)
            cns.sort()

            hierarchy = []
            hierarchy = cim_insight.get_all_hierarchy(conn,
                    self._local.url, self._local.ns, className)
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
            r['associations'] = associations
        return r.result

    @util.view()
    def on_AssociatorNames(self, path):
        conn = self.conn
        with self.renderer('associator_names.mako',
                className=path.classname) as r:
            assocs = conn.AssociatorNames(ObjectName=path)
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
                    infos.append(cim_insight.get_inst_info(iname))
                instances.append((inst.classname, inst.namespace, infos))
            r['instances'] = instances
        return r.result

    @util.view()
    def on_CMPIProvider(self, className):
        conn = self.conn
        with self.renderer('cmpi_provider.mako', className=className) as r:
            conn.GetClass(ClassName = className, LocalOnly=False,
                        IncludeClassOrigin=True, IncludeQualifiers=True)
        return r.result

    @util.view(http_method=util.POST)
    def on_CreateInstance(self, className, **params):
        return self._createOrModifyInstance(className, None, **params)

    @util.view()
    def on_CreateInstancePrep(self, className):
        conn = self.conn
        with self.renderer('modify_instance_prep.mako',
                new=True, className=className) as r:
            klass = conn.GetClass(ClassName=className,
                    LocalOnly=False, IncludeQualifiers=True)
            r['items'] = sorted(
                [   cim_insight.get_class_item_details(className, prop)
                for prop in klass.properties.values()],
                util.cmp_params(klass))
        return r.result

    @util.view()
    def on_DeleteClass(self, className):
        conn = self.conn
        with self.renderer('delete_class.mako', className=className) as r:
            conn.DeleteClass(ClassName = className)
        return r.result

    @util.view()
    def on_DeleteInstance(self, path):
        conn = self.conn
        with self.renderer('delete_instance.mako',
                className=path.classname) as r:
            r['iname'] = cim_insight.get_inst_info(path)
            conn.DeleteInstance(path)
        return r.result

    @util.view()
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
                    path=util.base_script(req))
        elif (  'yawn_instOnly' in req.cookies
             and req.cookies['yawn_instOnly'] == 'true'):
            instOnly = True

        if instOnly:
            return self._enumInstrumentedClassNames()

        with self.renderer('enum_class_names.mako',
                className=className, mode=mode) as r:
            lineage = []
            if className is not None:
                lineage = [className]
                klass = conn.GetClass(ClassName=className)
                while klass.superclass is not None:
                    lineage.insert(0, klass.superclass)
                    klass = conn.GetClass(ClassName=klass.superclass)
            r['lineage'] = lineage

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
            r['classes'] = classes
        return r.result

    @util.view()
    def on_EnumInstanceNames(self, className):
        conn = self.conn
        with self.renderer('enum_instance_names.mako',
                className=className) as r:
            klass = conn.GetClass(className, namespace=self._local.ns,
                    LocalOnly=False, IncludeQualifiers=True)
            instNames = conn.EnumerateInstanceNames(ClassName=className)
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
                    infos.append(cim_insight.get_inst_info(iname, klass,
                        include_all=True))
                instances.append((cname, iname.namespace, infos))
            r['instances'] = instances
        return r.result

    @util.view()
    def on_EnumInstances(self, className):
        conn = self.conn
        with self.renderer('enum_instances.mako', className=className) as r:
            insts = conn.EnumerateInstances(
                    ClassName=className, LocalOnly=False)

            ccache = pywbem.NocaseDict()
            instances = []
            for inst in insts:
                i = {}
                try:
                    klass = ccache[inst.path.classname]
                except KeyError:
                    klass = conn.GetClass(inst.path.classname, LocalOnly=False)
                    ccache[inst.path.classname] = klass
                i = cim_insight.get_inst_info(inst, klass, include_all=True)
                instances.append(i)
                r['instances'] = instances
        return r.result

    @util.view(require_ns=False)
    def on_EnumNamespaces(self):
        conn = self.conn
        nsinsts = []
        with self.renderer('enum_namespaces.mako', namespaces=[]) as r:
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
                return r.result
            nslist = [inst['Name'].strip('/') for inst in nsinsts]
            if interopns not in nslist:
            # Pegasus didn't get the memo that namespaces aren't hierarchical
            # This will fall apart if there exists a namespace
            # <interopns>/<interopns>
            # Maybe we should check the Server: HTTP header instead.
                nslist = [interopns+'/'+subns for subns in nslist]
                nslist.append(interopns)
            nslist.sort()
            r['namespaces'] = nslist
            if 'root/PG_InterOp' in nslist:
                r['nsd'] = dict([(x, 0) for x in nslist])
                caps = conn.EnumerateInstances('PG_ProviderCapabilities',
                        namespace='root/PG_InterOp',
                        PropertyList=['Namespaces'])
                for cap in caps:
                    for _ns in cap['Namespaces']:
                        try:
                            r['nsd'][_ns] += 1
                        except KeyError:
                            pass
            else:
                r['nsd'] = {}
        return r.result

    @util.view(http_method=util.GET_AND_POST)
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
        with self.renderer('filetered_reference_names.mako',
                className        = path.classname,
                assoc_call       = assoc_calls[assocCall],
                assoc_call_label = assoc_call_labels[assocCall],
                assoc_class      = assocClass,
                result_class     = resultClass,
                role             = role,
                result_role      = resultRole,
                properties       = properties) as r:
            objs = getattr(conn, funcs[assocCall])(ObjectName=path, **params)

            for o in objs:
                if assocCall in (AC_ASSOCIATORS, AC_REFERENCES):
                    # o is CIMInstance
                    klass = conn.GetClass(
                            ClassName=o.path.classname,
                            namespace=o.path.namespace,
                            LocalOnly=False, IncludeQualifiers=True)
                    results.append(cim_insight.get_inst_info(o, klass))
                else:
                    results.append(cim_insight.get_inst_info(o))
            r['results'] = results
        return r.result

    @util.view()
    def on_FilteredReferenceNamesDialog(self, path):
        return self.renderer('filtered_reference_names_dialog.mako',
                path       = path,
                className  = path.classname,
                iname      = cim_insight.get_inst_info(path)).result

    @util.view()
    def on_GetClass(self, className):
        conn = self.conn
        with self.renderer('get_class.mako', className=className) as r:
            klass = conn.GetClass(ClassName=className, LocalOnly=False,
                    IncludeClassOrigin=True, IncludeQualifiers=True)
            r['super_class'] = klass.superclass
            r['aggregation'] = klass.qualifiers.has_key('aggregation')
            r['association'] = klass.qualifiers.has_key('association')
            if klass.qualifiers.has_key('description'):
                r['description'] = klass.qualifiers['description'].value
            else:
                r['description'] = None
            if klass.qualifiers:
                r['qualifiers'] = [ (q.name, render.val2str(q.value))
                        for q in klass.qualifiers.values()
                        if  q.name.lower() != 'description']
            else:
                r['qualifiers'] = []

            items =  []
            for item in chain( klass.methods.values()
                             , klass.properties.values()):
                items.append(cim_insight.get_class_item_details(
                    className, item))
            r['items'] = sorted(items, util.cmp_params(klass))
        return r.result

    @util.view(http_method=util.GET_AND_POST)
    def on_GetInstance(self, className=None, path=None, **params):
        if className is None and path is None:
            raise ValueError("either className or path must be given")
        if className is None:
            className = path.classname
        conn = self.conn
        with self.renderer('get_instance.mako', className=className) as r:
            klass = conn.GetClass(ClassName=className,
                    LocalOnly=False, IncludeQualifiers=True)
            if path is None:
                # Remove 'PropName.' prefix from param names.
                params = dict([(x[9:],y) for (x, y) in params.items()
                                         if x.startswith('PropName.')])
                path = pywbem.CIMInstanceName(className,
                        keybindings=params, namespace=self._local.ns)

            inst = conn.GetInstance(InstanceName=path, LocalOnly = False)
            r['instance'] = cim_insight.get_inst_info(inst, klass)
        return r.result

    @util.view()
    def on_GetInstD(self, className):
        conn = self.conn
        with self.renderer('get_instance_dialog.mako',
                className=className) as r:
            klass = conn.GetClass(ClassName=className, LocalOnly=False,
                    IncludeQualifiers=True)

            items = [   cim_insight.get_class_item_details(className, i)
                for i in sorted( klass.properties.values()
                               , key=lambda a: a.name)
                if  i.qualifiers.has_key('key') ]
            r['items'] = items
        return r.result

    @util.view(http_method=util.POST)
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

        with self.renderer('invoke_method.mako',
                className=className, method_name=method) as r:
            klass = conn.GetClass(ClassName = className, LocalOnly=False)
            cimmethod = klass.methods[method]

            in_values  = defaultdict(str)
            out_values = defaultdict(str)

            in_params = {}

            tmpl_in_params, tmpl_out_params = cim_insight.get_method_params(
                    className, cimmethod)

            for p in tmpl_in_params:
                value = inputparse.formvalue2cimobject(p, 'MethParam.', params)
                p['value'] = render.val2str(value)
                if value is not None:
                    in_params[p['name']] = value
            r['in_params'] = tmpl_in_params

            (rval, out_params) = conn.InvokeMethod(
                    MethodName = method,
                    ObjectName = className if path is None else path,
                    **in_params)
            out_values = {}
            if out_params:
                for p in tmpl_out_params:
                    value = out_params[p['name']]
                    if isinstance(p['type'], dict):
                        p['value'] = value
                    else:
                        p['value'] = render.val2str(value)
            r['out_params'] = tmpl_out_params

            r['iname'] = None
            if path is not None:
                r['iname'] = cim_insight.get_inst_info(path, klass)

            out = cim_insight.get_class_item_details(
                    className, cimmethod, path)
            out['value_orig'] = rval
            if (   cimmethod.qualifiers.has_key('values')
               and cimmethod.qualifiers.has_key('valuemap')):
                out['value'] = render.mapped_value2str(
                        rval, cimmethod.qualifiers)
            elif isinstance(out['type'], dict):
                out['value'] = rval
            else:
                out['value'] = render.val2str(rval)
            r['return_value'] = out

        return r.result

    @util.view(http_method=util.POST, require_url=False, require_ns=False,
            returns_response=True)
    def on_Login(self, **kwargs):
        try:
            scheme, host, port = [kwargs[k] for k in (
                "scheme", "host", "port")]
        except KeyError:
            raise BadRequest(
                    "missing one of ['scheme', 'host', 'port'] arguments")
        ns = kwargs.get('ns', getattr(self._local, 'ns', None))
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

    @util.view(require_url=False, require_ns=False)
    def on_Logout(self):
        # Enable the client to reauthenticate, possibly as a new user
        self.response.set_cookie('yawn_logout', "true",
                path=util.base_script(self._local.request))
        return self.renderer('logout.mako').result

    @util.view(http_method=util.POST)
    def on_ModifyInstance(self, path, **params):
        return self._createOrModifyInstance(path.classname, path, **params)

    @util.view(http_method=util.GET_AND_POST)
    def on_ModifyInstPrep(self, path):
        conn = self.conn
        with self.renderer('modify_instance_prep.mako',
                new=False, className=path.classname) as r:
            klass = conn.GetClass(ClassName=path.classname,
                    LocalOnly=False, IncludeQualifiers=True)
            inst  = conn.GetInstance(InstanceName=path,
                    LocalOnly=False, IncludeQualifiers=True)
            r['instance'] = cim_insight.get_inst_info(inst, klass)
        return r.result

    @util.view(require_url=False, require_ns=False)
    def on_Pickle(self, path):
        return self.renderer('pickle.mako',
                className      = path.classname,
                str_obj        = str(path),
                compressed_obj = render.encode_reference(path),
                xml_obj        = path.tocimxml().toprettyxml()).result

    @util.view()
    def on_PrepMethod(self, method, path=None, className=None):
        if path is None and className is None:
            raise ValueError("either object path or className argument must"
                    " be given")
        if className is None:
            className = path.classname
        conn = self.conn
        with self.renderer('prep_method.mako',
                className=className, method_name=method) as r:
            klass = conn.GetClass(ClassName = className, LocalOnly=False,
                    IncludeQualifiers=True)

            cimmethod = klass.methods[method]
            r['in_params'], r['out_params'] = cim_insight.get_method_params(
                    className, cimmethod)
            r['iname'] = None
            if path is not None:
                r['iname'] = cim_insight.get_inst_info(path, klass,
                        include_all=True)
            r['return_type'] = cimmethod.return_type
        return r.result

    @util.view()
    def on_PyProvider(self, className):
        conn = self.conn
        with self.renderer('py_provider.mako', className=className) as r:
            klass = conn.GetClass(ClassName = className, LocalOnly=False,
                        IncludeClassOrigin=True, IncludeQualifiers=True)
            r['code'], r['mof'] = codegen(klass)
        return r.result

    @util.view(http_method=util.POST)
    def on_Query(self, query=None, lang=QLangConverter.QLANG_WQL):
        conn = self.conn
        if query is None:
            if "query" not in self._local.request.form:
                raise ValueError("missing query string argument")
            query = request.form["query"]
        if isinstance(lang, int):
            lang = QLangConverter.query_languages[QLangConverter.QLANG_WQL]
        elif isinstance(lang, basestring):
            if not lang in QLangConverter.query_languages:
                raise ValueError("lang must be one of: {}".format(
                    QLangConverter.query_languages))
        else:
            raise TypeError("lang must be either string or integer not: {}".
                    format(lang.__class__.__name__))

        with self.renderer('query.mako', qlang=lang, query=query) as r:
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
                results.append(cim_insight.get_inst_info(inst, klass,
                    include_all=True))
            r['results'] = results
        return r.result

    @util.view()
    def on_QueryD(self, className=''):
        return self.renderer('query_dialog.mako', className=className).result

    @util.view()
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
        conn = self.conn
        with self.renderer('reference_names.mako',
                iname=cim_insight.get_inst_info(path)) as r:
            # TODO remove this namespace hack when pywbem is fixed
            oldns = path.namespace
            path.namespace = None
            refs = conn.ReferenceNames(ObjectName=path)
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
            r['associations'] = sorted(refdict.keys())

            refmap = {}
            for assoc, roles in sorted(refdict.items(), key=lambda i: i[0]):
                rols = refmap[assoc] = []
                for role, refs in sorted(roles.items(), key=lambda i: i[0]):
                    if not refs: continue
                    rs = []
                    for cls, ref_paths in sorted(
                            refs.items(), key=lambda i: i[0]):
                        rfs = [   cim_insight.get_inst_info(p)
                              for p in sorted(ref_paths) ]
                        rs.append((cls, p.namespace, rfs))
                    rols.append((role, rs))
            r['refmap'] = refmap

        return r.result

