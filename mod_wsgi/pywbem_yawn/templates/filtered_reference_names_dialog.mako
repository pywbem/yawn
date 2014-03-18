<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * iname dictionary
</%doc>
<%def name="subtitle()">Filtered ReferenceNames Dialog ... (Coming...)</%def>
<%def name="scripts()">
  ${parent.scripts()}
  ${utils.res_js('jquery.min')}
  <script type="application/x-javascript">
    (function($) {
      $(document).ready(function($) {
        var toggle_inputs_visibility = function() {
          var objs = $("#assoc_class, #result_role");
          if ($("#call_type select").val().match(/^assoc/i) != null) {
            objs.show();
          }else {
            objs.hide();
          }
        };

        $("#call_type select").change(toggle_inputs_visibility);
        toggle_inputs_visibility();
      });
    })(jQuery);
  </script>
</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance_names')}
  ${utils.res_css('filtered_reference_names_dialog')}
</%def>
<%def name="caption()">
  <% args = {'ns':ns, 'url':url, 'verify':verify, 'className':className} %>
  <h1>Filtered References on Class ${utils.make_href('GetClass', args, className)}</h1>
</%def>
<%def name="content()">
  <%
    args = {'path':path }
  %>
  ${utils.show_instance_names([iname])}
  <form action="${urls.build('FilteredReferenceNames', args) | h}" method="post">
    <table id="filters">
      <tr id="assoc_class" title="Not applicable for Reference/ReferenceNames">
        <th>Association Class</th>
        <td><input type="text" name="assocClass" /></td>
      </tr>
      <tr id="result_class">
        <th>Result Class</th>
        <td><input type="text" name="resultClass" /></td>
      </tr>
      <tr id="role">
        <th>Role</th>
        <td><input type="text" name="role" /></td>
      </tr>
      <tr id="result_role" title="Not applicable for Reference/ReferenceNames">
        <th>Result Role</th>
        <td><input type="text" name="resultRole" /></td>
      </tr>
      <tr id="properties" title="Comma-separated">
        <th>Properties</th>
        <td><input type="text" name="properties" /></td>
      </tr>
      <tr id="call_type">
        <th>Call type</th>
        <td>
          <select name="assocCall">
            <option selected="selected" value="Associators">Associators</option>
            <option value="AssociatorNames">Associator Names</option>
            <option value="References">References</option>
            <option value="ReferenceNames">Reference Names</option>
          </select>
        </td>
      </tr>
      <tr id="submit">
        <td colspan="2">
          % for n, v in (('ns', ns), ('url', url), ('verify', verify)):
            <input type="hidden" name="${n}" value="${v | h}" />
          % endfor
          <input type="submit" value="Submit" />
        </td>
      </tr>
    </table>
  </form>
</%def>
## ex:et:ts=2:sw=2
