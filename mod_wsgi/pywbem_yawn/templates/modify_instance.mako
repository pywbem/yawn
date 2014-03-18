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
  % if not cim_error:
    <% args = {'url':url, 'ns':ns, 'verify':verify, 'path':instance['path'] } %>
    <meta http-equiv="Refresh" content="1;url=${urls.build('GetInstance', args)}" />
  % endif
</%def>
<%def name="content()">
  % if cim_error:
    ${self.print_cim_error("Failed to %s instance!" % (
        "create" if new else "modify"))}
  % else:
    <% args = {'url':url, 'ns':ns, 'verify':verify, 'path':instance['path'] } %>
    The Instance has been saved. Refreshing...</br>
    If your browser doesn't refresh to the new instance,
    click ${utils.make_href_str('GetInstance', args, 'here')}.
  % endif
</%def>
## ex:et:sw=2:ts=2
