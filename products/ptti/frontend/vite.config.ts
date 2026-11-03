import { defineConfig } from 'vite';
import { mediaDistributionPlugin } from './scripts/mediaDistributionGate.mjs';
export default defineConfig({plugins:[mediaDistributionPlugin()],server:{proxy:{'/api':'http://127.0.0.1:8765'}}});
