#!/usr/bin/env python3
"""check_docs.py: the documentation check (no Blender, no render). From the repo root:

    python blender/tests/pipeline/check_docs.py

  1. every relative link in AGENTS.md, docs/*.md, blender/README.md and tools-guides/*.md points at a file that exists
  2. every Python module under blender/eidoblend/ is covered by docs/TOOLS.md (listed itself, or its family package)
  3. every guide in tools-guides/ is in AGENTS.md's table, and every guide that table names exists
Exit 0 when all hold; each problem is printed with its file.
"""
import glob
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
LINK = re.compile(r'\]\(([^)\s#]+)(?:#[^)]*)?\)')
problems = []


def md_files():
    out = ['AGENTS.md', 'blender/README.md'] + glob.glob('docs/*.md') + glob.glob('tools-guides/*.md')
    return [f.replace(os.sep, '/') for f in out if os.path.exists(f)]


def check_links():
    n = 0
    for md in md_files():
        text = open(md, encoding='utf-8').read()
        text = re.sub(r'```.*?```', '', text, flags=re.S)                  # links inside code blocks are examples
        for target in LINK.findall(text):
            if re.match(r'^[a-z]+:', target) or target.startswith('mailto:'):
                continue
            n += 1
            p = os.path.normpath(os.path.join(os.path.dirname(md), target.replace('%20', ' ')))
            if not os.path.exists(p):
                problems.append(f'{md}: broken link -> {target}')
    return n


def check_inventory():
    t = open('docs/TOOLS.md', encoding='utf-8').read()
    listed = {os.path.normpath(os.path.join('docs', l)).replace(os.sep, '/') for l in LINK.findall(t)}
    packages = {os.path.dirname(l) for l in listed if l.endswith('/__init__.py')}
    mods = [m.replace(os.sep, '/') for m in glob.glob('blender/eidoblend/**/*.py', recursive=True)
            if '__pycache__' not in m]
    for m in sorted(mods):
        if m in listed or any(m.startswith(p + '/') for p in packages if p != 'blender/eidoblend'):
            continue
        problems.append(f'docs/TOOLS.md: {m} is not covered (list it, or its family package)')
    return len(mods)


def check_index():
    agents = open('AGENTS.md', encoding='utf-8').read()
    named = set(re.findall(r'\(tools-guides/([a-z0-9-]+\.md)\)', agents))
    on_disk = {os.path.basename(g) for g in glob.glob('tools-guides/*.md')}
    for g in sorted(on_disk - named):
        problems.append(f'AGENTS.md: tools-guides/{g} is not in the guide table')
    for g in sorted(named - on_disk):
        problems.append(f'AGENTS.md: names tools-guides/{g}, which does not exist')
    return len(on_disk)


if __name__ == '__main__':
    os.chdir(ROOT)
    links = check_links()
    mods = check_inventory()
    guides = check_index()
    print(f'{links} links, {mods} eidoblend modules, {guides} guides checked')
    for p in problems:
        print('  ' + p)
    print('docs OK' if not problems else f'{len(problems)} problem(s)')
    sys.exit(1 if problems else 0)
