<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * assoc_call  - one of [ associators, associatornames
                          , references, referencenames]
   * assoc_call_label
   * assoc_class
   * result_class
   * role
   * result_role
   * properties   - { key: value, ... }
   * results      - { class_name : [iname1, iname2, ...] }
</%doc>
<%def name="subtitle()">${assoc_call} ${assoc_class}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  % for css in ('instance', 'instance_names', 'filtered_reference_names'):
    ${utils.res_css(css)}
  % endfor
</%def>
<%def name="caption()">
  <% args = { 'ns':ns, 'url': url, 'className':className } %>
  <h1>
    Filtered Objects associated with instance of
    ${utils.make_href('GetClass', args, className)}
  </h1>
</%def>
<%def name="content()">
  <%
    params = [ ('ResultClass', result_class)
             , ('Role', role)
             , ('Properties', properties)]
    if assoc_call.startswith('associator'):
      params.insert(0, ('AssocClass', assoc_class))
      params.insert(3, ('ResultRole', result_role))
  %>
  <span id="call">${''.join(assoc_call_label.split(' '))}(
    % for i, (pname, pval) in enumerate(params):
      ${pname}="${pval | h}"${', ' if i < len(params) - 1 else ''}
    % endfor
  )</span>
  % if cim_error:
    ${self.print_cim_error("Failed to get %s!" % assoc_call_label)}
  % else:
    <div id="stats">Showing ${len(results)} resulting
      object${'s' if len(results) != 1 else ''}.</div><br />

    % for class_name, res in results:
      <hr />
      <% cargs = { 'ns':ns, 'url': url, 'className':class_name } %>
      <h2>Objects of Class ${utils.make_href('GetClass', cargs, class_name)}</h2>
      ${utils.show_instance_names(res)}
      % if assoc_call in ('associators', 'references'):
        % for inst in res:
          ${utils.show_instance(inst)}
        % endfor
      % endif
    % endfor
  % endif
</%def>
## ex:et:ts=2:sw=2
