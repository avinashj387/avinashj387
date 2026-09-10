const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const FPS = 30, DUR = 75, TOTAL = FPS * DUR;
const FF = process.env.FF, OUT = process.env.OUT;
(async () => {
  const ff = spawn(FF, ['-y','-loglevel','error','-f','image2pipe','-vcodec','png','-framerate',String(FPS),
    '-i','pipe:0','-c:v','libx264','-preset','slow','-crf','18','-pix_fmt','yuv420p',
    '-movflags','+faststart','-r',String(FPS), OUT], { stdio:['pipe','inherit','inherit'] });
  const b = await chromium.launch({ args:['--font-render-hinting=none','--force-color-profile=srgb','--hide-scrollbars'] });
  const p = await b.newPage({ viewport:{width:1080,height:1920}, deviceScaleFactor:1 });
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto('file://' + path.resolve(__dirname,'reel.html'));
  await p.waitForTimeout(1200);
  const write = buf => new Promise(r => ff.stdin.write(buf) ? r() : ff.stdin.once('drain', r));
  const t0 = Date.now();
  for (let i = 0; i < TOTAL; i++){
    await p.evaluate(tt => window.seek(tt), i / FPS);
    await write(await p.screenshot({ type:'png' }));
    if (i % 300 === 0) process.stderr.write(`  frame ${i}/${TOTAL}  ${((Date.now()-t0)/1000).toFixed(0)}s\n`);
  }
  ff.stdin.end();
  await b.close();
  if (errs.length) console.log('PAGE ERRORS:', errs.slice(0,3).join(' | '));
  await new Promise(r => ff.on('close', r));
  console.log(`rendered ${TOTAL} frames in ${((Date.now()-t0)/1000).toFixed(0)}s`);
})();
