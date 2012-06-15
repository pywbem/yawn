<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  2 purposes:
   * modify existing instance of className
   * create a new one

  template arguments:
  * className
  * new: boolean saying, whether we are modifying existing or creating new one
  * instance: dictionary if modifying existing instance
  * items: list of properties if creating a new one
</%doc>
<%def name="subtitle()" filter="trim">
  ${'Create' if new else 'Modify'} Instance of ${className}
</%def>
<%def name="stylesheet()">
	${parent.stylesheet()}
  ${utils.res_css('instance')}
</%def>
<%def name="scripts()">
  ${parent.scripts()}
  ${utils.res_js('jquery.min')}
  ${utils.res_js('params')}
</%def>
<%def name="caption()">
  <% args = {'url':url, 'ns':ns, 'className':className} %>
  <h1>
    ${'Create' if new else 'Modify'} Instance of
    ${utils.make_href('GetClass', args, className)}
  </h1>
</%def>
<%def name="content()">
  <div class="${'new' if new else 'existing'}">
    <%
      args = {}
      if new:
        args['className'] = className
        params = items
        submit = 'Create Instance'
      else:
        args['path'] = instance['path']
        params = instance['props']
        submit = 'Save Instance'
      action = urls.build('CreateInstance' if new else 'ModifyInstance', args)
    %>
    ${utils.show_input_params(params, action=action, caption=False, submit=submit, prefix='PropName.')}
  </div>
</%def>
## ex:et:sw=2:ts=2
