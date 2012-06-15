<%! from pywbem_yawn.filters import hs %>\
<%inherit file="base.mako" />
<%def name="head()"></%def>
<%def name="subtitle()">Python Provider for ${className}</%def>
<%def name="content()">
  <h3>Python Provider for ${className}</h3>
  <div class="code">
    <pre>
${code | trim,hs}
    </pre>
  </div>
  <h3>Provider Registration MOF</h3>
  <div class="code">
    <pre>
${mof | trim,hs}
    </pre>
  </div>
</%def>
## ex:et:sw=2:ts=2
