const puppeteer = require('puppeteer');
const path = require('path');

async function screenshot(htmlPath, outputPath) {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Users/sound/.cache/puppeteer/chrome/mac_arm-149.0.7827.22/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
    args: ['--no-sandbox', '--disable-gpu', '--disable-setuid-sandbox']
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 720, height: 900 });
    
    await page.goto('file://' + htmlPath, { waitUntil: 'networkidle0' });
    
    // 获取完整页面高度
    const bodyHandle = await page.$('body');
    const box = await bodyHandle.boundingBox();
    const fullHeight = Math.ceil(box.height) + 40;
    
    await page.setViewport({ width: 720, height: fullHeight });
    
    await page.screenshot({
      path: outputPath,
      fullPage: true,
      type: 'png'
    });
    
    console.log(`OK: ${fullHeight}px`);
  } finally {
    await browser.close();
  }
}

const [,, htmlFile, pngFile] = process.argv;
screenshot(htmlFile, pngFile)
  .then(msg => console.log(msg || 'DONE'))
  .catch(e => { console.error(e.message); process.exit(1); });
