## -*- coding: utf-8 -*-
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

<%def name="scripts()"></%def>\

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
  <table id="cim_error" class="${cim_error.lower()}" >
    <tr class="title"><th colspan="2">Broker error</th></tr>
    <tr class="headers">
      <th>Error Code</th><th>Error Description</th>
    </tr>
    <tr><td id="cim_error_type">${cim_error}</td>
        <td id="cim_error_msg"><pre>${cim_error_msg | h}</pre></td></tr>
  </table>
</%def> \
## ex:et:ts=2:sw=2
