/**
 * Bundle the icons the site actually uses, instead of fetching them from
 * Iconify's public API at runtime.
 *
 * @iconify/react resolves an unknown icon by calling api.iconify.design (with
 * api.simplesvg.com and api.unisvg.com as fallbacks). Nothing registered any
 * collections offline, so EVERY icon on every page was a third-party request
 * on the render path -- including the loading spinner on /finops, which meant
 * the spinner shown during a slow request was itself waiting on a CDN. It is
 * also a privacy leak: it sends each visitor's IP to a third party.
 *
 * The full collections are ~19MB, so this writes a subset of only the icons
 * referenced in source. Every reference is a static string literal -- checked,
 * there is no template-literal or concatenated icon name -- so scanning source
 * finds all of them and a missed icon would simply fall back to the old API
 * behaviour rather than render nothing.
 *
 * Run via `npm run icons:build`. The output is committed so a build needs no
 * network; `npm run icons:check` fails if it is stale.
 */

import { readFile, readdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { getIcons } from "@iconify/utils";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");

const SCAN_DIRS = ["app", "components", "lib"];
const SCAN_EXTS = new Set([".ts", ".tsx"]);
const OUT = join(root, "lib", "generated", "icon-subset.json");

/** Prefixes with an installed @iconify-json package. */
const PREFIXES = ["mdi", "lucide", "logos", "line-md", "simple-icons"];

const ICON_RE = new RegExp(`"(${PREFIXES.join("|")}):([a-z0-9-]+)"`, "g");

async function* walk(dir) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === "generated") continue;
      yield* walk(full);
    } else if (SCAN_EXTS.has(extname(entry.name))) {
      yield full;
    }
  }
}

async function collectNames() {
  /** @type {Map<string, Set<string>>} */
  const wanted = new Map();
  for (const dir of SCAN_DIRS) {
    for await (const file of walk(join(root, dir))) {
      const text = await readFile(file, "utf8");
      for (const match of text.matchAll(ICON_RE)) {
        const [, prefix, name] = match;
        if (!wanted.has(prefix)) wanted.set(prefix, new Set());
        wanted.get(prefix).add(name);
      }
    }
  }
  return wanted;
}

const wanted = await collectNames();
const subsets = [];
const missing = [];
let total = 0;

for (const prefix of PREFIXES) {
  const names = wanted.get(prefix);
  if (!names || names.size === 0) continue;
  const full = require(`@iconify-json/${prefix}/icons.json`);
  const sorted = [...names].sort();
  const subset = getIcons(full, sorted);
  if (!subset) {
    missing.push(`${prefix}: whole collection could not be subset`);
    continue;
  }
  const got = Object.keys(subset.icons ?? {}).length;
  const aliases = Object.keys(subset.aliases ?? {}).length;
  for (const name of sorted) {
    if (!(name in (subset.icons ?? {})) && !(name in (subset.aliases ?? {}))) {
      missing.push(`${prefix}:${name}`);
    }
  }
  total += got + aliases;
  subsets.push(subset);
  process.stdout.write(
    `  ${prefix}: ${got} icons${aliases ? ` + ${aliases} aliases` : ""} of ${sorted.length} requested\n`,
  );
}

// Stable key order so the committed file does not churn between runs.
const json = JSON.stringify(subsets, null, 2) + "\n";

if (process.argv.includes("--check")) {
  let current = "";
  try {
    current = await readFile(OUT, "utf8");
  } catch {
    /* missing counts as stale */
  }
  if (current !== json) {
    console.error(
      "\n✖ lib/generated/icon-subset.json is stale. Run `npm run icons:build`.",
    );
    process.exit(1);
  }
  if (missing.length) {
    console.error(`\n✖ icons not found in their collection:\n   ${missing.join("\n   ")}`);
    process.exit(1);
  }
  console.log(`\n✅ icon subset is current — ${total} icons bundled, none missing.`);
  process.exit(0);
}

await writeFile(OUT, json, "utf8");
console.log(`\nwrote ${OUT} — ${total} icons, ${(json.length / 1024).toFixed(0)} KB`);
if (missing.length) {
  console.error(`\n✖ NOT FOUND in their collection:\n   ${missing.join("\n   ")}`);
  process.exit(1);
}
