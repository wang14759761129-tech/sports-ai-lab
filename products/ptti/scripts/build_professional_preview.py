"""Build a separate local Windows preview without touching stable release assets."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
NAME='PTTI-Professional-Preview-v0.2'


def main():
    target=ROOT/'build'/'professional-preview'
    target.mkdir(parents=True,exist_ok=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
    info={'version':'0.2.0-professional-preview','commit':commit,'source_tree_dirty':dirty,
          'environment':'DEVELOPMENT','database':'%LOCALAPPDATA%/PTTI-Dev/ProfessionalPreview/matches.db',
          'local_vision_runtime_home':str(ROOT),'external_vision_runtime_required':True,
          'release_gate':'HISTORICAL_DB_UNVERIFIED','official_release':False}
    info_path=target/'build-info.json'
    info_path.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name',NAME,
             '--icon',str(ROOT/'assets/ptti.ico'),'--collect-all','webview','--paths',str(ROOT),
             '--distpath',str(target/'dist'),'--workpath',str(target/'work'),'--specpath',str(target)]
    for source,dest in [(info_path,'.'),(ROOT/'frontend/dist','frontend/dist'),
                        (ROOT/'data/professional','data/professional'),(ROOT/'data/samples','data/samples')]:
        command.extend(['--add-data',f'{source};{dest}'])
    for tool in ('ffmpeg','ffprobe'):
        executable=shutil.which(tool)
        if not executable:raise RuntimeError(f'{tool} is required to package working video import')
        command.extend(['--add-binary',f'{executable};.'])
    command.append(str(ROOT/'apps/desktop.py'))
    subprocess.run(command,cwd=ROOT,check=True)
    folder=target/'dist'/NAME
    shutil.copy2(info_path,folder/'build-info.json')
    (folder/'START-HERE.txt').write_text(
        'PTTI Professional Preview v0.2\n\n双击 PTTI-Professional-Preview-v0.2.exe。\n'
        '首页查看真实运动员与职业比赛；“导入完整比赛视频”可读取你有权使用的本机视频。\n'
        '视频分析 → 分析任务查看进度；比赛详情查看球轨迹、报告和人工时间轴。\n'
        '这是独立开发预览，不覆盖正式 v0.1.2。数据保存在 PTTI-Dev/ProfessionalPreview。\n'
        '本机 BallTrack 使用已安装的研究运行环境；此包不包含 GPU/PyTorch 运行环境。\n'
        '请保持整个文件夹完整。无需账号，不上传比赛。\n',encoding='utf-8')
    exe=folder/(NAME+'.exe')
    digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder/(NAME+'.exe.sha256')).write_text(f'{digest}  {exe.name}\n',encoding='ascii')
    print(json.dumps({'exe':str(exe),'bytes':exe.stat().st_size,'sha256':digest,'build':info},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
