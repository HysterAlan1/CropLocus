"""Assemble index.html from build/template.html, build/font.css, build/leaflet.min.js and build/data.js.

  python scripts/build_index.py
"""
import os
P = lambda *a: os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', *a)
rd = lambda *a: open(P(*a), encoding='utf-8').read()
t = rd('build', 'template.html')
for key, val in [('/*FONT*/', '<style>\n' + rd('build', 'font.css') + '\n</style>'),
                 ('/*LEAFLET*/', '<script>' + rd('build', 'leaflet.min.js') + '</script>'),
                 ('/*DATA*/', '<script>' + rd('build', 'data.js') + '</script>')]:
    assert t.count(key) == 1, key
    t = t.replace(key, val)
open(P('index.html'), 'w', encoding='utf-8').write(t)
print('wrote index.html', len(t), 'bytes')
