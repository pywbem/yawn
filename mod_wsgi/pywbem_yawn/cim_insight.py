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
Defines functions for obtaining information from pywbem objects.
"""

import pywbem
from pywbem_yawn import render
from pywbem_yawn import util

def get_all_hierarchy(conn, url, ns, className):
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
    return hierarchy

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
            i['value'] = render.mapped_value2str(
                    _get_value(prop.name), prop.qualifiers)
        elif prop.reference_class is not None:
            i['value'] = _get_value(prop.name)
        else:
            i['value'] = render.val2str(_get_value(prop.name))

    if prop.qualifiers.has_key('valuemap'):
        i['is_valuemap'] = True
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
                  or prop.qualifiers['in'].value)
        i['out'] = (  prop.qualifiers.has_key('out')
                   and prop.qualifiers['out'].value)

    return i

def get_class_item_details(className, item, inst=None):
    """
    @param item can be one of {
        CIMProperty, CIMMethod, CIMParameter }
    @param inst provides some additional info (if given)
    """
    if not isinstance(className, basestring):
        raise TypeError('className must be a string')
    if not isinstance(item, (pywbem.CIMProperty, pywbem.CIMMethod,
            pywbem.CIMParameter)):
        raise TypeError('item must be either CIMProperty,'
                ' CIMParameter or CIMMethod')
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
        if q.name.lower() in ('description', 'deprecated', 'key', 'required'):
            continue
        i['qualifiers'].append((q.name, render.val2str(q.value)))
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
        if None, then all properties declared by klass will be returned
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
    keys = sorted(keys, util.cmp_pnames(klass))

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

