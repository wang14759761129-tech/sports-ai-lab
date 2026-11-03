import { defineConfig } from 'vite';
// Keep the browser's Host and Origin together. Vite's string shorthand sets
// changeOrigin:true, which changes Host only and triggers the local-file guard.
// A playback worktree supplies its own loopback target rather than using a
// different worktree's backend on 8765. Never rewrite or remove Origin.
const target=process.env.PTTI_QA_API_TARGET||'http://127.0.0.1:8765';
const url=new URL(target);
if(url.protocol!=='http:'||!['127.0.0.1','localhost'].includes(url.hostname)||url.username||url.password||url.pathname!=='/'||url.search||url.hash)throw Error('PTTI QA proxy target must be a plain loopback HTTP origin');
export default defineConfig({server:{proxy:{'/api':{target,changeOrigin:false}}}});
