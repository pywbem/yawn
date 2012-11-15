(function($) {
    $(document).ready(function() {

        /*!
         * init the behaviour of item Remove link
         */
        function init_remove($a) {
            $a.click(function() {
                var $row = $a.parents('tr'),
                    row = parseInt($row.attr('id').match(/.*-row-(\d+)$/)[1]),
                    prefix = $row.attr('id').match(/^param-(.*)-row-\d+$/)[1],
                    re_inp_name = RegExp('^('+RegExp.escape(prefix)+
                            "-)(\\d+)"),
                    $next_prop_rows = $row.nextAll('tr[id^="param-'+
                        prefix+'-row-"]'),
                    $add_row = $next_prop_rows.last(),
                    $next_prop_rows = $next_prop_rows.not($add_row),
                    size = parseInt($add_row
                        .find('input[type="hidden"][name$=".size"]').val());

                $next_prop_rows.find('input, select, .container, button')
                    .add($next_prop_rows.find('.container')
                            .find('input, select, button'))
                    .each(function() {
                        // decrease indexes in ids and names of inputs by 1
                        var $this = $(this);
                        $.each(["id", "name"], function(i, attr) {
                            if ($this.attr(attr)) {
                                var index = parseInt(
                                    $this.attr(attr).match(re_inp_name)[2]);
                                $this.attr(attr, $this.attr(attr).replace(
                                        re_inp_name, '$1'+(index - 1)));
                            }
                        });
                    });
                // decrease size of array by one
                $add_row.find('input[type="hidden"][name$=".size"]')
                    .val(size - 1);
                // decrease the rowspan of first two cells from the left
                // (with name and type)
                (row == 1 ? $row
                          : $row.prevAll('tr[id="param-'+prefix+'-row-1"]'))
                    .children('td[id^="param_name"], td[id^="param_type"]')
                    .prop('rowspan', Math.max(1, size));
                // remove the last two cells of the first row
                $a.parent().add($a.parent().prev()).remove();
                // move the contents of the next row to this one
                $row.next().contents().detach().appendTo($row);
                // remove the next row
                $row.next().remove();
                // decrease indexes of the following rows by one
                $next_prop_rows.add($add_row).each(function(i) {
                    $(this).attr('id', 'param-'+prefix+'-row-'+(row+i));
                });
            }).hover(function() { // over
                    var $td = $(this).parent();
                    $td.add($td.prev()).addClass("select-to-remove");
                },
                function() { // out
                    var $td = $(this).parent();
                    $td.add($td.prev()).removeClass("select-to-remove");
            });
        }

        $('.in.params tr.array').not('.fixed_size').each(function() {
            var $this = $(this);
            $this.find("a.remove").each(function() {
                init_remove($(this));
            });
            $this.find('input[type="button"][id$="_add"], button[id$="_add"]')
                .click(function() {
                    var $this     = $(this),
                        name  = $this.attr('id').match(/^(.*)_add$/)[1],
                        $size = $this.parent().find('input[type="hidden"]'),
                        size  = parseInt($size.val()),
                        $def_inp= $this.parent().find('.hidden'
                            +'[id$="-default"],'
                            +' .hidden[id$="-default-container"]'),
                        $new_def_inp = $def_inp.clone(),
                        inp_name = name + "-" + size,
                        re_id_sub = RegExp('^('+RegExp.escape(name)+
                                "-)default"),
                        new_def_inp_name = $new_def_inp.attr("id")
                                .replace(re_id_sub, "$1"+size),
                        $remove = $('<a href="javascript://">X</a>')
                            .addClass("remove"),
                        $row = $this.parents('tr').first(),
                        $new_row = $('<tr></tr>')
                            .attr('id', 'param-'+name+'-row-'+(size + 2))
                            .attr('class', $row.attr('class'));
                    init_remove($remove);
                    $new_def_inp.attr('id', new_def_inp_name)
                        .each(function() {
                            var $this = $(this);
                            if ($this.attr('name')) $this.attr('name', new_def_inp_name);
                        })
                        .removeClass('hidden')
                        .removeClass('default')
                        .find('input, select, button').each(function() {
                                var $this = $(this);
                                $.each(["id", "name"], function(i, attr) {
                                    if ($this.attr(attr)) {
                                        $this.attr(attr, $this.attr(attr)
                                            .replace(re_id_sub, "$1"+size));
                                    }
                                });
                        });

                    $this.parent().detach().appendTo($new_row);
                    $row.append($('<td></td>').addClass('array_item')
                            .append($new_def_inp))
                        .append($('<td></td>').addClass('remove')
                            .append($remove));
                    $def_inp.data('clone_callback')

                    if ($def_inp.data('clone_callback')) {
                            $def_inp.data('clone_callback')($new_def_inp);
                    }
                    $size.val(size + 1);
                    (size == 0 ? $row
                              : $row.prevAll('tr[id="param-'+name+'-row-1"]'))
                        .children('td[id^="param_name"], td[id^="param_type"]')
                        .prop('rowspan', size + 2);
                    $row.after($new_row);
                    $new_def_inp.focus();
            });
        });
    });
})(jQuery);
// ex:et:ts=4:sw=4
