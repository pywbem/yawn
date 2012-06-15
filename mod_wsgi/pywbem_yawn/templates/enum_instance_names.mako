<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
   * instances: array of dictionaries
</%doc>
<%def name="subtitle()">Instances of ${className}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance_names')}
</%def>
<%def name="caption()">
  <% cnt = sum(len(i[2]) for i in instances) %>
  <h1>${self.iname_caption(className, cnt)}</h1>
</%def>
<%def name="content()">
  <% args = {'ns':ns, 'url':url} %>
  % for cname, namespace, inames in instances:
    % if len(instances) > 1:
      <h2>${self.iname_caption(cname, inames)}</h2>
    % endif
    ${utils.show_instance_names(inames, whole_path=True)}
    <% cargs = args.copy(); cargs['className'] = className %>
    <p>${utils.make_href('CreateInstancePrep', cargs, 'Create New Instance')}</p>
  % endfor
</%def>\

<%def name="iname_caption(cname, inames)">
  <%
    args = {'ns':ns, 'url':url, 'className':cname}
    if isinstance(inames, int):
      cnt = inames
    else:
      cnt = len(inames)
  %>
  ${cnt if cnt != 1 else ''} Instance${'s' if cnt != 1 else ''} of
  ${utils.make_href('GetClass', args, cname)}
</%def>\
## ex:et:ts=2:sw=2
