# Preview v0.3 分支集成审计

核验日期：2026-10-08。

- 产品 worktree：video-evidence-player-v0.1，HEAD 01789865959675f81604c982682bd1e6489d874e。
- 稳定化 worktree：research-integration，HEAD b950303f3f44c2be1d8e7dac713426888e9d0367，起始工作树干净。
- 两者属于同一 Git 仓库的 worktree，不是独立 clone。merge-base 等于产品 HEAD；左右独有提交为 0 / 13。
- 研究冻结祖先：17574a58078923cbf1828b69e9875e4cd1968411。
- 产品代码已由线性历史继承，未发现需要重新复制或合并的产品功能。稳定化修复尚未进入产品分支，但已进入本候选基础。
- 候选分支：release-candidate/video-evidence-v0.3-preview，从 b950303 建立；不重复 cherry-pick，不合并研究分支，不动 main。

继承修复：AI 过滤/原始记录保护、事务化并发审计、请求幂等、CSV 公式防护、checkpoint 输出哈希、预览流式窗口、视频原子发布、异步队列竞争保护、元数据校验、psutil 依赖。完整缺陷与回归证据见 ENGINEERING-AUDIT-STABILIZATION-2026-10-08.md。

本轮只增加独立 Preview 身份、构建与验收材料；Hit 冻结配置保持原 SHA256。
