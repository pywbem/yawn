<%inherit file="base.mako" />
<%doc>
  template arguments:
   * className
   * new: boolean saying,
          whether we are modifying existing or creating new one
   * instance: dictionary
</%doc>
<%def name="head()"></%def>
<%def name="subtitle()">Logging out ...</%def>
<%def name="scripts()">
  <meta http-equiv="Refresh" content="1;url=${urls.build('index')}" />
</%def>
<%def name="content()">
  Logging out ...
</%def>
## ex:et:sw=2:ts=2
