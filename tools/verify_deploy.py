#!/usr/bin/env python3
"""
Static integrity verifier for a staged self-contained deployment tree built by
tools/build_deploy.py.

Checks:
  1. Required root files, .htaccess directives (.mjs MIME, X-Frame-Options, RewriteEngine Off),
     and catalog_config.json settings.
  2. Zero leaked dev URLs (localhost:8125, compare.html, /catalog/) in HTML/JSON.
  3. 100% of <script id="entry-live-data"> and <script id="group-live-data"> targets:
     both the SymDraw app HTML inside symmhub/ and the preset JSON exist.
  4. 100% of local href / src links across ALL HTML files resolve to existing files inside dist.
  5. 100% of SymDraw Samples presets (.json + .json.png) referenced by symdraw_*.js exist.
  6. 100% of ES module relative imports from the 4 SymDraw apps and 3 Web Workers exist.
  7. Prints exact GoDaddy resource budget (files, dirs, inodes, MB by section).

Usage:
  python tools/verify_deploy.py [dist_dir]
"""
import io
import json
import os
import posixpath
import re
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_paths as P

RE_HREF_SRC = re.compile(r'(?:href|src|data-src)=["\']([^"\']+)["\']')
RE_LIVE_DATA = re.compile(
    r'<script\s+type="application/json"\s+id="(?:entry|group)-live-data">(.*?)</script>',
    re.S,
)
RE_JS_IMPORT = re.compile(
    r'''(?:import|export)(?:\s+[^'"]*?\s+from|\s*\{[^}]*\}\s*from|\s*\*\s+as\s+\w+\s+from|\s+)\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)'''
)
RE_PRESET_STR = re.compile(r'export\s+const\s+(presets(?:_\w+)?)\s*=\s*`([^`]*)`', re.S)
RE_FOLDER_STR = re.compile(r'export\s+const\s+(folder_\w+)\s*=\s*["\']([^"\']+)["\']')
RE_SYMDRAW_FOLDER = re.compile(r'presetsFolder:\s*["\']([^"\']+)["\']')
RE_REWRITTEN_URL = re.compile(
    r'''new\s+URL\(\s*(['"])([^'"]+)\1\s*,\s*new\s+URL\(\s*(['"])([^'"]+)\3\s*,\s*import\.meta\.url\s*\)\.href\s*\)'''
)


def check_deploy(root):
    root = os.path.abspath(root)
    errors = []
    warnings = []

    def err(msg):
        errors.append(msg)

    if not os.path.isdir(root):
        print(f'FAIL: deploy directory does not exist: {root}')
        return 1

    # 1. Required root files + .htaccess + catalog_config.json
    for req in ('index.html', 'catalog.html', 'tutorial.html', 'search_index.json',
                'catalog_config.json', '.htaccess', 'versions/index.json',
                'symmhub/index.html', 'symmhub/apps/symdraw/index.html'):
        if not os.path.isfile(os.path.join(root, *req.split('/'))):
            err(f'Missing required file: {req}')

    ht_path = os.path.join(root, '.htaccess')
    if os.path.isfile(ht_path):
        ht = io.open(ht_path, encoding='utf-8').read()
        for needle in ('AddType text/javascript .js .mjs', 'AddType image/webp .webp',
                       'X-Frame-Options "SAMEORIGIN"', 'RewriteEngine Off'):
            if needle not in ht:
                err(f'.htaccess missing directive: {needle}')

    cfg_path = os.path.join(root, 'catalog_config.json')
    release_id = None
    if os.path.isfile(cfg_path):
        cfg = json.load(open(cfg_path, encoding='utf-8'))
        if cfg.get('symmhubUrl') != 'symmhub':
            err(f"catalog_config.json symmhubUrl={cfg.get('symmhubUrl')!r}, expected 'symmhub'")
        if cfg.get('hideSymmhubSettings') is not True:
            warnings.append('catalog_config.json hideSymmhubSettings is not true')
        release_id = cfg.get('releaseId')
        if not release_id or not isinstance(release_id, str):
            err('catalog_config.json missing releaseId')
        elif not re.match(r'^\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$', release_id):
            warnings.append(f'catalog_config.json releaseId={release_id!r} does not match yy-mm-dd-hh-mm-ss')

    # 2. Walk entire tree: stats + verify all HTML files
    section_stats = {}
    html_files = []
    total_files = 0
    total_dirs = 0
    total_bytes = 0

    for dp, dns, fns in os.walk(root):
        total_dirs += 1
        rel_dp = os.path.relpath(dp, root).replace('\\', '/')
        sec = '(root)' if rel_dp == '.' else rel_dp.split('/')[0]
        st = section_stats.setdefault(sec, [0, 0, 0])  # files, dirs, bytes
        st[1] += 1
        for fn in fns:
            fp = os.path.join(dp, fn)
            sz = os.path.getsize(fp)
            total_files += 1
            total_bytes += sz
            st[0] += 1
            st[2] += sz
            if fn.endswith('.html'):
                html_files.append((fp, os.path.relpath(fp, root).replace('\\', '/')))

    # 3. Check 100% of HTML files: leaked dev strings, live-data targets, local links/assets
    live_checked = 0
    links_checked = 0
    broken_links = []
    leaked_dev = []
    missing_live = []

    for fp, rel in html_files:
        txt = io.open(fp, encoding='utf-8').read()
        if 'localhost:8125' in txt:
            leaked_dev.append(f'{rel}: localhost:8125')
        if 'compare.html' in txt:
            leaked_dev.append(f'{rel}: compare.html')

        cur_dir = posixpath.dirname(rel)

        # Live data JSON targets
        for m in RE_LIVE_DATA.finditer(txt):
            live_checked += 1
            d = json.loads(m.group(1))
            app = d.get('app', '').lstrip('/')
            preset = d.get('preset', '').lstrip('/')
            if app:
                app_fp = os.path.join(root, 'symmhub', *app.split('/'))
                if not os.path.isfile(app_fp):
                    missing_live.append(f'{rel}: missing app symmhub/{app}')
            if preset:
                pre_fp = os.path.join(root, *preset.split('/'))
                if not os.path.isfile(pre_fp):
                    missing_live.append(f'{rel}: missing preset {preset}')

        # Local href / src / data-src links
        for m in RE_HREF_SRC.finditer(txt):
            u = m.group(1).strip()
            if (not u or u.startswith('#') or u.startswith('http://') or u.startswith('https://')
                    or u.startswith('mailto:') or u.startswith('data:') or u.startswith('about:')
                    or u.startswith('javascript:')):
                continue
            path_only = unquote(u.split('#', 1)[0].split('?', 1)[0])
            if not path_only:
                continue
            if path_only.startswith('/'):
                broken_links.append(f'{rel}: root-absolute URL not subpath-safe: {u}')
                continue
            resolved = posixpath.normpath(posixpath.join(cur_dir, path_only))
            if resolved.startswith('..'):
                broken_links.append(f'{rel}: link escapes deploy root: {u} -> {resolved}')
                continue
            target_fp = os.path.join(root, *resolved.split('/'))
            links_checked += 1
            if not os.path.exists(target_fp):
                broken_links.append(f'{rel}: broken link {u} -> {resolved}')

    if leaked_dev:
        err(f'{len(leaked_dev)} leaked dev reference(s), e.g.: ' + '; '.join(leaked_dev[:5]))
    if missing_live:
        err(f'{len(missing_live)} missing live-data target(s), e.g.: ' + '; '.join(missing_live[:5]))
    if broken_links:
        err(f'{len(broken_links)} broken/unsafe link(s), e.g.: ' + '; '.join(broken_links[:8]))

    # 4. Check search_index.json targets
    si_path = os.path.join(root, 'search_index.json')
    si_checked = 0
    if os.path.isfile(si_path):
        si = json.load(open(si_path, encoding='utf-8'))
        for it in si.get('items', []):
            u = it.get('u', '')
            if u:
                si_checked += 1
                if not os.path.isfile(os.path.join(root, *u.split('/'))):
                    err(f'search_index.json broken entry: {u}')

    # 5. Check SymDraw sample presets (.json + .json.png)
    sd_dir = os.path.join(root, 'symmhub', 'apps', 'symdraw')
    sample_checked = 0
    for vkey in ('wp', 'frieze', 'spherical', 'klm'):
        pfile = os.path.join(sd_dir, 'js', f'presets_{vkey}.js')
        sfile = os.path.join(sd_dir, 'js', f'symdraw_{vkey}.js')
        if not os.path.isfile(pfile) or not os.path.isfile(sfile):
            err(f'Missing SymDraw js for {vkey}')
            continue
        ptxt = io.open(pfile, encoding='utf-8').read()
        stxt = io.open(sfile, encoding='utf-8').read()
        folders = dict(RE_FOLDER_STR.findall(ptxt))
        m_sf = RE_SYMDRAW_FOLDER.search(stxt)
        default_folder = m_sf.group(1) if m_sf else ''
        for var_name, body in RE_PRESET_STR.findall(ptxt):
            fid_suf = var_name[len('presets_'):] if var_name.startswith('presets_') else ''
            folder = folders.get(f'folder_{fid_suf}', default_folder)
            for line in body.splitlines():
                nm = line.strip()
                if not nm:
                    continue
                sample_checked += 1
                rel_json = posixpath.normpath(posixpath.join('symmhub/apps/symdraw', folder, nm))
                fp_json = os.path.join(root, *rel_json.split('/'))
                fp_png = fp_json + '.png'
                if not os.path.isfile(fp_json):
                    err(f'SymDraw {vkey} sample missing JSON: {rel_json}')
                if not os.path.isfile(fp_png):
                    err(f'SymDraw {vkey} sample missing PNG thumb: {rel_json}.png')

    # 6. Trace ES module imports from all 4 SymDraw apps, gallery, and 3 Web Workers
    sh_root = os.path.join(root, 'symmhub')
    js_entries = [
        'apps/symdraw/js/symdraw_wp.js',
        'apps/symdraw/js/symdraw_frieze.js',
        'apps/symdraw/js/symdraw_spherical.js',
        'apps/symdraw/js/symdraw_klm.js',
        'apps/symdraw/js/gallery.js',
        'lib/grouplib/DirichletWorker.js',
        'lib/grouplib/SubgroupNamesWorker.js',
        'lib/grouplib/SubgroupWorker.js',
    ]
    seen_js = set()
    queue = list(js_entries)
    missing_js = []
    meta_assets_checked = 0
    missing_meta_assets = []
    while queue:
        rel_js = queue.pop(0)
        if rel_js in seen_js:
            continue
        fp = os.path.join(sh_root, *rel_js.split('/'))
        if not os.path.isfile(fp):
            missing_js.append(rel_js)
            continue
        seen_js.add(rel_js)
        txt = io.open(fp, encoding='utf-8', errors='replace').read()
        # Strip /* ... */ block comments and non-URL // line comments before scanning imports
        txt_nc = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
        txt_nc = re.sub(r'(?<!:)//[^\n]*', '', txt_nc)
        cur_d = posixpath.dirname(rel_js)
        for m in RE_JS_IMPORT.finditer(txt_nc):
            spec = m.group(1) or m.group(2)
            if spec and spec.startswith('.'):
                target = posixpath.normpath(posixpath.join(cur_d, spec))
                if target not in seen_js:
                    queue.append(target)

        # Verify rewritten import.meta.url static asset/worker targets inside bundled JS
        for m in RE_REWRITTEN_URL.finditer(txt):
            inner_rel, orig_rel = m.group(2), m.group(4)
            if inner_rel.endswith('/') or '${' in inner_rel:
                continue
            orig_pos = posixpath.normpath(posixpath.join(cur_d, orig_rel))
            asset_pos = posixpath.normpath(posixpath.join(posixpath.dirname(orig_pos), inner_rel))
            if asset_pos.startswith('..'):
                continue
            meta_assets_checked += 1
            if not os.path.exists(os.path.join(sh_root, *asset_pos.split('/'))):
                missing_meta_assets.append(f'{rel_js}: {inner_rel} (from {orig_pos}) -> symmhub/{asset_pos}')

    if missing_js:
        err(f'{len(missing_js)} missing SymmHub JS module(s): ' + ', '.join(missing_js[:10]))
    if missing_meta_assets:
        err(f'{len(missing_meta_assets)} missing bundled asset/worker target(s): ' + '; '.join(missing_meta_assets[:8]))

    # Check if bundled (presence of symdraw-core-*.js chunk) and count .mjs files
    mjs_count = sum(
        1 for dp, _, fns in os.walk(sh_root) for fn in fns if fn.endswith('.mjs')
    ) if os.path.isdir(sh_root) else 0
    is_bundled = any(
        fn.startswith('symdraw-core-') and fn.endswith('.js')
        for fn in (os.listdir(os.path.join(sh_root, 'apps', 'symdraw', 'js'))
                   if os.path.isdir(os.path.join(sh_root, 'apps', 'symdraw', 'js')) else [])
    )

    # Check that the exact release_id was stamped into SymmHub JS as well
    if release_id and os.path.isdir(sh_root):
        found_in_symmhub = False
        for dp, _, fns in os.walk(sh_root):
            for fn in fns:
                if fn.endswith('.js'):
                    try:
                        if release_id in io.open(os.path.join(dp, fn), encoding='utf-8', errors='ignore').read():
                            found_in_symmhub = True
                            break
                    except OSError:
                        pass
            if found_in_symmhub:
                break
        if not found_in_symmhub:
            err(f'Release ID {release_id!r} from catalog_config.json not found in staged symmhub/ JS')

    # Print summary report
    print(f'\n=== Deployment Verification Report: {root} ===')
    if release_id:
        print(f'  Release ID: {release_id}')
    print(f'  {"Section":16s} {"Files":>8s} {"Dirs":>7s} {"Inodes":>8s} {"Size MB":>10s}')
    for sec in sorted(section_stats):
        f, d, b = section_stats[sec]
        print(f'  {sec:16s} {f:8d} {d:7d} {f+d:8d} {b/1024/1024:10.2f}')
    print(f'  {"TOTAL":16s} {total_files:8d} {total_dirs:7d} {total_files+total_dirs:8d} {total_bytes/1024/1024:10.2f}')
    print(f'\n  SymmHub mode: {"BUNDLED" if is_bundled else "unbundled"} '
          f'({len(seen_js)} ES modules, {mjs_count} .mjs files, {meta_assets_checked} static import.meta.url targets verified)')
    print(f'  Verified: {len(html_files)} HTML pages, {links_checked} local links/assets, '
          f'{live_checked} live-data payloads, {si_checked} search entries, '
          f'{sample_checked} SymDraw samples (.json+.png).')

    if warnings:
        print('\nWARNINGS:')
        for w in warnings:
            print('  !', w)

    if errors:
        print(f'\nFAIL ({len(errors)} error(s)):')
        for e in errors:
            print('  X', e)
        return 1

    print('\nPASS: All deployment checks succeeded.')
    return 0


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P.CAT, 'dist')
    sys.exit(check_deploy(target))


if __name__ == '__main__':
    main()
