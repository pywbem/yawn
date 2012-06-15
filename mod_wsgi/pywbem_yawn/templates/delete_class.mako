<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%doc>
  template arguments:
   * className
</%doc>
<%def name="subtitle()">Deleted class ${className}</%def>
<%def name="caption()">
  <h1>Deleted Class ${className}</h1>
</%def>
## ex:et:ts=2:sw=2
