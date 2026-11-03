export const REVIEW_VIEWS=Object.freeze([
 {id:'cinema',label:'Cinema 全屏',space:'cinema',hint:'窗口最大化，显示四列比赛墙；保留导航、封面、标题和星标。'},
 {id:'arena',label:'Arena 关键分',space:'arena',hint:'使用已有模拟局，推进至 9:9、10:9 或 10:10，截取比分和操作区域。'},
 {id:'pro_lab',label:'Pro Lab 训练界面',space:'pro-lab',hint:'选择你有权使用的本机录像；截图前留意私人文件名、备注和画面。'},
 {id:'narrow',label:'四空间窄屏',space:'cinema',hint:'缩窄浏览器窗口至约 390px，或用浏览器设备预览；保留导航与首张比赛卡。'},
]);
export function createReviewReceipt(input={},environment={},now=Date.now()){
 const views={};
 for(const {id} of REVIEW_VIEWS){const verdict=input.views?.[id]??'NOT_REVIEWED';if(!['NOT_REVIEWED','APPROVED','NEEDS_CHANGE'].includes(verdict))throw Error('请选择有效的人工验收结论');views[id]=verdict;}
 const feedback=typeof input.feedback==='string'?input.feedback.trim():'';
 if(feedback.length>2000)throw Error('反馈请控制在 2000 字以内');
 const viewport={width:Number(environment.width??0),height:Number(environment.height??0),device_pixel_ratio:Number(environment.devicePixelRatio??1),reduced_motion:environment.reducedMotion===true};
 if(!Number.isFinite(viewport.width)||viewport.width<0||!Number.isFinite(viewport.height)||viewport.height<0||!Number.isFinite(viewport.device_pixel_ratio)||viewport.device_pixel_ratio<=0)throw Error('窗口信息无效');
 return {schema:'ptti.founder-review/0.1',created_at:new Date(now).toISOString(),evidence_kind:'SELF_REPORTED_VISUAL_FEEDBACK',reviewer_identity:'NOT_VERIFIED',source_commit:null,source_binding:'UNBOUND_LOCAL_DEV',views,feedback,viewport,
   attachments:'MANUALLY_SELECTED_BY_FOUNDER_NOT_COLLECTED',media_permissions_changed:false};
}
