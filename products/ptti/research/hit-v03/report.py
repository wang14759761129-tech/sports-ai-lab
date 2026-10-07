"""Readable, source-backed research handoff. Never publishes or alters product UI."""
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import sys


def table(headers, rows):
    return '<table><thead><tr>'+''.join('<th>'+html.escape(str(h))+'</th>' for h in headers)+\
        '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+
        '</tr>' for row in rows)+'</tbody></table>'


def main(audit, ablation, output):
    audit, ablation, output = Path(audit), Path(ablation), Path(output)
    data = json.loads((ablation/'ablation.json').read_text(encoding='utf-8'))
    diagnostics = [json.loads((audit/f'game_{game}_diagnostics.json').read_text(encoding='utf-8')) for game in (1, 2, 3)]
    totals = {stage: Counter(label for g in diagnostics for fp in g['stages'][stage]['fp_diagnostics'] for label in fp['labels'])
              for stage in ['raw', 'cluster', 'decoded']}
    body = '<h1>PTTI Hit Event v0.3 · 完整 DEV 证据研究</h1>'
    body += '<p class="warning">仅 game_1–3。不是独立泛化验证，不包含正式 TEST、calibration 或 holdout。原始 BallTrack、正式数据库和桌面未改。</p>'
    body += '<h2>A/B/C/D 对比 · ±2 processing frames（16.667ms）</h2>'
    rows = []
    for mode, metrics in data['aggregate'].items():
        rows.append([mode, metrics['tp'], metrics['fp'], metrics['fn'],
            *(f'{metrics[k]:.3f}' for k in ['precision', 'recall', 'f1']),
            f'{metrics["fp_per_minute"]:.2f}', f'{metrics["fn_per_minute"]:.2f}',
            f'{metrics["review_workload"]["candidates_per_minute"]:.2f}'])
    body += table(['方案', 'TP', 'FP', 'FN', 'Precision', 'Recall', 'F1', 'FP/min', 'FN/min', 'Review/min'], rows)
    body += '<h2>Review 模式质量</h2>'
    body += table(['方案', 'TP', 'FP', 'FN', 'P', 'R', 'F1'], [[mode,
        metrics['review_metrics']['tp'], metrics['review_metrics']['fp'], metrics['review_metrics']['fn'],
        *(f'{metrics["review_metrics"][key]:.3f}' for key in ['precision', 'recall', 'f1'])]
        for mode, metrics in data['aggregate'].items()])
    body += '<h2>逐比赛 · 全部容差</h2>'
    rows = []
    for game in data['games']:
        for mode, result in game['modes'].items():
            for tolerance, metrics in result['automatic_metrics']['by_tolerance'].items():
                rows.append([game['game'], mode, tolerance, metrics['matched'], metrics['false_positives'], metrics['false_negatives'],
                    *(f'{metrics[k]:.3f}' for k in ['precision', 'recall', 'f1'])])
    body += table(['比赛', '方案', '容差', 'TP', 'FP', 'FN', 'P', 'R', 'F1'], rows)
    body += '<h2>误报的邻近事件与轨迹线索</h2><p>多标签可重叠。邻近不代表原因；SERVE_PREPARATION 仅是待看视频的假设。</p>'
    rows = [[label]+[totals[stage][label] for stage in ['raw', 'cluster', 'decoded']]
            for label in sorted(set().union(*(set(c) for c in totals.values())))]
    body += table(['线索', 'Raw FP', 'Cluster FP', 'Decoder FP'], rows)
    body += '<h2>192 Raw FN 与阶段丢失</h2><p>94 个上下文不完整；98 个上下文存在，但其中 97 个容差内没有可见球中心，另 1 个邻帧间隔不合格。64 个聚类丢失源于选中成员时间移出容差；103 个 Decoder 丢失中 40 个仅进入复核，63 个自动拒绝。</p>'
    body += '<h2>45 分钟比赛的复核成本估计</h2><p>每次候选复核假设 3 秒；尚未测量真人时间。</p>'
    body += table(['方案', '估计点击次数', '估计复核分钟'], [[mode,
        round(m['review_workload']['estimated_clicks_per_45_minute_match']),
        f'{m["review_workload"]["estimated_review_minutes_per_45_minute_match"]:.1f}'] for mode, m in data['aggregate'].items()])
    body += '<h2>证据与限制</h2><p>球台特征是静态侧机位、粗框图像坐标先验；不是真实三维落点。人物角色只是未确认候选。缺少角色证据时软特征保持中性，Pose OFF。单纯速度分布高度重叠，未证明可可靠区分 Hit/Bounce/Net。</p>'
    body += '<p>详细误报、漏检、原始轨迹和 Decoder 路径解释保存在同目录 research JSON 中；55 段短视频复核包保留源时间。研究数据 CC BY-NC-SA 4.0，非商业使用。</p>'
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PTTI Hit v0.3 DEV</title><style>body{max-width:1200px;margin:40px auto;padding:0 24px;background:#f7f8fa;color:#172334;font:16px/1.65 "Microsoft YaHei UI",sans-serif}table{border-collapse:collapse;width:100%;background:white;font-size:14px;margin:20px 0}th,td{padding:9px;border-bottom:1px solid #dde3eb;text-align:left}th{background:#e8eef5}h2{margin-top:34px}.warning{padding:16px;background:#fff0cb;border-left:4px solid #c18712}</style>'+body+'</html>'
    output.write_text(document, encoding='utf-8')
    print('report_sha256='+hashlib.sha256(document.encode()).hexdigest())


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
