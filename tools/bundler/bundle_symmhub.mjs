#!/usr/bin/env node
/**
 * Bundle staged SymmHub (SymDraw apps, gallery helper, Web Workers, CSS, and
 * all 37 UI/tool SVG icons) into an ultra-compact, self-contained bundle using
 * esbuild.
 *
 * Usage:
 *   node tools/bundler/bundle_symmhub.mjs <stageSymmhubDir> <outSymmhubDir>
 *
 * Key invariants:
 *   1. All SVG icon assets under lib/drawlib/res/*.svg and lib/symhublib/ui/res/*.svg
 *      are inlined directly into the JS bundle as `data:image/svg+xml;base64,...`
 *      URIs — eliminating 37 loose files and 20+ HTTP requests per Studio open.
 *   2. Every remaining `import.meta.url` reference (Web Workers, TopBar REPO_ROOT)
 *      is rewritten to:
 *        new URL('<relPathFromBundleDirToOriginalModule>', import.meta.url).href
 *      so all relative navigation & worker URLs resolve identically at any mount
 *      path (e.g. /, /symmetry/, /foo/bar/symmetry/).
 *   3. The 3 module Web Workers under lib/grouplib/ use ESM code splitting so
 *      DirichletWorker and SubgroupNamesWorker share one common worker-core chunk.
 */
import * as esbuild from 'esbuild';
import { readFile, readdir, mkdir } from 'node:fs/promises';
import { dirname, posix, relative, resolve, sep } from 'node:path';

const stageDir = resolve(process.argv[2] || '');
const outDir = resolve(process.argv[3] || '');
if (!process.argv[2] || !process.argv[3]) {
  console.error('Usage: node bundle_symmhub.mjs <stageSymmhubDir> <outSymmhubDir>');
  process.exit(2);
}

function toPosix(p) {
  return p.split(sep).join('/');
}

async function svgToDataUrl(filePath) {
  const buf = await readFile(filePath);
  return 'data:image/svg+xml;base64,' + buf.toString('base64');
}

async function loadSvgMap(dirPath, keyTransform = (fn) => fn) {
  const map = {};
  const entries = await readdir(dirPath);
  for (const fn of entries.sort()) {
    if (!fn.toLowerCase().endsWith('.svg')) continue;
    const key = keyTransform(fn);
    if (key) map[key] = await svgToDataUrl(resolve(dirPath, fn));
  }
  return map;
}

/**
 * esbuild plugin that:
 *  - Inlines static and dynamic ./res/*.svg icon lookups as base64 data URLs
 *  - Preserves original-file `import.meta.url` resolution for remaining uses
 */
function symmhubBundlePlugin(stageRoot, bundleOutSubdir) {
  const stageRootResolved = resolve(stageRoot);
  let inlinedSvgs = 0;

  return {
    name: 'symmhub-compact-bundle',
    setup(build) {
      build.onLoad({ filter: /\.(js|mjs)$/ }, async (args) => {
        const absPath = resolve(args.path);
        const relFromStage = toPosix(relative(stageRootResolved, absPath));
        if (relFromStage.startsWith('..')) return null;

        let src = await readFile(absPath, 'utf8');
        if (!src.includes('import.meta.url')) return null;

        let changed = false;

        // 1. Dynamic skin icons/cursors in lib/symhublib/ui/SymRendererSkin.js
        if (relFromStage === 'lib/symhublib/ui/SymRendererSkin.js') {
          const skinMap = await loadSvgMap(resolve(dirname(absPath), 'res'));
          const target = "new URL('res/' + name, import.meta.url).pathname";
          if (src.includes(target)) {
            src = src.replace(target, `(${JSON.stringify(skinMap)})[name]`);
            inlinedSvgs += Object.keys(skinMap).length;
            changed = true;
          }
        }

        // 2. Dynamic shape icons in lib/drawlib/ShapeTool.js
        if (relFromStage === 'lib/drawlib/ShapeTool.js') {
          const shapeMap = await loadSvgMap(
            resolve(dirname(absPath), 'res'),
            (fn) => (fn.startsWith('btn_') && fn.endsWith('.svg') ? fn.slice(4, -4) : null),
          );
          const target = 'new URL(`./res/btn_${kind}.svg`, import.meta.url).pathname';
          if (src.includes(target)) {
            src = src.replace(target, `(${JSON.stringify(shapeMap)})[kind]`);
            inlinedSvgs += Object.keys(shapeMap).length;
            changed = true;
          }
        }

        // 3. Static `new URL('./res/foo.svg', import.meta.url).pathname` lookups
        const staticSvgRe = /new\s+URL\(\s*(['"])(\.?\/?res\/[^'"]+\.svg)\1\s*,\s*import\.meta\.url\s*\)\.pathname/g;
        if (staticSvgRe.test(src)) {
          staticSvgRe.lastIndex = 0;
          const matches = [...src.matchAll(staticSvgRe)];
          for (const m of matches) {
            const fullMatch = m[0];
            const svgRel = m[2];
            const svgAbs = resolve(dirname(absPath), svgRel);
            const dataUrl = await svgToDataUrl(svgAbs);
            src = src.replace(fullMatch, JSON.stringify(dataUrl));
            inlinedSvgs++;
            changed = true;
          }
        }

        // 4. Preserve original module URL for remaining `import.meta.url` uses (workers, TopBar REPO_ROOT)
        if (src.includes('import.meta.url')) {
          let relToOrig = posix.relative(bundleOutSubdir, relFromStage);
          if (!relToOrig.startsWith('.')) relToOrig = './' + relToOrig;
          const replacement = `new URL(${JSON.stringify(relToOrig)}, import.meta.url).href`;
          src = src.replace(/(?<![.'"`])\bimport\.meta\.url\b/g, replacement);
          changed = true;
        }

        return changed ? { contents: src, loader: 'js' } : null;
      });

      build.onEnd(() => {
        if (inlinedSvgs > 0) {
          console.log(`  inlined ${inlinedSvgs} SVG icon entries into ${bundleOutSubdir} bundle`);
        }
      });
    },
  };
}

async function run() {
  const t0 = Date.now();
  const jsOutDir = resolve(outDir, 'apps', 'symdraw', 'js');
  const workersOutDir = resolve(outDir, 'lib', 'grouplib');
  await mkdir(jsOutDir, { recursive: true });
  await mkdir(workersOutDir, { recursive: true });

  // 1. Main SymDraw apps (code-split ESM: 4 tiny entries + 1 shared core chunk with inlined SVG icons)
  const mainResult = await esbuild.build({
    entryPoints: {
      symdraw_wp:        resolve(stageDir, 'apps', 'symdraw', 'js', 'symdraw_wp.js'),
      symdraw_frieze:    resolve(stageDir, 'apps', 'symdraw', 'js', 'symdraw_frieze.js'),
      symdraw_spherical: resolve(stageDir, 'apps', 'symdraw', 'js', 'symdraw_spherical.js'),
      symdraw_klm:       resolve(stageDir, 'apps', 'symdraw', 'js', 'symdraw_klm.js'),
    },
    outdir: jsOutDir,
    bundle: true,
    splitting: true,
    format: 'esm',
    minify: true,
    keepNames: true,
    target: ['es2020'],
    chunkNames: 'symdraw-core-[hash]',
    metafile: true,
    plugins: [symmhubBundlePlugin(stageDir, 'apps/symdraw/js')],
  });

  // 2. Lightweight gallery bundle (no WebGL / SymRenderer)
  const galleryResult = await esbuild.build({
    entryPoints: [resolve(stageDir, 'apps', 'symdraw', 'js', 'gallery.js')],
    outfile: resolve(jsOutDir, 'gallery.js'),
    bundle: true,
    format: 'esm',
    minify: true,
    keepNames: true,
    target: ['es2020'],
    metafile: true,
    plugins: [symmhubBundlePlugin(stageDir, 'apps/symdraw/js')],
  });

  // 3. Code-split module Web Workers at their original paths under lib/grouplib/
  //    (DirichletWorker & SubgroupNamesWorker share one deduplicated worker-core chunk)
  const workerResult = await esbuild.build({
    entryPoints: {
      DirichletWorker:     resolve(stageDir, 'lib', 'grouplib', 'DirichletWorker.js'),
      SubgroupNamesWorker: resolve(stageDir, 'lib', 'grouplib', 'SubgroupNamesWorker.js'),
      SubgroupWorker:      resolve(stageDir, 'lib', 'grouplib', 'SubgroupWorker.js'),
    },
    outdir: workersOutDir,
    bundle: true,
    splitting: true,
    format: 'esm',
    minify: true,
    keepNames: true,
    target: ['es2020'],
    chunkNames: 'worker-core-[hash]',
    metafile: true,
    plugins: [symmhubBundlePlugin(stageDir, 'lib/grouplib')],
  });

  // 4. CSS bundles (inlines all @imports and embeds tiny UI SVG arrows as data URLs)
  const cssPairs = [
    ['apps/symdraw/css/main.css', 'apps/symdraw/css/main.css'],
    ['css/index.css',             'css/index.css'],
    ['css/thumbnails.css',        'css/thumbnails.css'],
  ];
  const cssOutputs = [];
  for (const [srcRel, dstRel] of cssPairs) {
    const outFile = resolve(outDir, ...dstRel.split('/'));
    await mkdir(dirname(outFile), { recursive: true });
    const r = await esbuild.build({
      entryPoints: [resolve(stageDir, ...srcRel.split('/'))],
      outfile: outFile,
      bundle: true,
      minify: true,
      loader: { '.svg': 'dataurl', '.png': 'dataurl' },
      metafile: true,
    });
    cssOutputs.push(r.metafile.outputs);
  }

  // Print concise bundle breakdown
  const allOutputs = [
    mainResult.metafile.outputs,
    galleryResult.metafile.outputs,
    workerResult.metafile.outputs,
    ...cssOutputs,
  ];
  let totalBytes = 0;
  let totalFiles = 0;
  for (const map of allOutputs) {
    for (const [filePath, info] of Object.entries(map)) {
      totalFiles++;
      totalBytes += info.bytes;
      const relOut = toPosix(relative(outDir, resolve(filePath)));
      console.log(`  bundle ${relOut.padEnd(46)} ${(info.bytes / 1024).toFixed(1).padStart(7)} KB`);
    }
  }
  console.log(`Bundled ${totalFiles} files (${(totalBytes / 1024 / 1024).toFixed(2)} MB) in ${Date.now() - t0} ms`);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
