<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * error   - text description of error
   * details - dump
</%doc>\

<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('error')}
</%def>
<%def name="head()"></%def>
<%def name="subtitle()">Error</%def>\
<%def name="content()">
  % if error:
    <span class="description">${error | h}</div>
  % endif
  <pre class="details">${details | h}</pre>
  </hr>
  % if conn.last_request:
    <pre class="last_request">${conn.last_request | h}</pre>
  % endif
  % if conn.last_reply:
    <pre class="last_reply">${conn.last_reply | h}</pre>
  % endif
</%def>
## ex:et:ts=2:sw=2
