export function createDemoSyntheticFetcher(nativeFetch){if(typeof nativeFetch!=='function')throw Error('FETCH_UNAVAILABLE');return ()=>nativeFetch('/demo-synthetic.mp4')}
