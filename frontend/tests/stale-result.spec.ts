import { test, expect } from "@playwright/test";

const WORKLOAD_A =
  "I manage IT for a 3-hospital group in Pune. We want to move patient appointments, records and lab reports online so doctors and front desk can access them from all three sites. About 450 staff use it, roughly 6,000 record lookups a day, with peaks in the morning. Patient data must stay inside India and cannot be lost. Downtime during OPD hours is unacceptable. Budget is about $900 a month.";

const WORKLOAD_B =
  "Marketing site for our design studio. About 30,000 visitors a month, mostly from India. It's just pages and images, no login, no database. We want it cheap.";

test.describe("Phase 1: Stale-result fix on /terraform", () => {
  // The workload used to be read-only text with editing behind an "Edit
  // Workload" modal. It is an inline text box in the subheader now, so the
  // two extra clicks this test used to make are gone -- the interaction
  // being tested is the same one.
  test("editing the workload inline updates architecture, Terraform and prices", async ({
    page,
  }) => {
    await page.goto("/terraform", { waitUntil: "networkidle" });

    // Wait for initial render to settle before editing
    const stamp = page.getByTestId("generated-for-stamp");
    await expect(stamp).toBeVisible();

    // Submit Workload A
    const textarea = page.locator("#terraform-workload-bar");
    await expect(textarea).toBeVisible();
    await textarea.fill(WORKLOAD_A);
    await page.getByRole("button", { name: /^Generate$/ }).click();

    // Wait for Generated-for stamp matching Workload A
    await expect(stamp).toContainText("Generated for: I manage IT for a 3-hospital group in Pune");

    // Wait for Terraform editor to populate and capture Workload A code & price
    const tfEditor = page.locator('textarea[aria-label^="Terraform file"]');
    await expect(tfEditor).toBeVisible();
    await expect(tfEditor).not.toHaveValue("");
    const codeA = await tfEditor.inputValue();
    const headerPricesA = await page.locator("main header").first().innerText();

    // Submit Workload B
    await expect(textarea).toBeVisible();
    await textarea.fill(WORKLOAD_B);
    await page.getByRole("button", { name: /^Generate$/ }).click();

    // Wait for Generated-for stamp matching Workload B
    await expect(stamp).toContainText("Generated for: Marketing site for our design studio");
    await expect(tfEditor).toBeVisible();
    await expect(tfEditor).not.toHaveValue("");
    const codeB = await tfEditor.inputValue();
    const headerPricesB = await page.locator("main header").first().innerText();

    expect(codeB).not.toEqual(codeA);
    expect(headerPricesB).not.toEqual(headerPricesA);
    expect(headerPricesA).toContain("$");
    expect(headerPricesB).toContain("$");
  });
});
