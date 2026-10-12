// Interaction QA: asserts behaviours the screenshot loop does not cover. Usage: node scripts/interact.mjs [baseUrl]
import { chromium } from 'playwright-core';

const base = process.argv[2] ?? 'http://127.0.0.1:5173/';
const browser = await chromium.launch({ channel: process.env.QUORUM_BROWSER ?? 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const problems = [];
const results = [];
page.on('console', (m) => m.type() === 'error' && problems.push(`console: ${m.text()}`));
page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));

const wait = (ms) => page.waitForTimeout(ms);
const check = (name, ok, extra = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
};
const btn = (name) => page.getByRole('button', { name, exact: false }).first();
const text = (sel) => page.locator(sel).first().innerText();

// ---- landing page ----
await page.goto(base);
await page.waitForSelector('.lp-hero h1', { timeout: 15000 });
await wait(300);
check('landing loads with the product headline', (await text('.lp-h1')).replace(/\s+/g, ' ').includes('revert'));
check('hero window is live (graph svg present)', (await page.locator('.lp-window svg.lg').count()) === 1);
await page.evaluate(() => document.getElementById('playground')?.scrollIntoView());
await wait(900);
await page.getByRole('button', { name: /Window: 90 days/ }).first().click().catch(() => undefined);
const pg = page.locator('#playground');
await pg.locator('.lg-node.hot', { hasText: 'Up to 90 qualify' }).first().click();
await wait(2600);
const held = await pg.locator('.lp-meters div').first().innerText();
check('playground: clicking a belief quarantines it and everything downstream', /0?5/.test(held.split('\n')[0] ?? ''), held.replace(/\n/g, ' '));
check('playground: executed refunds roll back, the held email is cancelled', (await pg.locator('.lg-state', { hasText: 'Rolled back' }).count()) === 2 && (await pg.locator('.lg-state', { hasText: 'Cancelled' }).count()) === 1);
await pg.getByRole('button', { name: 'Restore everything' }).click();
await wait(300);
check('playground: restore returns everything to healthy', (await pg.locator('.lg-node.bad').count()) === 0);
await pg.locator('.lg-node.hot', { hasText: 'Window: 30 days' }).first().click();
await wait(300);
check('playground: a root fact refuses quarantine and blames the challenger', (await pg.locator('.lp-play-note').innerText()).includes('Root facts are never auto-quarantined'));
await page.evaluate(() => document.getElementById('defense')?.scrollIntoView());
await wait(600);
const before = await page.locator('#defense .lp-counter b').innerText();
await page.getByRole('button', { name: 'Next layer' }).click();
await wait(300);
check('defense carousel advances', (await page.locator('#defense .lp-counter b').innerText()) !== before);
await page.evaluate(() => document.getElementById('console')?.scrollIntoView());
await page.getByRole('button', { name: 'Next screen' }).click();
await wait(400);
check('console gallery advances and the screenshot loads', await page.locator('.lp-shot img').evaluate((i) => i.complete && i.naturalWidth > 0));
await page.evaluate(() => window.scrollTo(0, 0));
await page.getByRole('button', { name: 'Open console' }).first().click();
await page.waitForSelector('.cy canvas', { timeout: 15000 });
check('Open console routes into the app', page.url().endsWith('#/app'));
await page.getByRole('button', { name: 'Quorum home' }).click();
await page.waitForSelector('.lp-hero h1');
check('the app brand returns to the landing page', page.url().endsWith('#/') || !page.url().includes('#/app'));
await page.getByRole('button', { name: 'Watch the 90-second story' }).first().click();
await page.waitForSelector('.cy canvas', { timeout: 15000 });
await wait(2200);
check('the 90-second story button starts autopilot in the console', await btn('Inject poisoned webhook').isDisabled());
await page.goto(base.replace(/\/?$/, '/') + '#/');
await page.reload();

await page.goto(base.replace(/\/?$/, '/') + '#/app');
await page.waitForSelector('.cy canvas');
await wait(600);

check('sample-data chip is visible', (await text('.pill.sample')).includes('Sample data'));
check('mode badge says Replay', (await text('.pill.mode')) === 'Replay');

// shortcuts
await page.keyboard.press('?');
check('? opens the shortcut legend', await page.locator('.modal').isVisible());
await page.keyboard.press('Escape');
check('Esc closes the legend', !(await page.locator('.modal').count()));
await page.keyboard.press('l');
check('L toggles list view', await page.locator('.listview').isVisible());
await page.keyboard.press('l');
await page.keyboard.press('/');
check('/ focuses search', await page.evaluate(() => document.activeElement?.id === 'graph-search'));
await page.keyboard.press('Escape');

// scenario out of order is refused honestly
await btn('Audit memory').click();
await wait(500);
check('audit before agents ran is refused with a reason', (await text('.progress')).includes('Run the agents first'));

// run through to the audit
await btn('Inject poisoned webhook').click();
await wait(1700);
await btn('Run agents').click();
await wait(6000);

check('email action shows Held for review', (await page.locator('.feed').innerText()).includes('Held for review'));

// review queue: agent role gets the 403 message
await page.getByRole('tab', { name: 'Actions and handoffs' }).click();
await wait(500);
check('review queue shows the pending email review', (await page.locator('.handoff.kind-REVIEW').count()) === 1);
await page.getByRole('button', { name: 'Dev console' }).click();
await page.locator('.dev-role select').selectOption('agent');
await wait(1500);
await page.getByRole('tab', { name: 'Actions and handoffs' }).click();
await wait(400);
await page.getByRole('button', { name: 'Reject' }).first().click();
await wait(500);
check('agent token gets "Only a person can decide this"', (await page.locator('.toasts').innerText()).includes('Only a person can decide this'));
await page.locator('.dev-role select').selectOption('human');
await wait(1500);
await page.getByRole('button', { name: 'Dev console' }).click();

// scenario state may have been reloaded by role switch: it must still be consistent
await page.getByRole('tab', { name: 'Graph', exact: true }).click();
await wait(400);
await btn('Audit memory').click();
await wait(5200);

// inspector
const clicked = await page.evaluate(() => {
  const rect = document.querySelector('.cy canvas')?.getBoundingClientRect();
  return rect ? { w: rect.width, h: rect.height } : null;
});
check('canvas exists', !!clicked);
await page.getByRole('button', { name: 'List view' }).click();
await page.locator('.list-row', { hasText: 'Refund window is 90 days' }).first().click();
await wait(700);
check('inspector shows path for the poisoned fact', (await text('.inspector')).includes('Partner feed update'));
await page.getByRole('tab', { name: 'Details' }).click();
await wait(300);
const det = await text('.inspector');
check('details show quarantined status and 6 downstream nodes', det.includes('Quarantined') && det.includes('6 nodes built on this'));
await page.getByRole('tab', { name: 'Cypher' }).click();
await wait(500);
check('Cypher tab shows the cascade query', (await text('.inspector')).includes('QUARANTINED'));
await page.getByRole('button', { name: 'Graph view' }).click();

// containment report
check('containment report is docked', (await text('.containment')).includes('To containment'));

// time travel
await page.evaluate(() => {
  const el = document.querySelector('.tl-track input');
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  set.call(el, el.min);
  el.dispatchEvent(new Event('input', { bubbles: true }));
});
await wait(900);
check('slider enters the "Viewing the past" frame', await page.locator('.past-bar').isVisible());
await btn('Compare from here').click();
await page.evaluate(() => {
  const el = document.querySelector('.tl-track input');
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  set.call(el, el.max);
  el.dispatchEvent(new Event('input', { bubbles: true }));
});
await wait(900);
const diffText = await text('.belief-diff');
check('belief diff counts quarantined nodes between the two moments', /[1-9]\d* quarantined/.test(diffText), diffText.split('\n').slice(-1)[0]);
check('Back to now is gone at the present', !(await page.locator('.past-bar').count()));

// tenant switch
await page.selectOption('.tenant select', 'globex');
await wait(1200);
check('globex starts empty', (await page.locator('.canvas-empty').count()) === 1);
await page.getByRole('button', { name: 'Tenants', exact: true }).click();
await wait(600);
check('tenant denied-read reports DENIED for globex', (await text('.denied')).includes('Denied') && (await text('.denied')).includes('tenant_acme:commons'));
await page.getByRole('button', { name: 'Console', exact: true }).click();
await page.selectOption('.tenant select', 'acme');
await wait(1000);

// presentation mode
await page.keyboard.press('p');
await wait(500);
check('P enters presentation mode and hides the scenario panel', (await page.locator('.scenario').count()) === 0);
check('sample-data chip stays while presenting', await page.locator('.pill.sample').isVisible());
await page.keyboard.press('Escape');

// responsive
for (const w of [1280, 1024]) {
  await page.setViewportSize({ width: w, height: 800 });
  await wait(500);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  check(`no horizontal page scroll at ${w}px`, !overflow);
}
await page.setViewportSize({ width: 1440, height: 900 });

// autopilot (reset first)
await btn('Reset scenario').click();
await wait(1500);
await btn('Autopilot').click();
await wait(500);
check('autopilot disables manual steps', await btn('Inject poisoned webhook').isDisabled());
await wait(34000);
const views = await page.evaluate(() => document.querySelector('.navbtn.on')?.textContent);
const feed = await text('.feed');
check('autopilot ran poison, audit and supersede', feed.includes('Quarantined') && feed.includes('Replaced'), `view now: ${views}`);
await wait(9000);
check('autopilot finishes and re-enables controls', !(await btn('Inject poisoned webhook').isDisabled()));

await browser.close();
const failed = results.filter((r) => !r.ok);
if (problems.length) console.error('PROBLEMS:\n' + problems.join('\n'));
console.log(`\n${results.length - failed.length}/${results.length} checks passed, ${problems.length} console problems`);
process.exit(failed.length || problems.length ? 1 : 0);
