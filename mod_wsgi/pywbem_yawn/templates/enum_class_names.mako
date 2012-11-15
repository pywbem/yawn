<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
   * className may be None
   * lineage: [class_name1, ...]
   * mode is one of ['deep', 'shallow', 'flat']
   * classes - dictionary in format:
     { class_name1: [child1, child2, ...]
     , class_name2: [child1, child2, ...]
     , ...
     }
     array of children class names should be sorted
</%doc>\

<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('enum_class_names')}
</%def>\

<%def name="subtitle()">${"Classes in '%s'" % ns | h}</%def>\

<%def name="caption()"><h1>${"Classes in '%s/%s'" % (url, ns) | h}</h1></%def>\

<%def name="content()">
<% urlargs = {'ns':ns, 'url':url} %>
  <table class="nav">
    <tr>
      <td class="lineage">
      % if lineage:
        <%
          args = urlargs.copy();
          args['mode'] = mode
          lnhrefs = []
          lnhrefs.append(lineage[-1])
        %>
        ${utils.make_href('EnumClassNames', args, '<root>')}
        % for i, cname in enumerate(lineage):
          % if i >= len(lineage) - 1:
            / ${cname}
          % else:
            <% args['className'] = cname %>
            / ${utils.make_href('EnumClassNames', args, cname)}
          % endif
        % endfor
      % endif
      </td>
      <td class="listing_modes">
        <%
          modes = [m for m in ('deep', 'shallow') if m != mode]
          args = urlargs.copy()
        %>
        <table>
          <tr>
            <td colspan="2">Reload listing:</td>
            % for m in modes:
              <%
                args = urlargs.copy()
                args['mode'] = m
                if className is not None:
                  args['className'] = className
              %>
              <td>${utils.make_href('EnumClassNames', args, m.capitalize())}</td>
            % endfor
          </tr>
        </table>
      </td>
    </tr>
  </table>
<hr />
  % if classes:
    <table class="listing">
      <% start_class = 'None' if className is None else className %>
      ${utils.enum_classes(start_class, len(lineage))}
    </table>
  % elif cim_error:
    ${self.print_cim_error("Failed to enumerate class names!")}
  % endif
</%def>
## ex:et:ts=2:sw=2
