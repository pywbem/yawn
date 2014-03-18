<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * instances - array of instance dictionaries
</%doc>
<%def name="subtitle()">AssociatorNames ${className}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance_names')}
</%def>
<%def name="caption()"></%def>
<%def name="content()">
  % if cim_error:
    ${self.print_cim_error("Failed to get associator names!")}
  % else:
    <% args = {'ns':ns, 'url':url, 'verify':verify} %>
    % for cname, namespace, inames in instances:
      <h2 class="className">${cname}</h2>
      ${utils.show_instance_names(inames, True)}
    % endfor
  % endif
</%def>
## ex:et:ts=2:sw=2
