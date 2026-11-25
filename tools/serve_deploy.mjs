#!/usr/bin/env node
/* Standalone subpath static server to test a built deployment tree (e.g. dist/)
 * exactly as it will be served on GoDaddy under /symmetry/.
 *
 * Strictly rejects requests outside the configured prefix (e.g. / or /catalog/)
 * so any accidental root-relative leak fails immediately with 404.
 *
 *   node tools/serve_deploy.mjs [dir=dist] [port=8199] [prefix=/symmetry]
 */
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const CAT = resolve(fileURLToPath(new URL('..', import.meta.url)));
const root = normalize(resolve(CAT, process.argv[2] || 'dist'));
const port = Number(process.argv[3] || process.env.PORT || 8199);
let prefix = process.argv[4] ?? '/symmetry';
if (prefix && !prefix.startsWith('/')) prefix = '/' + prefix;
prefix = prefix.replace(/\/+$/, '');

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.bin': 'application/octet-stream',
};

createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(req.url.split('?')[0]);
    if (prefix) {
      if (pathname === prefix) {
        res.writeHead(301, { location: prefix + '/' }).end();
        return;
      }
      if (!pathname.startsWith(prefix + '/')) {
        res.writeHead(404, { 'content-type': 'text/plain' }).end('outside prefix ' + prefix);
        return;
      }
    }
    let rel = prefix ? pathname.slice(prefix.length) : pathname;
    if (rel.endsWith('/')) rel += 'index.html';
    let file = normalize(join(root, rel));
    if (!file.startsWith(root)) {
      res.writeHead(403).end('forbidden');
      return;
    }
    try {
      const st = await stat(file);
      if (st.isDirectory()) {
        res.writeHead(301, { location: pathname + '/' }).end();
        return;
      }
    } catch {
      res.writeHead(404, { 'content-type': 'text/plain' }).end('not found: ' + rel);
      return;
    }
    const body = await readFile(file);
    res.writeHead(200, {
      'content-type': TYPES[extname(file).toLowerCase()] || 'application/octet-stream',
      'x-frame-options': 'SAMEORIGIN',
      'x-content-type-options': 'nosniff',
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain' }).end('not found');
  }
}).listen(port, () => {
  console.log(`deploy preview: http://localhost:${port}${prefix}/  (root: ${root})`);
});
