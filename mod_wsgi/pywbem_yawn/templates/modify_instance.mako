<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
   * className
   * new: boolean saying,
          whether we are modifying existing or creating new one
   * instance: dictionary
</%doc>
<%def name="head()"></%def>
<%def name="subtitle()">Saving Instance Of ${className}</%def>
<%def name="scripts()">
  <% args = {'url':url, 'ns':ns, 'path':instance['path'] } %>
  <meta http-equiv="Refresh" content="1;url=${urls.build('GetInstance', args)}" />
</%def>
<%def name="content()">
  <% args = {'url':url, 'ns':ns, 'path':instance['path'] } %>
  The Instance has been saved. Refreshing...</br>
  If your browser doesn't refresh to the new instance,
  click ${utils.make_href_str('GetInstance', args, 'here')}.
</%def>
## ex:et:sw=2:ts=2
