import { copyFileSync, mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';

const outputDirectory = 'dist';
const assets = ['index.html', 'styles.css', 'app.js'];

rmSync(outputDirectory, { force: true, recursive: true });
mkdirSync(outputDirectory);

for (const asset of assets) {
  copyFileSync(asset, join(outputDirectory, asset));
}

console.log(`Built ${assets.length} assets in ${outputDirectory}/`);
