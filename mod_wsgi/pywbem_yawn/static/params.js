(function($) {
  $(document).ready(function() {

    function init_remove($a) {
      $a.click(function() {
        $a.prev().remove();
        $a.nextAll('input, select')
          .not('input[type="button"], button, input[type="hidden"]')
          .each(function() {
          var $this    = $(this),
              index    = $this.attr('name').match(/-(\d+)$/)[1],
              new_name = $this.attr('name').replace(/-(\d+)$/, '-'+(index - 1));
          $this.attr('name', new_name);
        });
        $a.next('br').remove();
        $a.parent().find('input[type="hidden"]').each(function() {
          var $this = $(this);
          $this.val(parseInt($this.val()) - 1);
        });
        $a.remove();
      });
    }

    $('.in.params tr.array').not('.fixed_size').each(function() {
      var $this = $(this);
      $this.find('td.value').each(function() {
        var $this = $(this);
        init_remove($this.find('a'));
        // init add
        $this.find('input[type="button"], button').click(function() {
          var $this   = $(this),
              name    = $this.attr('id').match(/^(.*)_add$/)[1],
              $size   = $this.parent().find('input[type="hidden"]'),
              size    = parseInt($size.val()),
              $input  = $('<input type="text" name="'+name+'-'+size+'" />'),
              $remove = $('<a href="javascript://">-</a>');
          init_remove($remove);
          $this.before($input.add($remove).add('<br />'));
          $input.focus();
          $size.val(size + 1);
        });
      });
    });

  });
})(jQuery);
// ex:et:ts=2:sw=2
