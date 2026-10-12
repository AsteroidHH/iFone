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
check('details show quarantined status and 7 downstream nodes', det.includes('Quarantined') && det.includes('7 nodes built on this'), det.replace(/s+/g, ' ').slice(0, 200));
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
check('slider enters the "Viewing the past" frame', await page.locator('.status-chip.past').isVisible());
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
check('Back to now is gone at the present', !(await page.locator('.status-chip.past').count()));

// navigation and analysis features
await page.keyboard.press('Control+k');
await page.locator('.palette').waitFor({ timeout: 2000 }).catch(() => {});
check('Ctrl K opens the command palette', await page.locator('.palette').isVisible());
await page.keyboard.type('prompt diff');
await wait(200);
await page.keyboard.press('Enter');
await wait(500);
check('palette runs a command: Prompt diff tab opens', (await page.locator('.diff').count()) === 1);
await page.keyboard.press('Control+k');
await page.keyboard.type('Approve refunds up to 90');
await wait(200);
await page.keyboard.press('Enter');
await wait(700);
check('palette jumps to a node and selects it', (await text('.crumb-trail')).includes('Approve refunds up to 90 days'));
await page.keyboard.press('Control+k');
await page.keyboard.type('Refund order 1042');
await page.keyboard.press('Enter');
await wait(600);
await page.keyboard.press('Alt+ArrowLeft');
await wait(400);
check('Alt Left returns to the previous selection', (await text('.crumb-trail')).includes('Approve refunds up to 90 days'));
await page.keyboard.press('Alt+ArrowRight');
await wait(400);
check('Alt Right moves forward again', (await text('.crumb-trail')).includes('Refund order 1042'));
await page.getByRole('tab', { name: 'Links' }).click();
await wait(300);
check('Links tab lists what the node is built from', (await text('.links')).includes('Approve refunds up to 90 days'));

await page.getByRole('button', { name: 'Show or hide the minimap' }).click();
await wait(300);
await page.getByRole('button', { name: 'Filters' }).click();
const mmBefore = await page.locator(".mm-node").count();
await page.getByLabel('Show only what needs attention').check();
await wait(700);
await page.keyboard.press('Escape');
const after = await page.locator('.mm-node').count();
check('Show only what needs attention hides healthy nodes', after > 0 && after < mmBefore, `${mmBefore} to ${after}`);
await page.getByRole('button', { name: /Filters/ }).click();
await page.getByRole('button', { name: 'Reset filters' }).click();
await page.keyboard.press('Escape');
await wait(400);
const restored = await page.locator('.mm-node').count();
check('Reset filters brings every node back', restored === mmBefore, `${restored}`);

const pos = await page.locator('.cy').evaluate((el) => {
  const cy = el.__cy;
  const n = cy.getElementById('fact_90d');
  const p = n.renderedPosition();
  const r = el.getBoundingClientRect();
  return { x: r.left + p.x, y: r.top + p.y };
});
await page.mouse.click(pos.x, pos.y, { button: 'right' });
await wait(300);
check('right-clicking a node opens its context menu', await page.locator('.ctxmenu').isVisible());
await page.getByRole('menuitem', { name: 'Trace back to its sources' }).click();
await wait(500);
check('Trace back highlights the path on the graph', await page.locator('.status-chip.path').isVisible());
await page.locator('.status-chip.path .iconbtn').click();

await page.getByRole('tab', { name: 'Insights' }).click();
await wait(500);
check('Insights shows the belief flow chart', (await page.locator('.ins-flow').count()) === 1);
check('Insights lists the most connected nodes', (await page.locator('.ins-gods li').count()) >= 3);
check('Insights has a quarantined count', (await text('.ins-kpi.bad')).includes('08'), (await text('.ins-kpi.bad')).replace(/s+/g, ' '));
await page.getByRole('button', { name: 'Show on graph' }).click();
await wait(500);
check('shortest path can be shown on the graph', await page.locator('.status-chip.path').isVisible());
await page.locator('.status-chip.path .iconbtn').click();
await page.getByRole('tab', { name: 'Graph', exact: true }).click();

for (const [key, name] of [['2', 'Memory'], ['3', 'Brain'], ['1', 'Console']]) {
  await page.keyboard.press(key);
  await wait(250);
  check(`key ${key} switches to ${name}`, (await text('.navbtn.on')).includes(name));
}

// overlays: layering, dismissal and collisions
const rect = (sel) => page.locator(sel).first().evaluate((el) => { const r = el.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; });
const hit = (a, b) => a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b;

await page.getByRole('tab', { name: 'Graph', exact: true }).click();
await wait(400);
const parts = {};
for (const [k, sel] of [['search', '.ov-toolbar .search'], ['view', '.ov-toolbar .seg'], ['filters', '.filters-wrap'], ['collapse', '.ov-toolbar .iconbtn.boxed'], ['mini', '.minimap'], ['legend', '.legend-toggle'], ['zoom', '.zoomdock']]) parts[k] = await rect(sel);
const names = Object.keys(parts);
const clashes = [];
for (let i = 0; i < names.length; i++) for (let j = i + 1; j < names.length; j++) if (hit(parts[names[i]], parts[names[j]])) clashes.push(`${names[i]}/${names[j]}`);
check('canvas controls never overlap each other', clashes.length === 0, clashes.join(', '));
const railTop = await page.locator('.rail-label').first().evaluate((el) => el.getBoundingClientRect().top);
check('rail labels sit below the toolbar and status line', railTop >= parts.search.b + 8, `${Math.round(railTop)} vs ${Math.round(parts.search.b)}`);
const cyBox = await rect('.cy');
check('the graph area stays clear of the minimap and zoom dock', cyBox.b <= parts.mini.t + 1 && cyBox.r <= parts.zoom.l + 1);

// popovers: one at a time, close on outside click and Escape, focus returns to the trigger
await page.getByRole('button', { name: /Filters/ }).click();
check('filters popover opens', await page.locator('.filters').isVisible());
await page.getByRole('button', { name: /Invariants hold/ }).click();
check('opening another popover closes the first', !(await page.locator('.filters').count()) && (await page.locator('.popover').isVisible()));
await page.mouse.click(700, 500);
await wait(200);
check('clicking outside closes a popover', (await page.locator('.popover').count()) === 0);
await page.getByRole('button', { name: /Filters/ }).click();
await page.keyboard.press('Escape');
await wait(200);
check('Escape closes the popover and returns focus to its button', (await page.locator('.filters').count()) === 0 && (await page.evaluate(() => document.activeElement?.getAttribute('data-popover-trigger'))) === 'filters');

// Escape closes only the topmost layer: the palette, not the selection behind it
await page.getByRole('button', { name: 'List view' }).click();
await page.locator('.list-row', { hasText: 'Refund window is 90 days' }).first().click();
await page.getByRole('button', { name: 'Graph view' }).click();
await wait(300);
await page.keyboard.press('Control+k');
await page.keyboard.press('Escape');
await wait(250);
check('Escape closes the palette without clearing the selection', (await page.locator('.palette').count()) === 0 && (await text('.crumb-trail')).includes('Refund window is 90 days'));
check('focus returns to the page after the palette closes', await page.evaluate(() => document.activeElement?.tagName !== 'INPUT' || document.activeElement?.id === 'graph-search'));

// toasts: stack, dedupe, pause while hovered, auto-dismiss, never cover the timeline
await page.evaluate(() => { const b = document.querySelector('.crumbs'); void b; });
await page.getByRole('button', { name: 'Inject poisoned webhook' }).isDisabled();
for (let i = 0; i < 3; i++) {
  await page.evaluate(() => window.__toast?.('Same message', 'info'));
}
const toastApi = await page.evaluate(() => typeof window.__toast);
check('toast test hook is available', toastApi === 'function');
await wait(200);
check('identical toasts are counted, not stacked', (await page.locator('.toast').count()) === 1 && (await text('.toast-count')).includes('x3'));
const tbox = await rect('.toast');
const tl = await rect('.timeline');
check('toasts stay above the timeline', tbox.b <= tl.t + 1, `${Math.round(tbox.b)} vs ${Math.round(tl.t)}`);
await page.locator('.toast').first().hover();
await wait(5200);
check('a hovered toast stays put past its normal lifetime', (await page.locator('.toast').count()) === 1);
await page.mouse.move(700, 600);
await wait(5600);
check('a toast disappears by itself once the pointer leaves', (await page.locator('.toast').count()) === 0);

// dev drawer is docked: it pushes the layout up instead of floating over it
await page.getByRole('button', { name: 'Dev console' }).click();
await wait(300);
const drawer = await rect('.dev-drawer');
const tl2 = await rect('.timeline');
check('the dev console docks below the timeline without overlapping it', drawer.t >= tl2.b - 1, `${Math.round(drawer.t)} vs ${Math.round(tl2.b)}`);
await page.getByRole('button', { name: 'Dev console' }).click();
await wait(200);

// frames belong to the landing page only; the console is clean
check('the console has no corner frames', (await page.locator('.app .crop').count()) === 0);
check('the console has no overlay frame element', (await page.locator('.app .lp-frame').count()) === 0);
check('production builds ship a content security policy', (await page.locator('meta[http-equiv="Content-Security-Policy"]').count()) === 1);

// opening the dev console must not redraw or rescale what is behind it
await page.getByRole('tab', { name: 'Graph', exact: true }).click();
await wait(300);
await page.getByRole('button', { name: 'Dev console' }).click();
await wait(500);
const allVisible = await page.locator('.cy').evaluate((el) => {
  const h = el.getBoundingClientRect().height;
  const w = el.getBoundingClientRect().width;
  return el.__cy.nodes(':visible').every((n) => { const b = n.renderedBoundingBox({ includeLabels: false, includeOverlays: false }); return b.y1 >= -2 && b.y2 <= h + 2 && b.x1 >= -2 && b.x2 <= w + 2; });
});
check('every node stays on screen when the dev console opens', allVisible);
const dh = await rect('.dev-drawer');
check('the dev console opens compact so the console stays visible', dh.h <= 140, `${Math.round(dh.h)}px`);
const sh = await rect('.stage');
check('most of the screen stays with the console while the dev console is open', sh.h > 520, `${Math.round(sh.h)}px`);
const handle = await rect('.dev-resize');
await page.mouse.move(handle.l + handle.w / 2, handle.t + 5);
await page.mouse.down();
await page.mouse.move(handle.l + handle.w / 2, handle.t - 80, { steps: 4 });
await page.mouse.up();
await wait(200);
const dh2 = await rect('.dev-drawer');
check('the dev console can be resized by dragging its top edge', dh2.h > dh.h + 40, `${Math.round(dh.h)} to ${Math.round(dh2.h)}`);
await page.getByRole('button', { name: 'Dev console' }).click();
await wait(200);

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
  const off = overflow
    ? await page.evaluate(() => [...document.querySelectorAll('body *')].filter((e) => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).slice(0, 4).map((e) => `${e.tagName}.${String(e.className).slice(0, 30)}`).join(', '))
    : '';
  check(`no horizontal page scroll at ${w}px`, !overflow, off);
}
await page.setViewportSize({ width: 1440, height: 900 });

// workspace: context, connect, team
await page.keyboard.press('Escape');
await page.keyboard.press('6');
await page.locator('.ctx').waitFor({ timeout: 3000 }).catch(() => {});
check('Context page shows a computed savings figure', /\d+%/.test(await text('.ctx-big')), (await text('.ctx-pct')).replace(/\s+/g, ''));
const mapTxt = await text('.ctx-pre');
check('Context page shows the compact map the agent receives', mapTxt.includes('quorum map'));
await page.getByLabel('Token budget', { exact: false }).first().fill('120').catch(() => {});
await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
await page.keyboard.press('7');
await page.locator('.cn').waitFor({ timeout: 3000 }).catch(() => {});
check('Connect page reports MCP status honestly in sample mode', (await text('.cn-status')).includes('Sample data (simulated)'));
check('Connect page lists the real MCP tools', (await page.locator('.cn-table tbody tr').count()) >= 10);
check('Connect page gives a ready-to-paste Claude Code command', (await text('.cn-block .terminal')).includes('claude mcp add'));
await page.locator('.cn-row').first().waitFor({ timeout: 8000 }).catch(() => {});
check('live feed fills with tool calls', (await page.locator('.cn-row').count()) > 0);
await page.getByRole('tab', { name: 'Chats' }).click();
await wait(600);
check('chats tab lists members', (await page.locator('.cn-people li').count()) >= 3);
await page.keyboard.press('8');
await page.locator('.tm').waitFor({ timeout: 3000 }).catch(() => {});
check('Team page shows seat usage', /\d+ \/ \d+/.test(await text('.tm-seats')));
await page.locator('.tm-form input[placeholder="Customer success"]').fill('Support');
await page.locator('.tm-form').first().getByRole('button', { name: 'Add team' }).click();
check('duplicate team name is refused with a message', (await text('.tm-err')).toLowerCase().includes('already exists'));
const linksBefore = await page.locator('.tm-links li').count();
const sels = page.locator('.tm-mesh .tm-form select');
await sels.nth(0).selectOption({ index: 3 });
await sels.nth(1).selectOption({ index: 4 });
await page.locator('.tm-mesh .tm-form').getByRole('button', { name: 'Link' }).click();
await wait(300);
check('linking two members adds a link', (await page.locator('.tm-links li').count()) === linksBefore + 1);
await page.keyboard.press('1');
await wait(400);
await page.getByRole('tab', { name: /Mind map/ }).click();
await wait(500);
check('Mind map tab shows the memory as a foldable tree', (await page.locator('.mm-node').count()) > 5);
await page.getByRole('tab', { name: /^Graph/ }).click();
await wait(300);

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
