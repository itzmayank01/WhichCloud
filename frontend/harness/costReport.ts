/* ── Does the cost report still add up? ──
   Run: npm run report:check

   The report lets a reader slice a bill a dozen ways, and every slice is
   a claim about their money. The property worth a harness is that NO
   SLICE INVENTS OR LOSES ANY: group by anything, bin by anything, fold
   the tail into "Other", and the parts still sum to the bill. */

import {
  applyFilters, bin, facet, group, projectedMonth, OTHER, UNLABELLED,
  type Filter,
} from "../lib/costReport";
import type { CostRow } from "../lib/api";

let failures = 0;
function check(name: string, condition: boolean, detail = "") {
  if (condition) return;
  failures += 1;
  console.error(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
}
function near(a: number, b: number) {
  return Math.abs(a - b) < 0.01;
}

const rows: CostRow[] = [];
const services = ["AmazonEC2", "AmazonRDS", "AmazonS3", "AWSLambda", "AmazonVPC"];
const regions = ["ap-south-1", "us-east-1"];
let seed = 7;
const rand = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
for (let d = 1; d <= 28; d++) {
  for (const service of services) {
    for (const region of regions) {
      rows.push({
        service, region,
        resource_type: rand() > 0.5 ? "large" : "small",
        day: `2024-03-${String(d).padStart(2, "0")}`,
        monthly_usd: Math.round(rand() * 5000) / 100,
        usage: 100,
      });
    }
  }
}
// A row the export left unlabelled, and one with no date at all. Both are
// real money and both have to survive every slice.
rows.push({ service: "AmazonEC2", region: "", resource_type: "", day: "2024-03-01", monthly_usd: 42.5, usage: 1 });
rows.push({ service: "Undated", region: "ap-south-1", resource_type: "x", day: "", monthly_usd: 17.25, usage: 1 });

const BILL = rows.reduce((sum, r) => sum + r.monthly_usd, 0);
console.log(`\n  ${rows.length} cells, $${BILL.toFixed(2)} billed\n`);

/* ── every grouping adds up ── */
for (const dimension of ["service", "region", "resource_type"] as const) {
  for (const size of ["day", "week", "month"] as const) {
    const grouped = group(rows, dimension, size);
    const summed = grouped.series.reduce((s, one) => s + one.total, 0);
    check(`group by ${dimension} / ${size} sums to the bill`, near(summed, BILL),
      `$${summed.toFixed(2)} vs $${BILL.toFixed(2)}`);

    const plotted = grouped.series.reduce(
      (s, one) => s + one.points.reduce((a, b) => a + b, 0), 0);
    check(`group by ${dimension} / ${size} plots the whole bill`, near(plotted, BILL),
      `$${plotted.toFixed(2)} vs $${BILL.toFixed(2)}`);
  }
}

/* ── the tail is folded, never dropped ── */
const tight = group(rows, "service", "day", 2);
check("a limit past the group count produces Other", tight.series.some((s) => s.key === OTHER));
check("folding the tail still sums to the bill",
  near(tight.series.reduce((s, one) => s + one.total, 0), BILL));
check("Other sorts last", tight.series[tight.series.length - 1].key === OTHER);
check("the folded count is reported", tight.otherCount === services.length + 1 - 2,
  `got ${tight.otherCount}`);

/* ── unlabelled dimensions stay visible ── */
const byRegion = group(rows, "region", "day");
check("an unstated region is labelled, not dropped",
  byRegion.series.some((s) => s.key === UNLABELLED));
check("grouping by an unstated dimension still sums to the bill",
  near(byRegion.series.reduce((s, one) => s + one.total, 0), BILL));

/* ── filters ── */
const isEc2: Filter = { id: "a", dimension: "service", operator: "is", values: ["AmazonEC2"] };
const notEc2: Filter = { id: "b", dimension: "service", operator: "is not", values: ["AmazonEC2"] };
const kept = applyFilters(rows, [isEc2]);
const rest = applyFilters(rows, [notEc2]);
check("a filter and its negation partition the bill",
  near(kept.reduce((s, r) => s + r.monthly_usd, 0)
     + rest.reduce((s, r) => s + r.monthly_usd, 0), BILL));
check("no row satisfies both", kept.every((r) => !rest.includes(r)));

const contains = applyFilters(rows, [
  { id: "c", dimension: "service", operator: "contains", values: ["amazon"] }]);
check("contains is case-insensitive", contains.length > 0);
check("contains is a superset of is",
  kept.every((row) => contains.includes(row)));

const empty = applyFilters(rows, [
  { id: "d", dimension: "service", operator: "is", values: [] }]);
check("a filter with no values filters nothing", empty.length === rows.length);

const multi = applyFilters(rows, [
  { id: "e", dimension: "service", operator: "is", values: ["AmazonEC2", "AmazonRDS"] }]);
check("values within one filter are OR'd",
  multi.length > kept.length);

const both = applyFilters(rows, [isEc2,
  { id: "f", dimension: "region", operator: "is", values: ["us-east-1"] }]);
check("separate filters are AND'd", both.every(
  (r) => r.service === "AmazonEC2" && r.region === "us-east-1"));

/* ── facets offer only values that return something ── */
const menu = facet(rows, "region", [isEc2], "zzz");
check("facet values are ranked by spend",
  menu.every((entry, i) => i === 0 || menu[i - 1].monthly_usd >= entry.monthly_usd));
for (const entry of menu) {
  const narrowed = applyFilters(rows, [isEc2,
    { id: "g", dimension: "region", operator: "is", values: [entry.value] }]);
  check(`facet "${entry.value}" returns rows`, narrowed.length > 0);
}
const selfExcluded = facet(rows, "service", [isEc2], "a");
check("a filter does not narrow its own menu",
  selfExcluded.length > 1, `${selfExcluded.length} option(s)`);

/* ── date binning ── */
check("a month bins to its first", bin("2024-03-17", "month") === "2024-03-01");
check("a week bins to its Monday", bin("2024-03-17", "week") === "2024-03-11");
check("a Monday bins to itself", bin("2024-03-11", "week") === "2024-03-11");
check("a Sunday bins back, not forward", bin("2024-03-17", "week") === "2024-03-11");
check("an undated row bins to nothing", bin("", "day") === "");

const daily = group(rows, "service", "day");
const monthly = group(rows, "service", "month");
check("rebinning does not change the total", near(daily.total, monthly.total));
check("coarser bins mean fewer buckets", monthly.buckets.length < daily.buckets.length);

/* ── projection is withheld where it would be invented ── */
check("a daily series projects a month", (projectedMonth(daily, "day") ?? 0) > 0);
check("a monthly series does not project", projectedMonth(monthly, "month") === null);
check("one bucket does not project",
  projectedMonth(group(rows.slice(0, 2), "service", "day"), "day") === null);

/* ── partial periods ── */
// The sample runs 2024-03-01 (a Friday) to 2024-03-28 (a Thursday), so
// both end weeks are clipped and neither end month is whole.
// Note the undated bucket: it sorts to index 0, so the dated ends are
// NOT positions 0 and length-1. Assuming they were is exactly the bug
// this found -- a genuinely clipped first week went unflagged.
const weekly = group(rows, "service", "week");
const datedAt = weekly.buckets.map((b, i) => (b ? i : -1)).filter((i) => i >= 0);
const [head, tail] = [datedAt[0], datedAt[datedAt.length - 1]];
check("the undated bucket is not a dated end", head !== 0);
check("the first clipped week is flagged", weekly.partial[head] === true);
check("the last clipped week is flagged", weekly.partial[tail] === true);
check("interior weeks are not flagged",
  datedAt.slice(1, -1).every((i) => weekly.partial[i] === false),
  "a gap mid-series is a quiet day, not missing data");
check("the undated bucket is never flagged partial", weekly.partial[0] === false);
check("daily bins are never flagged",
  group(rows, "service", "day").partial.every((p) => p === false));

// A range that starts exactly on a Monday and ends on a Sunday covers
// its weeks completely, and flagging them would cry wolf.
const whole: typeof rows = [];
for (let d = 4; d <= 17; d++) {   // 2024-03-04 Mon .. 2024-03-17 Sun
  whole.push({ service: "AmazonEC2", region: "ap-south-1", resource_type: "x",
    day: `2024-03-${String(d).padStart(2, "0")}`, monthly_usd: 10, usage: 1 });
}
const tidy = group(whole, "service", "week");
check("weeks covered end to end are not flagged",
  tidy.partial.every((p) => p === false),
  `flagged ${tidy.partial.filter(Boolean).length} of ${tidy.buckets.length}`);
check("a whole fortnight is two weeks", tidy.buckets.length === 2);

check("flagging partials does not change the total",
  near(weekly.total, BILL));

console.log(failures === 0
  ? "  All checks passed.\n"
  : `\n  ${failures} check(s) failed.\n`);
process.exit(failures === 0 ? 0 : 1);
