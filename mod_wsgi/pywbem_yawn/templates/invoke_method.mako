<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * iname: may be None
   * method_name
   * in_params
   * out_params
   * return_value
</%doc>
<%def name="subtitle()">Results of Method ${className}::${method_name}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance_names')}
  ${utils.res_css('instance')}
</%def>
<%def name="caption()">
  <% args = {'ns':ns, 'url':url, 'verify':verify, 'className':className} %>
  <h1>
    Invoked method ${utils.make_href('GetClass', args, className)}
    ::${utils.make_href('GetClass', args, method_name, '#'+method_name.lower())}()
  </h1>
</%def>
<%def name="content()">
  % if in_params:
    ${utils.show_input_params(in_params, read_only=True)}
  % endif
  % if cim_error:
    ${self.print_cim_error("Failed to invoke method!")}
  % else:
    % if out_params:
      ${utils.show_output_params(out_params, with_values=True)}
    % endif
    <div id="results">
      <span class="caption">Method returned:</span>
      <span class="value">${utils.print_data_value(return_value, True)}</span>
    </div>
  % endif
  <div class="nav">
    <% args = {'ns':ns, 'url':url, 'verify':verify, 'className':className} %>
    Return to class ${utils.make_href('GetClass', args, className)}
  </div>
  % if iname:
    ${utils.show_instance_names([iname])}
  % endif
</%def>
## ex:et:sw=2:ts=2
