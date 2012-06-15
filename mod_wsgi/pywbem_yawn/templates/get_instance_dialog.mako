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
</%def>
<%def name="caption()">
  <% args = {'url':url, 'ns':ns, 'className':className} %>
  <h1>Get Instance of
    ${utils.make_href('GetClass', args, className)}</h1>
</%def>
<%def name="content()">
	<% action = urls.build('GetInstance', {'className':className, }) %>
	<div class="get">
    ${utils.show_input_params(items, action=action, read_only=False, caption=False, submit='Get Instance', prefix='PropName.')}
	</div>
</%def>
## ex:et:sw=2:ts=2
