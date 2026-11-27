#!/usr/bin/env python3
"""
Build a single self-contained deployment tree of the Color Groups Catalog
with embedded main SymDraw (from SymmHub) for static hosting (e.g. GoDaddy
Apache under a domain folder such as /symmetry/).

What it stages into --out (default: catalog/dist):
  - Root pages: index.html, catalog.html, tutorial.html, search_index.json
  - Production catalog_config.json ({"symmhubUrl": "symmhub", "hideSymmhubSettings": true})
  - GoDaddy Apache .htaccess (.mjs MIME type, WebP MIME, X-Frame-Options SAMEORIGIN,
    RewriteEngine Off to isolate from parent CMS/WordPress, deflate compression, caching)
  - Shared css/ and js/
  - Main-only rendered families from catalog_paths.json (wp, frieze, axial, polyhedral,
    hyperbolic), excluding stray non-runtime files
  - Filtered versions/index.json (main versions only) + active preset snapshots
    (versions/<main>/presets/...) with auto-generated .json.png thumbnails where missing
  - Embedded pruned SymDraw runtime under symmhub/ (only the 4 main SymDraw apps used
    by the catalog: wp, frieze, spherical, klm + their gallery pages + lib/ minus
    heavy/unused directories like color_groups/, haeckel/, .bak, docs), with SymDraw's
    Samples drawer wired directly to the active catalog presets (zero duplication)

Neither catalog/ dev files nor the SymmHub source repo are modified.

Usage:
  python tools/build_deploy.py                         # build into catalog/dist (incremental copy)
  python tools/build_deploy.py --mode link --verify    # fast NTFS hardlink staging + verify
  python tools/build_deploy.py --out D:/deploy/sym --pack D:/deploy/zips --verify
"""
import argparse
import html as _html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_paths as P

CAT = P.CAT
SYMMHUB = os.path.normpath(P.SYMMHUB_DIR)

ROOT_HTML_FILES = ('index.html', 'catalog.html', 'tutorial.html')

# SymmHub subdirectories/files excluded when copying symmhub/lib
SYMMHUB_LIB_EXCLUDED_DIRS = {
    'lib/color_groups',
    'lib/symhublib/res/textures/haeckel',
    'lib/sublib/doc',
    'lib/uilib/css/junk',
}
SYMMHUB_EXCLUDED_EXTS = {'.bak', '.bat'}

# Mapping from SymDraw variant key -> (groupType, html, thumbHtml, label, families, description)
SYMDRAW_VARIANTS = [
    (
        'wp', 'Wallpaper', 'symdraw_wp.html', 'symdraw_thumb_wp.html',
        'Wallpaper', ['wp'],
        'The 17 Euclidean plane wallpaper group motifs used in the Color Groups Catalog.',
    ),
    (
        'frieze', 'Frieze', 'symdraw_frieze.html', 'symdraw_thumb_frieze.html',
        'Frieze', ['frieze'],
        'The 7 Euclidean strip frieze group motifs used in the Color Groups Catalog.',
    ),
    (
        'spherical', 'Spherical', 'symdraw_spherical.html', 'symdraw_thumb_spherical.html',
        'Spherical', ['polyhedral', 'axial'],
        'The 7 polyhedral and 49 axial spherical group motifs used in the Color Groups Catalog.',
    ),
    (
        'klm', 'KLM', 'symdraw_klm.html', 'symdraw_thumb_klm.html',
        'Hyperbolic', ['hyperbolic'],
        'The 16 hyperbolic triangle and quadrilateral motifs used in the Color Groups Catalog.',
    ),
]

HTACCESS_CONTENT = """# Color Groups Catalog — Apache / GoDaddy subpath configuration
# Safe to place inside any domain subfolder (e.g. public_html/symmetry/).

DirectoryIndex index.html
Options -Indexes

# Isolate this static subtree from parent CMS / WordPress rewrite rules
<IfModule mod_rewrite.c>
    RewriteEngine Off
</IfModule>

# Required MIME types (critical: SymmHub loads 60+ .glsl.mjs ES module shaders)
<IfModule mod_mime.c>
    AddType text/javascript .js .mjs
    AddType text/css .css
    AddType application/json .json
    AddType image/webp .webp
    AddType image/svg+xml .svg
    AddType font/woff2 .woff2
</IfModule>

# Allow the catalog's own inline Live preview <iframe> even if parent sets DENY
<IfModule mod_headers.c>
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
</IfModule>

# Gzip compression for text / HTML / JS / shaders / JSON
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html text/plain text/css text/javascript application/javascript application/json image/svg+xml
</IfModule>

# Caching: long immutable cache on rendered WebP/PNG assets and content-hashed JS chunks;
# revalidate HTML, JSON, CSS, and entry JS so new releases take effect immediately.
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType image/webp "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 month"
    ExpiresByType text/css "access plus 0 seconds"
    ExpiresByType text/javascript "access plus 0 seconds"
    ExpiresByType application/javascript "access plus 0 seconds"
    ExpiresByType application/json "access plus 0 seconds"
    ExpiresByType text/html "access plus 0 seconds"
</IfModule>

<IfModule mod_headers.c>
    <FilesMatch "\\.(webp|png)$">
        Header set Cache-Control "public, max-age=31536000, immutable"
    </FilesMatch>
    <FilesMatch "\\.(html|json|js|mjs|css)$">
        Header set Cache-Control "public, no-cache, must-revalidate"
    </FilesMatch>
    <FilesMatch "^(symdraw|worker)-core-[A-Z0-9]{8}\\.js$">
        Header set Cache-Control "public, max-age=31536000, immutable"
    </FilesMatch>
</IfModule>
"""


# ---- File helpers -----------------------------------------------------------

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def write_text(path, content):
    ensure_dir(os.path.dirname(path))
    data = content.encode('utf-8')
    if os.path.exists(path):
        try:
            with open(path, 'rb') as f:
                if f.read() == data:
                    return False
        except OSError:
            pass
    # Break hardlink if destination was previously hardlinked
    if os.path.exists(path):
        os.remove(path)
    with open(path, 'wb') as f:
        f.write(data)
    return True


def stage_binary(src, dst, mode='copy'):
    """Copy or hardlink a binary/static file incrementally."""
    ensure_dir(os.path.dirname(dst))
    st_src = os.stat(src)
    if os.path.exists(dst):
        st_dst = os.stat(dst)
        if mode == 'link' and st_src.st_ino == st_dst.st_ino and st_src.st_dev == st_dst.st_dev:
            return False
        if (mode == 'copy' and st_src.st_size == st_dst.st_size
                and int(st_src.st_mtime) == int(st_dst.st_mtime)):
            return False
        os.remove(dst)
    if mode == 'link':
        try:
            os.link(src, dst)
            return True
        except OSError:
            pass
    shutil.copy2(src, dst)
    return True


_RE_SYMMHUB_META = re.compile(r'<meta\s+name="symmhub-base"\s+content="[^"]*"\s*/?>')
_RE_LIVE_FOOT_HINT = re.compile(
    r'<span>Change SymmHub URL in top-right <b>(?:&#9881;|\u2699)</b> settings</span>'
)
_RE_COMPARE_BTN = re.compile(r'\s*<a[^>]+href="[^"]*compare\.html[^"]*"[^>]*>[^<]*</a>')
_RE_COMPARE_FOOT_SEP = re.compile(
    r'\s*<span>&middot;</span>\s*<a[^>]+href="[^"]*compare\.html[^"]*"[^>]*>[^<]*</a>'
)


def transform_html(text):
    """Rewrite dev SymmHub metadata and strip dev-only hints for standalone deploy."""
    if _RE_SYMMHUB_META.search(text):
        text = _RE_SYMMHUB_META.sub(
            '<meta name="symmhub-base" content="symmhub">\n'
            '<meta name="symmhub-settings" content="0">',
            text,
            count=1,
        )
    text = _RE_LIVE_FOOT_HINT.sub('', text)
    if 'compare.html' in text:
        text = _RE_COMPARE_FOOT_SEP.sub('', text)
        text = _RE_COMPARE_BTN.sub('', text)
    return text


_RE_ROOT_ASSET = re.compile(r'((?:href|src)=")((?:css|js)/[^"?#]+\.(?:css|js))(")')
_RE_CSS_IMPORT = re.compile(r"(@import\s+url\(['\"])([^'\"?#]+\.css)(['\"]\))")
_RE_SYMDRAW_HTML_ASSET = re.compile(r'((?:href|src)=")((?:\./)?(?:css|js)/[^"?#]+\.(?:css|js))(")')


def stage_html(src, dst, bust_version=''):
    with io.open(src, 'r', encoding='utf-8') as f:
        raw = f.read()
    out = transform_html(raw)
    if bust_version:
        out = _RE_ROOT_ASSET.sub(rf'\g<1>\g<2>?v={bust_version}\g<3>', out)
    return write_text(dst, out)


def make_thumb_png_from_webp(webp_path, png_path, size=256):
    """Generate a square PNG preset sample thumbnail from a group's rendered WebP."""
    ensure_dir(os.path.dirname(png_path))
    if os.path.exists(png_path) and os.path.getmtime(png_path) >= os.path.getmtime(webp_path):
        return False
    with Image.open(webp_path) as im:
        im = im.convert('RGBA')
        im.thumbnail((size, size), Image.Resampling.LANCZOS)
        im.save(png_path, 'PNG', optimize=True)
    return True


# ---- Preset discovery -------------------------------------------------------

def ordered_family_presets(fid, vname):
    """Return ordered list of (group_name, group_stem, preset_rel_from_root) for a main version."""
    vcfg = P.version_config(vname) or {}
    presets_map = vcfg.get('presets') or {}
    fmeta = P.family_meta(fid) or {}
    # Load index.json for exact group->stem mapping
    idx_path = P.path(P.family_cfg(fid)['dataDir'], 'index.json')
    stems = {}
    index_order = []
    if os.path.exists(idx_path):
        idx_doc = json.load(open(idx_path, encoding='utf-8'))
        for g in idx_doc.get('groups', []):
            stems[g['name']] = g['stem']
            index_order.append(g['name'])

    order = []
    for sec in fmeta.get('sections') or []:
        for gname in sec.get('groups', []):
            if gname in presets_map and gname not in order:
                order.append(gname)
    for gname in index_order:
        if gname in presets_map and gname not in order:
            order.append(gname)
    for gname in presets_map:
        if gname not in order:
            order.append(gname)

    items = []
    for gname in order:
        src_rel = presets_map[gname]
        snap_rel = P.snapshot(src_rel, vname)  # e.g. versions/wpe2/presets/wp/wpe2/wp-O.json
        stem = stems.get(gname) or gname.replace('\u221e', 'oo').replace('*', 's')
        items.append((gname, stem, snap_rel))
    return items


# ---- Staging steps ----------------------------------------------------------

def stage_catalog(out_dir, mode='copy', release_id='dev'):
    reg = P.registry()
    main_by_fam = {}
    for fid in P.FAMILIES:
        mv = P.main_version(fid)
        if mv:
            main_by_fam[fid] = mv

    stats = {'html': 0, 'binary': 0, 'thumbs_generated': 0, 'skipped_stray': 0}

    # 1. Root HTML files + search_index.json
    for fn in ROOT_HTML_FILES:
        src = P.path(fn)
        if os.path.exists(src):
            stage_html(src, os.path.join(out_dir, fn), bust_version=release_id)
            stats['html'] += 1

    search_src = P.path('search_index.json')
    if os.path.exists(search_src):
        stage_binary(search_src, os.path.join(out_dir, 'search_index.json'), mode='copy')
        stats['binary'] += 1

    # 2. Production catalog_config.json & GoDaddy .htaccess
    cfg = {
        '_comment': 'Self-contained deployment config: embedded SymmHub under ./symmhub/.',
        'symmhubUrl': 'symmhub',
        'hideSymmhubSettings': True,
        'releaseId': release_id,
    }
    write_text(os.path.join(out_dir, 'catalog_config.json'), json.dumps(cfg, indent=1) + '\n')
    write_text(os.path.join(out_dir, '.htaccess'), HTACCESS_CONTENT)

    # 3. Shared css/ and js/ (stamp ?v= on CSS @import so stale caches bust immediately)
    for sub in ('css', 'js'):
        src_dir = P.path(sub)
        for dp, _, fns in os.walk(src_dir):
            rel_dp = os.path.relpath(dp, CAT)
            for fn in fns:
                if fn.endswith('.bak') or fn.startswith('.'):
                    continue
                src_fp = os.path.join(dp, fn)
                dst_fp = os.path.join(out_dir, rel_dp, fn)
                if sub == 'css' and fn.endswith('.css') and release_id:
                    css_txt = io.open(src_fp, 'r', encoding='utf-8').read()
                    css_out = _RE_CSS_IMPORT.sub(rf'\g<1>\g<2>?v={release_id}\g<3>', css_txt)
                    write_text(dst_fp, css_out)
                else:
                    stage_binary(src_fp, dst_fp, mode='copy')
                stats['binary'] += 1

    # 4. All registered main family trees (only .html and .webp — drops stray dev PNGs/CSS)
    for fid, fcfg in P.FAMILIES.items():
        fdir = fcfg['familyDir']
        src_root = P.path(fdir)
        if not os.path.isdir(src_root):
            print(f'WARNING: family dir missing: {src_root}')
            continue
        for dp, _, fns in os.walk(src_root):
            rel_dp = os.path.relpath(dp, CAT)
            for fn in fns:
                src = os.path.join(dp, fn)
                dst = os.path.join(out_dir, rel_dp, fn)
                if fn == 'index.html':
                    stage_html(src, dst)
                    stats['html'] += 1
                elif fn.endswith('.webp'):
                    stage_binary(src, dst, mode=mode)
                    stats['binary'] += 1
                else:
                    stats['skipped_stray'] += 1

    # 5. Filtered versions/index.json (main versions only) + active preset snapshots + thumbnails
    filtered_versions = {}
    for fid, vname in main_by_fam.items():
        meta = dict(reg.get('versions', {}).get(vname, {}))
        meta['family'] = fid
        filtered_versions[vname] = meta
    filtered_reg = {
        'main': main_by_fam.get(P.DEFAULT_FAMILY) or reg.get('main'),
        'versions': filtered_versions,
        'mainByFamily': main_by_fam,
    }
    write_text(
        os.path.join(out_dir, 'versions', 'index.json'),
        json.dumps(filtered_reg, indent=1, ensure_ascii=False) + '\n',
    )

    family_preset_lists = {}
    for fid, vname in main_by_fam.items():
        fdir = P.family_cfg(fid)['familyDir']
        items = ordered_family_presets(fid, vname)
        family_preset_lists[fid] = items
        for gname, stem, snap_rel in items:
            src_json = P.path(snap_rel)
            if not os.path.exists(src_json):
                raise FileNotFoundError(f'Missing preset snapshot for {fid}/{gname}: {src_json}')
            dst_json = os.path.join(out_dir, *snap_rel.split('/'))
            stage_binary(src_json, dst_json, mode='copy')
            stats['binary'] += 1

            # Sample thumbnail (.json.png) for SymDraw's Samples drawer & gallery
            src_png = src_json + '.png'
            dst_png = dst_json + '.png'
            if os.path.exists(src_png):
                stage_binary(src_png, dst_png, mode=mode)
                stats['binary'] += 1
            else:
                # Generate from rendered <family>/<stem>/gen/group.webp
                hero_webp = P.path(fdir, stem, 'gen', 'group.webp')
                if not os.path.exists(hero_webp):
                    raise FileNotFoundError(
                        f'Missing preset thumbnail {src_png} and fallback {hero_webp}'
                    )
                make_thumb_png_from_webp(hero_webp, dst_png, size=256)
                stats['thumbs_generated'] += 1

    return stats, family_preset_lists


def _stage_symmhub_source(sh_out, family_preset_lists, mode='copy', release_id='dev'):
    """Stage full unbundled SymDraw + pruned lib/ + generated glue files into sh_out."""
    stats = {'files': 0}

    # 1. SymmHub portal CSS & icon (for SymDraw gallery pages)
    for fn in ('icon_symmhub.svg', 'index.css', 'portal_theme.js', 'thumbnails.css'):
        src = os.path.join(SYMMHUB, 'css', fn)
        if os.path.exists(src):
            stage_binary(src, os.path.join(sh_out, 'css', fn), mode='copy')
            stats['files'] += 1

    # 2. SymmHub lib/ (pruned: excludes color_groups, haeckel textures, docs, junk, .bak/.bat)
    lib_src = os.path.join(SYMMHUB, 'lib')
    for dp, dns, fns in os.walk(lib_src):
        rel_dp = os.path.relpath(dp, SYMMHUB).replace('\\', '/')
        if any(rel_dp == ex or rel_dp.startswith(ex + '/') for ex in SYMMHUB_LIB_EXCLUDED_DIRS):
            dns[:] = []
            continue
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SYMMHUB_EXCLUDED_EXTS or fn.startswith('.'):
                continue
            # AppCatalog.js and BuildInfo.js are generated custom below
            rel_file = rel_dp + '/' + fn
            if rel_file in ('lib/symhublib/ui/AppCatalog.js', 'lib/symhublib/BuildInfo.js'):
                continue
            src = os.path.join(dp, fn)
            dst = os.path.join(sh_out, *rel_file.split('/'))
            stage_binary(src, dst, mode='copy')
            stats['files'] += 1

    # 3. SymDraw static assets (HTML, CSS, img, core JS)
    sd_src = os.path.join(SYMMHUB, 'apps', 'symdraw')
    sd_out = os.path.join(sh_out, 'apps', 'symdraw')

    for _, _, html_file, _, _, _, _ in SYMDRAW_VARIANTS:
        src_html = os.path.join(sd_src, html_file)
        dst_html = os.path.join(sd_out, html_file)
        raw_html = io.open(src_html, 'r', encoding='utf-8').read()
        if release_id:
            raw_html = _RE_SYMDRAW_HTML_ASSET.sub(rf'\g<1>\g<2>?v={release_id}\g<3>', raw_html)
        write_text(dst_html, raw_html)
        stats['files'] += 1

    for fn in ('main.css', 'icon_symdraw.svg'):
        stage_binary(os.path.join(sd_src, 'css', fn), os.path.join(sd_out, 'css', fn), mode='copy')
        stats['files'] += 1

    for vkey, *_ in SYMDRAW_VARIANTS:
        img_name = f'tmb_{vkey}.png'
        src_img = os.path.join(sd_src, 'img', img_name)
        if os.path.exists(src_img):
            stage_binary(src_img, os.path.join(sd_out, 'img', img_name), mode=mode)
            stats['files'] += 1

    for fn in ('modules.js', 'SymdrawLayerFactory.js'):
        stage_binary(os.path.join(sd_src, 'js', fn), os.path.join(sd_out, 'js', fn), mode='copy')
        stats['files'] += 1

    # Lightweight gallery entry (avoids pulling WebGL/SymRenderer on thumbnail gallery pages)
    write_text(
        os.path.join(sd_out, 'js', 'gallery.js'),
        "export { appendThumbnails2 } from '../../../lib/symhublib/appendThumbnails.js';\n",
    )
    stats['files'] += 1

    # 4. Staged symdraw_app.js: allow explicit opt.samples (for combined polyhedral+axial spherical samples)
    app_js_path = os.path.join(sd_src, 'js', 'symdraw_app.js')
    app_js = io.open(app_js_path, 'r', encoding='utf-8').read()
    old_samples_line = "samples:           makeSamplesArray(opt.presets || '', opt.presetsFolder || ''),"
    new_samples_line = "samples:           opt.samples || makeSamplesArray(opt.presets || '', opt.presetsFolder || ''),"
    if old_samples_line not in app_js:
        raise RuntimeError(f'Unexpected symdraw_app.js format — could not find {old_samples_line!r}')
    write_text(os.path.join(sd_out, 'js', 'symdraw_app.js'), app_js.replace(old_samples_line, new_samples_line, 1))
    stats['files'] += 1

    # 5. Staged SymDraw entry JS, preset lists, and gallery pages wired to catalog's active presets
    for vkey, group_type, html_file, thumb_html, label, fam_ids, desc in SYMDRAW_VARIANTS:
        # Group presets by their common folder relative to symmhub/apps/symdraw/
        groups_by_folder = []
        total_presets = 0
        for fid in fam_ids:
            items = family_preset_lists.get(fid, [])
            if not items:
                continue
            folder_rel = '../../../' + os.path.dirname(items[0][2]).replace('\\', '/') + '/'
            names = [os.path.basename(snap_rel) for _, _, snap_rel in items]
            groups_by_folder.append((fid, folder_rel, names))
            total_presets += len(names)

        if len(groups_by_folder) == 1:
            _, folder_rel, names = groups_by_folder[0]
            presets_js = 'export const presets = `\n' + '\n'.join(names) + '\n`;\n'
            write_text(os.path.join(sd_out, 'js', f'presets_{vkey}.js'), presets_js)
            entry_js = (
                "import { startSymdraw } from './modules.js';\n"
                f"import {{ presets }} from './presets_{vkey}.js';\n\n"
                f"startSymdraw({{ groupType: {json.dumps(group_type)}, "
                f"presetsFolder: {json.dumps(folder_rel)}, presets }});\n"
            )
            write_text(os.path.join(sd_out, 'js', f'symdraw_{vkey}.js'), entry_js)
            thumb_script = (
                "    import { appendThumbnails2 } from './js/gallery.js';\n"
                f"    import {{ presets }} from './js/presets_{vkey}.js';\n\n"
                "    appendThumbnails2({\n"
                "        elem:          document.getElementById('thumbnails'),\n"
                f"        page:          {json.dumps(html_file)},\n"
                f"        folder:        {json.dumps(folder_rel)},\n"
                "        target:        'SYMDRAW',\n"
                "        presetsString: presets,\n"
                "    });\n"
            )
        else:
            # Multi-family variant (Spherical = polyhedral + axial)
            parts = []
            entry_imports = []
            sample_spreads = []
            thumb_calls = []
            for fid, folder_rel, names in groups_by_folder:
                var = f'presets_{fid}'
                parts.append(f'export const {var} = `\n' + '\n'.join(names) + '\n`;')
                parts.append(f'export const folder_{fid} = {json.dumps(folder_rel)};')
                entry_imports.extend([var, f'folder_{fid}'])
                sample_spreads.append(f'    ...makeSamplesArray({var}, folder_{fid}),')
                thumb_calls.append(
                    "    appendThumbnails2({\n"
                    "        elem:          document.getElementById('thumbnails'),\n"
                    f"        page:          {json.dumps(html_file)},\n"
                    f"        folder:        folder_{fid},\n"
                    "        target:        'SYMDRAW',\n"
                    f"        presetsString: {var},\n"
                    "    });"
                )
            write_text(os.path.join(sd_out, 'js', f'presets_{vkey}.js'), '\n'.join(parts) + '\n')
            entry_js = (
                "import { startSymdraw, makeSamplesArray } from './modules.js';\n"
                f"import {{ {', '.join(entry_imports)} }} from './presets_{vkey}.js';\n\n"
                "const samples = [\n" + '\n'.join(sample_spreads) + "\n];\n"
                f"startSymdraw({{ groupType: {json.dumps(group_type)}, samples }});\n"
            )
            write_text(os.path.join(sd_out, 'js', f'symdraw_{vkey}.js'), entry_js)
            thumb_script = (
                "    import { appendThumbnails2 } from './js/gallery.js';\n"
                f"    import {{ {', '.join(entry_imports)} }} from './js/presets_{vkey}.js';\n\n"
                + '\n'.join(thumb_calls) + '\n'
                f"    const meta = document.querySelector('.gallery-toolbar__meta');\n"
                f"    if (meta) meta.textContent = '{total_presets} presets';\n"
            )
        stats['files'] += 2

        thumb_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="./css/icon_symdraw.svg">
    <title>SymDraw {_html.escape(label)} Presets</title>
    <meta name="description" content="{_html.escape(desc)}">
    <link rel="stylesheet" href="../../css/thumbnails.css"/>
    <link rel="stylesheet" href="../../css/index.css"/>
</head>
<body>
    <header>
    <h1>SymDraw &mdash; {_html.escape(label)} Presets</h1>
    </header>
    <div class="container">
        <p>{_html.escape(desc)} Click any thumbnail to open it interactively in SymDraw.</p>
        <div id="thumbnails"></div>
    </div>
    <footer>
        <a href="./index.html">SymDraw</a>
        <a href="../../../index.html">Color Groups Catalog</a>
    </footer>
</body>
<script type="module">
{thumb_script}</script>
</html>
"""
        write_text(os.path.join(sd_out, thumb_html), thumb_page)
        stats['files'] += 1

    # 6. Staged SymDraw gallery index.html (4 main families only)
    card_html = []
    for vkey, _, _, thumb_html, label, fam_ids, desc in SYMDRAW_VARIANTS:
        n_pre = sum(len(family_preset_lists.get(fid, [])) for fid in fam_ids)
        card_html.append(
            f'      <a class="app-card" href="{thumb_html}">\n'
            f'        <div class="app-card__media"><img src="img/tmb_{vkey}.png" alt="{_html.escape(label)} Symmetry" loading="lazy"></div>\n'
            f'        <div class="app-card__body">\n'
            f'          <span class="app-card__title">{_html.escape(label)} Symmetry</span>\n'
            f'          <p class="app-card__desc">{n_pre} catalog presets</p>\n'
            f'        </div>\n'
            f'      </a>'
        )
    sd_index = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" type="image/svg+xml" href="./css/icon_symdraw.svg">
  <title>SymDraw — Color Groups Catalog</title>
  <meta name="description" content="SymDraw: vector drawing with symmetry">
  <link rel="stylesheet" href="../../css/index.css?v={release_id}"/>
  <script src="../../css/portal_theme.js?v={release_id}"></script>
</head>
<body>
  <nav class="portal-nav" aria-label="SymDraw navigation">
    <div class="portal-nav__inner">
      <div class="portal-crumb">
        <a class="portal-brand" href="../../../index.html">
          <img src="../../css/icon_symmhub.svg" alt="">
          Color Groups Catalog
        </a>
        <span class="portal-crumb__sep" aria-hidden="true">&rsaquo;</span>
        <span class="portal-crumb__current">SymDraw</span>
      </div>
      <div class="portal-nav__actions">
        <a class="btn-primary" href="symdraw_wp.html">Start Drawing &rarr;</a>
        <button type="button" class="theme-btn" data-theme-toggle>&#9728; Light</button>
      </div>
    </div>
  </nav>

  <main class="container">
    <div class="gallery-toolbar">
      <h1 class="gallery-toolbar__title">SymDraw &mdash; Vector Drawing with Symmetry</h1>
    </div>
    <p class="portal-hero__lead" style="margin-bottom: 1.5rem;">
      Vector drawing folded in real time by the SymmHub symmetry engine. Choose a symmetry family to browse the catalog&rsquo;s presets or start a blank canvas.
    </p>

    <div class="card-grid">
{chr(10).join(card_html)}
    </div>
  </main>

  <footer>
    <a href="../../../index.html">Color Groups Catalog</a>
    &middot;
    <a href="../../../catalog.html">Browse all families</a>
    &middot;
    <span>Release <code>{release_id}</code></span>
  </footer>
</body>
</html>
"""
    write_text(os.path.join(sd_out, 'index.html'), sd_index)
    stats['files'] += 1

    # 7. Stamped BuildInfo.js (exact release ID yy-mm-dd-hh-mm-ss) & trimmed AppCatalog.js
    build_info_js = (
        "/* Stamped by build_deploy.py during release packaging. */\n"
        f"export const RELEASE_ID = {json.dumps(release_id)};\n"
    )
    write_text(os.path.join(sh_out, 'lib', 'symhublib', 'BuildInfo.js'), build_info_js)
    stats['files'] += 1

    variants_js = ',\n'.join(
        f"                {{ label: {json.dumps(label)}, "
        f"page: 'apps/symdraw/{html_file}', "
        f"thumbPage: 'apps/symdraw/{thumb_html}' }}"
        for _, _, html_file, thumb_html, label, _, _ in SYMDRAW_VARIANTS
    )
    app_catalog_js = f"""/*
 * Staged AppCatalog.js for self-contained Color Groups Catalog deployment.
 * Lists only the bundled SymDraw variants and points Home back to the catalog.
 */
export const APP_CATALOG = {{
    home: '../index.html',
    docs: [],
    apps: [
        {{
            id: 'symdraw',
            title: 'SymDraw',
            subtitle: 'Vector drawing with symmetry',
            badge: 'Vector',
            index: 'apps/symdraw/index.html',
            thumb: 'apps/symdraw/img/tmb_wp.png',
            variants: [
{variants_js}
            ],
        }},
    ],
}};
"""
    write_text(os.path.join(sh_out, 'lib', 'symhublib', 'ui', 'AppCatalog.js'), app_catalog_js)
    stats['files'] += 1

    # 8. Redirect landing page at symmhub/index.html so /symmetry/symmhub/ never 404s
    sh_index = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=../index.html">
  <title>SymmHub — Color Groups Catalog</title>
</head>
<body>
  <p>Redirecting to <a href="../index.html">Color Groups Catalog</a> (<a href="apps/symdraw/index.html">SymDraw Gallery</a>)…</p>
</body>
</html>
"""
    write_text(os.path.join(sh_out, 'index.html'), sh_index)
    stats['files'] += 1

    return stats


def stage_symmhub(out_dir, family_preset_lists, mode='copy', bundled=True, release_id='dev'):
    """Stage SymmHub under <out_dir>/symmhub (esbuild-bundled by default, or unbundled)."""
    if not os.path.isdir(SYMMHUB):
        raise FileNotFoundError(f'SymmHub directory not found: {SYMMHUB}')

    sh_out = os.path.join(out_dir, 'symmhub')
    # Always recreate symmhub/ cleanly so stale unbundled modules or old chunk hashes never linger
    if os.path.exists(sh_out):
        shutil.rmtree(sh_out)

    if not bundled:
        stats = _stage_symmhub_source(sh_out, family_preset_lists, mode=mode, release_id=release_id)
        stats['mode'] = 'unbundled'
        return stats

    bundler_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bundler')
    bundler_script = os.path.join(bundler_dir, 'bundle_symmhub.mjs')
    esbuild_dir = os.path.join(bundler_dir, 'node_modules', 'esbuild')
    if not os.path.isdir(esbuild_dir):
        raise RuntimeError(
            f'esbuild is not installed in {bundler_dir}.\n'
            f'Run: npm --prefix "{bundler_dir}" install'
        )

    with tempfile.TemporaryDirectory(prefix='symmhub_stage_') as tmp_stage:
        _stage_symmhub_source(tmp_stage, family_preset_lists, mode='copy', release_id=release_id)

        ensure_dir(sh_out)
        print('Bundling SymmHub with esbuild...')
        subprocess.run(['node', bundler_script, tmp_stage, sh_out], check=True)

        # Copy only minimal non-bundled runtime static assets
        static_files = [
            'index.html',
            'css/icon_symmhub.svg',
            'css/portal_theme.js',
            'apps/symdraw/index.html',
            'apps/symdraw/css/icon_symdraw.svg',
        ]
        for vkey, _, html_file, thumb_html, _, _, _ in SYMDRAW_VARIANTS:
            static_files.extend([
                f'apps/symdraw/{html_file}',
                f'apps/symdraw/{thumb_html}',
                f'apps/symdraw/img/tmb_{vkey}.png',
                f'apps/symdraw/js/presets_{vkey}.js',
            ])
        for rel in static_files:
            src = os.path.join(tmp_stage, *rel.split('/'))
            if os.path.exists(src):
                stage_binary(src, os.path.join(sh_out, *rel.split('/')), mode='copy')

    total_files = sum(len(fns) for _, _, fns in os.walk(sh_out))
    return {'files': total_files, 'mode': 'bundled'}


# ---- Optional GoDaddy zip chunking ------------------------------------------

COMPRESS_EXTS = {'.html', '.css', '.js', '.mjs', '.json', '.svg', '.txt', ''}


def _add_path_to_zip(zf, full_path, arcname):
    ext = os.path.splitext(full_path)[1].lower()
    comp = zipfile.ZIP_DEFLATED if (ext in COMPRESS_EXTS or os.path.basename(full_path) == '.htaccess') else zipfile.ZIP_STORED
    zf.write(full_path, arcname, compress_type=comp)


def pack_godaddy_zips(out_dir, zip_dir, max_chunk_mb=500):
    """Pack out_dir into upload-friendly zip archives (each <= ~max_chunk_mb) for cPanel Extract."""
    ensure_dir(zip_dir)
    # Partition top-level items into clean logical buckets:
    #   01_core_and_symmhub.zip: root files (.htaccess, index.html, ...), css/, js/, versions/, symmhub/
    #   02_... : family trees, split cleanly by group folder if exceeding max_chunk_mb
    core_files = []
    for entry in sorted(os.listdir(out_dir)):
        full = os.path.join(out_dir, entry)
        if entry in P.FAMILIES:
            continue
        if os.path.isfile(full):
            core_files.append((full, entry))
        else:
            for dp, _, fns in os.walk(full):
                for fn in sorted(fns):
                    fp = os.path.join(dp, fn)
                    core_files.append((fp, os.path.relpath(fp, out_dir).replace('\\', '/')))

    archives = [('01_core_and_symmhub.zip', core_files)]

    # Collect family sub-units (top-level files/dirs inside each family dir)
    units = []
    for fid in P.FAMILIES:
        fdir = P.family_cfg(fid)['familyDir']
        fpath = os.path.join(out_dir, fdir)
        if not os.path.isdir(fpath):
            continue
        for entry in sorted(os.listdir(fpath)):
            ep = os.path.join(fpath, entry)
            unit_files = []
            unit_bytes = 0
            if os.path.isfile(ep):
                unit_files.append((ep, f'{fdir}/{entry}'))
                unit_bytes += os.path.getsize(ep)
            else:
                for dp, _, fns in os.walk(ep):
                    for fn in sorted(fns):
                        fp = os.path.join(dp, fn)
                        unit_files.append((fp, os.path.relpath(fp, out_dir).replace('\\', '/')))
                        unit_bytes += os.path.getsize(fp)
            units.append((fid, unit_bytes, unit_files))

    max_bytes = max_chunk_mb * 1024 * 1024
    cur_files, cur_bytes, cur_fams = [], 0, []
    idx = 2
    for fid, ubytes, ufiles in units:
        if cur_files and cur_bytes + ubytes > max_bytes:
            tag = '_'.join(dict.fromkeys(cur_fams))
            archives.append((f'{idx:02d}_{tag}.zip', cur_files))
            idx += 1
            cur_files, cur_bytes, cur_fams = [], 0, []
        cur_files.extend(ufiles)
        cur_bytes += ubytes
        cur_fams.append(fid)
    if cur_files:
        tag = '_'.join(dict.fromkeys(cur_fams))
        archives.append((f'{idx:02d}_{tag}.zip', cur_files))

    created = []
    for zname, flist in archives:
        zpath = os.path.join(zip_dir, zname)
        with zipfile.ZipFile(zpath, 'w', allowZip64=True) as zf:
            for fp, arc in flist:
                _add_path_to_zip(zf, fp, arc)
        zmb = os.path.getsize(zpath) / (1024 * 1024)
        created.append((zname, len(flist), zmb))
        print(f'  packed {zname}: {len(flist):6d} files, {zmb:6.1f} MB')

    guide = (
        "GoDaddy cPanel / SFTP Upload Guide (e.g. into public_html/symmetry/)\n"
        "=====================================================================\n\n"
        "Option A — SFTP + cPanel File Manager Extract (recommended without SSH):\n"
        "  1. Create folder public_html/symmetry/ on GoDaddy.\n"
        "  2. Upload all .zip files below into public_html/symmetry/ via SFTP (FileZilla/WinSCP).\n"
        "  3. Open GoDaddy cPanel -> File Manager -> public_html/symmetry/.\n"
        "  4. Select each .zip archive one by one and click Extract (into public_html/symmetry/).\n"
        "     (Enable 'Show Hidden Files' in File Manager Settings to confirm .htaccess extracted.)\n"
        "  5. Delete the uploaded .zip files after extraction.\n"
        "  6. Visit https://yourdomain.com/symmetry/ and test an entry's Live preview.\n\n"
        "Option B — SSH rsync (fastest for initial upload AND incremental updates):\n"
        "  rsync -avz --delete dist/ user@yourserver:~/public_html/symmetry/\n\n"
        "Archives in this folder:\n"
        + '\n'.join(f"  - {n} ({c} files, {mb:.1f} MB)" for n, c, mb in created)
        + '\n'
    )
    write_text(os.path.join(zip_dir, 'UPLOAD_GODADDY.txt'), guide)
    return created


# ---- Main -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description='Build self-contained Color Groups Catalog + SymmHub deployment tree.')
    ap.add_argument('--out', default=os.path.join(CAT, 'dist'), help='Output deployment directory (default: catalog/dist)')
    ap.add_argument('--mode', choices=('copy', 'link'), default='copy',
                    help='copy (portable, incremental) or link (fast same-drive NTFS hardlinks for images)')
    ap.add_argument('--symmhub', choices=('bundled', 'unbundled'), default='bundled',
                    help='bundled (esbuild minified chunks + workers, default) or unbundled (raw ES modules)')
    ap.add_argument('--clean', action='store_true', help='Remove existing --out directory before staging')
    ap.add_argument('--release-id', default='',
                    help='Explicit release ID (default: current local timestamp yy-mm-dd-hh-mm-ss)')
    ap.add_argument('--pack', default='', help='Optional directory to write GoDaddy-chunked .zip archives')
    ap.add_argument('--max-zip-mb', type=int, default=500, help='Target max size per zip chunk in MB (default: 500)')
    ap.add_argument('--verify', action='store_true', help='Run verify_deploy.py after staging')
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out)
    if args.clean and os.path.exists(out_dir):
        print(f'Cleaning {out_dir} ...')
        shutil.rmtree(out_dir)

    release_id = args.release_id.strip() or time.strftime('%y-%m-%d-%H-%M-%S')
    t0 = time.time()
    print(f'Staging self-contained catalog -> {out_dir} (mode={args.mode}, symmhub={args.symmhub})')
    print(f'  Release ID:     {release_id}')
    print(f'  Catalog source: {CAT}')
    print(f'  SymmHub source: {SYMMHUB}')

    cat_stats, family_preset_lists = stage_catalog(out_dir, mode=args.mode, release_id=release_id)
    sh_stats = stage_symmhub(
        out_dir, family_preset_lists,
        mode=args.mode, bundled=(args.symmhub == 'bundled'), release_id=release_id,
    )
    dt = time.time() - t0

    print(f'Staged in {dt:.1f}s (Release ID: {release_id}):')
    print(f"  Catalog: {cat_stats['html']} HTML, {cat_stats['binary']} assets, "
          f"{cat_stats['thumbs_generated']} generated sample thumbs, "
          f"{cat_stats['skipped_stray']} stray dev files skipped")
    print(f"  SymmHub: {sh_stats['files']} files ({sh_stats['mode']}; 4 SymDraw apps + workers + assets)")

    if args.pack:
        pack_dir = os.path.abspath(args.pack)
        print(f'Packing GoDaddy upload archives -> {pack_dir}')
        pack_godaddy_zips(out_dir, pack_dir, max_chunk_mb=args.max_zip_mb)

    if args.verify:
        verifier = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_deploy.py')
        subprocess.run([sys.executable, verifier, out_dir], check=True)


if __name__ == '__main__':
    main()
