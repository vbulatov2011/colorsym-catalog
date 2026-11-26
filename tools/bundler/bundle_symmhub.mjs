#!/usr/bin/env node
/**
 * Bundle staged SymmHub (SymDraw apps, gallery helper, Web Workers, and CSS)
 * into minimal, self-contained ES module bundles using esbuild.
 *
 * Usage:
 *   node tools/bundler/bundle_symmhub.mjs <stageSymmhubDir> <outSymmhubDir>
 *
 * Key invariant:
 *   Every module inside <stageSymmhubDir> that references `import.meta.url`
 *   (tool SVG icons, UI skin icons, Web Worker URLs, TopBar REPO_ROOT) has
 *   `import.meta.url` rewritten to:
 *     new URL('<relPathFromBundleDirToOriginalModule>', import.meta.url).href
 *   so all relative asset/worker/navigation URLs resolve identically at any
 *   mount path (e.g. /, /symmetry/, /foo/bar/symmetry/).
 */
import * as esbuild from 'esbuild';
import { readFile, mkdir } from 'node:fs/promises';
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

/**
 * esbuild plugin that preserves original-file `import.meta.url` resolution
 * after bundling into `bundleOutSubdir` (posix path relative to symmhub root).
 */
function preserveImportMetaUrlPlugin(stageRoot, bundleOutSubdir) {
  const stageRootResolved = resolve(stageRoot);
  return {
    name: 'preserve-import-meta-url',
    setup(build) {
      build.onLoad({ filter: /\.(js|mjs)$/ }, async (args) => {
        const absPath = resolve(args.path);
        const relFromStage = toPosix(relative(stageRootResolved, absPath));
        if (relFromStage.startsWith('..')) return null;

        const src = await readFile(absPath, 'utf8');
        if (!src.includes('import.meta.url')) return null;

        let relToOrig = posix.relative(bundleOutSubdir, relFromStage);
        if (!relToOrig.startsWith('.')) relToOrig = './' + relToOrig;

        // Replace bare import.meta.url tokens (not preceded by dot/quote)
        const replacement = `new URL(${JSON.stringify(relToOrig)}, import.meta.url).href`;
        const rewritten = src.replace(/(?<![.'"`])\bimport\.meta\.url\b/g, replacement);
        return { contents: rewritten, loader: 'js' };
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

  // 1. Main SymDraw apps (code-split ESM: 4 tiny entries + 1 shared core chunk)
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
    plugins: [preserveImportMetaUrlPlugin(stageDir, 'apps/symdraw/js')],
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
    plugins: [preserveImportMetaUrlPlugin(stageDir, 'apps/symdraw/js')],
  });

  // 3. Standalone Web Worker bundles at their original paths under lib/grouplib/
  const workerResult = await esbuild.build({
    entryPoints: {
      DirichletWorker:     resolve(stageDir, 'lib', 'grouplib', 'DirichletWorker.js'),
      SubgroupNamesWorker: resolve(stageDir, 'lib', 'grouplib', 'SubgroupNamesWorker.js'),
      SubgroupWorker:      resolve(stageDir, 'lib', 'grouplib', 'SubgroupWorker.js'),
    },
    outdir: workersOutDir,
    bundle: true,
    splitting: false,
    format: 'esm',
    minify: true,
    keepNames: true,
    target: ['es2020'],
    metafile: true,
    plugins: [preserveImportMetaUrlPlugin(stageDir, 'lib/grouplib')],
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
