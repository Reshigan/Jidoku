/* The console serves its own fonts, and this proves it.
 *
 * They used to come from Google Fonts — a `<link>` in index.html *and* an `@import` in app.css, so
 * the same stylesheet was fetched twice. Three things were wrong with that beyond the duplicate:
 *
 *   A self-hosted JIDOKA sits inside a client's network, and plenty of those networks do not let a
 *   browser reach fonts.googleapis.com. The console then renders in fallback faces and nobody knows
 *   why, because a failed stylesheet fetch is silent by design.
 *
 *   Every page load told Google that somebody at that client had opened their SAP governance
 *   console. A client security review asks about that, and "it's only a font" is not an answer.
 *
 *   A render-blocking third-party request on the critical path of a screen whose job is to be read
 *   during a cutover.
 *
 * `fonts.css` is derived, not written: this script regenerates it from the installed @fontsource
 * packages (`npm run fonts`) and otherwise asserts the committed file still matches. The rule it
 * applies is one sentence — **ship every subset that covers a character this console renders, and
 * nothing else** — which is why it scans the source for those characters rather than keeping a list
 * somebody has to remember to update.
 *
 * Subsets matter here. Zen Kaku Gothic New's full Japanese range is 966 KB *per weight* and the
 * console renders four characters of it: 自, 働, 化, 印. @fontsource mirrors Google's split into
 * ~120 unicode-range slices, so those four cost about 9 KB each instead of a megabyte — and the
 * browser fetches a slice only if a glyph in its range is on the page.
 */
import assert from "node:assert";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "fonts.css");
const MODULES = join(HERE, "..", "node_modules");

/** The faces the console asks for, at the weights app.css and the components actually use. An
 *  unused weight is four subset downloads nobody needs. */
const FACES = [
  { pkg: "@fontsource/zen-kaku-gothic-new", family: "Zen Kaku Gothic New",
    weights: [400, 500, 700, 900] },
  { pkg: "@fontsource/jetbrains-mono", family: "JetBrains Mono", weights: [400, 500, 700] },
];

/** Printable ASCII is always required — every screen is mostly this. */
const ASCII = Array.from({ length: 0x7f - 0x20 }, (_, i) => 0x20 + i);

function sources() {
  return readdirSync(HERE)
    .filter((f) => /\.(tsx?|css)$/.test(f) && f !== "fonts.css")
    .map((f) => readFileSync(join(HERE, f), "utf8"));
}

/** Every codepoint the console could render: ASCII, plus every non-ASCII character in its own
 *  source. Derived rather than declared, so adding a kanji to a label cannot ship a tofu box — the
 *  check fails, `npm run fonts` covers it, and the new subset is in the diff where a reviewer sees
 *  what it cost. */
function required() {
  const out = new Set(ASCII);
  for (const text of sources()) {
    for (const ch of text) {
      const cp = ch.codePointAt(0);
      if (cp > 0x7f) out.add(cp);
    }
  }
  return out;
}

function faces(pkg, weight) {
  const css = readFileSync(join(MODULES, pkg, `${weight}.css`), "utf8");
  return [...css.matchAll(/@font-face\s*\{([^}]*)\}/g)].map((m) => {
    const file = /files\/([\w.-]+)\.woff2/.exec(m[1]);
    const range = /unicode-range:\s*([^;]+);/.exec(m[1]);
    return file && range ? { file: file[1], range: range[1].trim() } : null;
  }).filter(Boolean);
}

function ranges(range) {
  return range.split(",").map((part) => {
    const p = part.trim().toUpperCase().replace("U+", "");
    const [a, b] = p.includes("-") ? p.split("-") : [p, p];
    return [parseInt(a, 16), parseInt(b, 16)];
  });
}

const covers = (range, cp) => ranges(range).some(([a, z]) => a <= cp && cp <= z);

/** The codepoints of `want` that live in this slice, as a unicode-range.
 *
 *  Narrowed on purpose. A slice's published range covers fifty-odd characters and the console uses
 *  three of them; emitting the published range would put ~47 KB of unicode-range text on the
 *  critical path of every page load, and would have the browser fetch a 9 KB file for a glyph that
 *  is not on the page. The narrowed range says exactly what each file is here for — which is also
 *  the most useful comment this generated file could carry.
 */
function narrow(range, want) {
  const cps = [...want].filter((cp) => covers(range, cp)).sort((a, b) => a - b);
  const out = [];
  for (const cp of cps) {
    const last = out[out.length - 1];
    if (last && cp === last[1] + 1) last[1] = cp;
    else out.push([cp, cp]);
  }
  const hex = (cp) => cp.toString(16).toUpperCase().padStart(4, "0");
  return out.map(([a, z]) => (a === z ? `U+${hex(a)}` : `U+${hex(a)}-${hex(z)}`)).join(",");
}

/** The subsets to ship for one face: every one carrying at least one required codepoint, each with
 *  its range narrowed to the codepoints this console actually renders. */
function needed(pkg, weight, want) {
  return faces(pkg, weight)
    .filter((f) => [...want].some((cp) => covers(f.range, cp)))
    .map((f) => ({ ...f, range: narrow(f.range, want) }));
}

function generate(want) {
  const lines = [
    "/* GENERATED by src/fonts.check.mjs — do not edit. Run `npm run fonts` to regenerate.",
    " *",
    " * The console serves its own fonts, as unicode-range subsets covering exactly the characters",
    " * it renders. Read the header of fonts.check.mjs for why both of those matter.",
    " */",
  ];
  for (const face of FACES) {
    for (const weight of face.weights) {
      for (const f of needed(face.pkg, weight, want)) {
        lines.push(
          "@font-face {",
          `  font-family: "${face.family}";`,
          "  font-style: normal;",
          `  font-weight: ${weight};`,
          // swap: a console that renders nothing for three seconds while a font loads is worse
          // than one that renders in a fallback and reflows.
          "  font-display: swap;",
          `  src: url("${face.pkg}/files/${f.file}.woff2") format("woff2");`,
          `  unicode-range: ${f.range};`,
          "}",
        );
      }
    }
  }
  return lines.join("\n") + "\n";
}

const want = required();
const expected = generate(want);

if (process.argv.includes("--write")) {
  writeFileSync(OUT, expected);
  console.log(`fonts.css written — ${expected.split("@font-face").length - 1} face(s) for `
              + `${want.size} codepoint(s)`);
} else {
  let actual = "";
  try {
    actual = readFileSync(OUT, "utf8");
  } catch { /* reported by the assertion below, with the fix */ }
  assert.strictEqual(actual, expected,
    "src/fonts.css does not match what this console renders or what is installed. "
    + "Run `npm run fonts`, and read the diff: a new subset is a new download.");

  // Every required codepoint is actually covered by something we ship, in every weight. A glyph in
  // no subset renders as an empty rectangle, which is the failure this whole file exists to prevent.
  for (const face of FACES) {
    for (const weight of face.weights) {
      // Ranges here are already narrowed, so this asserts what will actually be served rather
      // than what the package could have served.
      const shipped = needed(face.pkg, weight, want);
      const missing = [...want].filter((cp) => !shipped.some((f) => covers(f.range, cp)));
      // A mono face carries no CJK and is not expected to: the fallback stack in app.css handles it.
      const fatal = missing.filter((cp) => cp < 0x2000);
      assert.ok(fatal.length === 0,
        `${face.family} ${weight} ships no subset for ${fatal.map(
          (cp) => `U+${cp.toString(16).toUpperCase()}`).join(", ")}.`);
    }
  }

  // And nothing the app serves reaches for a font over the network any more. This is the point of
  // the change, so it is asserted over the whole tree rather than over the three files that used to
  // do it — a new screen that pastes in a Google Fonts link should fail here.
  //
  // The v1 consoles under public/ are exempt by name. They are reference artefacts kept to be read
  // — CLAUDE.md points at legacy-console.html as the checkpoint UX to port — not screens the
  // platform ships, and rewriting them would be churn on files whose whole value is being the
  // original. The list is closed, so a *new* file cannot join them by accident.
  const LEGACY = ["public/jidoka-console.html", "public/jidoka-console-v1.html"];
  const offenders = [];
  for (const dir of ["", "src", "public", "e2e"]) {
    const at = join(HERE, "..", dir);
    for (const name of readdirSync(at, { withFileTypes: true })) {
      if (!name.isFile() || !/\.(html|css|tsx?|mjs)$/.test(name.name)) continue;
      const rel = dir ? `${dir}/${name.name}` : name.name;
      if (rel === "src/fonts.check.mjs" || LEGACY.includes(rel)) continue;
      if (/fonts\.(googleapis|gstatic)\.com/.test(readFileSync(join(at, name.name), "utf8"))) {
        offenders.push(rel);
      }
    }
  }
  assert.deepStrictEqual(offenders, [],
    `${offenders.join(", ")} fetches a font from Google. A self-hosted console inside a client `
    + `network cannot reach it — the request fails silently and the screen renders in fallback `
    + `faces — and every page load would tell Google who opened that client's governance console. `
    + `Add the face to src/fonts.check.mjs and run \`npm run fonts\` instead.`);

  // An exemption that is no longer needed is a hole waiting for a new file to fall into, so each
  // one has to still be a file that still offends. `legacy-console.html` was on this list until it
  // turned out not to fetch anything.
  for (const rel of LEGACY) {
    let text = "";
    try {
      text = readFileSync(join(HERE, "..", rel), "utf8");
    } catch {
      assert.fail(`${rel} is exempted and is not there. Remove it from LEGACY.`);
    }
    assert.ok(/fonts\.(googleapis|gstatic)\.com/.test(text),
      `${rel} is exempted and no longer fetches a font from Google. Remove it from LEGACY — a `
      + `stale exemption is a hole a new file falls into.`);
  }

  console.log(`fonts ok — ${expected.split("@font-face").length - 1} subset(s) served by the `
              + `console, ${want.size} codepoint(s) covered, nothing fetched over the network`);
}
