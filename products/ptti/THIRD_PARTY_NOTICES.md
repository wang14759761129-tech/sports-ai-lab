# Third-party notices

## RacketVision — AAAI 2026

- Repository: https://github.com/OrcustD/RacketVision
- Pinned commit: `c44af2a08524d3cb54d818f19686f4cdea4d2793`
- Integration date: 2026-10-05
- License: MIT, Copyright (c) 2025 Linfeng Dong. The original LICENSE remains in the pinned checkout.
- Local modifications: none. TTI adapters live outside the official checkout.
- Purpose: ball tracking, eventual racket pose / trajectory integration, benchmark evaluation.
- Runtime checkout is ignored, reproducibly cloned by the setup script; no model or video is shipped in Git.
- Dataset: https://huggingface.co/datasets/linfeng302/RacketVision at `85157ca21faa2abca96d837dd2b963738029bcc8`; dataset card declares MIT. No assertion of independent WTT broadcast licensing is made.
- Models: https://huggingface.co/linfeng302/RacketVision-Models at `a3760773233a0988c9605259743fbdd87c59d3a3`.

MIT License

Copyright (c) 2025 Linfeng Dong

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Extended OpenTTGames

- Repository: https://github.com/moamal01/table_tennis_data
- Pinned revision used for this research adapter: `36471a76b969a0340df59258a813bf8214e68e7c`
- License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0).
- Purpose: non-commercial research and evaluation of match-structure/event annotations.
- Dataset fields are used only in explicitly labeled research runs; the dataset is not included in product installers, portable builds, commercial assets, or Git.
- Attribution and license terms must accompany any permitted redistribution or adaptation. Do not use this material for commercial purposes.
- Staged local files are kept under `%LOCALAPPDATA%\PTTI-Dev\research-datasets\ExtendedOpenTTGames`; no video or annotation file is tracked by this repository.
- Dataset metadata declares `commercial_use: false`.
