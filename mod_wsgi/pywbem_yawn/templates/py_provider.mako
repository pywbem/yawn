<%! from pywbem_yawn.filters import hs %>\
<%inherit file="base.mako" />
<%def name="head()"></%def>
<%def name="subtitle()">Python Provider for ${className}</%def>
<%def name="content()">
  <h3>Python Provider for ${className}</h3>
  <div class="code">
    <pre>
${code | n,hs,trim}
    </pre>
  </div>
  <h3>Provider Registration MOF</h3>
  % if cim_error:
    ${self.print_cim_error("Failed to get class details!")}
  % else:
    <div class="code">
      <pre>
${mof | n,hs,trim}
      </pre>
    </div>
  % endif
</%def>
## ex:et:sw=2:ts=2
