<%inherit file="base.mako" />
<%def name="head()"></%def>
<%def name="content()">
  <h3>${self.subtitle()}</h3>
  <div class="code">
    <pre>
${self.code()}
    </pre>
  </div>
</%def>
## ex:et:sw=2:ts=2
