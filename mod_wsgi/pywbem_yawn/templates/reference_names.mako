<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * iname
   * associations: [ cls1, cls2, ... ]
   * refmap: { assoc_cls:
               [ ( role , [iname1, inam2, ...])
               , ...
               ]
             , ...
             }
</%doc>
<%def name="subtitle()">ReferenceNames ${iname['className']}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance_names')}
  ${utils.res_css('reference_names')}
</%def>
<%def name="caption()">
  <% args = {'ns':ns, 'url':url, 'className':iname['className']} %>
  <h1>Objects associated with instance of
    ${utils.make_href('GetClass', args, iname['className'])}</h1>
</%def>
<%def name="content()">
  ${utils.show_instance_names([iname])}
  <hr />
  % if cim_error:
    ${self.print_cim_error("Failed to get reference names!")}
  % else:
    <h2>Associations Available</h2>
    % if len(associations):
      <ul id="associations">
        % for assoc in associations:
          <li><a id="#${assoc}">${assoc}</a></li>
        % endfor
      </ul>
    % endif
    <hr />
    % for assoc in associations:
      <% args = {'ns': ns, 'url':url, 'className':assoc} %>
      <table class="assoc details">
        <tr class="assoc_header">
          <th colspan="2">
            <a href="#${assoc}"></a>
            Association: ${utils.make_href('GetClass', args, assoc)}
          </th>
        </tr>
        % for ri, (role, refs) in enumerate(refmap[assoc]):
          ${utils.make_elem('tr', utils.make_count_tags(ri, len(refmap[assoc]), set(('role',))))}
            <td class="key">Role</td>
            <td class="value">${role}</td>
          </tr>
          % for rfi, (cls, namespace, insts) in enumerate(refs):
            <% cargs = {'ns':ns, 'url':url, 'className':cls} %>
            ${utils.make_elem('tr', utils.make_count_tags(rfi, len(refs), set(('type',))))}
              <td class="key">Type</td>
              <td class="value">${utils.make_href('GetClass', cargs, cls)}</td>
            </tr>
            <tr class="instance_names">
              <td colspan="2">
                ${utils.show_instance_names(insts)}
              </td>
            </tr>
          % endfor
        % endfor
      </table>
    % endfor
  % endif
</%def>
## ex:et:sw=2:ts=2
