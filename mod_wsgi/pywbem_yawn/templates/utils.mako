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
  if classes:
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
    return "%s REF" % make_href_str('GetClass', args, p['type']['className'])
  else:
    res = p['type']
  if isinstance(p, dict) and p['is_array']:
    if 'array_size' in p and p['array_size'] is not None:
      res += ' [%s]' % str(p['array_size'])
    else:
       res += ' [ ]'
  return markupsafe.escape(res)
%></%def>\

<%def name="print_data_value(p, cname=None, whole_path=False)"><%doc>
    if value is an object path and whole_path is True, then its string
    representation is printed
    it whole_path is False, then only classname part is printed
  </%doc><%
    if p['value'] is None: return ''
    if isinstance(p['type'], dict):
      args = { 'url' : p['type'].get('url', url)
             , 'ns'  : p['type'].get('ns', ns)
             , 'path': p['value'] }
      if not args['ns'] and ns:
        args['ns'] = ns
      if not whole_path and cname:
        target = cname
      elif not whole_path and p['type'].get('className', None):
        target = p['type']['className']
      elif not whole_path and className:
        target = className
      else:
        target = p['value']
      return make_href_str('GetInstance', args, target)
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

<%def name="make_elem(name, css, description=None)"><%
  args = []
  if not isinstance(css, basestring):
    if len(css): css = ' '.join(css)
  if css:
    args.append('class="%s"' % css)
  if description is not None:
    args.append('title="%s"' % markupsafe.escape(description))
  argsstr = ""
  if len(args): argsstr = " " + " ".join(args)
  return "<%s%s>"%(name, argsstr)
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
      </td><td class="title" title="${p['description'] | hs}">
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
                  (${', '.join(params) | hs})</td></tr>
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

<%def name="show_instance_names(inames, with_get_link=True, whole_path=False)">
  % if len(inames) > 0:
    <table class="details">
      <tr class="headers">
      % if with_get_link:
        <th class="get" />
      % endif
      % for p in inames[0]['props']:
        % if p['is_key']:
          <th>${p['name'] | hs}</th>
        % endif
      % endfor
      <th class="namespace">Namespace</th>
      </tr>
      % for iname in inames:
        ${show_instance_name(iname, with_get_link, whole_path)}
      % endfor
    </table>
  % endif
</%def>\

<%def name="show_instance_name(iname, with_get_link=True, whole_path=False)">
  <tr class="instance">
    % if with_get_link:
      <%
        args = {'ns':iname['ns'], 'url':url, 'path':iname['path']}
      %>
      <td class="get">${make_href('GetInstance', args, 'get')}</td>
    % endif
    % for p in iname['props']:
      % if p['is_key']:
        <td>${print_data_value(p, iname['className'], whole_path=whole_path)}</td>
      % endif
    % endfor
    <td class="namespace">${iname['ns'] | hs}</td>
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
        if caption is None:
          caption = (  'With Input Parameters'
                    if read_only else 'Enter Input Parameters')
        action = urls.build('InvokeMethod', args)
      if submit is None:
        submit = "Invoke Method"
      if prefix is None:
        prefix = "MethParam."
  %>
  % if caption is not False and params:
    <h3>${caption | hs}</h3>
  % endif
  % if not read_only:
    <form action="${action}" method="post">
  % endif
  % if params:
    <table id="in_params" class="in params">
      <tr class="headers">
        <th class="data_type">Data Type</th>
        <th class="param_name">Param Name</th>
        <th class="value">Value</th>
      </tr>
      % for p in params:
        ${make_elem('tr', make_param_css(p), p['description'])}
          <td class="data_type">${print_data_type(p)}</td>
          <td class="param_name">
            <% cargs = {'url':url, 'ns':ns, 'className':className } %>
            ${make_href('GetClass', cargs, p['name'], '#'+p['name'].lower())}
          </td>
          <td class="value">
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
          <td class="param_name">${p['name'] | hs}</td>
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
  %>${"(%s)"%', '.join(p['values'][value]) | hs}
</%def>\

<%def name="make_input(p, prefix='')">
  ## prefix is used for name collision avoidance
  <% paramname = prefix + p['name'] %>
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
          <td class="value">${v | hs}</td>
          <td class="description">${param_valmap_values(p, v)}</td>
        </tr>
      % endfor
      </table>
    % else:
      <select name="${paramname | h}">
        <option value=""></option>
      % for v in p['valuemap']:
        <% selected = p['value_orig'] is not None and str(p['value_orig']) == v %>
        <option value="${v | h}"${' selected="selected"' if selected else ''}>
          ${v | hs} ${param_valmap_values(p, v)}
        </option>
      % endfor
      </select>
    % endif
  % elif p['type'] == 'boolean':
    <select name="${paramname | h}">
    % for v in ("", True, False):
      <% selected = p['value_orig'] is not None and bool(p['value_orig']) == v %>
      <option value="${v | h}"${' selected="selected"' if selected else ''}>${v | hs}</option>
    % endfor
    </select>
  % else:
    % if p['is_array']:
      <% 
      if p['array_size'] is not None:
        size = p['array_size']
      elif isinstance(p['value_orig'], list):
        size = len(p['value_orig'])
      else:
        size = 0
      %>
      % for i in range(size):
        <input type="text" name="${paramname | h}-${i}"
        ${'value="%s"'%p['value_orig'][i] if i < size else ''} />
        % if p['array_size'] is None:
          <a href="javascript://">-</a>
        % endif
        <br />
      % endfor
      % if p['array_size'] is None:
        <input type="button" id="${paramname}_add" value="Add" /> 
      % endif
      <input type="hidden" id="${paramname}.size" name="${paramname | h}.size" value="${size}" />
    % else:
      <input type="text" name="${paramname | h}"
      ${'value="%s"'%markupsafe.escape(p['value_orig']) if p['value_orig'] is not None else ''}/>
    % endif
  % endif
</%def>\
## ex:et:sw=2:ts=2
