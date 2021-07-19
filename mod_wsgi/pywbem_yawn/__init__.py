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

"""
Module defining wsgi YAWN application, that provides access to
CIM brokers with pywbem --- using WBEM CIM-XML protocol.
"""

import bisect
import inspect
import logging
import pywbem
import pywbem._cim_http
import mako
import mako.lookup
import pkg_resources
import traceback
import functools
from collections import defaultdict, namedtuple
from itertools import chain
from werkzeug.wrappers import Response, Request
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import (
        HTTPException, NotFound, Unauthorized, BadRequest)
from werkzeug.local import Local, release_local
try:
    from pywbem.cim_provider2 import codegen
except ImportError:
    codegen = None  #pylint: disable=C0103
from pywbem_yawn import cim_insight
from pywbem_yawn import inputparse
from pywbem_yawn import render
from pywbem_yawn import util
from pywbem_yawn import views
from pywbem_yawn.url_convert import (
        IdentifierConverter, Base64Converter, QLangConverter)

_LOG = logging.getLogger(__name__)

AC_ASSOCIATORS, AC_ASSOCIATOR_NAMES, AC_REFERENCES, AC_REFERENCE_NAMES = \
        range(4)
ASSOC_CALLS = [ 'associators', 'associatornames'
              , 'references', 'referencenames' ]
ASSOC_CALL_LABELS = [ 'Associators', 'Associator Names'
                    , 'References', 'Reference Names' ]

URL_MAP = Map([
    Rule('/', endpoint='index'),
    Rule('/json_get_class_list', endpoint="json_get_class_list",
        methods=["GET"]),
    Rule('/json_get_class_keys/<id:className>',
        endpoint="json_get_class_keys", methods=["GET"]),
    Rule('/json_query_instances',
        endpoint="json_query_instances", methods=["GET"]),
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
    """
    WSGI application providing access to CIMOMs.
    YAWN means Yet Another WBEM Navigator. WBEM is a protocol is XML based
    protocol for communication between CIMOM broker and clients.
    
    It's supposed to run either under lightweight daemon using for
    example workzeug's run_simple function, or under apache. For the
    latter a SharedDateMiddleware class from workzeug's wsgi module can be
    used.

    Methods beginning with 'on_' are views, which are called with parameters
    parsed from HTTP methods GET and POST, and that return xhtml rendered
    pages as text in return.

    Views typically gather data from CIMOM broker based on client's request
    and then render html page with use of maco template system.
    For this pupose a renderer function is called to obtain context manager
    handling the rendering.
    """

    def __init__(self,
            templates     = None,
            modules       = None,
            static_prefix = None,
            debug         = False):

        if templates is None:
            templates = pkg_resources.resource_filename(__name__, 'templates')
            _LOG.debug('templates directory: {}'.format(templates))
        self._lookup = mako.lookup.TemplateLookup(
                directories      = templates,
                module_directory = modules
        )
        self._static_prefix = static_prefix
        self._debug = debug
        self._local = Local()

    @property
    def response(self):
        """
        Cached property.
        @return Response object, that is created with the first invocation of
        this property.
        """
        try:
            return self._local.response
        except AttributeError:
            resp = Response(content_type="text/html")
            try:
                url = self._local.url
                resp.headers['WWW-Authenticate'] = (
                        ', '.join([ 'Basic realm="CIMOM at %s"'%url
                                  , 'qop="auth,auth-int"']))
            except AttributeError:
                pass
            self._local.response = resp
            return resp

    @property
    def static_prefix(self):
        """
        Cached property.
        @return url prefix to use for static files
        """
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
        """
        Cached property.
        @return url map binded to current request environment. It's created
        with the first invocation.
        """
        try:
            return self._local.urls
        except AttributeError:
            self._local.urls = URL_MAP.bind_to_environ(
                    self._local.request.environ)
            return self._local.urls

    @property
    def conn(self):
        """
        Cached property.
        It obtaines authentication data from request headers and passes
        them to connection object. But they are not checked. Only after
        ther first call to any method of this object, it will be known,
        whether all informations are correct.
        @return wbem connection object created upon first invocation.
        """
        url = self._local.url
        namespace  = self._local.namespace
        verify = getattr(self._local, 'verify', True)
        if (   hasattr(self._local, 'connection')
           and self._local.connection.url == url
           and self._local.connection.default_namespace == namespace
           and self._local.connection.no_verification == (not verify)):
            return self._local.connection

        req = self._local.request
        (user, password) = util.get_user_pw(req)
        if user is None:
            user = ''
        if password is None:
            password = ''
        if (   len(user) > 0
           and 'yawn_logout' in req.cookies):
            if req.cookies['yawn_logout'] in ['true', 'pending']:
                self.response.set_cookie('yawn_logout', 'false',
                        path=util.base_script(req))
                user, password = '', ''
        kwargs = {}
        argspec = inspect.getargspec(pywbem.WBEMConnection.__init__)
        if 'no_verification' in argspec.args:
            # check first, whether pywbem is new enough
            kwargs['no_verification'] = not verify
        self._local.connection = pywbem.WBEMConnection(
                url, (user, password), **kwargs)
        self._local.connection.default_namespace = namespace
        self._local.connection.debug = True
        return self._local.connection

    def renderer(self, template, **kwargs):
        """
        Every view rendering html page should use object returned by
        this method to render it. Renderer is passed some arguments,
        that are already known and any other passed in kwargs by caller.
        @return Renderer context manager object.
        @see Renderer
        """
        url = getattr(self._local, 'url', None)
        if url and isinstance(url, bytes):
            url = url.decode()
        render_kwargs = {
                'urls'   : self.urls,
                'static' : self.static_prefix,
                'conn'   : getattr(self._local, 'connection', None),
                'url'    : url,
                'ns'     : getattr(self._local, 'namespace', None),
              }
        if      (   render_kwargs['url']
                and render_kwargs['url'].startswith('https://')
                and getattr(self._local, 'verify', True)):
            render_kwargs['verify'] = '1'
        else:
            render_kwargs['verify'] = '0'
        render_kwargs.update(kwargs)
        return render.Renderer(self._lookup, template,
                debug=self._debug, **render_kwargs)

    def dispatch_request(self, request):
        """
        Calls local handler beginning with 'on_' corresponding to request's
        url.
        @return Response object with html rendered page.
        """
        self._local.request = request
        try:
            endpoint, values = self.urls.match()
            return getattr(self, 'on_' + endpoint)(**values)
        except HTTPException as exc:
            return exc

    def wsgi_app(self, environ, start_response):
        """
        Wraps above dispatch_request method in a way, that it prepares
        Request object, and binds returned response to environment.
        """
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        """
        This method should be called to handle any request from client.
        It directs arguments to wsgi_app and handles any exception, that
        might occur. In case of AuthError returned by broker, it returns
        unauthorized response object.

        Finally it releases any allocated data during request handling.
        @return Response object.
        """
        try:
            return self.wsgi_app(environ, start_response)
        except pywbem._cim_http.AuthError:
            response = self.response
            unresp = Unauthorized().get_response(environ)
            response.status_code = unresp.status_code
            response.data = unresp.data
            return response(environ, start_response)

        except Exception as exc:
            _LOG.debug("In __call__: Exception:" + str(exc))
            # this is a fallback for any unhandled exception
            if not self._debug:
                output = traceback.format_exc()
                response = Response(output, content_type='text/plain')
                return response(environ, start_response)
            raise

        finally:
            release_local(self._local)

    def _create_or_modify_instance(self, class_name, path, **params):
        """
        Main function called either to create or modify instance.
        If path is None, new instance will be created.
        @param params is a dictionary of attributes to set.
        """
        conn = self.conn
        with self.renderer('modify_instance.mako', className=class_name) \
                as renderer:
            klass = conn.GetClass(ClassName=class_name,
                    LocalOnly=False, IncludeQualifiers=True)
            if path is not None:
                inst = conn.GetInstance(InstanceName=path, LocalOnly = False)
            else:
                inst = pywbem.CIMInstance(class_name)
                inst.path = pywbem.CIMInstanceName(
                        class_name, namespace=self._local.namespace)

            for prop in cim_insight.get_class_props(
                    klass, inst=inst, include_all=True):
                if path is not None and prop['is_key']:
                    # do not allow key modification of existing instance
                    continue
                value = inputparse.formvalue2cimobject(
                        prop, 'propname.', pywbem.NocaseDict(params), True,
                        namespace=self._local.namespace)
                if prop['is_key']:
                    inst.path[prop['name']] = value
                if (  value is None
                   or (isinstance(value, list) and len(value) == 0)):
                    inst.update_existing([(prop['name'], None)])
                else:
                    inst[prop['name']] = value
            _LOG.debug("not handled formvalues: {}".format(params))
            if path:
                if path.namespace is None:
                    path.namespace = self._local.namespace
                inst.path = path
                conn.ModifyInstance(ModifiedInstance=inst)
            else:
                path = conn.CreateInstance(NewInstance=inst)
            inst = conn.GetInstance(InstanceName=path, LocalOnly = False)
            renderer['instance'] = cim_insight.get_inst_info(inst, klass)
        return renderer.result

    def _enum_instrumented_class_names(self):
        """
        Enumerates only those class names, that are instrumented (there
        is a provider under broker implementing its interface.
        """
        fetched_classes = []
        def get_class(cname):
            """Obtain class from broker and store it in cache."""
            fetched_classes.append(cname)
            return conn.GetClass(ClassName=cname,
                       LocalOnly=True, PropertyList=[],
                       IncludeQualifiers=False, IncludeClassOrigin=False)
        conn = self.conn
        start_class = '.'
        with self.renderer('enum_instrumented_class_names.mako',
                mode='deep', className=start_class) as renderer:
            caps = None
            last_error = AssertionError("No interop namespace found")
            for interopns in ('root/PG_InterOp', 'root/interop'):
                try:
                    caps = conn.EnumerateInstances(
                                    ClassName='PG_ProviderCapabilities',
                                    namespace=interopns,
                                    PropertyList=['Namespaces', 'ClassName'])
                    break
                except pywbem.CIMError as err:
                    if err.args[0] != pywbem.CIM_ERR_INVALID_NAMESPACE:
                        raise
                    last_error = err
            else:
                raise last_error
            deep_dict = {start_class:[]}
            for cap in caps:
                if self._local.namespace not in cap['Namespaces']:
                    continue
                if cap['ClassName'] in fetched_classes:
                    continue
                klass = get_class(cap['ClassName'])
                if klass.superclass is None:
                    deep_dict[start_class].append(klass.classname)
                else:
                    try:
                        deep_dict[klass.superclass].append(klass.classname)
                    except KeyError:
                        deep_dict[klass.superclass] = [klass.classname]
                    while klass.superclass is not None:
                        if klass.superclass in fetched_classes:
                            break
                        klass = get_class(klass.superclass)
                        if klass.superclass is None and \
                                klass.superclass not in deep_dict[start_class]:
                            deep_dict[start_class].append(klass.classname)
                        elif klass.superclass in deep_dict:
                            if (  klass.classname
                               not in deep_dict[klass.superclass]):
                                deep_dict[klass.superclass].append(
                                        klass.classname)
                            break
                        else:
                            deep_dict[klass.superclass] = [klass.classname]
            renderer['classes'] = deep_dict
        return renderer.result

    def _enum_namespaces(self):
        """
        Different brokers have different CIM classes, that can be used to
        enumerate namespaces. And those may be nested under miscellaneous
        namespaces. This method tries all known combinations and returnes
        first non-empy list of namespace instance names.
        @return (interopns, nsclass, nsinsts)
        where
            interopns is a instance name of namespace holding namespace CIM
                class
            nsclass is a name of class used to enumerate namespaces
            nsinsts is a list of all instance names of nsclass
        """
        conn = self.conn
        nsclasses =  ['CIM_Namespace', '__Namespace']
        namespaces = [ 'root/cimv2', 'Interop', 'interop', 'root'
                     , 'root/interop']
        interopns = None
        nsclass = None
        nsinsts = []
        for icls in range(len(nsclasses)):
            for ins in range(len(namespaces)):
                try:
                    nsinsts = conn.EnumerateInstanceNames(
                            nsclasses[icls],
                            namespace=namespaces[ins])
                    interopns = namespaces[ins]
                    nsclass = nsclasses[icls]
                except pywbem.CIMError as arg:
                    if arg[0] in [pywbem.CIM_ERR_INVALID_NAMESPACE,
                                  pywbem.CIM_ERR_NOT_SUPPORTED,
                                  pywbem.CIM_ERR_INVALID_CLASS]:
                        continue
                    else:
                        raise
                if len(nsinsts) > 0:
                    break
        return (interopns, nsclass, nsinsts)

    def on_index(self):
        """
        View with login form.
        """
        resp = self.response
        resp.data = self.renderer('index.mako').result
        return resp

    @views.html_view()
    def on_AssociatedClasses(self, className):      #pylint: disable=C0103
        """
        View rendering associated classes of className.
        """
        conn = self.conn
        with self.renderer('associated_classes.mako', className=className) \
                as renderer:
            class_names = conn.References(
                    ObjectName=className,
                    IncludeQualifiers=True)

            hierarchy = cim_insight.get_all_hierarchy(conn, className)
            last_assoc_class = ''
            associations = []
            for klass in [cn[1] for cn in sorted(class_names)]:
                asc = defaultdict(str, assoc_class=klass.classname)

                # to find the result_class, I have to iterate the properties
                # to a REF that is not className
                for propname in klass.properties.keys():
                    prop = klass.properties[propname]
                    if prop.reference_class is None:
                        continue
                    refcls = prop.reference_class
                    description = ''
                    if 'description' in prop.qualifiers:
                        description = prop.qualifiers['description'].value

                    if refcls in hierarchy:
                        if asc['assoc_class'] == last_assoc_class:
                            if asc['result_class'] == '':
                                asc['result_class'] = refcls
                                asc['result_role'] = propname
                                asc['result_role_description'] = description
                            else:
                                asc['role'] = propname
                                asc['role_description'] = description
                        else:
                            if asc['role'] == '' and refcls in hierarchy:
                                asc['role'] = propname
                                asc['role_description'] = description
                            else:
                                asc['result_class'] = refcls
                                asc['result_role'] = propname
                                asc['result_role_description'] = description
                    else:
                        if asc['result_class'] == '':
                            asc['result_class'] = refcls
                            asc['result_role'] = propname
                            asc['result_role_description'] = description
                associations.append(tuple([asc[attr] for attr in (
                    "result_class", "assoc_class", "role", "role_description",
                    "result_role", "result_role_description")]))
                last_assoc_class = asc['assoc_class']
            renderer['associations'] = associations
        return renderer.result

    @views.html_view()
    def on_AssociatorNames(self, path):             #pylint: disable=C0103
        """
        View rendering associated instance names of path.
        """
        conn = self.conn
        with self.renderer('associator_names.mako', className=path.classname) \
                as renderer:
            assocs = conn.AssociatorNames(ObjectName=path)
            grouped_assocs = defaultdict(list)
            for assoc in assocs:
                grouped_assocs[assoc.classname].append(assoc)
            # [(class_name, namespace, [iname1, iname2, ...]]
            instances = []
            for setkey in sorted(grouped_assocs.keys()):
                insts = grouped_assocs[setkey]
                if len(insts) < 1:
                    continue
                infos = []
                for iname in insts:
                    infos.append(cim_insight.get_inst_info(iname))
                instances.append((insts[0].classname,
                    insts[0].namespace, infos))
            renderer['instances'] = instances
        return renderer.result

    @views.html_view()
    def on_CMPIProvider(self, className):           #pylint: disable=C0103
        """
        View rendering cmpi provider skeleton in C for class.
        """
        conn = self.conn
        with self.renderer('cmpi_provider.mako', className=className) \
                as renderer:
            conn.GetClass(
                    ClassName=className,
                    LocalOnly=False,
                    IncludeClassOrigin=True,
                    IncludeQualifiers=True)
        return renderer.result

    @views.html_view(http_method=views.POST)
    def on_CreateInstance(self, className, **params):   #pylint: disable=C0103
        """
        View rendering newly created instance of class with provided params.
        """
        return self._create_or_modify_instance(className, None, **params)

    @views.html_view()
    def on_CreateInstancePrep(self, className):     #pylint: disable=C0103
        """
        View rendering form for creating the new instance of class.
        """
        conn = self.conn
        with self.renderer('modify_instance_prep.mako',
                new=True, className=className) as renderer:
            klass = conn.GetClass(ClassName=className,
                    LocalOnly=False, IncludeQualifiers=True)
            renderer['items'] = sorted(
                [   cim_insight.get_class_item_details(className, prop)
                for prop in klass.properties.values()],
                util.cmp_params(klass))
        return renderer.result

    @views.html_view()
    def on_DeleteClass(self, className):            #pylint: disable=C0103
        """
        View for removal of class.
        """
        conn = self.conn
        with self.renderer('delete_class.mako', className=className) \
                as renderer:
            conn.DeleteClass(ClassName = className)
        return renderer.result

    @views.html_view()
    def on_DeleteInstance(self, path):              #pylint: disable=C0103
        """
        View for removal of instance.
        """
        conn = self.conn
        with self.renderer('delete_instance.mako', className=path.classname) \
                as renderer:
            renderer['iname'] = cim_insight.get_inst_info(path)
            conn.DeleteInstance(path)
        return renderer.result

    @views.html_view()
    def on_EnumClassNames(self,                     #pylint: disable=C0103
            className=None,
            mode=None,
            instOnly=None):
        """
        View for enumerating class names.
        @param mode can be one of { 'deep', 'flat' }
        @param instOnly is a boolean saying, whether to show instrumented
        class names only
        """
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
            return self._enum_instrumented_class_names()

        with self.renderer('enum_class_names.mako',
                className=className, mode=mode) as renderer:
            lineage = []
            if className is not None:
                lineage = [className]
                klass = conn.GetClass(ClassName=className)
                while klass.superclass is not None:
                    lineage.insert(0, klass.superclass)
                    klass = conn.GetClass(ClassName=klass.superclass)
            renderer['lineage'] = lineage

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
            renderer['classes'] = classes
        return renderer.result

    @views.html_view()
    def on_EnumInstanceNames(self, className):      #pylint: disable=C0103
        """
        View enumerating instance names of class.
        """
        conn = self.conn
        with self.renderer('enum_instance_names.mako',
                className=className) as renderer:
            klass = conn.GetClass(className,
                    namespace=self._local.namespace,
                    LocalOnly=False,
                    IncludeQualifiers=True)
            inst_names = conn.EnumerateInstanceNames(ClassName=className)
            iname_dict = pywbem.NocaseDict()
            for iname in inst_names:
                if iname.classname not in iname_dict:
                    iname_dict[iname.classname] = [iname]
                else:
                    iname_dict[iname.classname].append(iname)

            instances = []
            for cname, inames in sorted(iname_dict.items(),
                    key=lambda k: k[0]):
                infos = []
                for iname in inames:
                    infos.append(cim_insight.get_inst_info(iname, klass,
                        include_all=True, keys_only=True))
                instances.append((cname, iname.namespace, infos))
            renderer['instances'] = instances
        return renderer.result

    @views.html_view()
    def on_EnumInstances(self, className):          #pylint: disable=C0103
        """
        View enumerating instances of class.
        """
        conn = self.conn
        with self.renderer('enum_instances.mako', className=className) \
                as renderer:
            insts = conn.EnumerateInstances(
                    ClassName=className,
                    LocalOnly=False)

            ccache = pywbem.NocaseDict()
            instances = []
            for inst in insts:
                try:
                    klass = ccache[inst.path.classname]
                except KeyError:
                    klass = conn.GetClass(inst.path.classname, LocalOnly=False)
                    ccache[inst.path.classname] = klass
                instances.append(cim_insight.get_inst_info(
                    inst, klass, include_all=True))
            renderer['instances'] = instances
        return renderer.result

    @views.html_view(require_namespace=False)
    def on_EnumNamespaces(self):                    #pylint: disable=C0103
        """
        View enumerating namespaces.
        They are obtained by enumerating instace names of CIM_Namespace class
        or similar -- depending on which is available on broker.
        """
        conn = self.conn
        with self.renderer('enum_namespaces.mako', namespaces=[]) as renderer:
            interopns, _, nsinsts = self._enum_namespaces()
            if len(nsinsts) == 0:
                return renderer.result

            nslist = [inst['Name'].strip('/') for inst in nsinsts]
            if interopns not in nslist:
                # Pegasus didn't get the memo that namespaces aren't
                # hierarchical
                # This will fall apart if there exists a namespace
                # <interopns>/<interopns>
                # Maybe we should check the Server: HTTP header instead.
                nslist = [interopns+'/'+subns for subns in nslist]
                nslist.append(interopns)
            nslist.sort()
            renderer['namespaces'] = nslist
            if 'root/PG_InterOp' in nslist or 'root/interop' in nslist:
                renderer['nsd'] = dict([(x, 0) for x in nslist])
                caps = conn.EnumerateInstances('PG_ProviderCapabilities',
                        namespace='root/PG_InterOp'
                            if 'root/PG_InterOp' in nslist else 'root/interop',
                        PropertyList=['Namespaces'])
                for cap in caps:
                    for _ns in cap['Namespaces']:
                        try:
                            renderer['nsd'][_ns] += 1
                        except KeyError:
                            pass
            else:
                renderer['nsd'] = {}
        return renderer.result

    @views.html_view(http_method=views.GET_AND_POST)
    def on_FilteredReferenceNames(self, path,       #pylint: disable=C0103
            assocCall=None,
            assocClass="",
            resultClass="",
            role="",
            resultRole="",
            properties=""):
        """
        View rendering instance names of classes referencing path.
        @param assocCall is one of ASSOC_CALLS; this determines, what
        operation will be invoked
        """
        conn = self.conn
        if assocCall is None:
            raise BadRequest('missing "assocCall" argument')
        if assocCall.lower() not in ASSOC_CALLS:
            raise BadRequest('assocCall must be one of: [%s]'%
                    ', '.join(ASSOC_CALLS))
        assocCall = ASSOC_CALLS.index(assocCall.lower())

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

        results = defaultdict(list)
        funcs = { AC_ASSOCIATORS      : 'Associators'
                , AC_ASSOCIATOR_NAMES : 'AssociatorNames'
                , AC_REFERENCES       : 'References'
                , AC_REFERENCE_NAMES  : 'ReferenceNames' }
        classes = {}
        with self.renderer('filtered_reference_names.mako',
                className        = path.classname,
                assoc_call       = ASSOC_CALLS[assocCall],
                assoc_call_label = ASSOC_CALL_LABELS[assocCall],
                assoc_class      = assocClass,
                result_class     = resultClass,
                role             = role,
                result_role      = resultRole,
                properties       = properties) as renderer:
            objs = getattr(conn, funcs[assocCall])(ObjectName=path, **params)

            for i in objs:
                path = i if isinstance(i, pywbem.CIMInstanceName) else i.path
                if not path.classname in classes:
                    classes[path.classname] = conn.GetClass(
                            ClassName=path.classname,
                            namespace=path.namespace,
                            LocalOnly=False, IncludeQualifiers=True)
                klass = classes[path.classname]
                keys_only = not assocCall in (AC_ASSOCIATORS, AC_REFERENCES)
                results[path.classname].append(
                    cim_insight.get_inst_info(i, klass,
                        include_all=True, keys_only=keys_only))
            renderer['results'] = [(k, results[k]) for k in sorted(results)]
        return renderer.result

    @views.html_view()
    def on_FilteredReferenceNamesDialog(self, path):    #pylint: disable=C0103
        """
        View rendering form for filtering objects referencing path.
        """
        return self.renderer('filtered_reference_names_dialog.mako',
                path       = path,
                className  = path.classname,
                iname      = cim_insight.get_inst_info(path)).result

    @views.html_view()
    def on_GetClass(self, className):               #pylint: disable=C0103
        """
        View rendering class details.
        """
        conn = self.conn
        with self.renderer('get_class.mako', className=className) as renderer:
            klass = conn.GetClass(
                    ClassName=className,
                    LocalOnly=False,
                    IncludeClassOrigin=True,
                    IncludeQualifiers=True)
            renderer['super_class'] = klass.superclass
            renderer['aggregation'] = 'aggregation' in klass.qualifiers
            renderer['association'] = 'association' in klass.qualifiers
            if 'description' in klass.qualifiers:
                renderer['description'] = klass.qualifiers['description'].value
            else:
                renderer['description'] = None
            if klass.qualifiers:
                renderer['qualifiers'] = [ (q.name, render.val2str(q.value))
                        for q in klass.qualifiers.values()
                        if  q.name.lower() != 'description']
            else:
                renderer['qualifiers'] = []

            items =  []
            for item in chain( klass.methods.values()
                             , klass.properties.values()):
                items.append(cim_insight.get_class_item_details(
                    className, item))
            # This is simply ported from Python 2, but can be faster by rewriting the key function.
            renderer['items'] = sorted(items, key=functools.cmp_to_key(util.cmp_params(klass)))

        return renderer.result

    @views.html_view(http_method=views.GET_AND_POST)
    def on_GetInstance(self,                        #pylint: disable=C0103
            className=None,
            path=None,
            **params):
        """
        View rendering instance details.
        All instance property values should be prefixed with "propname.".
        """
        if className is None and path is None:
            raise ValueError("either className or path must be given")
        if className is None:
            className = path.classname
        conn = self.conn
        with self.renderer('get_instance.mako', className=className) \
                as renderer:
            klass = conn.GetClass(ClassName=className,
                    LocalOnly=False, IncludeQualifiers=True)
            if path is None:
                in_params = {}

                _LOG.error('params: {}'.format(params))
                classes = {className : klass}
                for prop in cim_insight.get_class_props(klass, keys_only=True):
                    if isinstance(prop["type"], dict):
                        if not prop['type']['className'] in classes:
                            ref_class = conn.GetClass(
                                        ClassName=prop['type']['className'],
                                        LocalOnly=False,
                                        IncludeQualifiers=True)
                            classes[ref_class.classname] = ref_class
                        else:
                            ref_class = classes[prop['type']['className']]
                        prop['type']['keys'] = pywbem.NocaseDict(
                                    dict((p['name'], p)
                                for p in cim_insight.get_class_props(
                                    ref_class, keys_only=True)))

                    try:
                        value = inputparse.formvalue2cimobject(
                                prop, 'propname.', params,
                                namespace=self._local.namespace)
                    except inputparse.ReferenceDecodeError as exp:
                        _LOG.error('Invalid argument: %s'%exp)
                        renderer['invalid_argument'] = str(exp)
                    if value is None:
                        continue
                    in_params[prop['name']] = value
                path = pywbem.CIMInstanceName(className,
                        keybindings=in_params, namespace=self._local.namespace)
            inst = conn.GetInstance(InstanceName=path, LocalOnly = False)
            renderer['instance'] = cim_insight.get_inst_info(inst, klass)
        return renderer.result

    @views.html_view()
    def on_GetInstD(self, className):               #pylint: disable=C0103
        """
        View rendering form allowing user to fill in property values in
        order to get instance.
        """
        conn = self.conn
        with self.renderer('get_instance_dialog.mako', className=className) \
                as renderer:
            klass = conn.GetClass(ClassName=className,
                    LocalOnly=False,
                    IncludeQualifiers=True)

            items = [    cim_insight.get_class_item_details(className, i)
                for i in sorted( klass.properties.values()
                               , key=lambda a: a.name)
                if  'key' in i.qualifiers ]
            renderer['items'] = items
        return renderer.result

    @views.html_view(http_method=views.POST)
    def on_InvokeMethod(self, method,               #pylint: disable=C0103
            path=None,
            className=None,
            **params):
        """
        View for invoking method of class or instance and displaying
        results.
        """
        if path is None and className is None:
            raise ValueError("either object path or className argument must"
                    " be given")
        conn = self.conn
        if className is None:
            className = path.classname
        if (   isinstance(path, pywbem.CIMInstanceName)
           and path.namespace is None):
            path.namespace = self._local.namespace

        with self.renderer('invoke_method.mako',
                className=className, method_name=method) as renderer:
            klass = conn.GetClass(ClassName = className, LocalOnly=False)
            cimmethod = klass.methods[method]

            in_params = {}

            tmpl_in_params, tmpl_out_params = cim_insight.get_method_params(
                    className, cimmethod)

            classes = {className : klass}
            for param in tmpl_in_params:
                if isinstance(param["type"], dict):
                    if not param['type']['className'] in classes:
                        ref_class = conn.GetClass(
                                    ClassName=param['type']['className'],
                                    LocalOnly=False,
                                    IncludeQualifiers=True)
                        classes[ref_class.classname] = ref_class
                    else:
                        ref_class = classes[param['type']['className']]
                    param['type']['keys'] = pywbem.NocaseDict(
                                dict((param['name'], param)
                            for param in cim_insight.get_class_props(
                                ref_class, keys_only=True)))
                value = inputparse.formvalue2cimobject(param, 'methparam.',
                        pywbem.NocaseDict(params))
                if isinstance(param['type'], dict):
                    param['value'] = value
                else:
                    param['value'] = render.val2str(value)
                if value is not None:
                    in_params[param['name']] = value
            renderer['in_params'] = tmpl_in_params

            (rval, out_params) = conn.InvokeMethod(
                    MethodName = method,
                    ObjectName = className if path is None else path,
                    **in_params)
            if out_params:
                for param in tmpl_out_params:
                    if not param['name'] in out_params:
                        continue
                    value = out_params[param['name']]
                    if isinstance(param['type'], dict):
                        param['value'] = value
                    else:
                        param['value'] = render.val2str(value)
            renderer['out_params'] = tmpl_out_params

            renderer['iname'] = None
            if path is not None:
                renderer['iname'] = cim_insight.get_inst_info(path, klass)

            out = cim_insight.get_class_item_details(
                    className, cimmethod, path)
            out['value_orig'] = rval
            if (   'values' in cimmethod.qualifiers
               and 'valuemap' in cimmethod.qualifiers):
                out['value'] = render.mapped_value2str(
                        rval, cimmethod.qualifiers)
            elif isinstance(out['type'], dict):
                out['value'] = rval
            else:
                out['value'] = render.val2str(rval)
            renderer['return_value'] = out

        return renderer.result

    @views.html_view(
            http_method=views.POST,
            require_url=False,
            require_namespace=False,
            returns_response=True)
    def on_Login(self, **kwargs):               #pylint: disable=C0103
        """
        View handling user informations from index page and showing
        enumeration of namespaces or class names, depending on user's
        arguments.
        """
        _LOG.debug("In on_Login")
        try:
            scheme, host, port = [kwargs[k] for k in (
                "scheme", "host", "port")]
        except KeyError:
            scheme = host = port = None
        ssl_verify = kwargs.get("ssl_verify", False)
        if not all((scheme, host, port)):
            raise BadRequest(
                    "missing one of ['scheme', 'host', 'port'] arguments")
        namespace = kwargs.get('ns', getattr(self._local, 'namespace', None))
        url = scheme+'://'+host
        if not (  (scheme == 'https' and port == '5989')
               or (scheme == 'http' and port == '5988')):
            url += ':'+port
        if host[0] == '/':
            url = host
        assert isinstance(namespace, str)
        self._local.url = url
        self._local.namespace = namespace
        self._local.verify = ssl_verify
        if namespace:
            return self.on_EnumClassNames()
        return self.on_EnumNamespaces()

    @views.html_view(require_url=False, require_namespace=False)
    def on_Logout(self):                        #pylint: disable=C0103
        """
        View used to log user out.
        """
        # Enable the client to reauthenticate, possibly as a new user
        self.response.set_cookie('yawn_logout', "true",
                path=util.base_script(self._local.request))
        return self.renderer('logout.mako').result

    @views.html_view(http_method=views.POST)
    def on_ModifyInstance(self, path, **params):    #pylint: disable=C0103
        """
        View used to modify existing instance and rendering the result.
        """
        return self._create_or_modify_instance(path.classname, path, **params)

    @views.html_view(http_method=views.GET_AND_POST)
    def on_ModifyInstPrep(self, path):          #pylint: disable=C0103
        """
        View rendering form allowing to modify existing instance.
        """
        conn = self.conn
        with self.renderer('modify_instance_prep.mako',
                new=False, className=path.classname) as renderer:
            klass = conn.GetClass(ClassName=path.classname,
                    LocalOnly=False, IncludeQualifiers=True)
            inst  = conn.GetInstance(InstanceName=path,
                    LocalOnly=False, IncludeQualifiers=True)
            renderer['instance'] = cim_insight.get_inst_info(inst, klass)
        return renderer.result

    @views.html_view(require_url=False, require_namespace=False)
    def on_Pickle(self, path):                  #pylint: disable=C0103
        """
        View rendering instance name in various formats, that can be used
        as arguments to various views.
        """
        return self.renderer('pickle.mako',
                className      = path.classname,
                str_obj        = str(path),
                compressed_obj = render.encode_reference(path),
                xml_obj        = path.tocimxml().toprettyxml()).result

    @views.html_view()
    def on_PrepMethod(self, method,             #pylint: disable=C0103
            path=None,
            className=None):
        """
        View rendering form for method invocation on particular instance
        name of class.
        """
        if path is None and className is None:
            raise ValueError("either object path or className argument must"
                    " be given")
        if className is None:
            className = path.classname
        conn = self.conn
        with self.renderer('prep_method.mako',
                className=className, method_name=method) as renderer:
            klass = conn.GetClass(ClassName = className, LocalOnly=False,
                    IncludeQualifiers=True)

            cimmethod = klass.methods[method]
            renderer['in_params'], renderer['out_params'] = (
                    cim_insight.get_method_params(className, cimmethod))
            renderer['iname'] = None
            if path is not None:
                renderer['iname'] = cim_insight.get_inst_info(path, klass,
                        include_all=True, keys_only=True)
            renderer['return_type'] = cimmethod.return_type
        return renderer.result

    @views.html_view()
    def on_PyProvider(self, className):         #pylint: disable=C0103
        """
        View rendering python provider code for paricular class.
        """
        conn = self.conn
        with self.renderer('py_provider.mako', className=className) \
                as renderer:
            klass = conn.GetClass(ClassName = className, LocalOnly=False,
                        IncludeClassOrigin=True, IncludeQualifiers=True)
            renderer['code'], renderer['mof'] = codegen(klass)
        return renderer.result

    @views.html_view(http_method=views.POST)
    def on_Query(self,                          #pylint: disable=C0103
            query=None,
            lang=QLangConverter.QLANG_WQL):
        """
        View rendering result of query.
        """
        conn = self.conn
        if query is None:
            if "query" not in self._local.request.form:
                raise ValueError("missing query string argument")
            query = self._local.request.form["query"]
        if isinstance(lang, int):
            lang = QLangConverter.query_languages[QLangConverter.QLANG_WQL]
        elif isinstance(lang, str):
            if not lang in QLangConverter.query_languages:
                raise ValueError("lang must be one of: {}".format(
                    QLangConverter.query_languages))
        else:
            raise TypeError("lang must be either string or integer not: {}".
                    format(lang.__class__.__name__))

        assert isinstance(self._local.namespace, str)
        with self.renderer('query.mako', qlang=lang, query=query) as renderer:
            insts = conn.ExecQuery(QueryLanguage=lang,
                    Query=query, namespace=self._local.namespace)
            results = []
            ccache = pywbem.NocaseDict()
            for inst in insts:
                clsname = inst.path.classname
                try:
                    klass = ccache[clsname]
                except KeyError:
                    klass = ccache[clsname] = conn.GetClass(
                            clsname, LocalOnly=False)
                results.append(cim_insight.get_inst_info(inst, klass,
                    include_all=True, keys_only=True))
            renderer['results'] = results
        return renderer.result

    @views.html_view()
    def on_QueryD(self, className=''):          #pylint: disable=C0103
        """
        View rendering form for query.
        """
        return self.renderer('query_dialog.mako', className=className).result

    @views.html_view()
    def on_ReferenceNames(self, path):          #pylint: disable=C0103
        """
        The goal here is to list InstPaths to all related objects, grouped
        in the following manner:
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
                iname=cim_insight.get_inst_info(path)) as renderer:
            # TODO remove this namespace hack when pywbem is fixed
            oldns = path.namespace
            path.namespace = None
            refs = conn.ReferenceNames(ObjectName=path)
            assert isinstance(self._local.namespace, str)
            path.namespace = (  oldns is not None and oldns
                             or self._local.namespace)

            # { association_class_name :
            #   { role_string : 
            #     { role_class_name :
            #       [ ( assoc_instance_name, role_instance_name), ... ]
            #     , ... }
            #   , ... }
            # , ... }
            refdict = util.rdefaultdict()
            for ref in refs:
                ref_iname = ref
                assoc_cname = ref_iname.classname
                for role in ref_iname.keys():
                    role_iname = ref_iname[role]
                    if util.inames_equal(role_iname, path):
                        continue
                    role_cname = role_iname.classname
                    if role_cname not in refdict[assoc_cname][role]:
                        refdict[assoc_cname][role][role_cname] = []
                    refdict[assoc_cname][role][role_cname].append(
                            (ref_iname, role_iname))
            renderer['associations'] = sorted(refdict.keys())

            # { accociation_class_name :
            #   [ (role, [role_iname_info, ... ])
            #   , ... ]
            # , ... }
            refmap = defaultdict(list)
            for assoc_cname, roles in sorted(refdict.items(),
                    key=lambda i: i[0]):
                for role, refs in sorted(roles.items(), key=lambda i: i[0]):
                    if not refs:
                        continue
                    ref_inames = []
                    for cls, ref_paths in sorted(
                            refs.items(), key=lambda i: i[0]):
                        rfs = []
                        for ref_iname, role_iname in sorted(ref_paths):
                            info = cim_insight.get_inst_info(role_iname)
                            info["assoc"] = ref_iname
                            rfs.append(info)
                        ref_inames.append((cls, ref_paths[0][1].namespace, rfs))
                    refmap[assoc_cname].append((role, ref_inames))
            renderer['refmap'] = refmap

        return renderer.result

    @views.json_view
    def on_json_get_class_list(self):
        """
        JSON view returning list of class names.
        """
        klasses = self.conn.EnumerateClassNames(
                LocalOnly=False, DeepInheritance=True)
        return sorted(klasses)

    @views.json_view
    def on_json_get_class_keys(self, className):
        """
        JSON view returning list of keys for particular class.
        """
        klass = self.conn.GetClass(ClassName=className,
                LocalOnly=False,
                IncludeQualifiers=True)
        return cim_insight.get_class_props(klass, keys_only=True)

    @views.json_view
    def on_json_query_instances(self):
        """
        JSON view accepting query string in WQL and returning list of matching
        instance names as json objects.
        """
        query = self._local.request.args['query']
        assert isinstance(self._local.namespace, str)
        insts = self.conn.ExecQuery(QueryLanguage='WQL',
                Query=query, namespace=self._local.namespace)
        self.response.headers["content-type"] = "application/json"
        result = []
        klass = None
        for inst in insts:
            if klass is None:
                klass = self.conn.GetClass(ClassName=inst.classname,
                        IncludeQualifiers=True, LocalOnly=False)
            item = cim_insight.get_inst_info(inst, klass, keys_only=True)
            for prop in item["props"]:
                if (  isinstance(prop['type'], dict)
                   or prop['type'] == 'reference'):
                    prop['value'] = str(prop['value'])
                    prop['value_orig'] = str(prop['value_orig'])
            item['path'] = str(item['path'])
            result.append(item)
        return result

