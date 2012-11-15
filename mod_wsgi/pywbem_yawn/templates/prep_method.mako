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
</%def>
<%def name="caption()">
  <% args = {'ns':ns, 'url':url, 'className': className} %>
  <h1>Invoke method ${utils.make_href('GetClass', args, className, '#'+method_name)}
    on ${'Instance' if iname is not None else 'Class'}</h1>
</%def>
<%def name="content()">
  % if cim_error:
    ${self.print_cim_error("Failed to get class details!")}
  % else:
    % if iname is not None:
      ${utils.show_instance_names([iname])}
    % endif
    ${utils.show_input_params(in_params)}
    ${utils.show_output_params(out_params)}
    <h3 class="return_type">
      Method return type: ${utils.print_data_type(return_type)}
    </h3>
  % endif
</%def>
## ex:et:sw=2:ts=2
