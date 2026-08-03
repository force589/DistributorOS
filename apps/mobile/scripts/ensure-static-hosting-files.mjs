import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const publicDir = join(projectRoot, 'public');
const distDir = join(projectRoot, 'dist');
const hostingFiles = ['_redirects', '_headers'];

if (!existsSync(distDir)) {
  throw new Error('Expo web export output directory does not exist: apps/mobile/dist');
}

for (const fileName of hostingFiles) {
  const source = join(publicDir, fileName);
  const target = join(distDir, fileName);
  if (!existsSync(source)) {
    throw new Error(`Missing static hosting file: apps/mobile/public/${fileName}`);
  }
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
}
