export async function confirmMomentContent(videoId,expectedSha,fetcher=fetch){
 if(typeof videoId!=='string'||!videoId||!/^[a-f0-9]{64}$/i.test(expectedSha||''))throw Error('视频登记身份不可验证');
 const response=await fetcher(`/api/video-evidence/videos/${encodeURIComponent(videoId)}/verify-moment-identity`,{method:'POST',cache:'no-store'});
 if(!response.ok)throw Error('视频内容无法验证；时刻未更改。');
 const result=await response.json();if(result.status!=='CONTENT_MATCH_AT_CHECK'||result.video_id!==videoId||result.sha256!==expectedSha.toLowerCase())throw Error('视频身份不匹配；时刻未更改。');
}
