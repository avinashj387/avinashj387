const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const times = process.argv.slice(2).map(Number);
  const b = await chromium.launch({ args:['--font-render-hinting=none','--force-color-profile=srgb','--hide-scrollbars'] });
  const p = await b.newPage({ viewport:{width:1080,height:1920}, deviceScaleFactor:0.5 });
  const errs=[]; p.on('pageerror',e=>errs.push(String(e)));
  await p.goto('file://'+path.resolve(__dirname,'reel.html'));
  await p.waitForTimeout(900);
  for (const t of times){
    await p.evaluate(tt => window.seek(tt), t);
    await p.screenshot({ path: `${__dirname}/prev-${String(t).replace('.','_')}.png` });
  }
  console.log(errs.length? 'ERRORS:\n'+errs.slice(0,5).join('\n') : 'no page errors');
  await b.close();
})();
