<%inherit file="base.mako" />
<%doc>
  template arguments:
   * className
   * compressed_obj
   * str_obj
   * xml_obj
</%doc>
<%def name="subtitle()">Object Serialization</%def>
<%def name="caption()">
  <h1>${className + "'s Object Serialization" | h}</h1>
</%def>
<%def name="content()">
  <div>
    To pass the following object as a Parameter Reference
    to a method call, copy this string to your clipboard and paste
    it to the parameter field.
  </div>
  <pre id="compressed">${compressed_obj | h}</pre>
  <hr />
  <pre id="text">${str_obj}</pre>
  <hr />
  <pre id="xml">${xml_obj | h}</pre>
</%def>
## ex:et:sw=2:ts=2
