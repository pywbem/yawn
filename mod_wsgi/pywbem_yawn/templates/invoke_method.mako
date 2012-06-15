<%! from pywbem_yawn.filters import hs %>\
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
  <% args = {'ns':ns, 'url':url, 'className':className} %>
  <h1>
    Invoked method ${utils.make_href('GetClass', args, className)}
    ::${utils.make_href('GetClass', args, method_name, '#'+method_name.lower())}()
  </h1>
</%def>
<%def name="content()">
  ${utils.show_input_params(in_params, read_only=True)}
  ${utils.show_output_params(out_params, with_values=True)}
  <div id="results">
    <span class="caption">Method returned:</span>
    <span class="value">${return_value | hs}</span>
  </div>
  <div class="nav">
    <% args = {'ns':ns, 'url':url, 'className':className} %>
    Return to class ${utils.make_href('GetClass', args, className)}
  </div>
  % if iname is not None:
    ${utils.show_instance_names([iname])}
  % endif
</%def>
## ex:et:sw=2:ts=2
