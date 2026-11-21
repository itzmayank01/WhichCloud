"use client";

import { addCollection } from "@iconify/react";

import subsets from "@/lib/generated/icon-subset.json";

/**
 * Registers the bundled icon data so @iconify/react never calls out to
 * Iconify's API.
 *
 * Unregistered, an Icon with an mdi or lucide name is resolved by fetching
 * api.iconify.design (falling back to api.simplesvg.com, then
 * api.unisvg.com). Nothing registered anything, so every icon on every page
 * was a third-party round trip on the render path -- and the one on /finops
 * is the loading spinner, so the spinner shown during a slow request was
 * itself waiting on a CDN. It also sent every visitor's IP to a third party.
 *
 * The registration is a module side effect rather than an effect in the
 * component: it has to happen before any <Icon> renders, and an effect runs
 * after. Importing this module from the root layout is what triggers it.
 *
 * lib/generated/icon-subset.json holds only the icons found in source --
 * `npm run icons:build` regenerates it, `npm run icons:check` fails if it is
 * stale. An icon added to source but not regenerated still renders: it falls
 * back to the API, as every icon did before this existed.
 */
for (const subset of subsets) {
  // Through `unknown`: TypeScript infers a union of per-collection
  // literal shapes from the JSON import, where each member has the other
  // members' icon keys as `undefined`, and that does not overlap
  // IconifyJSON's index signature. The data is Iconify's own, written by
  // its own getIcons(), and icons:check fails the build if it is stale.
  addCollection(subset as unknown as Parameters<typeof addCollection>[0]);
}

export function IconCollections() {
  return null;
}
