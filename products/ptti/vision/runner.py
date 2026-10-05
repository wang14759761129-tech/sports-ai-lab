import csv
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from .config import VisionConfig, PIPELINE_VERSION, RV_COMMIT
from .adapter import adapt_ball_rows
from .quality import video_metadata, classify, normalize
from .benchmark import read_ground_truth, compare
from .schema import Source

def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1024 * 1024): digest.update(chunk)
    return digest.hexdigest()

def cache_key(video_hash, model_hash, options):
    return hashlib.sha256(json.dumps([video_hash, model_hash, RV_COMMIT, PIPELINE_VERSION, options], sort_keys=True).encode()).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def report_html(result):
    body = '<h1>PTTI · 视频视觉分析（实验）</h1><p>仅包含球位置观测；不推断旋转、技战术、落点或球员能力。</p>'
    body += '<h2>视频与来源</h2><pre>' + escape(json.dumps(result['source'], ensure_ascii=False, indent=2)) + '</pre>'
    if result.get('metrics'):
        body += '<h2>真实小样本基线 · 尚无通过阈值</h2><table>'
        for key, value in result['metrics'].items():
            body += f'<tr><th>{escape(key)}</th><td>{escape(str(value))}</td></tr>'
        body += '</table>'
    body += '<h2>复现与运行记录</h2><pre>' + escape(json.dumps(result['provenance'], ensure_ascii=False, indent=2)) + '</pre>'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PTTI 视觉分析</title><style>body{font-family:Microsoft YaHei,sans-serif;max-width:960px;margin:30px auto}th,td{padding:8px;text-align:left;border-bottom:1px solid #ddd}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>' + body + '</html>'

def run_analysis(video, source, gt=None, config=None, device='cuda', stage=lambda value: None, force_recompute=False):
    config = config or VisionConfig.load()
    source = Source.model_validate(source).model_dump()
    checkpoint = config.model_root / 'balltrack_best.pth'
    if not config.worker_python.is_file() or not checkpoint.is_file():
        raise ValueError('BallTrack 未安装。请先运行 setup_vision.ps1；模型不会自动下载。')
    commit = subprocess.check_output(['git', '-C', str(config.runtime_root), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != RV_COMMIT: raise ValueError('RacketVision checkout does not match pinned commit')
    stage('读取视频')
    meta = video_metadata(video)
    if meta['duration'] > 60 or (meta['frame_count'] or meta['duration'] * meta['fps']) > 1800:
        raise ValueError('当前视觉实验仅处理不超过 60 秒、1800 帧的短片段。请保留原始视频并先剪出短回合。')
    key = cache_key(sha256(video), sha256(checkpoint), {'device': device})
    config.cache_root.mkdir(parents=True, exist_ok=True)
    cache = config.cache_root / key
    analysis_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + key[:12]
    out = config.output_root / analysis_id
    out.mkdir(parents=True, exist_ok=False)
    logs = out / 'logs'; logs.mkdir()
    write_json(out / 'source.json', source); write_json(out / 'video_meta.json', meta)
    write_json(out / 'quality.json', classify(meta))
    started = time.perf_counter(); reused = (not force_recompute and (cache / 'raw_prediction.json').is_file() and (cache / 'runtime.json').is_file())
    normalization_seconds=0.0
    if not reused:
        cache.mkdir(exist_ok=True)
        input_video = Path(video)
        if meta['codec'] != 'h264' or meta['rate_variable']:
            stage('规范化视频（保持分辨率）')
            normalization_started=time.perf_counter()
            input_video = normalize(video, cache / 'normalized.mp4', meta)
            normalization_seconds=time.perf_counter()-normalization_started
        stage('准备帧与球追踪')
        command = [str(config.worker_python), str(Path(__file__).resolve().parents[1] / 'vision_worker/balltrack.py'),
                   '--runtime', str(config.runtime_root), '--checkpoint', str(checkpoint),
                   '--video', str(input_video), '--output', str(cache), '--device', device]
        with (logs / 'balltrack.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8', errors='replace')
            for line in process.stdout:
                log.write(line); log.flush()
                if line.startswith('STAGE '): stage(line.strip()[6:])
            if process.wait() != 0:
                raise RuntimeError('球追踪失败。请检查 GPU / 模型 / 日志：' + str(logs / 'balltrack.log'))
    stage('转换结果与基准对比')
    postprocess_started=time.perf_counter()
    raw = json.loads((cache / 'raw_prediction.json').read_text(encoding='utf-8'))
    points = adapt_ball_rows(raw, meta['width'], meta['height'], meta['fps'])
    write_json(out / 'ball_track.json', points)
    with (out / 'ball_track.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(points[0])); writer.writeheader(); writer.writerows(points)
    runtime = json.loads((cache / 'runtime.json').read_text(encoding='utf-8'))
    runtime['processing_fps'] = runtime['decoded_frames'] / runtime['processing_seconds']
    runtime['processing_realtime_factor'] = runtime['processing_seconds'] / meta['duration'] if meta['duration'] else None
    metrics = compare(points, read_ground_truth(gt), meta['width'], meta['height']) if gt else None
    write_json(out / 'metrics.json', metrics)
    postprocessing_seconds=time.perf_counter()-postprocess_started
    stage('生成轨迹叠加视频')
    overlay_started=time.perf_counter()
    overlay_command = [str(config.worker_python), str(Path(__file__).resolve().parents[1] / 'vision_worker/overlay.py'),
                       str(video), str(out / 'ball_track.json'), str(out / 'ball_overlay.mp4')]
    with (logs / 'overlay.log').open('w', encoding='utf-8') as log:
        subprocess.run(overlay_command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=3600)
    overlay_encoding_seconds=time.perf_counter()-overlay_started
    git_sha = subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parents[1]), 'rev-parse', 'HEAD'], text=True).strip()
    provenance = dict(tti_commit=git_sha, racketvision_commit=commit, pipeline=PIPELINE_VERSION,
                      checkpoint_sha256=sha256(checkpoint), video_sha256=sha256(video),
                      gt_sha256=sha256(gt) if gt else None, recorded_at=datetime.now(timezone.utc).isoformat(),
                      cache_reused=reused, elapsed_seconds=time.perf_counter() - started, runtime=runtime,
                      profile=dict(runtime.get('profile',{}),normalization_seconds=normalization_seconds,
                                   postprocessing_seconds=postprocessing_seconds,
                                   overlay_encoding_seconds=overlay_encoding_seconds),
                      quality=classify(meta), worker_device=device, model_batchsize=2, heatmap_threshold=.5,
                      confidence_semantics='Mean sigmoid heatmap value inside selected bounding rectangle; not calibrated probability.',
                      source_tree_dirty=bool(subprocess.check_output(['git','-C',str(Path(__file__).resolve().parents[1]),'status','--porcelain'],text=True).strip()))
    result = dict(analysis_id=analysis_id, source=source, video=meta, metrics=metrics, provenance=provenance,
                  outputs=['ball_track.json', 'ball_track.csv', 'metrics.json', 'ball_overlay.mp4', 'report.html'])
    write_json(out / 'analysis.json', result)
    (out / 'report.html').write_text(report_html(result), encoding='utf-8')
    if metrics: (out / 'benchmark_report.html').write_text(report_html(result), encoding='utf-8')
    stage('完成')
    return result
