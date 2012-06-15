<%inherit file="base.mako" />
<%namespace name="utils" file="utils.mako" />
<%def name="subtitle()">Login</%def>
<%def name="stylesheet()">
  ${parent.stylesheet()}
  ${utils.res_css('index')}
</%def>
<%def name="head()"></%def>
<%def name="content()">
  <h1>
    % for w in ('yet', 'another', 'WBEM', 'navigator'):
      <span class="big">${w[0].upper()}</span>${w[1:]}
    % endfor
    (YAWN)
  </h1>
  <h3>${'"All CIM Browsers suck. This one sucks less"' | h}</h3>
  <hr />
  <form action="${urls.build('Login')}" method="post">
    <table>
      <tr>
        <td>URI Scheme:</td>
        <td><select name="scheme">
            <option value="https">https</option>
            <option value="http">http</option></select>
        </td>
      </tr><tr>
        <td>Host:</td><td><input id="host" type="text" name="host" /></td>
      </tr><tr>
        <td>Port:</td><td><input id="port" type="text" name="port" value="5989" /></td>
      </tr><tr>
        <td>Namespace:</td><td><input type="text" name="ns" /></td>
      </tr><tr class="submit">
        <td></td><td><input type="submit" value="Login" /></td>
      </tr>
    </table>
  </form>
  <hr />
  <div class="foot">
    <p>Powered by</p>
    <img src="http://www.modpython.org/mod_python.gif" alt="MOD_PYTHON" />
  </div>
</%def>
## ex:ts=2:sw=2
