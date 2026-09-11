import { chromium } from "playwright";
const OUT="/Users/mayankthakur/.claude/jobs/4b197142/tmp";
const DESC="Online stock and billing system for a retail chain in India with 40 stores. Around 300 staff use it daily and we do about 8,000 transactions a day. It must not go down during business hours. Budget is around $500 a month.";
const b=await chromium.launch();
for (const scheme of ["light","dark"]) {
  const p=await b.newPage({viewport:{width:1680,height:1000},deviceScaleFactor:2,colorScheme:scheme});
  await p.goto("http://127.0.0.1:3000/shot-preview",{waitUntil:"networkidle"});
  await p.fill("textarea",DESC);
  await p.getByRole("button",{name:/price it/i}).click();
  await p.waitForSelector("text=/on-demand/i",{timeout:180000});
  await p.waitForTimeout(3500);
  await p.screenshot({path:`${OUT}/theme-${scheme}.png`});
  console.log(`captured ${scheme}`);
  await p.close();
}
await b.close();
