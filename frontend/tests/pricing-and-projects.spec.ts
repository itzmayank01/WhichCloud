import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const QA_DIR = path.resolve(__dirname, "../../docs/qa");
fs.mkdirSync(QA_DIR, { recursive: true });

function trackPageHealth(page: import("@playwright/test").Page) {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const txt = msg.text();
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
    if (status >= 500 && !url.includes("clerk")) {
      failedRequests.push(`${status} ${url}`);
    }
  });
  return { consoleErrors, failedRequests };
}

test.describe("Monetization & Projects QA", () => {
  test("Pricing (/pricing) desktop & mobile, annual toggle, ROI calculator, FAQ", async ({ page }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/pricing", { waitUntil: "load" });

    await expect(page.locator("h1")).toContainText("Invest in clarity");
    await expect(page.locator("text=Pro Engineer")).toBeVisible();
    await expect(page.locator("text=Team & Scale")).toBeVisible();
    await expect(page.locator("text=Starter / Free")).toBeVisible();

    // Default is annual: Pro is $24
    await expect(page.getByText("$24", { exact: true }).first()).toBeVisible();

    // Toggle to monthly
    const toggleButton = page.locator('button[role="switch"]');
    await toggleButton.click();
    await expect(page.getByText("$29", { exact: true }).first()).toBeVisible();

    // ROI calculator check
    const slider = page.locator("#spend-slider");
    await expect(slider).toBeVisible();
    await expect(page.locator("text=Calculated Annual ROI")).toBeVisible();

    // Take desktop screenshot
    await page.screenshot({
      path: path.join(QA_DIR, "pricing-desktop.png"),
      fullPage: false,
    });

    // Mobile 390px check
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(4);

    await page.screenshot({
      path: path.join(QA_DIR, "pricing-mobile.png"),
      fullPage: false,
    });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("Projects Hub (/projects) tabs, actions, responsive layout", async ({ page }) => {
    const { consoleErrors, failedRequests } = trackPageHealth(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/projects", { waitUntil: "load" });

    await expect(page.locator("h1")).toContainText("Cloud Projects & Infrastructure Hub");
    await expect(page.locator("text=Cloud Architectures")).toBeVisible();
    await expect(page.locator("text=Connected Cloud Accounts")).toBeVisible();
    await expect(page.locator("text=Multi-Env IaC Deployments")).toBeVisible();

    // Switch to Connected Accounts tab
    await page.click("text=Connected Cloud Accounts");
    await expect(page.locator("text=AWS Account: demo")).toBeVisible();
    await expect(page.locator("text=Open FinOps Live")).toBeVisible();

    // Switch to Multi-Env Deployments tab
    await page.click("text=Multi-Env IaC Deployments");
    await expect(page.getByRole("heading", { name: "dev", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "staging", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "production", exact: true })).toBeVisible();

    // Desktop screenshot
    await page.screenshot({
      path: path.join(QA_DIR, "projects-desktop.png"),
      fullPage: false,
    });

    // Mobile check
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(4);

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });
});
