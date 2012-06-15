<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />\
<%doc>
  template arguments:
  * className
  * instance
</%doc>
<%def name="subtitle()">Instance of ${className}</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('instance')}
</%def>
<%def name="caption()"><h1>Get Instance of ${className}</h1></%def>
<%def name="content()">
  ${utils.show_instance(instance)}
</%def>
## ex:et:sw=2:ts=2
