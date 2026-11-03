import { defineConfig } from 'vite';
export default defineConfig(({mode})=>({server:mode==='demo'?{host:'127.0.0.1',strictPort:true,proxy:{'/demo-api':{target:'http://127.0.0.1:5201',changeOrigin:true,rewrite:path=>path.replace(/^\/demo-api/,'')}}}:{proxy:{'/api':'http://127.0.0.1:8765'}}}));
