/* What the panels added this session actually render.
   The endpoint-coverage walk proves each one's request is made; it proves nothing about what
   comes back onto the screen. These assert the content, because a panel that fetches correctly
   and renders an empty table is a panel nobody would notice was broken. */
import { expect, test, type Page } from "@playwright/test";

const ROLES = ["builder", "reviewer", "approver", "auditor"];
const IR = [{
  object: "PicklistOption", product: "SuccessFactors", system_binding: "KOM-SF-DEV",
  external_code: "MIBCO_FLAG", tier: "A",
  source: { workbook: "ZA-payroll-v3.xlsx", signed_by: "T. Mabaso", date: "2026-09-01" },
  intent: {
    externalCode: "MIBCO_FLAG",
    entitlement: { value: 21, refinement: { kind: "bounded", max: 15, statute: "BCEA s20",
                                            signed_by: "T. Mabaso", date: "2026-09-01" } },
  },
  contract: { owner: "EC", consumers: ["Time Off", "EE Reporting"], feeds: ["ECC IT0001"],
              statutory: "MIBCO main agreement" },
}];

async function open(page: Page, who: string) {
  await page.goto("/");
  await page.getByLabel("Name").fill(who);
  for (const r of ROLES) {
    const btn = page.getByRole("button", { name: r, exact: true });
    if (!((await btn.getAttribute("class"))?.includes("primary") ?? false)) await btn.click();
  }
  await page.getByRole("button", { name: "Enter the console" }).click();
  await expect(page.locator(".topbar")).toContainText(who);
  await page.getByRole("button", { name: "New engagement" }).click();
  await page.getByLabel("Client").fill("Komatsu");
  await page.getByLabel("Name").last().fill(`Panels ${Date.now()}`);
  await page.getByRole("button", { name: "Open it" }).click();
  await expect(page.locator(".scrim")).toHaveCount(0);
}

test("the type-check prints the statute, the signer and the date it was refused on", async ({ page, request }) => {
  await open(page, "panel.tester");
  const eid = await page.getByLabel("Engagement").inputValue();
  expect((await request.post(`/engagements/${eid}/ir`, { data: IR })).ok()).toBeTruthy();

  await page.getByRole("tab", { name: /^Intent/ }).click();
  const types = page.locator(".sec", { hasText: "What the types say" });
  // The rejection is the auditor's control narrative, so the screen must show it word for word.
  await expect(types).toContainText("configured as 21");
  await expect(types).toContainText("signed statutory maximum is 15");
  await expect(types).toContainText("BCEA s20, signed by T. Mabaso on 2026-09-01");
  await expect(types).toContainText("not a configuration choice");
});

test("the contract registry names the owner and everyone registered to read it", async ({ page, request }) => {
  await open(page, "contract.tester");
  const eid = await page.getByLabel("Engagement").inputValue();
  await request.post(`/engagements/${eid}/ir`, { data: IR });

  await page.getByRole("tab", { name: /^Intent/ }).click();
  const row = page.locator(".sec", { hasText: "Cross-module contracts" }).locator("tbody tr").first();
  await expect(row).toContainText("EC");
  await expect(row).toContainText("Time Off");
  await expect(row).toContainText("EE Reporting");
  await expect(row).toContainText("MIBCO main agreement");
});

test("the account of itself says what it cannot measure, not only what it can", async ({ page }) => {
  await open(page, "account.tester");
  await page.getByRole("tab", { name: /^Evidence/ }).click();
  const panel = page.locator(".sec", { hasText: "What I got wrong" });
  await expect(panel).toContainText("I have refused nothing here");
  await panel.getByText("What these numbers cannot tell you").click();
  await expect(panel).toContainText("never reached a gate");
  await expect(panel).toContainText("Harm avoided");
});

test("the portfolio says which engagements need a person, in words", async ({ page }) => {
  await open(page, "portfolio.tester");
  await page.getByRole("tab", { name: /^Portfolio/ }).click();
  const panel = page.locator(".sec", { hasText: "Every engagement" });
  await expect(panel).toContainText("need a person today");
  // A night that has never run is on the list, not assumed fine — the failure this exists for is
  // a programme nobody has opened in three weeks looking exactly like one that is going well.
  await expect(panel.locator("tbody tr").first()).toContainText("No night has ever been worked");
});

test("the night shift card reports a stopped clock above the handover", async ({ page }) => {
  await open(page, "clock.tester");
  await page.getByRole("tab", { name: /^Crew/ }).click();
  const panel = page.locator(".sec", { hasText: "The night shift" });
  await expect(panel).toContainText("No night has ever been worked here");
});
