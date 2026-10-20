# Worker-01 Contribution: Stateless Language Agents Analysis

> **訂正（2026-10-20）**
>
> このファイルは 9行のまま一度も見直されず、後発メモが確立した水準（節番号付きの
> 逐語引用・negative findings の記録・実行済み確認の列挙）を満たしていなかった。
> とくに **「Inference-time Sinkhole」は本リポジトリのどこにも出典がなく、
> arXiv:2610.07625 の本文にも存在しない語** である（全文読解レポート1 は PDF 全14
> チャンクを通読しており、該当記述を報告していない）。出典のない独自の命名を
> 論文の知見として "Findings" に置くのは、2026-10-19 の監査が摘発した
> 「原文に存在しない文の引用」と同系統のリスクである。以下を訂正した。
>
> - **訂正1**：「Inference-time Sinkhole」を**本ノート独自の比喩**として明示し、
>   論文の知見としての扱いをやめた。出典なし。
> - **訂正2**：「最新の学術的発見と**完全に一致**している」を後退させた。SLA と
>   ResearchOS は規模も評価対象も異なり、一致は設計原則の方向についてであって
>   実証的な一致ではない。
> - **訂正3**：節番号と主要な制約（n=1・トークン一致であってコスト一致でない）を追加。
>
> 対応する台帳記録：`CLM-20261020-60f5`（CLM-001 の反証）、`CLM-20261020-b07e`。

## Findings

1. **会話履歴肥大化の弊害:** トークンコスト増加にとどまらず、モデルが過去の自身の出力
   （とくに中間的な誤りや迷走）にアテンションを奪われ、探索が硬直化する。
   - **注記（2026-10-20）：** この現象に対する「Inference-time Sinkhole」という呼び方は
     **本ノートの著者による比喩であり、arXiv:2610.07625 の用語ではない。出典なし。**
     論文が実際に述べているのは、履歴を保持する構成で「agents replay growing
     histories, duplicate one another's work, or stop experimenting while token
     consumption continues」（Abstract, §1）という観察である。
2. **Stateless Harness の構造:**
   - 永続正本: ファイルシステム / 構造化State
   - モデルへの入力: 「現在のタスク定義 + 直近の観測 + 参照すべき証拠抜粋」のみ
   - 分離は「依頼」ではなく「実行」で強制される（§3.3: "Statelessness and isolation
     are enforced rather than requested"）。Worker は非特権プロセス＋Linux Landlock
     で他 Worker の作業場と過去成果物へのアクセスを遮断される。
3. **ResearchOS への示唆:**
   - ResearchOS Core の設計原則「会話履歴と永続研究状態の分離」は、SLA が提唱する
     方向と**整合する**。
   - **注記（2026-10-20）：** 旧記述の「完全に一致している」は過剰である。SLA は
     最大10億トークン規模・8タスクの評価であり、ResearchOS のような小規模リポジトリ
     での有効性を実証したものではない。設計原則の**方向が同じ**というにとどめる。

## このノートが書かれた時点では無視されていた制約（2026-10-20 に追記）

- **再現回数の偏り**：主要結果は Anthropic カーネル＋Codex（3回）とチェックポイント
  継続アブレーション（各3回）を除き**すべて単一実行**（§4.1 "Other main-result
  configurations use one run per method"、§5）。
- **コスト一致ではない**：比較はトークン予算を一致させたものであり、実験実行・評価の
  計算コストは見積もりに含まれない（§5）。
- **stateless 化そのものは未分離**：アブレーションが変えるのは「何を見るか」であって
  「会話を持ち越すか否か」ではない（§5）。
- **曖昧なタスクは未検証**：全タスクが実行可能な評価器付きであり、"goals that are
  vague or slow to evaluate remain untested"（§5）。

（以上は本リポジトリの `contributions/2026-10-20_sla_fulltext_reading.md` が
arXiv PDF 全14チャンクの通読で確認した内容の転記。）

## 参考文献

[1] Qizheng Zhang, Changxiu Ji, Isaac Sun, …, Kunle Olukotun. "Stateless Language Agents: Scaling Long-Horizon Automated Research." arXiv:2610.07625v1 [cs.LG], 2026（投稿 2026-10-06）. https://arxiv.org/abs/2610.07625 / DOI: 10.48550/arXiv.2610.07625
