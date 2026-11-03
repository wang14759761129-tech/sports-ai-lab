const task=await taskSpace(1);
await task.finish({keep:[]});
console.log('Agent QA page closed after resource monitor stop. No further browser QA.');
