import { chromium } from "@playwright/test";
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
await p.goto("http://localhost:5273/");
await p.getByLabel("Name").fill("shot.tester");
for (const r of ["reviewer", "approver", "auditor"]) {
  const btn = p.getByRole("button", { name: r, exact: true });
  if (!((await btn.getAttribute("class")) || "").includes("primary")) await btn.click();
}
await p.getByRole("button", { name: "Enter the console" }).click();
await p.waitForTimeout(1200);
// pick the seeded engagement
const sel = p.locator("select").first();
if (await sel.count()) {
  const opts = await sel.locator("option").allTextContents();
  console.log("engagements:", opts.join(" | "));
}
await p.getByRole("tab", { name: /^Memory/ }).click();
await p.waitForTimeout(1500);
await p.screenshot({ path: "/private/tmp/claude-501/-Users-reshigan-Jidoku/9d6b315b-2cb2-489b-9ccc-1fe31246671b/scratchpad/mem.png" });
await b.close();
