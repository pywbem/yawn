<%inherit file="codegen.mako" />
<%def name="subtitle()">CMPI Provider for ${className}</%def>
<%def name="code()" filter="trim,h">\
  <%include file="cmpi_provider_code.txt" args="className=className" />
</%def>
## ex:et:sw=2:ts=2
