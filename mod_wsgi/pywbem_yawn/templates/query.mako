<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
  * className: optional
  * qlang: query language
  * query
  * results: [inst1, inst2, ...]
</%doc>
<%def name="subtitle()">Query Results</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance')}
  ${utils.res_css('query')}
</%def>
<%def name="caption()"><h2>Query Results</h2></%def>
<%def name="content()">
  <table id="query_info" class="query">
    <tr class="lang">
      <th>Query Language:</th>
      <td>${qlang | h}</th>
    </tr>
    <tr class="query">
      <th>Query:</th>
      <td>${query | h}</td>
    </tr>
  </table>
  <p>
  % if cim_error:
    ${self.print_cim_error("Failed to get results for query!")}
  %else:
    % if len(results) == 0:
      No Instances
    % else:
      Showing ${len(results)} Instance${'s' if len(results) > 1 else ''}
    % endif
    </p>
    <hr />
    % for res in results:
      ${utils.show_instance(res)}
    % endfor
  % endif
</%def>
## ex:et:sw=2:ts=2
