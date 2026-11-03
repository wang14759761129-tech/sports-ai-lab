export function createSingleFlight(onChange=()=>{}) {
 let busy=false;
 return async task=>{if(busy)return {status:'BUSY'};busy=true;onChange(true);try{return {status:'DONE',value:await task()}}finally{busy=false;onChange(false)}};
}
