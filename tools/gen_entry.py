# Generates the 632/632[3] catalog entry page.
import sys

OUT = sys.argv[1]
N = 3                                    # colors
CELL = max(70, min(235, 720 // N))       # table cell size; shrinks as N grows


def stack(layers, cap):
    out = []
    for l in layers:
        if isinstance(l, tuple):
            out.append("      <img src='%s' class='%s'>" % l)
        else:
            out.append("      <img src='%s'>" % l)
    return ("    <div class='stack'>\n      <div class='cap'>%s</div>\n%s\n    </div>"
            % (cap, "\n".join(out)))


def cell(i, j):
    L = ["sub_tiling.png", "sub_domain.png"]
    if j > 0:
        L.append(("%d0.png" % i, "op20"))
    elif i > 0:
        L.append(("00.png", "op20"))
    L.append("%d%d.png" % (i, j))
    if j > 0:
        L.append("g%d.png" % j)
    elif i > 0:
        L.append("f%d.png" % i)
    return L


def by_cosets(i):
    """Coloring by cosets for placement i: the three cells of column i."""
    return ["sub_tiling.png", "sub_domain.png"] + ["%d%d.png" % (i, j) for j in range(N)]


def by_orbits():
    """Coloring by orbits: the three H-orbits 00, 10, 20 given three colors.
    The motif layers are pure cyan, so an exact channel permutation recolors
    10 and 20 without touching the greys -- see the SVG filters in the page."""
    return ["sub_tiling.png", "sub_domain.png",
            "00.png", ("10.png", "toY"), ("20.png", "toR")]


F = ["e", "f<sub>1</sub>", "f<sub>2</sub>"]
Gl = ["H", "H g<sub>1</sub>", "H g<sub>2</sub>"]
PT = [".1", ".2", ".3"]
PIX = ["p", "f<sub>1</sub>(p)", "f<sub>2</sub>(p)"]

# ---- coset table ---------------------------------------------------------
rows = []
for j in range(N):
    tds = []
    for i in range(N):
        lab = ("%s %s" % (F[i], Gl[j])).replace("e H", "H")
        tds.append("   <td class='cell'>\n%s\n   </td>" % stack(cell(i, j), lab))
    tds.append("   <td class='cell marg'>\n%s\n   </td>"
               % stack(["sub_tiling.png", "sub_domain.png", "012_%d.png" % j],
                       "all orbits of %s" % Gl[j]))
    rows.append("  <tr>\n   <th class='row'><span class='sw sw%d'></span> orbits of %s"
                "</th>\n%s\n  </tr>" % (j, Gl[j], "\n".join(tds)))

tds = ["   <td class='cell marg'>\n%s\n   </td>"
       % stack(by_cosets(i), "632/632[3]%s" % PT[i]) for i in range(N)]
tds.append("   <td class='cell marg'></td>")
rows.append("  <tr>\n   <th class='row'>all colors"
            "<span class='hint'>coloring by cosets</span></th>\n%s\n  </tr>"
            % "\n".join(tds))

head = ("  <tr>\n   <th></th>\n"
        + "\n".join("   <th class='col'>%s<span class='hint'>%s</span></th>" % (PT[i], F[i])
                    for i in range(N))
        + "\n   <th class='col marg'>&#8746;"
          "<span class='hint'>all orbits</span></th>\n  </tr>")
TABLE = ("<table class='grid' style='--cell:%dpx'>\n%s\n%s\n</table>"
         % (CELL, head, "\n".join(rows)))

# ---- hero ----------------------------------------------------------------
HERO_ONE = "\n".join([
    " <figure>",
    stack(["group_tiling.png", "group_pattern.png", "group_domain.png"], "G"),
    "  <figcaption><b>G = 632</b> &mdash; the uncolored pattern: one orbit of the motif "
    "<code>p</code>, with a fundamental domain of G marked.</figcaption>",
    " </figure>",
    " <figure>",
    stack(by_orbits(), "632/632[3].o"),
    "  <figcaption><b class='name'>632/632[3].o</b> &mdash; coloring by orbits. The pattern "
    "splits into three H-orbits, one per motif element <code>p</code>, "
    "<code>f<sub>1</sub>(p)</code>, <code>f<sub>2</sub>(p)</code>. There is only ever one "
    "such coloring.</figcaption>",
    " </figure>",
])

HERO_ROW = "\n".join(
    " <figure>\n%s\n  <figcaption><b class='name'>632/632[3]%s</b> &mdash; coloring by "
    "cosets, motif at <code>%s</code>.</figcaption>\n </figure>"
    % (stack(by_cosets(i), "632/632[3]%s" % PT[i]), PT[i], PIX[i])
    for i in range(N))

GEO = "\n".join([
    " <figure>",
    stack(["group_tiling.png", "group_domain.png", "group_gens.png"], "G: domain + pairings"),
    "  <figcaption><b>G = 632</b> &mdash; the fundamental domain, shaded, together with the "
    "pairing transforms that carry it onto its neighboring cells. They are drawn as "
    "hurricane symbols at the corners, the number of arms giving the order of the "
    "rotation: 2, 3 or 6. The grid behind is the tiling of the plane by the images of "
    "that one domain.</figcaption>",
    " </figure>",
    " <figure>",
    stack(["sub_tiling.png", "sub_domain.png", "sub_gens.png"], "H: domain + pairings"),
    "  <figcaption><b>H = 632</b> &mdash; the same construction for H: its own fundamental "
    "domain, its own pairing transforms in the same 2/3/6-arm convention, and behind them "
    "the tiling of the plane by the images of <em>that</em> domain.</figcaption>",
    " </figure>",
    " <figure>",
    stack(["group_tiling.png", "sub_domain.png", "group_domain.png"],
          "H&rsquo;s domain = 3 of G&rsquo;s"),
    "  <figcaption><b>H&rsquo;s domain as a union</b> &mdash; the same picture on "
    "G&rsquo;s grid. H&rsquo;s fundamental domain is exactly <b>3</b> cells of G&rsquo;s "
    "tiling, one of which is G&rsquo;s own domain, drawn darker. That count is the index, "
    "and so the number of colors.</figcaption>",
    " </figure>",
    " <figure>",
    stack(["group_tiling.png", "sub_tiling.png", "sub_domain.png"], "both tilings"),
    "  <figcaption><b>The two tilings</b> &mdash; the fine tiling by G&rsquo;s domain and "
    "the coarse one by H&rsquo;s, together. Every cell of the coarse tiling is three of the "
    "fine one, everywhere in the plane.</figcaption>",
    " </figure>",
])

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>632/632[3]</title>
<link rel="stylesheet" href="./css/entry.css">
</head>
<body>

<!-- Exact channel permutations, used to recolor the pure-cyan motif layers when
     building the coloring by orbits.  sRGB, so values pass through unchanged. -->
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
 <filter id="toY" color-interpolation-filters="sRGB">
  <feColorMatrix type="matrix" values="0 0 1 0 0  0 1 0 0 0  1 0 0 0 0  0 0 0 1 0"/>
 </filter>
 <filter id="toR" color-interpolation-filters="sRGB">
  <feColorMatrix type="matrix" values="0 1 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 1 0"/>
 </filter>
</svg>

<header class="entry">
<div class="wrap">
<h1>632/632<span class="sub">[3]</span></h1>
<p class="lede">Three-color patterns from the wallpaper group 632 and its index-3 subgroup
of the same type. H sits inside G in three inequivalent ways, so there are three colorings
by cosets &mdash; but only one by orbits.</p>
</div>
</header>

<div class="wrap">

<div class="hero-one">
%s
</div>

<div class="hero-row">
%s
</div>

<p class="legend">Two different things get colored here, and they only agree when H is
normal.<br>
<b class="name">.o</b> &mdash; <b>coloring by orbits</b> gives each H-orbit its own color.
The orbits are determined by H alone, so this coloring is unique: there is nothing to
choose.<br>
<b class="name">.1 .2 .3</b> &mdash; <b>coloring by cosets</b> gives each coset of H its own
color, and depends on where the motif is placed among the three copies of G&rsquo;s
fundamental domain inside H&rsquo;s. Here that yields three distinct colorings. They share
<em>exactly</em> the same uncolored pattern &mdash; the shapes coincide pixel for pixel;
only the assignment of colors moves. Were H normal, all four would be one and the same.<br>
<b>Any picture on this page enlarges on click.</b></p>

<p class="legend">A group here is given by a <b>fundamental domain</b> together with the
<b>pairing transforms</b> that carry that domain onto its neighboring cells; the images of
the domain then tile the plane. Both G and H are presented that way below.</p>

<h2 class="sec">the color group</h2>
<dl class="facts">
  <div class="fact">
    <dt>group G</dt>
    <dd>632 <span class="note">p6 &nbsp;&middot;&nbsp;
        <code>&lang; a, b | a&sup2;, b&sup3;, (ab)&#8310; &rang;</code></span></dd>
  </div>
  <div class="fact">
    <dt>subgroup H</dt>
    <dd>632 <span class="note">index 3 &nbsp;&middot;&nbsp;
        <code>&lang; a, bab, b&#8315;&sup1;ab&#8315;&sup1; &rang;</code></span></dd>
  </div>
  <div class="fact">
    <dt>colors</dt>
    <dd>3 &nbsp;<span class="sw sw0"></span><span class="sw sw1"></span><span class="sw sw2"></span>
        <span class="note">one per coset of H, equivalently one per orbit</span></dd>
  </div>
  <div class="fact">
    <dt>placements</dt>
    <dd>3 <span class="note">the conjugates of H, <code>[G : N<sub>G</sub>(H)]</code>.
        This is 1 exactly when H is normal &mdash; here it is not.</span></dd>
  </div>
</dl>

<h2 class="sec">how G permutes the colors</h2>
<table class="action">
 <tr><th>generator</th>
     <th><span class="sw sw0"></span></th>
     <th><span class="sw sw1"></span></th>
     <th><span class="sw sw2"></span></th>
     <th>cycles</th></tr>
 <tr><th class="gen">a</th>
     <td><span class="sw sw0"></span></td>
     <td><span class="sw sw2"></span></td>
     <td><span class="sw sw1"></span></td>
     <td class="cyc">(1&nbsp;2)</td></tr>
 <tr><th class="gen">b</th>
     <td><span class="sw sw1"></span></td>
     <td><span class="sw sw2"></span></td>
     <td><span class="sw sw0"></span></td>
     <td class="cyc">(0&nbsp;1&nbsp;2)</td></tr>
</table>
<p class="legend"><b>Words act left to right</b>, as maps applied in reading order:
<code>(a*b)(p) = b(a(p))</code>. So in <code>f<sub>i</sub> H g<sub>j</sub></code> the motif
is moved by <code>f<sub>i</sub></code> first, then orbited by H, then carried by
<code>g<sub>j</sub></code>.<br>
The order-2 rotation <code>a</code> holds <span class="sw sw0"></span> fixed and exchanges
the other two; the order-3 rotation <code>b</code> cycles all three. Together they generate
every permutation of the three colors &mdash; the full S&#8323;, of order 6 &mdash; which is
why H is not normal: a normal subgroup of index 3 would act as &#8484;/3 only. The
transversal used below is <code>e, (ab)&sup3;, b&#8315;&sup1;</code>.</p>

<h2 class="sec">fundamental domains and pairing transforms</h2>
<div class="geometry">
%s
</div>

<h2 class="sec">the two families of motions</h2>
<dl class="facts">
  <div class="fact">
    <dt class="plain">f<sub>1</sub>, f<sub>2</sub> &mdash; where the motif starts</dt>
    <dd class="small">Read them off the panels: each is drawn as a small arrow or an axis
        symbol inside H&rsquo;s fundamental domain. They carry the motif to the other two
        positions in that domain, which is exactly what separates the placements
        <code>.1 .2 .3</code>. Any element of the coset does the same job, so these are
        shown rather than named &mdash; the picture is the definition. (The hurricane
        symbols are not among them: those mark rotation centers, drawn by the generators
        layer.)</dd>
  </div>
  <div class="fact">
    <dt class="plain">g<sub>1</sub>, g<sub>2</sub> &mdash; what makes the colors</dt>
    <dd class="small"><code>g<sub>1</sub></code> carries H onto coset 1 and
        <code>g<sub>2</sub></code> onto coset 2. In the panels <code>g<sub>1</sub></code>
        is a half-turn, <b>&pi;</b>, and <code>g<sub>2</sub></code> a rotation by
        <b>2&pi;/3</b>. As words, <code>g<sub>1</sub> = (ab)&sup3;</code> &mdash; the cube of
        the 6-fold rotation &mdash; and <code>g<sub>2</sub> = b&#8315;&sup1; = b&sup2;</code>,
        giving the transversal <code>e, (ab)&sup3;, b&#8315;&sup1;</code>. The three sets
        <code>H</code>, <code>H g<sub>1</sub></code>, <code>H g<sub>2</sub></code> are the
        coset partition &mdash; and that partition <em>is</em> the coloring. Representatives
        are not unique: any other element of the same coset would serve just as well.</dd>
  </div>
</dl>

<h2 class="sec">color partitioning</h2>
<div class="cosets">
%s
</div>
<p class="legend">Each of the nine panels is <code>f<sub>i</sub> H g<sub>j</sub></code>, and
all nine are distinct sets. Every row and every column is a partition of the whole pattern
into three.<br>
<b>Rows are orbits</b> &mdash; the orbits of <code>H</code>, of <code>H g<sub>1</sub></code>
and of <code>H g<sub>2</sub></code>, one color per row. The top row is the H-orbits of
<code>p</code>, <code>f<sub>1</sub>(p)</code> and <code>f<sub>2</sub>(p)</code>; the rows
below are that same picture carried by <code>g<sub>1</sub></code> and
<code>g<sub>2</sub></code>.<br>
<b>Columns are placements</b> <code>.1 .2 .3</code> &mdash; where the motif starts.<br>
The <b>right margin</b> takes a row&rsquo;s orbits together, which is the whole pattern in
one color. The <b>bottom margin</b> is all colors: the coloring by cosets for that placement,
the same three pictures as at the top of the page.</p>

<footer class="entry">
<div><a href="../../../index.html">catalog</a> &middot;
<a href="v1.html">original layout</a></div>
</footer>

</div>

<div id="lb" hidden>
 <div>
  <div class="stack" id="lb-stack"></div>
  <div id="lb-hint">click anywhere or press Esc to close &middot; arrow keys to move</div>
 </div>
</div>

<script>
/* Click-to-enlarge.  Every .stack on the page opens in the overlay, which just
 * re-uses the same layer markup at a larger size; arrow keys walk the set, and
 * up/down step a whole row while inside the coset table. */
(function () {
  var lb = document.getElementById('lb'),
      box = document.getElementById('lb-stack'),
      stacks = [].slice.call(document.querySelectorAll('.wrap .stack')),
      grid = document.querySelector('table.grid'),
      cols = grid ? grid.rows[0].cells.length - 1 : 0,
      idx = -1;

  function inGrid(i) {
    return stacks[i] && !!stacks[i].closest('table.grid');
  }
  function show(i) {
    if (i < 0 || i >= stacks.length) return;
    idx = i;
    box.innerHTML = stacks[i].innerHTML;
    lb.hidden = false;
  }
  function hide() { lb.hidden = true; box.innerHTML = ''; idx = -1; }

  stacks.forEach(function (s, i) {
    s.tabIndex = 0;
    s.setAttribute('role', 'button');
    s.addEventListener('click', function () { show(i); });
    s.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); show(i); }
    });
  });

  lb.addEventListener('click', hide);
  document.addEventListener('keydown', function (e) {
    if (lb.hidden) return;
    if (e.key === 'Escape') { hide(); return; }
    var t = null;
    if (e.key === 'ArrowRight') t = idx + 1;
    else if (e.key === 'ArrowLeft') t = idx - 1;
    else if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && cols && inGrid(idx)) {
      var d = e.key === 'ArrowDown' ? cols : -cols;
      if (inGrid(idx + d)) t = idx + d;
    }
    if (t !== null) { e.preventDefault(); show(t); }
  });
})();
</script>

</body>
</html>
"""

open(OUT, "w", encoding="utf-8").write(PAGE % (HERO_ONE, HERO_ROW, GEO, TABLE))
print("wrote %s  (cell %dpx)" % (OUT, CELL))
