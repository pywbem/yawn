<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
  * className
  * instances
</%doc>
<%def name="subtitle()">Instances of ${className}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css("instance")}
</%def>
<%def name="caption()"><h1>Instances of ${className}</h1></%def>
<%def name="content()">
  % if cim_error:
    ${self.print_cim_error("Failed to enumerate instances!")}
  % else:
    <div class="stats">
    % if len(instances) == 0:
      No Instances
    % elif len(instances) > 1:
      Showing ${len(instances)} Instances
    % endif
    </div>
    <hr />
    % for inst in instances:
      ${utils.show_instance(inst)}
    % endfor
  % endif
</%def>
## ex:et:ts=2:sw=2
