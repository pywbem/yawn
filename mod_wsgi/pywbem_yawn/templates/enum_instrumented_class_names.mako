<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
   * className may be None
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
</%def>
<%def name="subtitle()">${"Classes in '%s'" % ns | h}</%def>
<%def name="caption()"><h1>${"Classes in '%s/%s'" % (url, ns) | h}</h1></%def>
<%def name="content()">
  % if cim_error:
    ${self.print_cim_error("Failed to enumerate instrumented class names!")}
  % else:
    <% urlargs = {'ns':ns, 'url':url} %>
    <table class="listing">
      <% start_class = 'None' if className is None else className %>
      ${utils.enum_classes(start_class)}
    </table>
  % endif
</%def>
## ex:et:ts=2:sw=2
