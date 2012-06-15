<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * namespaces - list of strings without '/' at the beginning
   * nsd        - { 'namespace_name': number of instrumented classes }
</%doc>
<%def name="subtitle()">Namespaces</%def>
<%def name="caption()"><h1>CIM Namespaces in ${url}</h1></%def>
<%def name="content()">
  % if len(namespaces):
    <table class="namespaces">
    % for namespace in namespaces:
      <% args = {'ns':namespace, 'url':url, 'instOnly':False} %>
      <tr><td>${utils.make_href('EnumClassNames', args, namespace)}</td>
      % if namespace in nsd and nsd[namespace]:
        <%
          args['instOnly'] = True
          target = '%d Instrumented Classes' % nsd[namespace]
        %>
        <td class="inst_only">${utils.make_href('EnumClassNames', args, target)}</td>
      % endif
      </tr>
    % endfor
    </table>
  % else:
    <h1 class="error">Error</h1>
    Unable to enumerate Namespaces. Return to the
    ${utils.make_href('index', target="Login page")}
   and specify a Namespace.
    % if conn.last_reply is not None:
      <pre>${conn.last_reply | h}</pre>
    % endif
  % endif
</%def>
## ex:et:ts=2:sw=2
