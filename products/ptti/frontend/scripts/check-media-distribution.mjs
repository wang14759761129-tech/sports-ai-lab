import {verifyMediaTree} from './mediaDistributionGate.mjs';
const args=process.argv.slice(2),root=args[0];
if(!root)throw Error('Usage: node scripts/check-media-distribution.mjs ARTIFACT_ROOT [--windows] [--package]');
console.log(JSON.stringify(verifyMediaTree(root,{target:args.includes('--windows')?'WINDOWS_DESKTOP':'WEB',packageTree:args.includes('--package')})));
