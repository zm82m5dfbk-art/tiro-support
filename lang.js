/* The language menu in the header (see tools/build-languages.py).
 * The menu is a <details>, so it opens and works without this script; this
 * only closes it on a click elsewhere or Escape, and remembers the language
 * picked, so the home page doesn't send that visitor anywhere else again. */
(function () {
  var KEY = 'tiro_site_lang';
  function closeAll(except) {
    var open = document.querySelectorAll('details.lang-switch[open]');
    for (var i = 0; i < open.length; i++) if (open[i] !== except) open[i].removeAttribute('open');
  }
  document.addEventListener('click', function (e) {
    var t = e.target;
    var menu = t.closest ? t.closest('details.lang-switch') : null;
    closeAll(menu);
    var link = t.closest ? t.closest('.lang-menu a[data-lang]') : null;
    if (link) { try { localStorage.setItem(KEY, link.getAttribute('data-lang')); } catch (err) { /* private mode */ } }
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeAll(null); });
})();
