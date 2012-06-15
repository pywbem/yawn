<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * iname
</%doc>
<%def name="subtitle()">Deleted Instance of ${className}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance_names')}
</%def>
<%def name="caption()">
  <% args = { 'ns':ns, 'url':url, 'className':className } %>
    <h1>
      Deleted Instance of
      ${utils.make_href('GetClass', args, className)}
    </h1>
</%def>
<%def name="content()">
  ${utils.show_instance_names([iname], with_get_link=False)}
</%def>
## ex:et:ts=2:sw=2

