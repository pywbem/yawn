<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * method_name
   * iname: may be None
   * in_params
      [ { name: name
        , description: description
        , is_array: bool
        , is_required: bool
        , is_valuemap
        , class_origin
        , qualifiers: [ (qualname, qualvalue), ... ]
        , type: either string or {'ns':ns, 'className':class_name} if
                it is a reference
        , args: in case of method:
        , array_size: None if not given or not an array, int otherwise
        , ...
        }
      , ...
      ]
   * out_params - same parameters as above
   * return_type - may be None
</%doc>
<%def name="subtitle()">Method ${className}::${method_name}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance_names')}
  ${utils.res_css('instance')}
  ${utils.res_css('ui-lightness/jquery-ui.min')}
  ${utils.res_css('ref_input')}
</%def>
<%def name="scripts()">
  ${parent.scripts()}
  % if not cim_error:
    ${utils.js_input_params(in_params, prefix='methparam.')}
    ${utils.res_js('jquery.min')}
    ${utils.res_js('jquery-ui.min')}
    ${utils.res_js('ref_input')}
    ${utils.res_js('params')}
  % endif
</%def>
<%def name="caption()">
  <% args = {'ns':ns, 'url':url, 'verify':verify, 'className': className} %>
  <h1>Invoke method ${utils.make_href('GetClass', args, className)}
    ::${utils.make_href('GetClass', args, method_name, '#'+method_name.lower())}()
    on ${'Instance' if iname is not None else 'Class'}</h1>
</%def>
<%def name="content()">
  % if cim_error:
    ${self.print_cim_error("Failed to get class details!")}
  % else:
    % if iname is not None:
      ${utils.show_instance_names([iname])}
    % endif
    ${utils.show_input_params(in_params, prefix='methparam.')}
    ${utils.show_output_params(out_params)}
    <h3 class="return_type">
      Method return type: ${utils.print_data_type(return_type)}
    </h3>
  % endif
</%def>
## ex:et:sw=2:ts=2
