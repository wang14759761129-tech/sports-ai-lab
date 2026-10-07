"""Build a local, source-backed Technology Foundation readout; no web upload or product changes."""
import html
import json
from pathlib import Path
import subprocess

from ptti_benchmark.core import file_sha256

PRODUCT = Path(__file__).resolve().parents[2]
ROOT = Path.home() / "AppData/Local/PTTI-Dev/technology-foundation"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def escaped(value):
    return html.escape(str(value), quote=True)


def main():
    target = ROOT / "technology_foundation_report.json"
    if target.exists() or target.with_suffix(".html").exists():
        raise FileExistsError("FOUNDATION_REPORT_EXISTS")
    paths = {"rf_detr": ROOT/"rf-detr-comparison-corrected-coco.json",
             "supervision": ROOT/"supervision-v2-ball-visible/report.json",
             "cvat": ROOT/"benchmark-v0/cvat-tasks/task-preparation.json",
             "uv": ROOT/"uv-rebuild-verification.json", "inventory": ROOT/"stack_inventory.json",
             "manifest": ROOT/"benchmark-v0/PTTI_VISION_BENCHMARK_V0_MANIFEST_R1.json",
             "attempt_index": ROOT/"rf-detr-attempt-status.json",
             "cards": PRODUCT/"research/vision-benchmark/TOOL_VALUE_CARDS.json"}
    data = {name: read(path) for name, path in paths.items()}
    result = {"title": "PTTI Technology Foundation v0.1", "date": "2026-10-07",
              "git_commit": subprocess.check_output(["git","rev-parse","HEAD"], cwd=PRODUCT, text=True).strip(),
              "git_branch": subprocess.check_output(["git","branch","--show-current"], cwd=PRODUCT, text=True).strip(),
              "evidence_sources": {name: {"path": str(path), "sha256": file_sha256(path)} for name,path in paths.items()},
              "research_script_hashes": {p.name: file_sha256(p) for p in Path(__file__).parent.glob("*.py")},
              "scope": "RESEARCH_FOUNDATION; NO_PRODUCT_REPLACEMENT_OR_TUNING", "results": data,
              "gates": {"release": "HISTORICAL_DB_UNVERIFIED", "balltrack": "BALLTRACK_V1_FROZEN_RAW",
                        "hit": "HIT_EVENT_V0_2_PARTIAL", "cvat": "MANUAL_WORKFLOW_NOT_VERIFIED"},
              "next_tools": ["Ruff for new code", "uv for new isolated workers", "CVAT acceptance on a suitable annotation workstation"]}
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2), encoding="utf-8")
    rf = data["rf_detr"]
    rv_m, rf_m = rf["aggregate"]["RacketVision_RAW"], rf["aggregate"]["RF_DETR_Nano"]
    body = ['<header><span class="eyebrow">PTTI · RESEARCH FOUNDATION</span><h1>技术是否有用，让比赛证据回答。</h1>',
            '<p>Technology Foundation v0.1 · 2026-10-07<br>独立研究分支；当前产品与冻结模型保持原状。</p></header>',
            '<section><h2>当前真正的瓶颈</h2><ol><li>缺少整场球位置真值；击球误报不能直接算球检测误报。</li>',
            '<li>192 个 Raw 漏检中，94 个缺少前后球观测，98 个已有前后观测。</li>',
            '<li>整场球员证据尚未进入 Hit baseline，击球方无法评价。</li>',
            '<li>需用统一标注和公平对照证明工具价值，当前不继续调 Hit 参数。</li></ol></section>',
            '<section><h2>RF-DETR Nano：当前预训练版本不替换 BallTrack</h2>',
            '<p>五场官方训练片段，125 个原生标注帧；115 个可见球帧，10 个明确无球帧。已知 TRAIN 数据，不能代表未见比赛泛化。</p>',
            '<table><tr><th>指标</th><th>RacketVision RAW</th><th>RF-DETR Nano</th></tr>']
    for label,key in (("可见帧响应","detected_ball_frames"),("20px 内定位 Recall","recall"),
                      ("错误/多余球检测","false_detections"),("平均定位误差 px","center_error_mean_px"),
                      ("中位误差 px","center_error_median_px"),("P95 px","center_error_p95_px")):
        values=[]
        for metrics in (rv_m,rf_m):
            value=metrics[key]
            if key=="recall":
                value=f"{value*100:.2f}%"
            elif isinstance(value,float):
                value=f"{value:.3f}"
            values.append(escaped(value))
        body.append(f'<tr><td>{escaped(label)}</td><td>{values[0]}</td><td>{values[1]}</td></tr>')
    body += ['</table><p class="notice">最终有效结果采用官方类别名称映射，CPU 受控评估。先前“0 个检测”的错误类别适配结果已作废并保留。权重、帧集、阈值未调。</p>',
             '<p>有效推理 5.50 sampled FPS；加载约 16.40 秒；峰值 RAM 1.40 GiB。稀疏标注无法评价整场 FP/min、真实轨迹连续性和下游 Hit 指标。</p></section>',
             '<section><h2>Supervision：这次没有证明能省代码</h2><p>真实两秒片段，240 帧、178 帧球观测。两条路径逐像素一致。</p>',
             '<table><tr><th></th><th>当前 OpenCV 绘制</th><th>Supervision</th></tr><tr><td>适配器代码行数</td><td>10</td><td>10</td></tr>',
             '<tr><td>240 帧绘制时间</td><td>0.02498s</td><td>0.06158s</td></tr></table><p>保留 TRIAL。未重构检测/追踪架构；后续只有能减少更多重复胶水代码才考虑采用。</p></section>',
             '<section><h2>CVAT：数据任务已准备，实际工作台仍待验收</h2><p>五个图像任务 + 三个短视频任务。125 条已有原生 GT 的 XML 格式往返校验通过；九个误报上下文候选待复核。</p>',
             '<p class="notice">本机没有可用 Docker。未部署 CVAT；未测界面导航、协作和 100 个事件标注耗时。没有宣称标注提速。</p></section>',
             '<section><h2>技术雷达与完整价值卡</h2><p>0–10 分为工程判断，并非已经测得的性能提升。</p>']
    for card in data["cards"]["cards"]:
        body.append(f'<details><summary>{escaped(card["name"])} <span class="pill">{escaped(card["radar"])} · {escaped(card["decision"])}</span></summary>')
        for label,key in (("解决问题","problem_solved"),("严重程度","current_problem_severity"),
                          ("当前方案","current_solution"),("之前","before"),("之后 / 真实结论","after"),
                          ("证据状态","evidence_status")):
            body.append(f'<p><b>{label}</b>　{escaped(card[key])}</p>')
        for label,key in (("预期收益评分","benefits"),("成本评分","cost"),("风险","risks")):
            body.append(f'<h3>{label}</h3><dl>')
            for k,v in card[key].items():
                body.append(f'<dt>{escaped(k)}</dt><dd>{escaped(v)}</dd>')
            body.append('</dl>')
        body.append('</details>')
    body += ['</section><section><h2>可复核的评估跑道</h2><p>Model Adapter → Canonical timestamp/observations → Detector metrics → 可选冻结 Raw Hit Engine → JSON/HTML → 相同数据上的描述性排序。</p>',
             '<p>源视频、原始标注、转换后标签和 RAW cache 都有 SHA256；禁止把未知当负样本；报告拒绝覆盖。</p>',
             f'<p>Manifest SHA256<br><code>{escaped(file_sha256(paths["manifest"]))}</code></p></section>',
             '<section><h2>下一步只推荐三项</h2><ol><li>Ruff：新研究代码质量检查。</li><li>uv：新隔离 worker 的锁定重建。</li><li>CVAT：在适合的标注机器上完成真实 100-event 工作流验收。</li></ol></section>',
             '<footer><p>Release: HISTORICAL_DB_UNVERIFIED · Hit: HIT_EVENT_V0_2_PARTIAL<br>没有 Production DB 访问、main 合并、tag 或 Release。</p>',
             f'<p>研究代码提交：<code>{escaped(result["git_commit"])}</code></p></footer>']
    style = 'body{margin:0;background:#edf1f4;color:#182733;font:16px/1.7 "Microsoft YaHei UI",Segoe UI,sans-serif}main{max-width:1080px;margin:auto;padding:30px}header,section,footer{background:white;border:1px solid #dce3e8;border-radius:14px;padding:28px;margin-bottom:20px}header{background:#143b48;color:white}h1{font-size:32px;line-height:1.4}h2{font-size:23px}h3{font-size:17px}.eyebrow{letter-spacing:2px;color:#8fd7c4}table{width:100%;border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #e0e7eb;text-align:left}.notice{background:#fff5db;border-left:4px solid #ddad36;padding:15px}details{border-bottom:1px solid #e0e7eb;padding:14px 0}summary{cursor:pointer;font-weight:bold}.pill{font-size:12px;color:#245965;margin-left:12px}dl{display:grid;grid-template-columns:170px 1fr;gap:8px}dt{font-weight:600}dd{margin:0}code{overflow-wrap:anywhere;font-size:13px}footer{font-size:13px;color:#53626d}@media(max-width:650px){main{padding:12px}header,section{padding:18px}dl{grid-template-columns:1fr}h1{font-size:25px}}'
    target.with_suffix(".html").write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PTTI Technology Foundation v0.1</title><style>'+style+'</style><main>'+''.join(body)+'</main></html>',encoding="utf-8")
    for path in (target,target.with_suffix(".html")):
        path.with_suffix(path.suffix+".sha256").write_text(file_sha256(path)+"  "+path.name+"\n")
    print(json.dumps({"report":str(target.with_suffix(".html")),"sha256":file_sha256(target.with_suffix(".html")),"commit":result["git_commit"]}))


if __name__ == "__main__":
    main()
