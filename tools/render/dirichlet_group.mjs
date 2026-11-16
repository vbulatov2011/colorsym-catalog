/*
  dirichlet_group.mjs - G on the Dirichlet domain a document asks for, built as
  the renderer builds it (SymmHub DirichletDomainTool getResult): the preset's
  symmetry.dirichlet {enabled, baseX, baseY, words}.

  Shared by tools/make_manifest.mjs (node) and tools/render/catalog_driver.js
  (the browser), so the f/g words of a manifest and the cell words the driver
  looks its glyphs up by are the same strings.  The two load SymmHub by other
  URLs, so its functions come in as `lib`:
    DirichletDomain.js  dirichletBase, dirichletSide, makeDirichletGroup,
                        dirichletSourceWord, parseWords
    Permutations.js     sidePermutations

  The Dirichlet group DG has one generator per side, its own letters a, b, ...;
  letter k acts as the side's word in G's generators (dirichletSourceWord, checked
  against the transforms 2026-11-16).  The coset tables stay G's: a side's
  permutation is the one its word composes (sidePermutations), so H, its cosets
  and the colours are the same - only the cells H's domain is made of change.
*/

/** the Dirichlet group of G for the config, null when the document has none */
export function dirichletGroup(lib, G, cfg) {
    if (!cfg || !cfg.enabled) return null;
    const base = lib.dirichletBase(cfg);
    const found = lib.parseWords(cfg.words).map(w => lib.dirichletSide(G, base, w)).filter(Boolean);
    const DG = found.length ? lib.makeDirichletGroup(G, { base, words: found.map(s => s.word) }) : null;
    if (!DG) throw new Error(`no Dirichlet domain from the words '${cfg.words}'`);
    return DG;
}

/** G's coset table ('acb bca ...', one permutation per generator of G) as DG's:
    one permutation per side, as a fold across it composes them (cosets mode) */
export function sideCosets(lib, DG, cosets) {
    const perms = String(cosets).trim().split(/[\s,]+/)
        .map(w => Array.from(w, ch => ch.charCodeAt(0) - 97));
    return lib.sidePermutations(DG, perms, false)
        .map(p => p.map(i => String.fromCharCode(97 + i)).join('')).join(' ');
}

/** a word in DG's letters as a word of G's generators, freely reduced ('' = e) */
export function sourceWord(lib, DG, word) {
    const out = [];
    for (const ch of lib.dirichletSourceWord(DG, word)) {
        const top = out[out.length - 1];
        if (top && top !== ch && top.toLowerCase() === ch.toLowerCase()) out.pop();
        else out.push(ch);
    }
    return out.join('');
}
