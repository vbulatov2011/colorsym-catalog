/* static server for SymmHub + POST /save endpoint that writes rendered
 * PNGs into the colorsym catalog tree. */
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize, dirname } from 'node:path';

const root = 'D:/home/projects/00.docs/250125_symhub/repo_v2/SymmHub';
const saveRoot = 'D:/home/projects/00.docs/250117_colorsym/catalog';
const port = 8125;
const TYPES = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8', '.json':'application/json; charset=utf-8',
  '.css':'text/css; charset=utf-8', '.png':'image/png', '.jpg':'image/jpeg', '.svg':'image/svg+xml' };

createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (req.method === 'POST' && url.pathname === '/save') {
      const rel = url.searchParams.get('path') || '';
      const file = normalize(join(saveRoot, rel));
      if (!file.startsWith(normalize(saveRoot)) || rel.includes('..')) {
        res.writeHead(403).end('forbidden'); return;
      }
      const chunks = [];
      for await (const c of req) chunks.push(c);
      await mkdir(dirname(file), { recursive: true });
      await writeFile(file, Buffer.concat(chunks));
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ saved: rel, bytes: Buffer.concat(chunks).length }));
      console.log('saved', rel, Buffer.concat(chunks).length, 'bytes');
      return;
    }
    // also serve the catalog data files to the app
    if (url.pathname.startsWith('/catalog/')) {
      const file = normalize(join(saveRoot, url.pathname.slice('/catalog/'.length)));
      if (!file.startsWith(normalize(saveRoot))) { res.writeHead(403).end(); return; }
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' });
      res.end(body);
      return;
    }
    let rel = decodeURIComponent(url.pathname);
    if (rel.endsWith('/')) rel += 'index.html';
    const file = normalize(join(root, rel));
    if (!file.startsWith(normalize(root))) { res.writeHead(403).end('forbidden'); return; }
    const body = await readFile(file);
    res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch { res.writeHead(404).end('not found'); }
}).listen(port, () => console.log('symmhub+save: http://localhost:' + port + '/'));
