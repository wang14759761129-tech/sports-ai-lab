const task=await taskSpace('PTTI Moment Cards Integration 20261026');
const page=task.page('p1');
await page.goto('http://127.0.0.1:5173');
console.log({spaceId:task.spaceId});
console.log(await page.snapshot());
