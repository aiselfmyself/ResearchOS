# Worker-02 Contribution: GitSwarm Architecture & Boundary Conditions

> **訂正（2026-10-20）**
>
> このファイルは 2026-10-19 の監査時点から、論文の内容と**逆の記述**を1件含んだまま
> `main` に残っていた。`contributions/2026-10-20_stateless_vs_gitswarm.md` §5 と
> `contributions/2026-10-20_git_swarm_fulltext_reading.md` §6 がそれぞれ「論文と逆」と
> 指摘していたが、当該ファイルは訂正されなかった。2026-10-20 に以下を訂正した。
>
> - **訂正1（重大）**：旧「多数決の危険性」の項は「Plurality Readout は検証可能な課題で
>   **有効**」と述べていた。これは逆である。GitSwarm は検証可能な課題では readout を
>   **剥離**し、検証性能で候補を選ぶ（§3.3）。readout は検証スコアが使えない場合の
>   フォールバックである（§2.5）。訂正前の文面は §訂正記録 に残す。
> - **訂正2**：再利用 94.7% と負の結果 70.1% にスコープ注記を追加した（ProgramBench /
>   NanoChat の限定窓の値であり、全タスクの普遍値ではない）。
> - **訂正3**：「後続ワーカーの無駄な探索の回避に**直接貢献する**」を観測表現に改めた。
>   論文は再利用を「観測」であって因果寄与の分離ではないとしている（§3.4 末尾、§4）。
>
> 根拠：`EVD-20261020-932f`、検証 `VER-20261020-4843`（result: fail）。

## Key Strengths

1. **Compounding Inference (累積推論):**
   - 従来のエージェントは独立試行の「成功／失敗」のみを記録し、道中の計算は破棄されていた。
   - GitSwarm はコミットとして保存し、**ProgramBench では** 94.7% が後続に構築される
     （IMOProofBench では 44.4%。§3.4）。
2. **Negative Results の価値:**
   - 負と明示された研究コミットのうち **NanoChat の最初の24アクティブ時間では** 709件中
     497件（70.1%）が後続に引用された（§3.3、Appendix E.4）。後続ワーカーが同じ行き
     止まりを避ける助けになると**報告されている**。

## Critical Boundary Limitations

1. **多数決の位置づけ（訂正済み）：** GitSwarm は「決定論的多重度推薦（Plurality
   Readout）」を実装しているが、これは**検証スコアが使えない場合の選択規則**である
   （§2.5）。検証性能で選べる実験では readout を**外している**
   （§3.3: "We strip GitSwarm of the nomination based decentralized readout for these
   experiments since all tasks discussed here support a validation performance based
   candidate selection"）。ダッシュボードにも「votes are not evidence of correctness」
   と明記される（§2.4）。票は「coordination signals, not independent proofs of
   correctness」（Appendix G.3）であって、**検証の代替にはならない**。
2. **文献調査・社会科学への適用限界:** 自然言語主体の研究で同質モデルに多数決をとらせると、
   共通のハルシネーションや偏見が最多得票になりうる。
   - 補足（2026-10-20）：この懸念は 2026-10-20 に決定論的投票モデルで測定された
     （`gitswarm/readout_sim.py`、`contributions/2026-10-20_common_mode_measurement.md`）。
     結果は「増幅は無条件には起きない」。相関のみ（共有見解が個人と同等に正しい）場合は
     誤りは増幅されず、**統合の恩恵が完全に失われる**（追従率0.9・N=15 で増幅率 1.001
     ＝15人を集めても統計的な中身は1人分）。誤った共有見解への追従率が `p/(1+p)` を
     超えると増幅する（増幅率最大 1.308）。**ただしワーカーはモデル上の標本であり、
     実 LLM ワーカー群の追従率は未測定である。**

## 訂正記録

以下の文面を 2026-10-20 に削除・差し替えた。捏造の記録として原文を残す。

> **旧 Critical Boundary Limitations 1（削除）：**
> 「GitSwarm は「決定論的多重度推薦（Plurality Readout）」を採用しているが、これは
> 証明問題やベンチマークのように解の正しさが後から確認できる課題で有効。」

この記述は GitSwarm §3.3 と正反対である。**検証可能な課題で有効なのは検証性能による
選択であって、多数決ではない。**

## 参考文献

[1] Vedant Shah, Ankur Samanta, Paras Dahal, …, Anirudh Goyal. "GitSwarm: Decentralized Compounding Inference." arXiv:2610.04862v1 [cs.AI], 2026（投稿 2026-10-04）. https://arxiv.org/abs/2610.04862 / DOI: 10.48550/arXiv.2610.04862

[2] Qizheng Zhang, Changxiu Ji, Isaac Sun, …, Kunle Olukotun. "Stateless Language Agents: Scaling Long-Horizon Automated Research." arXiv:2610.07625v1 [cs.LG], 2026（投稿 2026-10-06）. https://arxiv.org/abs/2610.07625 / DOI: 10.48550/arXiv.2610.07625

（節番号は arXiv:2610.04862v1 の本文・Appendix による。数値の照合は本リポジトリの `contributions/2026-10-20_git_swarm_fulltext_reading.md` を参照。）
