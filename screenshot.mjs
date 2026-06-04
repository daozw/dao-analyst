import puppeteer from 'puppeteer';
import { resolve } from 'path';

const CHROME = '/Users/sound/.cache/puppeteer/chrome/mac_arm-149.0.7827.22/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';

async function screenshot(htmlPath, outputPath) {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-gpu']
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 720, height: 900 });
    await page.goto('file://' + htmlPath, { waitUntil: 'networkidle0', timeout: 10000 });
    
    const body = await page.$('body');
    const box = await body.boundingBox();
    const h = Math.ceil(box.height) + 40;
    await page.setViewport({ width: 720, height: h });
    
    await page.screenshot({ path: outputPath, fullPage: true, type: 'png' });
    console.log(`✅ ${h}px`);
  } finally {
    await browser.close();
  }
}

const [,, htmlFile, pngFile] = process.argv;
screenshot(htmlFile, pngFile).catch(e => { console.error(e.message); process.exit(1); });
