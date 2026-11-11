"""Build the site's other languages from the English pages.

    python3 tools/build-languages.py          # build es/ pt/ fr/ and refresh the English pages' menus
    python3 tools/build-languages.py --list   # every English text the translations need

The English pages at the top of the site are the source: edit those, then run
this. For each translated page (PAGES) it writes es/, pt/ and fr/ copies with
exactly the same markup — only the text changes, from tools/i18n/<lang>.py
(English text → translation) — so a layout change never has to be made four
times. Links to files that aren't translated (privacy, terms, styles, assets)
are pointed back up a folder.

Blocks between <!-- name --> … <!-- /name --> are written here, on every page:
  lang        the language menu in the header (+ lang.js)
  alternates  canonical, og:url and hreflang links (search engines)
  autolang    the English home page only: a first visit from a phone set to
              Spanish, Portuguese or French goes to that language's home
              (never again once a language is picked from the menu)

It stops, writing nothing, if any English text has no translation — and lists
them. Text without letters (numbers, times) is kept as it is, unless the
language's file has it (a decimal comma: "62,5"). """
import html
import os
import re
import runpy
import sys
from html.parser import HTMLParser

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SITE = 'https://tiro-football.com/'
LANGS = ['en', 'es', 'pt', 'fr']
CODE = {'en': 'en', 'es': 'es', 'pt': 'pt-BR', 'fr': 'fr'}
NAME = {'en': 'English', 'es': 'Español', 'pt': 'Português', 'fr': 'Français'}
PAGES = ['index.html', 'support.html']                 # translated
ENGLISH_ONLY = ['privacy.html', 'terms.html']          # menu links to each language's home
TRANSLATE_ATTRS = {'aria-label', 'title', 'alt'}
META_CONTENT = {('name', 'description'), ('property', 'og:title'), ('property', 'og:description')}
BLOCK = re.compile(r'<!-- (lang|alternates|autolang) -->.*?<!-- /\1 -->', re.S)
GLOBE = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
         'stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>'
         '<path d="M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9s1.3-6.4 3.8-9z"/></svg>')


def url_path(lang, page):
    """The page's path from the site's root."""
    folder = '' if lang == 'en' else lang + '/'
    return folder + ('' if page == 'index.html' else page)


def rel(from_lang, to_lang, page):
    """A link from a page in `from_lang` to `page` in `to_lang`."""
    if from_lang == to_lang:
        return page
    up = '' if from_lang == 'en' else '../'
    folder = '' if to_lang == 'en' else to_lang + '/'
    return up + folder + page


def lang_block(lang, page, t):
    up = '' if lang == 'en' else '../'
    items = []
    for other in LANGS:
        target = page if page in PAGES else 'index.html'
        here = ' aria-current="page"' if other == lang and page in PAGES or (page not in PAGES and other == 'en') else ''
        items.append(f'<li><a href="{rel(lang, other, target)}" lang="{CODE[other]}" hreflang="{CODE[other]}" '
                     f'data-lang="{other}"{here}>{NAME[other]}</a></li>')
    label = html.escape(t('Language'), quote=True)
    return (f'<details class="lang-switch"><summary aria-label="{label}">{GLOBE}<span>{lang.upper()}</span></summary>'
            f'<ul class="lang-menu">{"".join(items)}</ul></details><script src="{up}lang.js" defer></script>')


def alternates_block(lang, page):
    out = [f'<link rel="canonical" href="{SITE}{url_path(lang, page)}">']
    if page == 'index.html':
        out.append(f'<meta property="og:url" content="{SITE}{url_path(lang, page)}">')
    for other in LANGS:
        out.append(f'<link rel="alternate" hreflang="{CODE[other]}" href="{SITE}{url_path(other, page)}">')
    out.append(f'<link rel="alternate" hreflang="x-default" href="{SITE}{url_path("en", page)}">')
    return '\n'.join(out)


AUTOLANG = ("<script>(function(){try{if(localStorage.getItem('tiro_site_lang'))return;}catch(e){return;}"
            "var l=((navigator.languages&&navigator.languages[0])||navigator.language||'').toLowerCase().slice(0,2);"
            "if(l==='es'||l==='pt'||l==='fr')location.replace(l+'/');})();</script>")


def fill_blocks(src, lang, page, t):
    def one(m):
        name = m.group(1)
        if name == 'lang':
            body = lang_block(lang, page, t)
        elif name == 'alternates':
            body = alternates_block(lang, page)
        else:
            body = AUTOLANG if (lang == 'en' and page == 'index.html') else ''
        return f'<!-- {name} -->{body}<!-- /{name} -->'
    return BLOCK.sub(one, src)


def empty_blocks(src):
    return BLOCK.sub(lambda m: f'<!-- {m.group(1)} --><!-- /{m.group(1)} -->', src)


def norm(s):
    return ' '.join(s.split())


def has_letters(s):
    return re.search(r'[^\W\d_]', s) is not None


class Scan(HTMLParser):
    """Finds the text runs and the start tags, with where they are in the source."""

    def __init__(self, src):
        super().__init__(convert_charrefs=False)
        self.src = src
        starts = [0]
        for i, ch in enumerate(src):
            if ch == '\n':
                starts.append(i + 1)
        self.line_starts = starts
        self.runs = []      # (start, end, raw)
        self.tags = []      # (start, end, tag, attrs)
        self.run = None
        self.stack_skip = 0

    def at(self):
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def flush(self):
        if self.run:
            self.runs.append(self.run)
            self.run = None

    def add_text(self, raw):
        if self.stack_skip:
            return
        start = self.at()
        if self.run and self.run[1] == start:
            self.run = (self.run[0], start + len(raw), self.run[2] + raw)
        else:
            self.flush()
            self.run = (start, start + len(raw), raw)

    def handle_data(self, data):
        self.add_text(data)

    def handle_entityref(self, name):
        self.add_text(f'&{name};')

    def handle_charref(self, name):
        self.add_text(f'&#{name};')

    def handle_starttag(self, tag, attrs):
        self.flush()
        raw = self.get_starttag_text()
        start = self.at()
        self.tags.append((start, start + len(raw), tag, attrs))
        if tag in ('script', 'style'):
            self.stack_skip += 1

    def handle_startendtag(self, tag, attrs):
        self.flush()
        raw = self.get_starttag_text()
        start = self.at()
        self.tags.append((start, start + len(raw), tag, attrs))

    def handle_endtag(self, tag):
        self.flush()
        if tag in ('script', 'style') and self.stack_skip:
            self.stack_skip -= 1

    def handle_comment(self, data):
        self.flush()

    def handle_decl(self, decl):
        self.flush()

    def close(self):
        super().close()
        self.flush()


def texts_of(src):
    """Every text the page needs translated: (kind, English)."""
    sc = Scan(src)
    sc.feed(src)
    sc.close()
    found = []
    for start, end, raw in sc.runs:
        key = norm(html.unescape(raw))
        if key and has_letters(key):
            found.append(key)
    for start, end, tag, attrs in sc.tags:
        a = dict(attrs)
        for name, value in attrs:
            if value and (name in TRANSLATE_ATTRS or (tag == 'meta' and name == 'content' and any(a.get(k) == v for k, v in META_CONTENT))):
                if has_letters(value):
                    found.append(norm(value))
    return sc, found


def local_link(value):
    return not re.match(r'^(?:[a-z][a-z0-9+.-]*:|#|/)', value)


def translate_page(src, lang, page, d):
    t = d.__getitem__
    has = d.__contains__   # text without letters (a number) only if the language writes it differently
    src = empty_blocks(src)
    sc, _ = texts_of(src)
    edits = []   # (start, end, new)
    for start, end, raw in sc.runs:
        key = norm(html.unescape(raw))
        if not key or not (has_letters(key) or has(key)):
            continue
        lead = raw[:len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        edits.append((start, end, lead + html.escape(t(key), quote=False) + trail))
    for start, end, tag, attrs in sc.tags:
        raw = src[start:end]
        new = raw
        a = dict(attrs)
        for name, value in attrs:
            if value is None:
                continue
            repl = None
            if name in TRANSLATE_ATTRS or (tag == 'meta' and name == 'content' and any(a.get(k) == v for k, v in META_CONTENT)):
                if has_letters(value):
                    repl = t(norm(value))
            elif name in ('href', 'src') and local_link(value):
                file = value.split('#')[0]
                repl = value if file in PAGES else '../' + value
            elif tag == 'html' and name == 'lang':
                repl = CODE[lang]
            if repl is not None and repl != value:
                pat = re.compile(r'(\b' + re.escape(name) + r'\s*=\s*)(["\'])(.*?)\2', re.S)
                new = pat.sub(lambda m: m.group(1) + '"' + html.escape(repl, quote=True) + '"', new, count=1)
        if new != raw:
            edits.append((start, end, new))
    out = src
    for start, end, new in sorted(edits, reverse=True):
        out = out[:start] + new + out[end:]
    return fill_blocks(out, lang, page, t)


def main():
    sources = {p: open(os.path.join(ROOT, p), encoding='utf-8').read() for p in PAGES + ENGLISH_ONLY}
    needed = []
    for p in PAGES:
        for key in texts_of(empty_blocks(sources[p]))[1] + ['Language']:
            if key not in needed:
                needed.append(key)
    if '--list' in sys.argv:
        for k in needed:
            print(repr(k))
        return

    dicts = {l: runpy.run_path(os.path.join(ROOT, 'tools', 'i18n', f'{l}.py'))['T'] for l in LANGS if l != 'en'}
    missing = {l: [k for k in needed if k not in d] for l, d in dicts.items()}
    if any(missing.values()):
        for l, keys in missing.items():
            for k in keys:
                print(f'{l}: no translation for {k!r}')
        sys.exit(1)
    for l, d in dicts.items():
        stale = [k for k in d if k not in needed and has_letters(k)]
        for k in stale:
            print(f'{l}: not used any more: {k!r}')

    # the English pages: just their menu and links
    for p, src in sources.items():
        out = fill_blocks(src, 'en', p, lambda k: k)
        if out != src:
            open(os.path.join(ROOT, p), 'w', encoding='utf-8').write(out)
            print(f'en  {p}')
    for l, d in dicts.items():
        os.makedirs(os.path.join(ROOT, l), exist_ok=True)
        for p in PAGES:
            out = translate_page(sources[p], l, p, d)
            open(os.path.join(ROOT, l, p), 'w', encoding='utf-8').write(out)
            print(f'{l}  {p}')


if __name__ == '__main__':
    main()
