# 原典照合 S1 — 2026-10-20

対象は arXiv:2507.13334（P1）と arXiv:2606.10209（P2）。`bottlenecks` の文献番号 [1]/[2] は `integrated_survey_report` の [4]/[5] に対応するが、以下は arXiv ID で識別した。原典の abs で投稿履歴を確認し、最新版 HTML を読んだ。数値の再計算・実験はしていない。逐語引用と箇所は同名 JSON に収録する。

| arXiv ID | abs で確認した最新版 | メモ引用版 | 読んだ HTML | 版差 |
|---|---|---|---|---|
| 2507.13334 | v2（v1: 2025-07-17、v2: 2025-07-21） | v2 | https://arxiv.org/html/2507.13334v2 | なし |
| 2606.10209 | v1（2026-06-08） | v1 | https://arxiv.org/html/2606.10209v1 | なし |

abs: https://arxiv.org/abs/2507.13334 ・ https://arxiv.org/abs/2606.10209

## arXiv:2507.13334

| claim | 判定 | 根拠・留意点 |
|---|---|---|
| C-05de-01 | `verbatim` | Abstract: over 1400 research papers |
| C-05de-02 | `paraphrase_ok` | Abstract: systematic optimization of information payloads; 「定式化」は意訳 |
| C-05de-03 | `verbatim` | Abstract: 三つの foundational Components。厳密には上下の「階層」ではなく三段階の構成要素 |
| C-05de-04 | `paraphrase_ok` | Abstract: understanding complex contexts と generating sophisticated long-form outputs の asymmetry |
| C-05de-05 | `paraphrase_ok` | abs の Comments は “ongoing work”。査読済みでないとの扱いは書誌からの慎重な解釈であり査読状態の独立証明ではない |
| C-05de-06 | `verbatim` | abs の投稿履歴に 17 Jul 2025 の v1、HTML v2 ヘッダに cs.CL。**2025-07-17 は初回投稿で、v2 の改訂日は 2025-07-21** |

## arXiv:2606.10209

| claim | 判定 | 確認箇所 |
|---|---|---|
| C-787b-01 | `verbatim` | Abstract、Table 2: GPT-5 の C1–C4。ただし C1 は user model なしの motivating ablation、文脈ポリシーの統制比較は C2–C4 |
| C-787b-02 | `verbatim` | §3.6、Table 2 caption: 50-task hotel expense benchmark |
| C-787b-03 | `verbatim` | Abstract、Table 2 caption: 5 independent runs。user model 固定は C2–C4 に限る |
| C-787b-04 | `verbatim` | Table 2 C1: 完了 **8.0%** |
| C-787b-05 | `verbatim` | Table 2 C2: 完了 **71.0%**、Total Tok.(K) **1,481.0**、Time **14.56** hrs。正確なトークン値 **1,480,996** は §4.2／Abstract |
| C-787b-06 | `verbatim` | Table 2 C3: 完了 **79.0%**、Total Tok.(K) **535.3**、Time **5.39** hrs。正確なトークン値 **535,274** は §4.3／Abstract |
| C-787b-07 | `verbatim` | Table 2 C4: 完了 **91.6%**、%Amt **99.64%**、Total Tok.(K) **553.4**、Time **5.79** hrs。正確なトークン値 **553,374** は §4.4／Abstract |
| C-787b-08 | `paraphrase_ok` | §4.9: Claude Sonnet 4.5 でも pruning に summarization を加えると完了率 **92.0% → 94.5%**。ただし GPT-5 の C1 8.0% と違い Sonnet の非対話 baseline は 88.0% |
| C-787b-09 | `paraphrase_ok` | Abstract と §6.4: 主実験は D365 F&O 経費明細、追加で他の経費カテゴリも扱う。「1課題クラス」は enterprise expense workflow という意味なら妥当だが、ホテルだけに限定した実験という意味ではない |

**表の読み方**：Table 2 のトークン列は千単位に丸められている。メモの整数値は表のセルそのものではなく本文 §4.2–4.4 と照合した。8.0、71.0、79.0、91.6、99.64、1,480,996、535,274、553,374、14.56、5.39、5.79 を個別に確認した。いずれも原典記載と一致する。ここでは原著者の報告値の実測妥当性は検証していない。
