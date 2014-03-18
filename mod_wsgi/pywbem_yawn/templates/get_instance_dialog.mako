<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
  * className
  * items: list of key property dictionaries
</%doc>
<%def name="subtitle()" filter="trim">
  Get Instance of ${className}
</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance')}
  ${utils.res_css('ui-lightness/jquery-ui.min')}
  ${utils.res_css('ref_input')}
</%def>
<%def name="scripts()">
  ${parent.scripts()}
  % if not cim_error:
    ${utils.js_input_params(items, prefix='propname.')}
    ${utils.res_js('jquery.min')}
    ${utils.res_js('jquery-ui.min')}
    ${utils.res_js('ref_input')}
    ${utils.res_js('params')}
  % endif
</%def>
<%def name="caption()">
  <% args = {'url':url, 'ns':ns, 'verify':verify, 'className':className} %>
  <h1>Get Instance of
    ${utils.make_href('GetClass', args, className)}</h1>
</%def>
<%def name="content()">
  % if cim_err:
    ${self.print_cim_error("Failed to get class details!")}
  % else:
    <% action = urls.build('GetInstance', {'className':className, }) %>
    <div class="get">
      ${utils.show_input_params(items, action=action, read_only=False, caption=False, submit='Get Instance', prefix='propname.')}
    </div>
  % endif
</%def>
## ex:et:sw=2:ts=2
