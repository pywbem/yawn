<%! from pywbem_yawn.filters import hs %>
<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * aggregation
   * association
   * super_class      - either its class_name or None
   * description
   * qualifiers       - [(name, value), ... ]
   * items            - list in format:
      [ { name: name
        , description: description
        , is_deprecated: bool
        , is_local: bool
        , is_array: bool
        , is_method: bool
        , is_key: bool
        , class_origin
        , qualifiers: [ (name, value), ... ]
        , type: either string or {'ns':ns, 'className':class_name} if
                it is a reference
        , args: in case of method:
        [ { name: name
          , description: description
          , type: either string or dict for ref
          , is_array
          , array_size - None if not given or not an array, int otherwise
          , qualifiers: [ (name, value), ... ]
          }
        , ...
      , ...
      ]
</%doc>
<%def name="subtitle()">Class ${className}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('get_class')}
</%def>
<%def name="caption()"><h1>Class ${className}</h1></%def>
<%def name="content()">
  <%
    args  = {'url':url, 'ns':ns}
    cargs = args.copy();
    cargs['className'] = className
  %>
  <table>
    <tr>
      <td>
        <div class="nav">
          ${utils.make_href('DeleteClass', cargs, 'Delete Class')},
          ${utils.make_href('GetInstD', cargs, 'Get Instance')},
          ${utils.make_href('CreateInstancePrep', cargs, 'Create Instance')}
          or view ${utils.make_href("EnumInstanceNames", cargs, 'Instance Names')}
          or ${utils.make_href('EnumInstances', cargs, 'Instances')}
          or ${utils.make_href('AssociatedClasses', cargs, 'AssociatedClasses')}
          of this class.
          ${utils.make_href('PyProvider', cargs, 'Python Provider')}
          ${utils.make_href('CMPIProvider', cargs, 'CMPI Provider')}
        </div>
        <table class="details">
          <%
            css = set(('class_header', ))
            if aggregation:
              css.add('aggregation')
            if association:
              css.add('association')
          %>
          ${utils.make_elem('tr', css)}
            <td class="name"><a id="${className}"></a>${className}</td>
            <td class="parent">
              % if super_class:
                <% sargs = args.copy(); sargs['className'] = super_class %>
                Superclass: ${utils.make_href('GetClass', sargs, super_class)}
              % endif
            </td>
          </tr>
          % if description:
            <tr class="description">
              <td colspan="2">${description | hs}</td>
            </tr>
          % endif
          <tr class="qualifiers"><td colspan="2">
            <span class="caption">Qualifiers:</span>
            <% qfirst = True %>
            % for i, (qn, qv) in enumerate(qualifiers):
              % if qn not in ('Composition', 'Association', 'Aggregation'):
                ${', ' if not qfirst else ''}${qn}(${'"%s"'%qv | hs})
                <% qfirst = False %>
              % endif
            % endfor
          </td></tr>
          <tr class="params_header">
            <td colspan="2">Parameters (local in grey)</td>
          </tr>
          <tr>
            <td colspan="2">
              ${self.params()}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</%def>\

<%def name="params()">
  <table class="params">
  % for p in items:
    <%
      css = set(('item', ))
      for k, v in p.items():
        if k.startswith('is_') and v:
          css.add(k[3:])
    %>
    ${utils.make_elem('tr', css)}
      <td><a id="${p['name'].lower()}"></a>
      % for qn, qv in p['qualifiers']:
        ${qn | hs} ${qv | hs}<br />
      % endfor
      <span class="type">${utils.print_data_type(p)}</span>
      % if p['is_method']:
        <%
          args = { 'ns':ns, 'url':url, 'method':p['name']
                 , 'className':className }
        %>
        <span class="name">${utils.make_href('PrepMethod', args, p['name'])}</span>(
        % if len(p['args']) > 0:
          <table class="args">
          % for ia, a in enumerate(p['args']):
            <%
              in_out = []
              css = set(('info', ))
              quals = dict((k.lower(), v) for k, v in a['qualifiers'])
              if 'in' in quals:
                val = quals.pop('in')
                if val in ['True', True, '1', 'yes']:
                  in_out.append("In")
                  css.add('in')
              if 'out' in quals:
                val = quals.pop('out')
                if val in ['True', True, '1', 'yes']:
                  in_out.append("Out")
                  css.add('out')
              if ia == 0: css.add('first')
              if ia == len(p['args']) - 1: css.add('last')
              if ia % 2:
                css.add('odd')
              else:
                css.add('even')
            %>
            ${utils.make_elem('tr', css)}
              <td class="spacer" />
                % if len(in_out):
                  <td class="spacer in_out">(${", ".join(in_out)})</td>
                % else:
                  <td class="spacer" />
                % endif
              <td>
                % if a['description']:
                  <span class="description">
                    ${a['description'] | hs}
                  </span>
                % endif
                % if len(quals):
                  <table class="qualifiers">
                    <tr><td class="caption">Qualifiers:</td>
                    <% aqfirst = True %>
                    % for qn, qv in a['qualifiers']:
                      % if qn.lower() not in ('in', 'out'):
                        ${'<tr><td></td>' if not aqfirst else ''}<td>${qn} ${qv | hs}</td></tr>
                        <% aqfirst = False %>
                      % endif
                    % endfor
                  </table>
                % endif
              </td>
            </tr>
            <%
              css.remove('info')
              css.add('declaration')
            %>
            ${utils.make_elem('tr', css)}
              <td class="spacer" />
              <td colspan="2">
                <span class="type">${utils.print_data_type(a)}</span>
                <span class="name">${a['name']}</span>
                % if p['is_array']:
                  ${'[%s]'%('' if a['array_size'] is None else str(a['array_size']))}
                % endif
              </td>
            </tr>
          % endfor
          </table>
        % endif
        )
      % else:
        <span class="name">${p['name']}</span>;
      % endif
      <br />
      % if p['description']:
        <span class="description">
          ${p['description'] | hs}
        </span><br />
      % endif
      % if not p['is_local'] and p['class_origin']:
        <% args = {'ns':ns, 'url':url, 'className': p['class_origin'] } %>
        <div class="class_origin">
          <span class="caption">Class Origin:</span>
          ${utils.make_href('GetClass', args, p['class_origin'])}
        </div>
      % endif
      </td>
    </tr>
  % endfor
  </table>
</%def>
## ex:et:ts=2:sw=2
