<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
  * className: optional
</%doc>
<%def name="subtitle()">Query</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('query')}
</%def>
<%def name="caption()"><h2>Execute Query</h2></%def>
<%def name="content()">
  <form action="${urls.build('Query')}" method="post">
    <table id="query" class="query">
      <tr>
        <th>Query Language:</th>
        <td>
          <select name="lang">
            <option value="WQL">WQL</option>
          </select>
        </td>
      </tr>
      <tr>
        <th>Query:</th>
        <td><input type="text" value="SELECT * FROM ${className} WHERE" name="query" /></td>
      </tr>
    </table>
    <div class="submit">
      <input type="hidden" name="url" value="${url | h}" />
      <input type="hidden" name="ns" value="${ns | h}" />
      <input type="submit" value="Execute Query" />
    </div>
  </form>
</%def>
## ex:et:sw=2:ts=2
