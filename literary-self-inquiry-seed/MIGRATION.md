# ResearchOSからの選定・移行手順

## 1. 方針

新リポジトリへは全台帳を複製せず、テーマの入口になる**選定済みの出典・短い証拠抜粋・来歴**だけを移します。元の記録IDは消さず、`origin` と `migration/manifest.json` で追跡可能にします。

移行対象は、現在の `ResearchOS` の次の記録です。

- **出典（SRC）10件**：外部記憶・複数セッション間の継続・記録の再利用を扱う研究、およびLLMの自己認識／自己選好に関する研究。
- **証拠（EVD）14件**：各出典から主題を考えるきっかけになる短い抜粋。元の節・ページと既存解釈を添える。
- **調査メモへの参照7件**：本文は自動コピーせず、参照先として記録する。必要なメモだけ人が新リポジトリへ複製・改稿する。
- **初期の問い5件・モチーフ6件**：特定の科学仮説ではなく、ユーザーの希望に沿った開かれた問いとして新規に作成する。

**範囲の偏り**：移行素材はAIエージェントの設計・評価研究に偏っています。元リポジトリには、人間の自己、身体性、文学作品を直接扱う人文学資料はほぼありません。`Q-001` に結びつけたAI記憶研究は比喩的な入口であり、人間についての根拠や結論ではありません。人間側の資料は新リポジトリで別途選び、追加する前提です。

### 選定した出典

| 元SRC | 文献 | 移行する理由／扱い |
|---|---|---|
| `SRC-001` | *Stateless Language Agents: Scaling Long-Horizon Automated Research* | 会話の継続と、外部状態から再構成される文脈の対照 |
| `SRC-002` | *GitSwarm: Decentralized Compounding Inference* | 先行記録を後続が引き継ぐ「系譜」の比喩 |
| `SRC-20261020-f295` | *Agora: Git as Shared Memory for Collective AutoResearch* | 共有記憶、相互可視性、集団の声の素材 |
| `SRC-20261021-0a74` | *MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks* | 外部記憶が常に全履歴より優位とは限らない対照 |
| `SRC-20261021-5bb4` | *Beyond Semantic Organization: Memory as Execution State Management for Long-Horizon Agents* | 記憶を事実の保管ではなく行為状態として見る入口 |
| `SRC-20261021-d652` | *Beyond the Context Window: A Cost-Performance Analysis of Fact-Based Memory vs. Long-Context LLMs for Persistent Agents* | 事実再生と「自己らしさ」を混同しないための対照 |
| `SRC-20261021-aa4e` | *LLM Evaluators Recognize and Favor Their Own Generations* | 自己認識・自己選好の研究。ただし主観的自己の証明ではない |
| `SRC-20261021-e315` | *Can LLMs predict the outcomes of machine learning experiments?* | 別課題では自己選好が検出されなかったという対照 |
| `SRC-20261021-2276` | *Self- and Other-Labels Induce Bidirectional Bias in LLM Judges* | 自己／他者というラベルが評価を変える素材 |
| `SRC-20261021-fe40` | *Self-Generated Text Recognition: Quality Heuristics, Cross-Task Transfer, and Downstream Bias in LLM Evaluation* | 自己認識と品質判断の交絡・課題依存性 |

対象ID、各抜粋を問いへ結びつけた理由、適用範囲の留保は [`migration/selection.json`](migration/selection.json) を参照してください。

## 2. 何を移さないか

- 既存の `HYP`、`PRD`、`REL` の判定値を、文芸的な答え・物語上の真実として移さない。
- `support / refute / neutral / unresolved` を文芸的な関係ラベルとして流用しない。
- 科学仮説サイクル専用の必須反証条件、停止条件、実験評価用のCIを持ち込まない。
- TSPベンチマーク、科学研究OSのガバナンス監査、並列セッションの全作業記録、今回のテーマと関係の薄い文献は含めない。
- `.git`、全履歴、論文全文、未選定の証拠はコピーしない。
- 保存されていない生の会話や「当時のAIの内面」は復元できないため、移行したように装わない。

特に、ResearchOSの `HYP-001`（外部化記憶と長文脈の比較）は結論として移さず、たとえば「過去の記録を読み直す主体は、どの意味で同じ自己なのか」という**新しい文芸的な問い**へ変換します。

## 3. 同じ選定で素材を再生成する

`migration/selection.json` が入力です。取り込むのは出典メタデータと選定したEVDのみで、元リポジトリの台帳は書き換えません。

```sh
python3 tools/import_researchos.py --source-root /path/to/ResearchOS --check
python3 tools/validate_seed.py
```

元データを新しい版へ更新する場合は、差分を確認してから明示的に書き込みます。

```sh
python3 tools/import_researchos.py --source-root /path/to/ResearchOS --write
python3 tools/validate_seed.py
```

`--write` が再生成するのは次の2ファイルのみです。

- `state/materials.jsonl`
- `migration/manifest.json`

`--write` は現在のResearchOS HEADを新しい上流スナップショットとして記録します。未選定のソースや全文は追加しません。

`--check` は、選定IDが元リポジトリに存在すること、EVDの出典が選定済みSRCに含まれること、および生成済みファイルが選定記録と一致することを確認します。ResearchOSのHEADがこのキットの追加コミットで進んでも検査結果が不必要に変わらないよう、`--check` は既存manifestの上流コミットを来歴表示に再利用しつつ、選定した台帳レコード自体は現在のチェックアウトと照合します。選定したレコードが変わっていれば `--check` は stale と報告します。

## 4. 空の新リポジトリへ移す

1. 新しい空リポジトリを作り、名前・公開範囲を決める。候補名は `human-ai-self-inquiry` だが、確定ではない。
2. この `literary-self-inquiry-seed/` の**中身**を新リポジトリのルートへコピーする。`ResearchOS/.git` はコピーしない。ローカルに空のcheckoutがある場合の例：

   ```sh
   cp -a /path/to/ResearchOS/literary-self-inquiry-seed/. /path/to/human-ai-self-inquiry/
   ```

3. `MIGRATION.md`、`migration/manifest.json`、`state/materials.jsonl` を確認し、出典URL・版・元ID・引用範囲を点検する。
4. `python3 tools/validate_seed.py` を実行する。
5. 最初のセッションでは問いを一つ選び、`prompts/first_session.md` を使う。出力を確認したあと、採用する断片だけを `state/fragments.jsonl` に記録する。
6. 問い・モチーフ・断片の関係は、編集上意味がある場合だけ `state/relations.jsonl` に追記する。全てを形式化する必要はない。
7. 新しいGit履歴で初回コミットを作る。元のResearchOSとの関係は、マニフェストに記録した上流リポジトリURLとコミットで追跡する。

新しいリポジトリを作成する前に、最初の一作をこのキット内で試作することもできます。ただし、その場合も出典付き素材と創作断片の区別は保ちます。

## 5. 来歴に関する注意

このスナップショットの上流は `migration/manifest.json` に記録されています。既存メモに書かれた解釈は、原典に対する最終判定ではありません。とくに自己認識・自己選好に関する研究は、評価課題でのモデル挙動を扱う資料であり、AIに主観的経験があることを示す資料ではありません。文学的な問いを生む素材として扱い、結論へ短絡させないでください。
