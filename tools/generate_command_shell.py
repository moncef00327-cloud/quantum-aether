"""Generate shared Flask chrome directly from the imported review's rendered markup."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
for lang in ['ar','en']:
    source=(ROOT/f'templates/command/{lang}.html').read_text()
    aside=re.search(r'<aside\b.*?</aside>',source).group()
    aside=aside.replace('<aside ', '<aside id="command-sidebar" ',1)
    aside=aside.replace('href="#"', 'href="{{ url_for(\'site.index\', lang=lang) }}"')
    nav=re.search(r'<nav\b.*?</nav>',aside).group()
    buttons=re.findall(r'<button\b.*?</button>',nav)
    ids=['overview','scanner','tracker','monitor','guides','business','llm']
    destinations=["url_for('site.index',lang=lang)","url_for('site.index',lang=lang) ~ '#scanner'","url_for('site.adoption_page',lang=lang)","url_for('site.monitoring',lang=lang)","url_for('site.guides_index',lang=lang)","url_for('site.business_page',lang=lang)","url_for('site.index',lang=lang) ~ '#llm'"]
    for button,id,url in zip(buttons,ids,destinations):
        inner=re.sub(r'^<button[^>]*>|</button>$','',button)
        inner=re.sub(r'<i></i>$','',inner)
        a='<a href="{{ '+url+' }}" class="{% if command_section == \''+id+'\' %}active{% endif %}" {% if command_section == \''+id+'\' %}aria-current="page"{% endif %}>'+inner+"{% if command_section == '"+id+"' %}<i></i>{% endif %}</a>"
        nav=nav.replace(button,a)
    aside=re.sub(r'<nav\b.*?</nav>',lambda _:nav,aside)
    header=re.search(r'<header\b.*?</header>',source).group()
    header=re.sub(r'<b>.*?</b>', '<b>{{ command_title }}</b>',header,count=1)
    header=re.sub(r'<button(?=[^>]*aria-label="(?:التبديل|Switch))[^>]*>.*?</button>', '<a class="command-language" href="{{ localized_url(other_lang) }}" lang="{{ other_lang }}">{{ lang_names[other_lang] }}</a>',header)
    (ROOT/f'templates/command/sidebar-{lang}.html').write_text(aside+'\n')
    (ROOT/f'templates/command/header-{lang}.html').write_text(header+'\n')
