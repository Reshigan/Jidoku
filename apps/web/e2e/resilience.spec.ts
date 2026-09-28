/* The four defects a 16-test e2e suite and a strict typecheck both missed.
   Each one was reproduced before it was fixed; each test here fails against the old code. */
import { expect, test, type Page } from "@playwright/test";

const ROLES = ["builder", "reviewer", "approver", "auditor"];

async function signIn(page: Page, who: string) {
  await page.goto("/");
  await page.getByLabel("Name").fill(who);
  for (const r of ROLES) {
    const btn = page.getByRole("button", { name: r, exact: true });
    const on = (await btn.getAttribute("class"))?.includes("primary") ?? false;
    if (!on) await btn.click();
  }
  await page.getByRole("button", { name: "Enter the console" }).click();
  await expect(page.locator(".topbar")).toContainText(who);
}

async function newEngagement(page: Page, name: string) {
  await page.getByRole("button", { name: "New engagement" }).click();
  await page.getByLabel("Client").fill("Komatsu");
  await page.getByLabel("Name").last().fill(name);
  await page.getByRole("button", { name: "Open it" }).click();
  await expect(page.locator(".scrim")).toHaveCount(0);
}

test("a person can type a whole word into a dialog", async ({ page }) => {
  /* The defect: Modal's focus effect depended on `props`, a fresh object every render, so every
     keystroke re-ran it and pulled focus back to the dialog container. One character landed and
     the rest went nowhere — every dialog in the product, unusable by a human. The suite missed it
     because Playwright's fill() sets a value in one operation. This types it. */
  await signIn(page, "typing.tester");
  await page.getByRole("button", { name: "New engagement" }).click();
  const client = page.getByLabel("Client");
  await client.click();
  await client.pressSequentially("Komatsu", { delay: 20 });
  await expect(client).toHaveValue("Komatsu");
});

test("a slow answer about the last engagement never paints over this one", async ({ page }) => {
  /* The defect: load() set state unconditionally, so switching engagements while a load was in
     flight let the slower response win — the selector naming one client and the ledger, plan and
     decisions on screen belonging to another. */
  await signIn(page, "race.tester");
  await newEngagement(page, "AAA race one");
  await newEngagement(page, "ZZZ race two");

  const slow = new Set<string>();
  await page.route("**/engagements/*/**", async (route) => {
    const id = route.request().url().match(/engagements\/([^/]+)\//)?.[1] ?? "";
    if (slow.has(id)) await new Promise((r) => setTimeout(r, 2000));
    await route.continue();
  });

  const sel = page.getByLabel("Engagement");
  const options = await sel.locator("option").evaluateAll((os) =>
    (os as HTMLOptionElement[]).map((o) => ({ id: o.value, label: o.textContent ?? "" })));
  const one = options.find((o) => o.label.includes("AAA race one"))!;
  const two = options.find((o) => o.label.includes("ZZZ race two"))!;

  slow.add(one.id);
  await sel.selectOption(one.id);
  await sel.selectOption(two.id);
  await page.waitForTimeout(8000);          // long enough for the stale answer to land

  await expect(sel.locator("option:checked")).toHaveText(/ZZZ race two/);
  await expect(page.locator(".head h1")).toHaveText("ZZZ race two");
});

test("the rail never names a number key that selects a different view", async ({ page }) => {
  /* The defect: the label was `press ${(i + 1) % 10}` for all fifteen views, so Memory announced
     "press 1" — which selects Line. A label naming a key that does something else is worse than
     no label, and worst for the person who cannot see which lamp lit. */
  await signIn(page, "key.tester");
  const tabs = await page.getByRole("tab").evaluateAll((els) =>
    els.map((e) => ({ label: e.getAttribute("aria-label") ?? "", text: e.textContent ?? "" })));
  const lies = tabs.flatMap((t, i) => {
    const claim = t.label.match(/press (\d)/)?.[1];
    if (!claim) return [];
    const selects = claim === "0" ? 10 : Number(claim);
    return selects === i + 1 ? [] : [`${t.text} claims "press ${claim}", which selects view ${selects}`];
  });
  expect(lies).toEqual([]);
});

test("a panel that throws does not take the console with it", async ({ page }) => {
  /* Observed for real: a view hit data it did not expect, React unmounted the whole tree
     including the rail, and the screen went blank with no way back. Here the failure is forced by
     answering one panel's endpoint with a shape it cannot read. */
  await signIn(page, "boundary.tester");
  await newEngagement(page, "Boundary probe");
  await page.route("**/engagements/*/objections", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"nonsense": true}' }));

  await page.getByRole("tab", { name: /^Decisions/ }).click();
  await expect(page.getByText("could not be shown")).toBeVisible();
  // The rail is still there, the decision points beside it are still there, and the operator can
  // still navigate away — which is the whole property.
  await expect(page.getByRole("tab", { name: /^Ledger/ })).toBeVisible();
  await page.getByRole("tab", { name: /^Ledger/ }).click();
  await expect(page.locator(".page")).not.toBeEmpty();
});
