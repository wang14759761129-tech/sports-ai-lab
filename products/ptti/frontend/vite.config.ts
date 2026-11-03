import { defineConfig } from 'vite';
import {mediaDistributionPlugin} from './scripts/mediaDistributionGate.mjs';
export default defineConfig(({command,mode})=>({plugins:[mediaDistributionPlugin()],define:{__PTTI_MEDIA_MODE__:JSON.stringify(command==='serve'&&mode==='founder-internal-qa'?'INTERNAL_FOUNDER_QA':'DISTRIBUTABLE')},server:{proxy:{'/api':{target:'http://127.0.0.1:8765',changeOrigin:false}}}}));
