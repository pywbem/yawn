<%!
  import markupsafe
  from pywbem_yawn.filters import hs
%>\

<%def name="make_href_str(func, kwargs={}, target=None, append='', classes=[])"><%
  if target is None:
    target = func
  if not getattr(target, 'safe', False):
    target = markupsafe.escape(target)
  linkargs = {'href':urls.build(func, kwargs) + append}
  if len(classes):
    if isinstance(classes, basestring):
      linkargs['class'] = classes
    else:
      linkargs['class'] = ' '.join(classes)
  linkargs = ' '.join(   '%s="%s"' % (k, markupsafe.escape(v))
                     for k, v in linkargs.items())
  return '<a %s>%s</a>' % (linkargs, target)
%></%def>\

<%def name="make_href(func, kwargs={}, target=None, append='', classes=[])">
  ${make_href_str(func, kwargs, target, append, classes)}\
</%def>\

<%def name="make_res_path(name)"><%
  prefix = static if static else ''
  if prefix[-1] == '/':
    prefix = prefix[:-1]
  path = '/'.join([prefix, name])
  return path
%></%def>\

<%def name="res_css(name)">
  <link rel="stylesheet" type="text/css" href="${make_res_path(name)}.css" />
</%def>\

<%def name="res_js(name)">
  <script type="application/x-javascript" src="${make_res_path(name)}.js"></script>
</%def>\

<%def name="print_description(desc)">
  <%doc>
    somehow does not work ???
  </%doc>
  <% desc = markupsafe.escape(desc).replace('\\n', '<br />') %>
  ${desc}
</%def>\

<%def name="print_data_type(p)"><%
  if isinstance(p, basestring):
    res = p
  elif p is None or p['type'] is None:
    res = 'void'
  elif isinstance(p['type'], dict):
    args = p['type'].copy()
    if 'ns' not in args or not args['ns'] and ns:
      args['ns'] = ns
    if 'url' not in args:
      args['url'] = url
    res = "%s REF" % make_href_str('GetClass', args, p['type']['className'])
  else:
    res = markupsafe.escape(p['type'])
  if isinstance(p, dict) and p['is_array']:
    if 'array_size' in p and p['array_size'] is not None:
      res += ' [%s]' % str(p['array_size'])
    else:
      res += ' [ ]'
  return res
%></%def>\

<%def name="print_data_value(p, whole_path=True)"><%doc>
    if value is an object path and whole_path is True, then its string
    representation is printed
    it whole_path is False, then only classname part is printed
  </%doc><%
    if p['value'] is None: return ''
    if isinstance(p['value'], (tuple, list, set)):
      pn = dict((k, v) for k, v in p.items()
                       if  k not in ('is_array', 'value'))
      pn['is_array'] = False
      results = []
      for op in p['value']:
        pn['value'] = op
        results.append(print_data_value(pn, whole_path))
      return "{ " + ", ".join(results) + " }"
    if isinstance(p['type'], dict):
      args = { 'url' : p['type'].get('url', url)
             , 'ns'  : p['type'].get('ns', ns)
             , 'path': p['value'] }
      if not args['ns'] and ns:
        args['ns'] = ns
      if not whole_path and p['type'].get('className', None):
        target = p['type']['className']
      elif not whole_path and className:
        target = className
      else:
        target = p['value']
      return make_href_str('GetInstance', args, target, classes=["path-reference"])
    elif p['name'].lower().endswith('classname'):
      args = {'url':url, 'ns':ns, 'className':p['value']}
      return make_href_str('GetClass', args, p['value'])
    val = p['value']
    if not getattr(val, 'safe', False):
      return markupsafe.escape(val)
    return val
%></%def>\

<%def name="make_param_css(param, css=None)"><%
  if css is None:
    css = set()
  for k in ('array', 'required', 'local', 'valuemap', 'key', 'deprecated'):
    if ('is_'+k) in param and param['is_'+k]:
      css.add(k)
  if isinstance(param['type'], dict):
    css.add('ref')
  if 'array_size' in param and param['array_size'] is not None:
    css.add('fixed_size')
  return css
%></%def>\

<%def name="make_count_tags(counter, count, css=None)"><%
  if css is None:
    css = set()
  if counter == 0: css.add('first')
  if counter == count - 1: css.add('last')
  css.add('odd' if counter % 2 else 'even')
  return css
%></%def>

<%def name="make_elem(elem_name, css, description=None, terminated=False, **kwargs)"><%
  args = []
  if not isinstance(css, basestring):
    if len(css): css = ' '.join(css)
  if css:
    args.append('class="%s"' % css)
  if description is not None:
    args.append('title="%s"' % markupsafe.escape(description))
  for k, v in kwargs.items():
    args.append('%s="%s"' % (k, v))
  argsstr = ""
  if len(args): argsstr = " " + " ".join(args)
  return "<%s%s%s>"%(elem_name, argsstr, '/' if terminated else '')
%></%def>\

<%def name="show_instance(inst)">
  <%
    cname = inst['className'] if 'className' in inst else className
    args    = {'ns':ns, 'url':url}
    cargs   = args.copy(); cargs['className'] = cname
    objargs = args.copy(); objargs['path'] = inst['path']
    have_required_props = False
  %>
  <h2 class="title">Instance of ${make_href('GetClass', cargs, cname)}</h2>
  <h4 class="host">Host: <span class="value">${inst['host']}</span></h4>
  <h4 class="namespace">Namespace: <span class="value">${ns}</span></h4>
  <table class="details">
    <tr class="inst_nav">
      <td class="del_mod">
        ${make_href('DeleteInstance', objargs, 'Delete')}<br />
        ${make_href('ModifyInstPrep', objargs, 'Modify')}
      </td>
      <td class="assocs" colspan="2">${make_href('ReferenceNames', objargs,
          'Object Associated with this Instance')}<br />
          ${make_href('FilteredReferenceNamesDialog', objargs,
          '(With Filters)')}</td>
    </tr>
    <tr class="inst_header">
      <th>Type</th><th>Name</th><th>Value</th>
    </tr>
    % for p in inst['props']:
      <%
        css = set()
        if p['is_key']:
          css.add('key')
        if p['is_required']:
          css.add('required')
          have_required_props = True
        if p['type'] is None:
          css.add('not_in_schema')
      %>
      ${make_elem('tr', css)}<td class="type">
        ${print_data_type(p)}
        </td><td class="title" title="${p['description'] | n,hs}">
        ${make_href('GetClass', cargs, p['name'], '#'+p['name'].lower())}
      </td><td class="value">
        ${print_data_value(p)}
      </td></tr>
    % endfor
    <tr>
      <td colspan="3">
        <table class="prop_summary">
          <tr>
            <td class="key">Key Property</td>
            % if have_required_props:
              <td class="required">Required (non-key) Property</td>
            % endif
          </tr>
        </table>
      </td>
    </tr>
    % if inst['methods']:
      <tr>
        <td colspan="3">
          <table class="methods">
            <tr><td class="title">Methods</td></tr>
            % for name, params in inst['methods']:
              <% methargs = objargs.copy(); methargs['method'] = name %>
              <tr><td>${make_href('PrepMethod', methargs, name)}
                  (${', '.join(params) | n,hs})</td></tr>
            % endfor
          </table>
        </td>
      </tr>
    % endif
    <% pargs = args.copy(); pargs['path'] = inst['path'] %>
    <tr>
      <td colspan="3">
        Get the ${make_href('Pickle', pargs, 'LocalInstancePath')}
      </td>
    </tr>
  </table>
</%def>\

<%def name="show_instance_names(inames, with_get_link=True, with_assoc_link=False, whole_path=True)">
  % if len(inames) > 0:
    <table class="details">
      <tr class="headers">
      % if with_assoc_link:
        <th class="assoc" />
      % endif
      % if with_get_link:
        <th class="get" />
      % endif
      % for p in inames[0]['props']:
        % if p['is_key']:
          <th>${p['name'] | n,hs}</th>
        % endif
      % endfor
      <th class="namespace">Namespace</th>
      </tr>
      % for iname in inames:
        ${show_instance_name(iname, with_get_link, with_assoc_link, whole_path)}
      % endfor
    </table>
  % endif
</%def>\

<%def name="show_instance_name(iname, with_get_link=True, with_assoc_link=False, whole_path=True)">
  <tr class="instance">
    % if with_assoc_link:
      <%
        args = {'ns':iname['ns'], 'url':url, 'path':iname['assoc']}
      %>
      <td class="get">${make_href('GetInstance', args, 'assoc')}</td>
    % endif
    % if with_get_link:
      <%
        args = {'ns':iname['ns'], 'url':url, 'path':iname['path']}
      %>
      <td class="get">${make_href('GetInstance', args, 'get')}</td>
    % endif
    % for p in iname['props']:
      % if p['is_key']:
        <td>${print_data_value(p, whole_path=whole_path)}</td>
      % endif
    % endfor
    <td class="namespace">${iname['ns'] | n,hs}</td>
  </tr>
</%def>\

<%def name="enum_classes(curclass, level=0, ctx=None)">
  <%
    if ctx is None:
      ctx = {'counter' : 0}
  %>
  % for cname in classes[curclass]:
    <tr class="level${level} ${('even', 'odd')[ctx['counter']%2]}">
      <%
        args = {'url':url, 'ns':ns, 'className':cname}
        css = set()
        if cname.startswith('CIM_'):
          css.add('cim_schema')
        if cname in classes and len(classes[cname]):
          css.add('has_kids')
        ctx['counter'] += 1
      %>
      ${make_elem('td', css)}
        ${class_prefix(cname, level)}
        ${make_href('GetClass', args, cname)}
      </td><td>${make_href('EnumInstanceNames', args, 'Instance Names')}
      </td><td>${make_href('EnumInstances', args, 'Instances')}
      </td>
    </tr>
    % if mode == 'deep' and cname in classes and len(classes[cname]):
      ${enum_classes(cname, level+1, ctx)}
    % endif
  % endfor
</%def>\

<%def name="class_prefix(cname, level)">
  % if mode == 'deep':
    ${'|&nbsp;&nbsp;&nbsp;&nbsp;'*(level-1)}${'|---' if level > 0 else ''}
  % elif mode != 'flat' and cname in classes and len(classes[cname]):
    <% args = {'url':url, 'ns':ns, 'className': cname, 'mode':mode} %>
    ${make_href('EnumClassNames', args, '+')}
  % endif
</%def>\

<%def name="show_input_params(params, read_only=False, action=None, caption=None, submit=None, prefix=None)">
  <%doc>
    if caption is False => no caption will be printed
                  None  => some default will be printed
    action has meaning only for non-read-only forms
     * if None   => InvokeMethod action will be invoked on post
     * otherwise => action given will be invoked
    submit is a text on submit button
    prefix if placed before param name in input's name attribute to
      allow namespacing and thus avoid name collisions

    uses global variable 'new'
  </%doc>
  <%
    if not read_only:
      if action is None:
        args = {'method':method_name}
        if iname is None:
          args['className'] = className
        else:
          args['path'] = iname['path']
        action = urls.build('InvokeMethod', args)
      if submit is None:
        submit = "Invoke Method"
      if prefix is None:
        prefix = "methparam."
      prefix = prefix.lower()
    elif prefix is None:
        prefix = ''
    if caption is None:
      caption = (  'With Input Parameters'
                if read_only else 'Enter Input Parameters')
  %>
  % if caption is not False and params:
    <h3>${caption | n,hs}</h3>
  % endif
  % if not read_only:
    <form action="${action}" method="post">
  % endif
  % if params:
    <table id="in_params" class="in params">
      <tr class="headers">
        <th class="data_type">Data Type</th>
        <th class="param_name">Param Name</th>
        <th colspan="${2 if not read_only else 1}" class="value">Value</th>
      </tr>
      % for p in params:
        <%
          prop_name = p['name'].lower()
          rowspan = 1
          if not read_only and p['is_array'] and not p['is_valuemap']:
            if p['array_size'] is not None:
              ## fixed size array (no Add or Remove)
              rowspan = p['array_size']
            else:
              if isinstance(p['value_orig'], list):
                rowspan = len(p['value_orig'])
              else:
                rowspan = 0
              ## for Add button
              rowspan += 1
        %>
        ${make_elem('tr', make_param_css(p), p['description'],
            id="param-"+prefix+prop_name+"-row-1")}
          <td id="${'param_type-'+prefix+prop_name}"
              rowspan="${rowspan}" class="data_type">${print_data_type(p)}</td>
          <td id="${'param_name-'+prefix+prop_name}"
              rowspan="${rowspan}" class="param_name">
            <% cargs = {'url':url, 'ns':ns, 'className':className } %>
            ${make_href('GetClass', cargs, p['name'], '#'+prop_name)}
          </td>
          <%
            colspan = 1
            if (   not read_only
               and (  not p['is_array']
                   or p['array_size'] is not None
                   or p['is_valuemap']
                   or (   isinstance(p['value_orig'], list)
                      and not len(p['value_orig']))
                   or not p['value'])):
              colspan = 2
            css = ["value"]
            if p['is_array'] and not read_only:
              css.append("array_item")
          %>
          ${make_elem('td', css, colspan=colspan,
            id='param_value-'+prefix+prop_name)}
            % if read_only or (new is False and p['is_key']):
              ${print_data_value(p)}
            % else:
              ${make_input(p, prefix)}
            % endif
          </td>
        </tr>
      % endfor
    </table>
  % endif
    % if not read_only:
      <div class="submit">
        <input type="hidden" name="url" value="${url | h}" />
        <input type="hidden" name="ns" value="${ns}" />
        <input type="submit" value="${submit | h}" />
      </div>
    % endif
  % if not read_only:
    </form>
  % endif
</%def>\

<%def name="show_output_params(params, with_values=False)">
  % if params:
    <h3>Output Parameters</h3>
    <table id="out_params" class="out params">
      <tr class="header">
        <th class="data_type">Data type</th>
        <th class="param_name">Param Name</th>
        % if with_values:
          <th class="value">Value</th>
        % endif
      </tr>
      % for p in out_params:
        ${make_elem('tr', make_param_css(p), p['description'])}
          <td class="data_type">${print_data_type(p)}</td>
          <td class="param_name">${p['name'] | n,hs}</td>
          % if with_values:
            <td class="value">${print_data_value(p)}</td>
          % endif
        </tr>
      % endfor
    </table>
  % endif
</%def>\

<%def name="param_valmap_values(p, value)"><%
  if not p['values'][value]: return ""
  %>${"(%s)"%', '.join(p['values'][value]) | n,hs}
</%def>\

<%def name="make_input_no_array(p, prefix='', suffix='', css=[])">
  <%
    paramname = prefix + p['name'].lower() + suffix
    css_str=""
    if len(css):
      css_str = 'class="%s"' % (" ".join(css))
  %>
  % if p['is_valuemap']:
    <select ${css_str} id="${paramname | h}" name="${paramname | h}">
      <option value=""></option>
    % for v in p['valuemap']:
      <% selected = p['value_orig'] is not None and str(p['value_orig']) == v %>
      <option value="${v | h}"${' selected="selected"' if selected else ''}>
        ${v | n,hs} ${param_valmap_values(p, v)}
      </option>
    % endfor
    </select>
  % elif p['type'] == "boolean":
    <select ${css_str} id="${paramname | h}" name="${paramname | h}">
    % for v in ("", True, False):
      <% selected = p['value_orig'] is not None and bool(p['value_orig']) == v %>
      <option value="${v | h}"${' selected="selected"' if selected else ''}>${v | n,hs}</option>
    % endfor
    </select>
  % else:
    <%
      kwargs = { "id":paramname, "type":"text", "name":paramname,
          "terminated":True}
      if (   p['value_orig'] is not None
         and (not isinstance(p['value_orig'], list) or len(p['value_orig']))):
        kwargs['value'] = p['value_orig']
      null_kwargs = False
      if (   not p['is_required'] and not p['is_key'] and not p['is_array']
         and (p['type'] == 'string' or isinstance(p['type'], dict))):
        null_kwargs = { "type":"checkbox", "checked":"checked",
           "terminated" : True}
        null_kwargs['name'] = null_kwargs['id'] = (
            prefix + p['name'].lower() + '-null' + suffix)
        null_kwargs['title'] = "NULL - Do not send this value."
    %>
    % if null_kwargs:
      ${make_elem('input', css + ['null'], **null_kwargs)}
    % endif
    ${make_elem('input', css, **kwargs)}
  % endif
</%def> \

<%def name="make_input(p, prefix='')">
  ## prefix is used for name collision avoidance
  <% paramname = prefix + p['name'].lower() %>
  % if p['is_valuemap']:
    % if p['is_array']:
      <table class="valuemap">
      % for v in p['valuemap']:
        <%
          checked = (    isinstance(p['value_orig'], list)
                    and v in [str(mv) for mv in p['value_orig']])
        %>
        <tr>
          <td class="checkbox">
            <input type="checkbox" name="${paramname | h}-${v | h}"
            ${' checked="checked"' if checked else ''} />
          </td>
          <td class="value">${v | n,hs}</td>
          <td class="description">${param_valmap_values(p, v)}</td>
        </tr>
      % endfor
      </table>
    % else:
      ${make_input_no_array(p, prefix)}
    % endif
  % elif p['is_array']:
    <%
      if p['array_size'] is not None:
        size = p['array_size']
      elif isinstance(p['value_orig'], list):
        size = len(p['value_orig'])
      else:
        size = 0
    %>
    % for i in range(size):
      <%
        pnew = p.copy()
        pnew["value_orig"] = p['value_orig'][i] if i < size else ''
      %>
      ${make_input_no_array(pnew, prefix, '-'+str(i))}
      % if p['array_size'] is None:
        </td>${make_elem('td', ['remove'])}
        <a title="Remove this item" class="remove" href="javascript://">X</a></td></tr>
        ${make_elem('tr', make_param_css(p), id="param-"+paramname+"-row-"+str(i+2))}
        ${make_elem('td', ["array_item"], colspan=2 if i >= (size - 1) else 1)}
      % else:
        </td><td colspan="2"/>
      % endif
    % endfor
    <input type="hidden" id="${paramname | h}.size"
           name="${paramname | h}.size" value="${size}" />
    % if p['array_size'] is None:
      <input type="button" id="${paramname}_add" value="Add" />
      <% pnew = p.copy(); pnew['value_orig'] = None %>
      ${make_input_no_array(pnew, prefix, '-default', ["hidden", "default"])}
    % endif
  % else:
    ${make_input_no_array(p, prefix)}
  % endif
</%def>\

<%def name="js_input_params(params, prefix='')">
<script type="text/javascript">
  var input_param_details = {
    % for p in params:
      <%
        if isinstance(p['type'], dict):
          type_str = str(dict((str(k), str(v)) for k, v in p['type'].items()))
        else:
          type_str = str(p['type']).lower()
          if type_str == 'boolean':
            type_str = 'bool'
          type_str = '"%s"'%type_str
        values = []
        for k, v in p['values'].items():
          values.append('"%s":"%s"'%(
              markupsafe.escape(k), markupsafe.escape(v[0]) if v else ""))
        values = "{%s}"%", ".join(values)
        if p['value'] is None:
          value = 'null'
        else:
          value = '"%s"'%markupsafe.escape(p['value'])
        if p['value_orig'] is None:
          value_orig = 'null'
        else:
          if isinstance(p['value_orig'], list):
            value_orig = [(v.encode('utf-8') if isinstance(v, unicode) else str(v)) for v in p['value_orig']]
          else:
            value_orig = p['value_orig']
            if isinstance('value_orig', unicode):
              value_orig = value_orig.encode('utf-8')
          value_orig = '"%s"'%markupsafe.escape(p['value_orig'])
      %>
      "${prefix.lower()}${p['name'].lower()}" : {
        'name'       : "${prefix.lower()}${str(p['name'].lower())}",
        'valuemap'   : ${[str(v) for v in p['valuemap']]},
        'values'     : ${values},
        'is_array'   : ${'true' if p['is_array'] else 'false'},
        'is_valuemap': ${'true' if p['is_valuemap'] else 'false'},
        'array_size' : ${'null' if p['array_size'] is None else p['array_size']},
        'type'       : ${type_str},
        'value'      : ${value},
        'value_orig' : ${value_orig}
      },
    % endfor
  };
</script>
</%def>\
## ex:et:sw=2:ts=2
