import {Component,Suspense,type ReactNode} from 'react';

/** Keep a failed optional workspace from taking down the Cinema wall. */
export default class WorkspaceFrame extends Component<{name:string;onBack:()=>void;children:ReactNode},{failed:boolean}> {
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true}}
 render(){
  if(this.state.failed)return <section role="alert"><h2>{this.props.name} 暂未能打开</h2><p>可返回 Cinema 或切换其他空间。已保存记录仍保留；重新载入会清除未保存的输入。</p><button onClick={this.props.onBack}>返回 Cinema</button><button onClick={()=>{if(window.confirm('重新载入会清除未保存的输入，已保存记录不受影响。继续？'))window.location.reload()}}>重新载入页面</button></section>;
  return <Suspense fallback={<section className="grand-loading" role="status"><p>正在打开{this.props.name}…</p><button onClick={this.props.onBack}>返回 Cinema</button></section>}>{this.props.children}</Suspense>;
 }
}
