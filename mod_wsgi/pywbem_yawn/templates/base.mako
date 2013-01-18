## -*- coding: utf-8 -*-
<%! from pywbem_yawn.filters import b64enc, hs %>\
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
    * urls    - url adapter
    * static  - url prefix for static files
    * conn    - pywbem connection object
    * url     - (optional) CIMOM url
    * ns      - (optional) namespace
    * heading - (optional) text situated in page's caption
</%doc>\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" 
   "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" >
  <head>
    <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
    ${self.stylesheet()}
    ${self.scripts()}
    <title>YAWN: CIM ${self.subtitle()}</title>
  </head>
  <body>
    ${self.head()}
    ${self.content()}
  </body>
</html>
<%def name="stylesheet()">
  ${utils.res_css('base')}
</%def>\

<%def name="scripts()">
<script type="text/javascript">
  % if url:
    var url="${url}";
  % endif
  % if ns:
    var ns="${ns}";
  % endif
  % if className:
    var className="${className}";
  % endif
  % if conn and conn.creds and len(conn.creds[0]):
    <% tok = "%s:%s"%conn.creds %>
    var auth = "Basic ${tok | b64enc}";
  % endif
</script>
</%def>\

<%def name="head()">
  <table id="top_header">
    <tr><td class="heading">
        ${self.caption()}
      </td>
    % if ns and url:
      <% args = {'ns':ns, 'url':url} %>
      <td class="enum_class_names nav">${utils.make_href('EnumClassNames', args, ns)}</td>
    % endif
    % if url:
      <% args = {'url':url} %>
      <td class="enum_namespaces nav">${utils.make_href('EnumNamespaces', args, 'Namespaces')}</td>
    % endif
    % if ns and url:
      <% args = {'ns':ns, 'url':url} %>
      <td class="query_d nav">${utils.make_href('QueryD', args, 'Query')}</td>
    % endif
      <td class="logout nav">${utils.make_href('Logout', target='Logout >>')}</td>
    </tr>
  </table>
</%def>\

<%def name="caption()">
  % if heading:
    <h1>${heading}</h1>
  % endif
</%def>\

<%def name="print_cim_error(what)">
  <table id="cim_error" class="${cim_error.lower()}">
    <tr class="title"><th colspan="2">Broker error</th></tr>
    <tr class="headers">
      <th>Error Code</th><th>Error Description</th>
    </tr>
    <tr><td id="cim_error_type">${cim_error}</td>
        <td id="cim_error_msg"><pre>${cim_error_msg | hs}</pre></td></tr>
  </table><br/>
  % if error_cause_description:
  <table id="cim_error_cause">
    <tr class="title">
      <th colspan="2">Possible cause</th>
    </tr><tr>
      <th class="description">Problem</th>
      <td class="cim_cause_description">${error_cause_description | hs}</td>
    </tr><tr>
      <th class="solution">Possible fix</th>
      <td class="cim_cause_suggestion">${error_cause_suggestion}</td>
    </tr> 
  </table>
  % endif
</%def> \
## ex:et:ts=2:sw=2
