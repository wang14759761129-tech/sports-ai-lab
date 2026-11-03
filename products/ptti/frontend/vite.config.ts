import { defineConfig } from 'vite';
export default defineConfig(({mode})=>{
 const apiPort=process.env.PTTI_DEMO_API_PORT||'5221';
 if(!/^[0-9]{1,5}$/.test(apiPort)||Number(apiPort)<1||Number(apiPort)>65535)throw Error('Invalid loopback demo API port');
 return {server:mode==='demo'?{host:'127.0.0.1',strictPort:true,proxy:{'/demo-api':{target:`http://127.0.0.1:${apiPort}`,changeOrigin:true,rewrite:path=>path.replace(/^\/demo-api/,'')}}}:{proxy:{'/api':'http://127.0.0.1:8765'}}};
});
