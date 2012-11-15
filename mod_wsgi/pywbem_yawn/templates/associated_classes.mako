<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * associations:
     [ ( associated class name
       , via class name
       , role
       , role description
       , associated role
       , associated role description
       )
     , ...
     ]
</%doc>
<%def name="subtitle()">
  Classes Associated To ${className} in Namespace: ${ns}
</%def>
##<%def name="stylesheet()">
##  ${parent.stylesheet()}
##  ${utils.res_css('instance_names')}
##</%def>
<%def name="caption()">
  <% args = {'url':url, 'ns':ns, 'className':className} %>
    <h1>Classes Associated To ${utils.make_href('GetClass', args, className)}
      in Namespace: ${ns}</h1>
</%def>
<%def name="content()">
  % if cim_error:
    ${self.print_cim_error("Failed to list associated class names!")}
  % else:
    <table class="details">
      <tr class="headers">
        <th class="assoc_class_name">Associated Class Name</th>
        <th class="via">Via Association Class</th>
        <th class="role">Role</th>
        <th class="associated_role">Associated Role</th>
      </tr>
      <% args = {'url':url, 'ns':ns} %>
      % for i, (acn, vcn, role, roled, arole, aroled) in enumerate(associations):
        ${utils.make_elem('tr', utils.make_count_tags(i, len(associations)))}
          <% args['className'] = acn %>
          <td class="assoc_class_name">${utils.make_href('GetClass', args, acn)}</td>
          <% args['className'] = vcn %>
          <td class="via">${utils.make_href('GetClass', args, vcn)}</td>
          ${utils.make_elem('td', "role", roled)}${role}</td>
          ${utils.make_elem('td', "associated_role", aroled)}${arole}</td>
        </tr>
      % endfor
    </table>
  % endif
</%def>
## ex:et:ts=2:sw=2
