/*
 * This expects url and ns variables defined.
 * This should be included before params.js.
 *
 * NOTE: does not support key arrays
 */
(function($) {
    $(document).ready(function() {

        var base_url = $('script').filter(function() {
            return typeof $(this).attr('src') != "undefined";
        }).attr('src').match(RegExp('^(.*)/static/'))[1];

        RegExp.escape = function(s) {
                return s.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')
        };

        var param_valmap_values = function(p, value) {
            var res = String(value);
            if (p.values[value]) {
                res += ' '+p.values[value];
            }
            return res;
        }

        var cimerror2str = function(message, class_name, data) {
            if (data.exception[0] == -1) { // not a pywbem.CIMError
                return message+' '+class_name+': '+data.exception[1];
            }
            return ( message+' '+class_name+': '+data.exception[0]
                   + ' ('+data.exception[1]+') - '+data.exception[2]);
        }

        var render_param_input = function(prefix, param, suffix) {
            if (!suffix) suffix = '';
            var param_name = prefix + param.name.toLowerCase() + suffix;
            if (param.is_valuemap) {
                var res = $('<select></select>');
                res.append('<option value=""></option>');
                $.each(param.valuemap, function(i, v) {
                    var v = param.valuemap[i];
                    $('<option></option>').val(v)
                        .text(param_valmap_values(param, v))
                        .appendTo(res);
                });
            }else if (param.type == "boolean") {
                var res = $('<select></select>');
                res.append('<option value=""></option>'+
                        '<option value="True">Yes</option>'+
                        '<option value="False">No</option>');
            }else {
                var res = $('<input type="text"></input>');
            }
            res.attr("name", param_name).attr('title', param.description);
            return res;
        }

        var reference_selected = function(ireftype, iname) {
            /*
            var iname = $this.data('reference');
            */
            var prefix = ireftype.attr('name').match(/(.*)-reftype$/)[1];
            $.each(iname.props, function(i, prop) {
                var prop = iname.props[i],
                    input = ireftype.parent().find(
                            '[name^="'+prefix+"."+prop.name.toLowerCase()+'"]');
                if (prop.is_valuemap) {
                    input.children().each(function() {
                        var $this = $(this); //option
                        $this.prop("selected",
                            $this.val() == String(prop.value_orig));
                    });
                }else if (prop.type == "boolean") {
                    input.children().each(function() {
                        var $this = $(this); //option
                        $this.prop("selected",
                            $this.val() == (prop.value_orig?'True':'False'));
                    });
                }else {
                    input.val(prop.value_orig);
                }
            });
        }

        var handle_query_reply = function(prop, ireftype, data, textStatus) {
            var ref_class_name = prop.type.className,
                lookup = ireftype.nextAll('button');
            if (data instanceof Array) {
                if (data.length == 0) {
                    lookup.after($('<span></span>')
                            .addClass('query-failed')
                            .text("No instances found!"));
                }else if (data.length == 1) {
                    reference_selected(ireftype, data[0]);
                }else {
                    var dialog = $('<div id="reference-selector"></div>')
                       .attr("title", ref_class_name + ' instance name select')
                    var tab = $('<table width="100%" height="100%"></table>').appendTo(dialog),
                        heading = $('<tr class="heading"></tr>').appendTo(tab);
                    $.each(data[0].props, function(i, prop) {
                        if (prop.is_key) {
                            heading.append($('<th></th>').text(prop.name));
                        }
                    });
                    $.each(data, function(i, iname) {
                        var row = $('<tr></tr>')
                                .addClass(["odd", "even"][i%2])
                                .appendTo(tab)
                                .hover( function() { $(this).addClass("selected"); }
                                      , function() { $(this).removeClass("selected"); });
                        $.each(iname.props, function(j, prop) {
                            if (prop.is_key) {
                                row.append($('<td></td>').text(prop.value_orig));
                            }
                        });
                        row.data('reference', iname)
                           .click(function() {
                            reference_selected(ireftype, $(this).data('reference'));
                            dialog.dialog("close").dialog("destroy");
                        });
                        tab.append(row);
                    });
                    dialog.dialog({width: "600", modal:true});
                }
            }else {
                lookup.after($('<span></span>').addClass('broker-error')
                        .text(cimerror2str('Failed to query instance names of',
                            ref_class_name, data)));
            }
        }

        /**
         * Constructs a query from input fields to server requesting list
         * of instances of particular class matching filled key properties.
         * On successful reply:
         *   - it fills the rest of keys, if just one instance matched the
         *     reply
         *   - it popups a dialog window, that allows user to select correct
         *     instance name to use
         * @param prop is an object holding details of key property
         * for corresponding cell
         * @param ireftype is a jQuery holding select element of reference
         * type
         */
        var lookup_instance_names = function(prop, ireftype) {
            var ref_class_name = prop['type']['className'],
                query = "SELECT * FROM "+ref_class_name,
                prefix = prop.name.toLowerCase()+'.',
                prop_regexp = RegExp('^'+RegExp.escape(prefix)+'(.*)'),
                lookup = ireftype.nextAll('button'),
                inputs = ireftype.parent()
                    .find('input, select').not(ireftype)
                    .filter(function() {
                        var $this = $(this);
                        return (  (  this.nodeName.toLowerCase() == "input"
                                  && $this.attr('type').toLowerCase()
                                     == 'checkbox')
                               || $this.val());
                    });
            if (inputs.size()) {
                query += " WHERE ";
                query += inputs.map(function() {
                    var $this = $(this),
                        ref_prop_name = $this.attr('name')
                                             .match(prop_regexp)[1],
                        ref_props = ireftype.parents('table')
                            .data('params')[ref_class_name];
                    for (var i=0; i < ref_props.length; ++i) {
                        if (ref_props[i].name.toLowerCase() == ref_prop_name) {
                            ref_prop = ref_props[i];
                            break;
                        }
                    }
                    if (  ref_prop.type == "boolean"
                       || (  typeof ref_prop.type == "string"
                          && ref_prop.type.toLowerCase().match(/^[su]int/))) {
                        val = $this.val();
                    }else {
                        val = '"'+$this.val()+'"';
                    }
                    return ref_prop_name+'='+val;
                }).get().join(" AND ");
            }
            $.ajax({
                url      : base_url+'/json_query_instances',
                data     : {"url":url, "ns":ns, "verify":verify, "query":query},
                dataType : 'json',
                beforeSend : function(req) {
                    if (typeof auth == "string")
                        req.setRequestHeader('Authorization', auth);
                },
                success  : function(data, textStatus) {
                    handle_query_reply(prop, ireftype, data, textStatus);
                    lookup.prop("enabled", true);
                },
                error    : function(jqXHR, textStatus) {
                    lookup.after($('<span></span>')
                            .addClass('broker-error')
                            .text( "Failed to query for matching instance"
                                 + " names: " + textStatus))
                          .nextAll('button').prop("enabled", true);
                }
            });
        }

        /**
         * Renders table with input fields for each key property of
         * reference class. It's supposed to be used as a callback function
         * to handle reply from server after async request.
         *
         * @param prop is an object holding details of key property
         * for corresponding cell
         * @param cell is a cell of table, that will be filled with
         * another table with inputs for each key property of reference
         * class
         * @param data are obtained from server, it's a list of objects
         * containing details about every key property
         * @param textStatus from callback
         */
        var load_ref_keys = function(prop, ireftype, data, textStatus) {
            var input_table = $('<table></table>'),
                param_type,
                ref_class_name = prop.type.className,
                root_table = ireftype.parents('table'),
                prefix = ireftype.attr("name").match(/^(.*)-reftype/)[1]+'.';
            if (data instanceof Array) {
                $.each(data, function(i, ref_prop) {
                    if (ref_prop.is_key) {
                        if (typeof(ref_prop.type) == 'string') {
                            param_type = ref_prop.type;
                        }else {
                            param_type = ref_prop.type.classname+' REF';
                        }
                        var row = $('<tr></tr>');
                        $('<td></td>').text(param_type).appendTo(row);
                        $('<td></td>').text(ref_prop.name).appendTo(row);
                        $('<td></td>').append(render_param_input(
                                    prefix, ref_prop)).appendTo(row);
                        input_table.append(row);
                    }
                });
                var lookup = $( '<button onclick="return false;">'
                              + 'Lookup</button>')
                    .attr('id', ireftype.attr("name").match(
                                /^(.*)-reftype$/)[1] + "-lookup")
                    .attr('title', 'Lookup all instance names matching given'
                                 + ' keys and allow to select one of them.')
                    .click(function() {
                        lookup_instance_names(prop, ireftype);
                        $(this).prop("enabled", false).nextAll().remove();
                    });
                ireftype.after(input_table);
                input_table.after(lookup);
                if (!root_table.data('params')) {
                    root_table.data('params', {});
                }
                root_table.data('params')[ref_class_name] = data;
            }else {
                var msg = cimerror2str('Failed to obtain class keys for ',
                        ref_class_name, data);
                ireftype.after($('<span class="ajax-error"></span>').text(msg));
            }
        }

        /**
         * Callback function for change of reference type selector.
         * It deletes content of cell value and loads correct input
         * fields for newly selected reference type.
         *
         * @param prop is an object holding details of key property
         * @param ireftype is a jQuery holding select element of reference
         * type
         * */
        var load_ref_input_fields = function(prop, ireftype) {
            ireftype.nextAll().remove();
            var reftype = ireftype.val(),
                root_table = ireftype.parents('table'),
                ref_class_name = prop.type.className,
                value_name = ireftype.attr('name').match(/^(.*)-reftype/)[1];
            /*
            // save the current key-values
            save_current_ref_path(prop, ireftype);
            */
            if (reftype == "keys") {
                if (  root_table.data('params')
                   && root_table.data('params')[ref_class_name]) {
                    load_ref_keys(prop, ireftype,
                            root_table.data('params')[ref_class_name]);
                }else {
                    $.ajax({
                        url      : base_url+'/json_get_class_keys/'+ref_class_name,
                        data     : {"url":url, "ns":ns, "verify":verify},
                        dataType : 'json',
                        success  : function(data, textStatus) {
                            load_ref_keys(prop, ireftype, data, textStatus);
                        },
                        error    : function(jqXHR, textStatus) {
                            ireftype.after($("<span></span>")
                                .addClass("broker-error")
                                .text(
                                    "Failed to obtain class keys"
                                     + " (status code: "
                                     + jqXHR.status+", status text: "
                                     + jqXHR.statusText + ")"));
                        },
                        beforeSend : function(req) {
                            if (typeof auth == "string")
                                req.setRequestHeader("Authorization", auth);
                        }
                    });
                }
            }else {
                $field = $('<input type="text"></input>')
                            .attr('id', value_name)
                            .attr('name', value_name);
                ireftype.after($field);
                v = reftype == "compressed" ? prop.value : prop.value_orig;
                if (v != null) {
                    $field.val(v);
                }
            }
            //restore_ref_path(prop, ireftype);
        }

        var transform_input = function($inp) {
            var keys_title = 'Input all keys individually.',
                cmp_title  = ( 'Insert a compressed string representation'
                             + ' of reference.'),
                raw_title  = ( 'Insert a raw reference key-value pairs in'
                             + ' format: Key1=\"Value1\",Key2=\"Value2\",...'),
                ireftype = $( '<select></select>').attr(
                    'name', $inp.attr("name").toLowerCase()+'-reftype'),
                prop_name = $inp.parent().attr('id').match(
                        /^param_value-((.*)[^.]+)/)[1],
                prop_details = input_param_details[prop_name],
                ref_class_name = prop_details['type']['className'],
                ireftype = $( '<select></select>').attr(
                    'name', $inp.attr("name").toLowerCase()+'-reftype');

            $('<option value="keys">Keys</option>').attr('title', keys_title)
                .add($('<option value="compressed">Compressed</option>')
                        .attr('title', title=cmp_title)
                        .prop('selected', prop_details.value != null))
                .add($('<option value="raw">Raw</option>')
                    .attr('title', raw_title))
                .appendTo(ireftype);

            ireftype.change(function() {
                load_ref_input_fields(prop_details, ireftype);
                var $this = $(this);
                $this.next().removeClass("raw").removeClass("compressed");
                if ($this.val() == 'raw' || $this.val() == 'compressed') {
                    $this.next().addClass($this.val());
                }
            });

            var $container = $('<div></div>')
                .attr('id', $inp.attr('id') + "-container")
                .addClass('container')
                .append(ireftype);
            $inp.after($container).remove();

            load_ref_input_fields(prop_details, ireftype);
            return $container;
        }

        $('#in_params .ref td.value').each(function() {
            var $this = $(this),
                prop_name = $this.attr('id').match(
                        /^param_value-((.*)[^.]+)/)[1],
                prop_details = input_param_details[prop_name],
                ref_class_name = prop_details['type']['className'];
            if (prop_details.is_array) {
                var $def = $this.find('input[id$="-default"]');
                transform_input($def)
                    .addClass('hidden')
                    .addClass('default')
                    .data('clone_callback', function(cloned) {
                        cloned.find('select[name$="-reftype"]')
                            .change(function() {
                                var $this = $(this);
                                load_ref_input_fields(prop_details, $this);
                                $this.next().removeClass("raw").removeClass("compressed");
                                if (  $this.val() == 'raw'
                                   || $this.val() == 'compressed') {
                                    $this.next().addClass($this.val());
                                }
                            }).change();
                    });
            }else {
                $this.find('input[type="text"]').each(function() {
                    transform_input($(this));
                });
            }

        });
    });
})(jQuery);
