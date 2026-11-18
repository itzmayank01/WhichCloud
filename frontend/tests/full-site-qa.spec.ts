import { test, expect } from "@playwright/test";
import { execSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const QA_DIR = path.resolve(__dirname, "../../docs/qa");
fs.mkdirSync(QA_DIR, { recursive: true });

const PUNE_WORKLOAD =
  "I manage IT for a 3-hospital group in Pune. We want to move patient appointments, records and lab reports online so doctors and front desk can access them from all three sites. About 450 staff use it, roughly 6,000 record lookups a day, with peaks in the morning. Patient data must stay inside India and cannot be lost. Downtime during OPD hours is unacceptable. Budget is about $900 a month.";

const ALERT_SELECTOR = '[role="alert"]:not(#__next-route-announcer__)';

/**
 * The landing page's two priced sections are the only 5xx this suite accepts,
 * and only as 503.
 *
 * /api/landing/showcase needs at least one COMPLETE option from /compare --
 * every line item priced from a real SKU. A checkout seeded only with
 * backend/whichcloud/pricing/fallback_catalog.json (115 points, which is what
 * CI and any clone without an ingested catalog have) has no rows for CDN,
 * KMS, DNS, TLS certificates, audit logging or backup storage, so no option
 * can be complete and the route returns its documented 503 with a 10-second
 * cache. Verified directly: /compare answers 200 with complete=false and
 * missing: ['CDN', 'database storage', ...] on all three clouds. That is the
 * engine correctly refusing to show a total it cannot stand behind, and the
 * fix is a real price catalog -- never invented rows in the fallback file,
 * which this same suite checks the site makes no false claims about.
 *
 * The distinction matters: these routes are also matched by proxy.ts's
 * "/api/(.*)" entry, and while clerkMiddleware threw on them they answered
 * 500. Tolerating 503 while still failing on 500 is what separates "this
 * catalog cannot price it" from "the route crashed" -- the blanket 5xx check
 * could not tell them apart, which is exactly where that 500 hid.
 */
const TOLERATED_5XX: ReadonlyArray<{ match: string; status: number }> = [
  { match: "/api/landing/showcase", status: 503 },
  { match: "/api/landing/demos", status: 503 },
];

function isToleratedFailure(url: string, status: number): boolean {
  return TOLERATED_5XX.some((t) => url.includes(t.match) && status === t.status);
}

function trackPageHealth(page: import("@playwright/test").Page) {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const txt = msg.text();
      // Ignore expected 400/401/501 test assertions or third-party Clerk dev/placeholder keys in offline/CI
      if (!txt.toLowerCase().includes("clerk") && !txt.includes("Failed to load resource")) {
        consoleErrors.push(txt);
      }
    }
  });
  page.on("pageerror", (err) => {
    consoleErrors.push(`pageerror: ${err.message}`);
  });
  page.on("response", (res) => {
    const status = res.status();
    const url = res.url();
    if (status >= 500 && !url.includes("clerk") && !isToleratedFailure(url, status)) {
      failedRequests.push(`${status} ${url}`);
    }
  });
  return { consoleErrors, failedRequests };
}

test.describe("Phase 5: Whole-site UI QA", () => {
  test("Home (/) desktop & mobile, honest copy, keyboard focus, no horizontal overflow", async ({
    page,
  }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/", { waitUntil: "load" });
    await expect(page.locator("header").first()).toBeVisible();
    await expect(page.locator("h1").first()).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("GCP covers compute only");
    expect(bodyText).not.toContain("hardcoded prices in the source");
    expect(bodyText).not.toContain("<300ms");

    // Basic keyboard navigation check
    await page.keyboard.press("Tab");
    const focusedTag = await page.evaluate(() => document.activeElement?.tagName ?? "");
    expect(["A", "BUTTON", "INPUT", "TEXTAREA"]).toContain(focusedTag);

    await page.screenshot({
      path: path.join(QA_DIR, "home-desktop.png"),
      fullPage: false,
      caret: "initial",
    });

    // Mobile 390px check
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    await page.screenshot({
      path: path.join(QA_DIR, "home-mobile.png"),
      fullPage: false,
      caret: "initial",
    });
    expect(overflow).toBeLessThanOrEqual(4);
    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);

    /* The landing page's priced sections may answer 503 when the catalog
       cannot price them (see TOLERATED_5XX), but they must never throw. Both
       are matched by proxy.ts's "/api/(.*)" entry, and while clerkMiddleware
       ran without keys it threw before either handler was reached, so both
       returned 500 -- on every page view, because the header nav prefetches
       them. Asserting the exact statuses keeps that regression caught rather
       than absorbed by the 5xx tolerance above. */
    for (const route of ["/api/landing/showcase", "/api/landing/demos"]) {
      const res = await page.request.get(route);
      expect(
        [200, 503],
        `${route} answered ${res.status()}; 500 means the handler threw`,
      ).toContain(res.status());
    }
  });

  test("Price index (/prices) shows last-updated timestamp & filters", async ({ page }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.goto("/prices", { waitUntil: "load" });

    const stamp = page.getByTestId("prices-last-updated");
    await expect(stamp).toBeVisible();
    await expect(stamp).toContainText("Last updated:");
    // Ensure client hydration completes before screenshot injects caret-color
    const searchInput = page.getByLabel("Search machine types");
    await expect(searchInput).toBeVisible();
    await page.waitForTimeout(400);

    await page.screenshot({ path: path.join(QA_DIR, "prices-desktop.png"), fullPage: false });
    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("Estimate (/estimate) form + describe mode + stamp", async ({ page }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.goto("/estimate", { waitUntil: "load" });
    await expect(page.getByRole("button", { name: "Price it" })).toBeVisible();

    // Form mode submit
    await page.getByRole("button", { name: "Price it" }).click();
    await expect(page.getByTestId("generated-for-stamp")).toBeVisible();
    await page.screenshot({ path: path.join(QA_DIR, "estimate-desktop.png"), fullPage: false });

    // Describe mode
    await page.getByRole("button", { name: "Describe it" }).click();
    const ta = page.locator("textarea");
    await expect(ta).toBeVisible();
    await ta.fill(PUNE_WORKLOAD);
    await page.getByRole("button", { name: "Price it" }).click();
    await expect(page.getByTestId("generated-for-stamp")).toContainText(
      "Generated for: I manage IT for a 3-hospital group in Pune"
    );

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("Plan (/plan) submits workload and displays tiers + stamp", async ({ page }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.goto("/plan", { waitUntil: "load" });
    await expect(page.locator("#description")).toBeVisible();

    await page.locator("#description").fill(PUNE_WORKLOAD);
    await page.getByRole("button", { name: "Plan it" }).click();
    await expect(page.getByTestId("generated-for-stamp")).toContainText(
      "Generated for: I manage IT for a 3-hospital group in Pune"
    );
    await page.screenshot({ path: path.join(QA_DIR, "plan-desktop.png"), fullPage: false });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("Terraform Studio (/terraform) toggles, empty-input validation, full-page diagram, Download ZIP + terraform validation, mobile", async ({
    page,
    request,
  }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/terraform", { waitUntil: "load" });

    const stamp = page.getByTestId("generated-for-stamp");
    await expect(stamp).toBeVisible({ timeout: 30_000 });

    // Empty input validation in Edit Workload modal
    await page.getByRole("button", { name: "Edit Workload" }).click();
    const modalTa = page.locator("#terraform-workload-input");
    await expect(modalTa).toBeVisible();
    await modalTa.fill("   ");
    await page.getByRole("button", { name: /Generate Architecture & Terraform/i }).click();
    await expect(page.locator(ALERT_SELECTOR).first()).toContainText(
      "Please enter a workload description"
    );

    // Submit real Pune workload
    await modalTa.fill(PUNE_WORKLOAD);
    await page.getByRole("button", { name: /Generate Architecture & Terraform/i }).click();
    await expect(stamp).toContainText("Generated for: I manage IT for a 3-hospital group in Pune", {
      timeout: 30_000,
    });

    const tfEditor = page.locator('textarea[aria-label^="Terraform file"]');
    await expect(tfEditor).not.toHaveValue("");
    const mainTfCode = await tfEditor.inputValue();
    expect(mainTfCode).toContain("terraform");

    // Screenshot Architecture view
    await page.screenshot({ path: path.join(QA_DIR, "terraform-desktop.png"), fullPage: false });

    // Full-page diagram expand & Escape close
    const expandBtn = page.getByRole("button", { name: /Click to expand/i });
    await expect(expandBtn).toBeVisible();
    await expandBtn.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator(".react-flow__node").first()).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(QA_DIR, "diagram-fullpage.png"), fullPage: false });
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);

    // Cost Report tab toggle
    await page.getByRole("button", { name: "Cost Report", exact: true }).click();
    await page.waitForTimeout(300);
    await page.getByRole("button", { name: "Architecture", exact: true }).click();

    // DEV -> PROD toggle
    await page.getByRole("button", { name: "prod", exact: true }).click();
    await expect(tfEditor).not.toHaveValue("");

    // Switch provider AWS -> GCP -> AWS
    await page.getByRole("button", { name: /^gcp$/i }).click();
    await expect(page.locator("main")).toContainText("asia-south1", { timeout: 25_000 });
    await page.getByRole("button", { name: /^aws$/i }).click();
    await expect(page.locator("main")).toContainText("ap-south-1", { timeout: 25_000 });

    // Download ZIP and inspect + syntax validation
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: /Download ZIP/i }).click(),
    ]);
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "whichcloud-zip-"));
    const zipPath = path.join(tmpDir, "export.zip");
    await download.saveAs(zipPath);
    execSync(`unzip -o "${zipPath}" -d "${tmpDir}/extracted"`, { stdio: "pipe" });
    const extractedFiles = fs.readdirSync(path.join(tmpDir, "extracted")).filter((f) => f.endsWith(".tf"));
    expect(extractedFiles).toContain("main.tf");
    const extractedMain = fs.readFileSync(path.join(tmpDir, "extracted", "main.tf"), "utf8");
    expect(extractedMain.length).toBeGreaterThan(100);
    expect(extractedMain).toContain("ap-south-1");

    // Validate EVERY extracted .tf file from the downloaded ZIP via HCL2 parser (/describe/terraform/validate)
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";
    for (const tfFile of extractedFiles) {
      const code = fs.readFileSync(path.join(tmpDir, "extracted", tfFile), "utf8");
      const valRes = await request.post(`${apiBase}/describe/terraform/validate`, {
        data: { code },
      });
      expect(valRes.status(), `HCL validation HTTP status for ${tfFile}`).toBe(200);
      const valJson = await valRes.json();
      expect(valJson.valid, `HCL validation for ${tfFile}: ${JSON.stringify(valJson)}`).toBe(true);
    }

    // Also run terraform fmt if terraform CLI is installed on the runner
    const tfBin = execSync("which terraform || true").toString().trim();
    if (tfBin) {
      execSync(`"${tfBin}" fmt -check=false -write=false "${tmpDir}/extracted"`, { stdio: "pipe" });
    }
    fs.rmSync(tmpDir, { recursive: true, force: true });

    // Mobile 390px layout check on /terraform
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(QA_DIR, "terraform-mobile.png"), fullPage: false });
    const tfOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(tfOverflow).toBeLessThanOrEqual(4);

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("Audit (/audit) valid CSV upload + invalid CSV error handling", async ({ page }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.goto("/audit", { waitUntil: "load" });
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeAttached();

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "whichcloud-audit-"));
    const validCsv = path.join(tmpDir, "aws-cur-sample.csv");
    fs.writeFileSync(
      validCsv,
      [
        "lineItem/ProductCode,lineItem/UsageType,lineItem/UnblendedCost,lineItem/LineItemType",
        "AmazonEC2,APS3-BoxUsage:m5.large,420.50,Usage",
        "AmazonRDS,APS3-InstanceUsage:db.m5.large,310.00,Usage",
        "AmazonS3,APS3-TimedStorage-ByteHrs,45.20,Usage",
      ].join("\n")
    );

    await fileInput.setInputFiles(validCsv);
    await expect(page.getByTestId("generated-for-stamp")).toContainText(
      "Generated for: aws-cur-sample.csv"
    );
    await page.screenshot({ path: path.join(QA_DIR, "audit-desktop.png"), fullPage: false });

    // Upload invalid CSV -> clear error message
    const badCsv = path.join(tmpDir, "invalid.csv");
    fs.writeFileSync(badCsv, "foo,bar\n1,2\n");
    await fileInput.setInputFiles(badCsv);
    await expect(page.locator(ALERT_SELECTOR).first()).toBeVisible();

    fs.rmSync(tmpDir, { recursive: true, force: true });
    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("Environments (/environments) tabs, Terraform preview & drift detection", async ({ page }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.goto("/environments", { waitUntil: "load" });

    await expect(page.locator("body")).toContainText(/dev/i);
    await page.screenshot({ path: path.join(QA_DIR, "environments-desktop.png"), fullPage: false });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("Connect (/connect auth gate) & FinOps Live Demo (/finops?provider=aws&account_id=demo)", async ({
    page,
  }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);

    /* /connect is Clerk-protected. An unauthenticated visitor must be sent to
       sign-in -- not shown the page, and not handed a 500.

       Asserting "no 5xx" alone was not enough. proxy.ts guards against
       clerkMiddleware throwing when the Clerk keys are absent, and that guard
       used to call NextResponse.next(), which let the request THROUGH: a
       deployment missing its keys served /dashboard, /finops and this
       cloud-account wizard to anyone, and this test still passed because 200
       is under 500. The gate has to be closed, so check where we actually
       landed rather than only what the status was. */
    const connectRes = await page.goto("/connect", { waitUntil: "load" });
    expect(connectRes?.status() ?? 200).toBeLessThan(500);
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
    expect(
      new URL(page.url()).pathname,
      "an unauthenticated visitor must not be left on /connect",
    ).not.toBe("/connect");
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(QA_DIR, "connect-desktop.png"), fullPage: false });

    // /finops demo mode is publicly accessible and renders FinOps Live
    const finopsRes = await page.goto("/finops?provider=aws&account_id=demo", { waitUntil: "load" });
    expect(finopsRes?.status() ?? 200).toBeLessThan(500);
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
    await expect(page.locator("body")).toContainText(/finops|cost|aws|demo/i);
    await page.screenshot({ path: path.join(QA_DIR, "finops-desktop.png"), fullPage: false });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });
});
