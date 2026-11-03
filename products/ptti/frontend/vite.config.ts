import { defineConfig } from 'vite';
import {mediaDistributionPlugin} from './scripts/mediaDistributionGate.mjs';
export default defineConfig(({command,mode})=>{
 const founder=command==='serve'&&mode==='founder-internal-qa';
 const qaApi=process.env.PTTI_FOUNDER_QA_API;
 if(founder&&(!qaApi||!/^http:\/\/127\.0\.0\.1:(?:[1-9]\d{3,4})$/.test(qaApi)||Number(new URL(qaApi).port)>65535))throw Error('Founder QA requires an explicit isolated loopback API');
 return {cacheDir:'.cinema-original-vite-cache',plugins:[mediaDistributionPlugin()],define:{__PTTI_MEDIA_MODE__:JSON.stringify(founder?'INTERNAL_FOUNDER_QA':'DISTRIBUTABLE')},server:{proxy:{'/api':{target:founder?qaApi!:'http://127.0.0.1:8765',changeOrigin:false}}}};
});
