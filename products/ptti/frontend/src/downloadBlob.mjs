// Own exactly one temporary download URL and release it on success or error.
export function downloadJsonBlob(blob,filename,env){
 const url=env.url.createObjectURL(blob);
 try{
  const link=env.document.createElement('a');link.href=url;link.download=filename;link.click();
 }catch(error){env.url.revokeObjectURL(url);throw error}
 try{env.defer(()=>env.url.revokeObjectURL(url),1000)}catch(error){env.url.revokeObjectURL(url);throw error}
}
