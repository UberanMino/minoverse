// node shot.js 01 [02 ...]  → contact sheet build-check/NN.png aus 8 Zeitpunkten
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');
const B = path.join(__dirname, 'build/clips');
const OUT = path.join(__dirname, 'check');
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ids = process.argv.slice(2);
  for (const id of ids) {
    const file = fs.readdirSync(B).find((f) => f.startsWith(id + '-') && f.endsWith('.html'));
    const page = await br.newPage({ viewport: { width: 1080, height: 1920 } });
    const errs = [];
    page.on('pageerror', (e) => errs.push(e.message));
    page.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
    await page.goto('file://' + path.join(B, file));
    await page.waitForTimeout(600);
    const times = (process.env.T || '0.3,1.2,2.4,3.4,3.8,4.6,5.6,6.9').split(',').map(Number);
    const shots = [];
    for (const t of times) {
      await page.evaluate((t) => MV.seek(t), t);
      await page.waitForTimeout(60);
      const p = path.join(OUT, `${id}_${t}.png`);
      await page.screenshot({ path: p });
      shots.push(p);
    }
    if (shots.length > 1) execSync(`ffmpeg -v error -y ${shots.map((s) => `-i ${s}`).join(' ')} -filter_complex "${shots.map((_, i) => `[${i}]scale=270:480[s${i}]`).join(';')};${shots.map((_, i) => `[s${i}]`).join('')}hstack=inputs=${shots.length}" ${path.join(OUT, id + '.png')}`);
    console.log(id, file, errs.length ? 'ERR ' + errs.join(' | ') : 'ok');
    await page.close();
  }
  await br.close();
})();
