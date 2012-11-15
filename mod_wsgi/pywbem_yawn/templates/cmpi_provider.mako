<%inherit file="codegen.mako" />
<%def name="subtitle()">CMPI Provider for ${className}</%def>
<%def name="code()" filter="trim,h">\
  % if cim_error:
    ${self.print_cim_error("Failed to generate code!")}
  % else:
    <%include file="cmpi_provider_code.txt" args="className=className" />
  % endif
</%def>
## ex:et:sw=2:ts=2
