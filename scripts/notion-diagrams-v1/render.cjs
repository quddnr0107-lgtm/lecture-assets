#!/usr/bin/env node
/* Rasterize deterministic SVG originals. Requires sharp. */
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '../..');
const subject = path.join(root, 'integrated-defense');
const selected = process.argv.slice(2);
const records = JSON.parse(fs.readFileSync(path.join(subject, 'notion-v1/render-records.json'), 'utf8')).filter(rec => !selected.length || selected.includes(rec.id));
(async () => {
  for (const rec of records) {
    const base = path.join(subject, rec.base);
    await sharp(base + '.svg').png({compressionLevel: 9}).toFile(base + '.png');
    await sharp(base + '.svg').webp({quality: 88, effort: 5}).toFile(base + '.webp');
  }
  console.log(JSON.stringify({rendered: records.length, formats: ['png', 'webp'], width: 1600, height: 1120}));
})().catch(err => {console.error(err); process.exitCode = 1;});
