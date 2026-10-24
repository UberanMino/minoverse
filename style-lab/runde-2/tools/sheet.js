const { chromium } = require('playwright');
(async () => {
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await br.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('pageerror', (e) => console.log('ERR', e.message));
  page.on('console', (m) => m.type() === 'error' && console.log('CERR', m.text()));
  await page.goto('file://' + __dirname + '/build2/clips/sheet.html?' + (process.argv[2] || ''));
  await page.waitForTimeout(800);
  await page.screenshot({ path: __dirname + '/check2/' + (process.argv[3] || 'sheet') + '.png' });
  await br.close();
})();
