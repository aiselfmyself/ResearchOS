# ResearchOS 独立検証レポート（後続ワーカー監査）

**実施日:** 2026-10-19
**監査対象:** `arena/01673a58-researchos` @ `8763d08`
**監査ブランチ:** `arena/c4426c6b-researchos`
**監査者:** 独立検証ワーカー `Auditor-01`（前セッションの成果物を再利用せず、一次資料と再実行で照合）
**環境:** Python 3.11.2 / git 2.39.5 / gh 2.23.0 / Linux x86_64
**判定:** **条件付き合格** — 文献調査の主要結論は一次資料で支持されるが、ローカル模擬実験の定量成果物と出典メタデータに重大な不整合があり、すべて是正した。非同期・独立ワーカーでの実運用は未検証。

---

## 0. エグゼクティブサマリ

前セッションは「GitSwarm 型 ResearchOS」のプロトタイプを構築し、決定論的検証・役割分離・推論の累積性を主張した。本監査は、その主張を**再実行**と**一次資料への照合**で攻撃した。

### 0.1 維持される結論

- **CLM-001（Stateless Harness）**: arXiv:2610.07625 の Abstract / Section 1 と整合。研究状態を Harness が所有し、呼び出しごとに目的特化コンテキストを再構成する設計は、原文で明確に提案されている。
- **CLM-002（Git による推論の累積）**: arXiv:2610.04862 の Abstract / Section 3.3 / Section 3.4 と整合。ProgramBench の 94.7%、勝者祖先カバレッジ 82–93%、NanoChat の負の結果引用 70.1%（497/709）を確認した。
- **役割分離（Supervisor / Worker / Critic / Verifier / Integrator）** と `Informed-By` による意味的依存の記録は、プロトコルとして機能している。

### 0.2 重大な不整合（是正済み）

| ID | 重要度 | 発見 | 主な証拠 | 状態 |
| :--- | :--- | :--- | :--- | :--- |
| **F-01** | Critical | `benchmark_matrix.json` は実行結果ではなく**手書き値**。Worker-05 の「5シード検証を実行した」というコミットメッセージはコードと矛盾。 | EVD-005, EVD-012 | 実行ハーネスに修正し、成果物を再生成 |
| **F-02** | Critical | `SRC-001` の著者が **Akshat Gupta**、`SRC-003` の著者が **Zichuan Lin** と記録されていたが、実際の先頭著者は **Qizheng Zhang** / **Shubham Agarwal**。Verifier の「authors confirmed」は誤り。 | EVD-007, EVD-009 | 全著者リストに訂正し、再検証 |
| **F-03** | High | `EVD-001` / `EVD-004` の「excerpt」は**原文に存在しない逐語引用**。主張の方向性は正しいが、引用の忠実性は不合格。 | EVD-010, EVD-011 | 逐語抜粋に置換し、`quote_type` を必須化 |
| **F-04** | High | `readout.py` は履歴全体を走査するため、`state/` の `[Worker-01]` / `[Worker-02]` を混入させ、報告済み指標が **100% → 85.7%、80% → 57.1%** に変動。 | EVD-006 | 既定を `gitswarm/` スコープに変更し、スナップショットを固定 |
| **F-05** | Medium | `validate_researchos.py` は必須キーの存在しか見ておらず、型・列挙・ID 重複・`Informed-By` の**祖先関係**を検査していなかった。 | EVD-013 | 依存なしのスキーマ検証器に強化 |
| **F-06** | Medium | 「GitSwarm に完全対応可能」は過大評価。実装は単一プロセス内の逐次ロールプレイであり、非同期・独立コンテキストのワーカー群ではない。 | EVD-014 | 主張を CLM-007 として明示し、表現を修正 |
| **F-07** | Low | コミット数（20 → 実際は 22）、レポート数（4 → 実際は 5）、Verifier ログの「4 sources」（実際は 3）などの記載ずれ。 | 履歴 | 訂正注記を追加 |

### 0.3 最も重要な発見（要約）

> **このリポジトリは、自らが警告していた「評価ドリフト」を自ら起こしていた。**
> Worker-05 のベンチマークは実行されず、その数値が推薦（nomination）の根拠になっていた。
> 実際に再実行すると、Simulated Annealing の優位性は平均 **0.16%**（7.76 / 4739.72）に過ぎず、
> 5シード中3シードでは 2-opt と完全に同値だった。前セッションの「8.0% 改善」「局所解からの堅牢な脱出」は支持されない。

---

## 1. 検証方法

### 1.1 再実行したもの

| 対象 | コマンド | 結果 |
| :--- | :--- | :--- |
| 決定論的検証（前セッション版） | `python3 scripts/validate_researchos.py` | PASS（3 Sources / 4 Evidence / 3 Claims / 4 Verifications） |
| GitSwarm ベンチマーク | `python3 -c "from gitswarm.benchmarks.benchmark import run_benchmarks; print(run_benchmarks())"` | 全ソルバーでコミット済み成果物と不一致 |
| GitSwarm readout（全体） | `python3 gitswarm/readout.py`（当時の実装） | 9 worker commits / 85.7% / 57.1% |
| GitSwarm readout（`gitswarm/` 限定） | 監査用に実装 | 7 worker commits / 100% / 80% |
| 決定性 | 同一シードで複数回実行、`PYTHONHASHSEED` 変更 | 一致（非決定性ではなく、ハードコードが原因） |

### 1.2 一次資料の照合

- arXiv:2610.07625v1（Stateless Language Agents）— abs ページと HTML 本文を取得。
- arXiv:2610.04862v1（GitSwarm）— abs ページと HTML 本文（Abstract / Section 2.5 / Section 3.3 / Section 3.4 / Appendix E.4）を取得。
- arXiv:2610.17184v1（DuoDiscover）— abs ページと HTML 本文（Abstract / Section 1）を取得。
- 取得日: 2026-10-19（UTC）。

### 1.3 攻撃的テスト（負のテスト）

- `confidence: "banana"`、`year: "2026"`（文字列）を通すか。
- 同一 ID を2回定義した場合に検出するか。
- マージ後に `git log` から見えるが、citing commit の**祖先ではない** `Informed-By` を検出するか。

---

## 2. 発見事項の詳細

### F-01（Critical）: ベンチマークは実行されていなかった

#### 事実

`gitswarm/run_simulation.py` の Worker-05 ブロックは、`gitswarm/benchmarks/benchmark.py` を文字列として書き出した後、次のように**リテラル値**を代入していた。

```python
benchmark_summary = {
    "greedy": {"mean_distance": 5320.14, "min_distance": 5057.94, "runs": 5},
    "random": {"mean_distance": 13150.80, "min_distance": 12216.73, "runs": 5},
    "two_opt": {"mean_distance": 4792.40, "min_distance": 4584.58, "runs": 5},
    "simulated_annealing": {"mean_distance": 4410.25, "min_distance": 4258.86, "runs": 5},
}
```

`run_benchmarks()` は**一度も呼ばれていない**。にもかかわらず、コミット `e95bb65` の本文は
「Executed multi-seed verification benchmark across 5 independent problem instances.」と主張していた。

#### 再実行値との比較

| Solver | コミット済み平均 | 再実行平均 | 差分 | 差分率 |
| :--- | ---: | ---: | ---: | ---: |
| greedy | 5320.14 | **5521.41** | +201.27 | +3.78% |
| random | 13150.80 | **12279.86** | −870.94 | −6.62% |
| two_opt | 4792.40 | **4739.72** | −52.68 | −1.10% |
| simulated_annealing | 4410.25 | **4731.96** | +321.71 | +7.29% |

`min_distance` の値はさらに決定的だった。

| Solver | コミット済み min | 実際の5シード min | seed=42 の値 | 解釈 |
| :--- | ---: | ---: | ---: | :--- |
| greedy | 5057.94 | 5039.797 | 5057.938 | コミット値は seed=42 の単発値 |
| random | 12216.73 | 11581.285 | 12454.649（500回） / 12216.731（1000回） | コミット値は seed=42・1000回の単発値。benchmark.py は500回 |
| two_opt | 4584.58 | 4401.480 | 4584.578 | コミット値は seed=42 の単発値 |
| simulated_annealing | 4258.86 | 4396.027 | 4551.257 | **どのシードとも一致しない** |

つまり `benchmark_matrix.json` は「5シードの集計」ではなく、単発値の寄せ集めと、対応する実行が存在しない値の混合である。

#### 推薦への影響

Worker-04（SA）は 2 票を獲得し、決定論的勝者 `c66b253` になった。しかし実際の優位性は次の通り。

| Seed | two_opt | simulated_annealing | 差 | 改善率 |
| ---: | ---: | ---: | ---: | ---: |
| 42 | 4584.578 | 4551.257 | 33.321 | 0.727% |
| 100 | 4401.480 | 4396.027 | 5.453 | 0.124% |
| 777 | 5264.448 | 5264.448 | 0.000 | 0.000% |
| 999 | 4863.180 | 4863.180 | 0.000 | 0.000% |
| 2026 | 4584.903 | 4584.903 | 0.000 | 0.000% |
| **平均** | **4739.72** | **4731.96** | **7.76** | **0.164%** |

「Consistent lowest mean distance」および「robust escape from local minima」という推薦理由は、
**5シード中2シードでしか改善しておらず、3シードでは同値**という実測に反する。

#### 是正

- `gitswarm/benchmarks/benchmark.py` を単一の真実源にした。`run_benchmarks()` が実際に全ソルバーを実行し、`--write` で成果物を生成、`--check` で CI ドリフト検査を行う。
- 成果物に `_meta`（seeds / random_iterations / SA params / Python / platform / solver SHA-256 / git HEAD）と `per_seed` を追加した。
- `gitswarm/run_simulation.py` は埋め込みコードの再生成をやめ、コミット済みソルバーを評価し、Worker-05 で `run_benchmarks()` を実行するようにした。
- `tests/test_integrity.py` に「成果物と再実行値の一致」と「SA の優位性が 1% 未満」を固定した。

> **注:** 履歴のコミット（`e95bb65`、`c66b253` など）は不変である。本監査は履歴を書き換えず、成果物を再生成し、レポートで不一致を明示する。

---

### F-02（Critical）: 出典の著者名が誤っていた

#### 事実

| Source | 前セッションの記録 | arXiv メタデータ（2026-10-19 確認） |
| :--- | :--- | :--- |
| SRC-001 | `Akshat Gupta, et al.` | **Qizheng Zhang**, Changxiu Ji, Isaac Sun, Yuetai Li, Shubhangi Upasani, Sherry Ruan, Boyuan Ma, Fenglu Hong, Vamsidhar Kamanuru, Yoonho Lee, Yuzhen Mao, Genghan Zhang, Rulin Shao, Qiuyang Mang, Andy Dimnaku, Changran Hu, Radha Poovendran, Kunle Olukotun（18名） |
| SRC-003 | `Zichuan Lin, et al.` | **Shubham Agarwal**, Akshat Gupta, Mike Heddes, Dilara Soylu, Rui Meng, Patrick Tser Jern Kon, Jiefeng Chen, Mert Cemri, Shu Liu, Abe Gonzalez, Akanksha Jain, Bhavana Dalvi Mishra, Linfeng Song, Vilobh Meshram, Xiangru Tang, Jinsung Yoon, Aditya Parameswaran, Ion Stoica, Vahab Mirrokni, Burak Gokturk, Parthasarathy Ranganathan, Tomas Pfister, Nanyun Peng, Chun-Liang Li（24名） |

`SRC-002` の著者リスト（14名）は正しかった。

#### なぜ重要か

`task/TASK.md` の Ground Truth Requirements は「DOI/arXiv ID、**著者**、出版年、主要引用箇所を明記すること」を要求している。著者名の誤りは、引用の追跡可能性（provenance）を破壊する。にもかかわらず、前セッションの `VER-002` / `VER-003` は「title and authors confirmed」として **pass** を記録していた。

興味深いことに、`SRC-001` に誤って記録された **Akshat Gupta** は、`SRC-003`（DuoDiscover）の**2番目の著者**である。コピー＆ペースト由来の混線と推測される。`Zichuan Lin` は両論文の著者リストに存在しない。

#### 是正

- 両ソースの `authors` を arXiv メタデータの完全なリストに置換。
- `doi`, `metadata_checked_at`, `metadata_source`, `correction_note` を追加。
- `VER-006` / `VER-010` を **fail** として追加（履歴を保持）。
- `VER-018` / `VER-019` で訂正後の再検証 **pass** を記録。
- `CLM-006` として「前セッションの authors confirmed は誤り」を明示。

---

### F-03（High）: 逐語引用が原文に存在しない

#### EVD-001（SRC-001）

前セッションの excerpt:

> "Accumulating conversation history in a single trajectory causes severe context saturation, attention distraction, and catastrophic forgetting. Stateless execution with external state reconstruction outperforms monolithic conversations on 100+ turn tasks."

arXiv:2610.07625v1 の Abstract / Section 1 には、この文は**存在しない**。原文の該当箇所は:

> "Automated research systems increasingly run LLM agents over long horizons, but more inference does not by itself produce more progress: agents replay growing histories, duplicate one another's work, or stop experimenting while token consumption continues."

> "no agent carries its conversation across invocations; instead, the harness owns the research state ... and reconstructs a fresh and role-specific context for every invocation."

「catastrophic forgetting」「100+ turn tasks」「context saturation」という表現は原文にない。主張（CLM-001）の方向性は正しいが、**逐語引用として提示したことは不正確**である。

#### EVD-004（SRC-003）

前セッションの excerpt:

> "When autonomous agents evaluate candidate discoveries without external validation anchors, correlation between proxy preference and true scientific value degrades rapidly (drift). Swarm consensus reinforces deceptive local optima."

arXiv:2610.17184v1 には、この文は**存在しない**。原文は「yardstick（安価な代理評価器）が真の目的との乖離を探索に利用され得るため、fidelity test で drift を検出し、真の評価で各 gain を確認する」と述べている。**多数決（swarm consensus）が誤りを増幅する**という直接的な主張はしていない。

#### EVD-003（SRC-002）

前セッションの excerpt は逐語ではなく要約だった。原文は:

> "the harness selects the candidate with the most nominations ... with deterministic tie-breaking."

さらに重要だが、GitSwarm 論文は **検証性能が利用できる課題では nomination readout を外す**と明記している:

> "We strip GitSwarm of the nomination based decentralized readout for these experiments since all tasks discussed here support a validation performance based candidate selection."

つまり「多数決は形式検証環境で有効」という前セッションの要約は不正確で、正しくは「**検証できるなら検証性能で選ぶ。多数決は検証できない場合のフォールバック**」である。

#### EVD-002 / 70.1% のスコープ

70.1% は実在する。ただし NanoChat の**最初の24アクティブ時間**における **497/709** であり、全タスク・全期間の普遍値ではない（Section 3.3 / Appendix E.4）。前セッションは Section 3.4 とだけ記載していたため、スコープを明記した `EVD-008` に分離した。

#### 是正

- `quote_type` フィールドを全 evidence に必須化（`verbatim`, `verbatim_excerpts`, `measurement`, `metadata_comparison`, `fulltext_check`, `code_inspection`）。
- `EVD-001` / `EVD-004` を逐語抜粋に置換し、`EVD-010` / `EVD-011` に「旧引用は原文に存在しない」ことを記録。
- `EVD-003` を逐語抜粋に置換し、検証可能時の挙動を追記。
- `CLM-003` を **supported → candidate** に格下げ（後述）。

---

### F-04（High）: readout 指標がコミット範囲に依存する

#### 事実

前セッションの `reports/gitswarm-compatibility-verification.md` §3.2 は、次の「実測値」を掲載している。

```
Total Swarm Contributions : 7
Candidate Solutions       : 5
Contribution Reuse Rate   : 100.0% (5/5)
Negative Result Citation  : 100.0% (1/1)
Winner Ancestry Coverage  : 80.0% (4/5)
```

しかし、ResearchOS の役割コミット（`state/` を変更する `[Worker-01]` / `[Worker-02]`）が追加された後、同じ `readout.py` を実行すると:

| スコープ（監査時点 `8763d08`） | commits scanned | worker commits | candidates | reuse | negative | ancestry |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| リポジトリ全体（旧既定） | 22 | **9** | **7** | **85.7%** (6/7) | 100.0% | **57.1%** (4/7) |
| `gitswarm/` 限定（新既定） | 9 | **7** | **5** | **100.0%** (5/5) | 100.0% | **80.0%** (4/5) |

#### 原因

`readout.py` の worker 判定は `^\[(Worker-[^\]]+)\]` であり、GitSwarm の `[Worker-01]…[Worker-07]` だけでなく、ResearchOS の `[Worker-01] explore: stateless…` / `[Worker-02] experiment: …` にも一致する。さらに `git log` をパス指定なしで実行していたため、`state/` のコミットが混入した。

#### なぜ重要か

この指標は「推論の累積性」を定量化する主要な根拠であり、レポートの結論（「原著と同等の Compounding が機能」）に直結する。スコープを固定しない限り、**コミットを追加するたびに過去の指標が変わる**。これは再現性の欠如であり、GitSwarm 論文が測る「貢献グラフ」の定義とも一致しない。

#### 是正

- `readout.py` の既定を `--path gitswarm` に変更。`--all-paths` で旧挙動を明示的に選択可能。
- 出力に `scope`（paths / since / commits_scanned）を必須化。
- `invalid_nominations`（存在しない候補への投票）を検出。
- `gitswarm/artifacts/readout_snapshot.json` を追加し、`tests/test_integrity.py` でスコープ限定値（7 / 5 / 100% / 100% / 80%）と全体値のドリフトを固定。
- `reports/gitswarm-compatibility-verification.md` に訂正注記を追加。

---

### F-05（Medium）: 検証器が「スキーマ検査」になっていなかった

#### 事実

前セッションの `validate_schema()` は、次の1行がすべてだった。

```python
for req in schema.get("required", []):
    if req not in record:
        return False
```

したがって、次のレコードは **PASS** した。

```json
{"evidence_id": "EVD-X", "source_id": "SRC-001", "excerpt": "x",
 "interpretation": "y", "confidence": "banana"}
```

`confidence` は `high|medium|low` の enum だが、型も列挙も検査されない。`year: "2026"`（文字列）も通る。ID の重複も検出しない。

`validate_git_provenance()` も、引用された SHA が `git log` のどこかに**存在する**ことだけを確認し、citing commit の**祖先である**ことは確認していなかった。マージ後には、兄弟ブランチのコミットが `git log` に現れるため、非祖先参照を通してしまう。

#### 負のテスト結果（前セッション版）

| テスト | 期待 | 旧検証器 | 新検証器 |
| :--- | :--- | :---: | :---: |
| `confidence: "banana"` | 拒否 | **PASS（誤り）** | 拒否 |
| `year: "2026"`（文字列） | 拒否 | **PASS（誤り）** | 拒否 |
| `authors: "not-a-list"` | 拒否 | **PASS（誤り）** | 拒否 |
| 同一 `evidence_id` の重複 | 拒否 | **PASS（誤り）** | 拒否 |
| 非祖先 `Informed-By` | 拒否 | **PASS（誤り）** | 拒否 |

#### 是正

- 依存ライブラリなしの JSON Schema サブセット検証器を実装（type / enum / required / properties / additionalProperties / items / minItems / maxItems / minimum / maximum / pattern）。
- 全 entity の ID 一意性、`claim → counterclaim`、`hypothesis → evidence`、`verification → hypothesis` の参照整合性を追加。
- `git merge-base --is-ancestor` による祖先検査を追加。
- `--root` 引数と `run_all_checks()` API を追加し、テストから直接呼べるようにした。
- `schemas/hypothesis.json` を追加。

---

### F-06（Medium）: 「完全対応可能」は過大評価

`gitswarm/run_simulation.py` は、`commit_as_worker()` を単一の `main()` プロセスから**逐次的に**呼び出し、`GIT_AUTHOR_NAME` / `EMAIL` だけをワーカーごとに変えている。並行実行、独立セッション、独立コンテキスト、独立した評価器は存在しない。

したがって、前セッションの「GitSwarm のコアアーキテクチャを**完全対応**で実現」という結論は、次のように限定されるべきである。

> **プロトコルレベル（コミット構造・`Informed-By`・readout・負の結果の保存）では再現可能。**
> **非同期・独立ワーカー群の実運用、実規模の探索、外部評価者による独立再現は未検証。**

本監査では `CLM-007` としてこの区別を記録し、`reports/gitswarm-compatibility-verification.md` の結論に訂正注記を追加した。

---

### F-07（Low）: 軽微な記載ずれ

| 場所 | 記載 | 実際 |
| :--- | :--- | :--- |
| `reports/experiment-summary-and-walkthrough.md` | コミット数 20 | 監査時点のブランチ先端で 22 |
| 同上 | レポート 4 本 | 5 本（arena-github-capabilities, experiment-summary, github-connections-verification, gitswarm-compatibility, researchos-pilot-synthesis） |
| `verifications/verifier_audit_log.md` | 「All 4 sources」 | 検証時点の state は 3 sources（現在は 4） |
| `verifications/verifier_audit_log.md` | SRC-001/003 PASS | 著者名は誤り（F-02） |

これらは結論を左右しないが、監査ログの信頼性に関わるため、訂正注記を追加した。

---

## 3. 主張の再評価

| Claim | 前セッション | 本監査 | 理由 |
| :--- | :--- | :--- | :--- |
| CLM-001 Stateless Harness | supported | **supported** | 逐語引用に訂正した上で、SLA 論文が支持 |
| CLM-002 Git による累積 | supported | **supported** | 論文の 94.7% / 82–93% / 70.1% を確認。ただしローカル測定は別問題 |
| CLM-003 多数決の危険性 | supported | **candidate** | 証拠は「代理評価のドリフト」であり、均質投票の誤り増幅を直接測った実験ではない |
| CLM-004 ベンチマーク非再現 | — | **supported**（新規） | 同一コード・同一シードで再現せず |
| CLM-005 readout のスコープ依存 | — | **supported**（新規） | 全体 85.7%/57.1% vs 限定 100%/80% |
| CLM-006 著者メタデータ誤り | — | **supported**（新規） | arXiv abs ページと照合 |
| CLM-007 模擬実験の位置づけ | — | **supported**（新規） | 単一プロセス・逐次実行をコードで確認 |

**Hypotheses:**

- HYP-001（外部化メモリの優位）: **supported**。
- HYP-002（多数決の脆弱性）: **testing**（CLM-003 の格下げに伴う）。
- HYP-003（ローカル指標の再現性）: **falsified**（F-01）。

---

## 4. 是正措置

### 4.1 コード

| ファイル | 変更 |
| :--- | :--- |
| `scripts/validate_researchos.py` | 型・enum・items・pattern・ID 一意性・参照整合性・祖先検査を実装。`run_all_checks()` API を追加 |
| `schemas/hypothesis.json` | 新規。仮説の status と evidence 参照を検証 |
| `gitswarm/benchmarks/benchmark.py` | 実行・`--write`・`--check`・`_meta`・`per_seed` を実装。単一の真実源に |
| `gitswarm/artifacts/benchmark_matrix.json` | 実測値で再生成（SA 平均 4731.96、two_opt 4739.72） |
| `gitswarm/readout.py` | 既定を `gitswarm/` スコープに。`--all-paths` / `--since` / `--format json` / `--output` / `invalid_nominations` を追加 |
| `gitswarm/artifacts/readout_snapshot.json` | 新規。スコープ限定の固定スナップショット |
| `gitswarm/run_simulation.py` | 埋め込みコード再生成とハードコードを削除。`run_benchmarks()` を実行。`--dry-run` を追加 |
| `tests/test_integrity.py` | 新規。15テスト |
| `.github/workflows/verify-github-actions.yml` | 回帰テストとベンチマーク `--check` を追加 |

### 4.2 研究状態

| 種別 | 件数 | 主な変更 |
| :--- | ---: | :--- |
| Sources | 4 | SRC-001/003 の著者訂正、SRC-004（本リポジトリ）追加、DOI/照合日を追加 |
| Evidence | 14 | EVD-001/003/004 の引用訂正、EVD-005〜014（実測・メタデータ・コード監査）を追加 |
| Claims | 7 | CLM-003 を candidate に格下げ、CLM-004〜007 を追加 |
| Verifications | 21 | VER-005〜021（fail / warn / pass / falsified）を追加 |
| Hypotheses | 3 | HYP-002 を testing、HYP-003（再現性）を falsified で追加 |

### 4.3 レポート

- `reports/independent-verification-report.md`（本レポート）
- `verifications/independent_audit_log.md`（実行ログ）
- `reports/gitswarm-compatibility-verification.md` に訂正注記を追加
- `reports/researchos-pilot-synthesis-report.md` に訂正注記と出典著者の修正を追加
- `reports/experiment-summary-and-walkthrough.md` に訂正注記を追加
- `README.md` に検証手順を追加

---

## 5. 是正後の再検証結果

```
============================================================
 ResearchOS Core Deterministic Validation (hardened)
============================================================
Loaded: 4 Sources, 14 Evidence, 7 Claims, 21 Verifications, 3 Hypotheses
✓ Schema validation PASS (types, enums, required fields, items)
✓ ID uniqueness PASS
✓ Referential integrity PASS
✓ Git provenance Informed-By PASS (existence + ancestry)
============================================================
 ALL DETERMINISTIC CHECKS PASSED
============================================================
```

```
$ python3 -m unittest discover -s tests -v
Ran 15 tests in 1.225s
OK
```

```
$ python3 gitswarm/benchmarks/benchmark.py --check
PASS: benchmark artifact matches a fresh execution
```

```
$ python3 gitswarm/readout.py
Scope: paths=['gitswarm'] since=None
Commits scanned: 9
Total Swarm Contributions: 7
Candidate Solutions: 5
Vote Tallies: {'c66b253': 2}
Deterministic Winner: c66b253
- Contribution Reuse Rate: 100.0% (5/5)
- Negative Result Citation Rate: 100.0% (1/1)
- Winner Ancestry Coverage: 80.0%
```

---

## 6. 残存する未検証事項

1. **非同期・独立ワーカーの実運用**: 本リポジトリの実験は逐次ロールプレイであり、GitSwarm 論文の非同期性・独立コンテキスト・競合解決を実証していない。
2. **実規模**: 30都市TSP・5シード・7コミットは toy 規模。論文の ProgramBench / IMOProofBench / GPU 研究とは比較できない。
3. **外部再現**: 本監査は単一の監査者による再実行であり、第三者の独立再現ではない。
4. **arXiv の可変性**: メタデータと本文は 2026-10-19 時点。v2 以降で変わる可能性がある。
5. **70.1% の一般化**: NanoChat の最初の24時間・497/709 というスコープを外れて一般化すべきではない。
6. **CLM-003 の直接検証**: 「均質ワーカーの多数決が誤りを増幅する」ことを直接測る実験は、本リポジトリにも引用論文にもない。今後、同一モデル・同一プロンプトの多数決と、異種モデル／外部検証器の比較実験が必要。

---

## 7. 推奨事項

1. **検証可能な課題では検証性能で選ぶ。** GitSwarm 論文自身がそうしており、多数決はフォールバックに留める。
2. **すべての定量主張に「スコープ（コミット範囲・パス・シード）+ 実行者 + 再現コマンド」を付ける。** 本監査の `readout_snapshot.json` と `benchmark_matrix.json` の `_meta` が雛形。
3. **引用は逐語と要約を分離する。** `quote_type` を必須にし、要約には `paraphrase` を付ける。
4. **出典メタデータは機械的に照合する。** 今回は arXiv abs ページとの手動照合だったが、将来的には `title` / `authors[0]` / `arXiv ID` を自動照合する。
5. **成果物の再現性を CI で強制する。** `--check` と回帰テストを push ごとに実行する。
6. **「完全対応」のような強い結論は、実証した範囲を明記して弱める。** プロトコルレベル / 実運用レベル / 実規模レベルを分ける。

---

## 8. 付録: 実行コマンド

```bash
# 1. 前セッションの取り込み
git fetch origin arena/01673a58-researchos
git merge origin/arena/01673a58-researchos \
  -m "merge: 前セッション (arena/01673a58-researchos) の成果と研究状態を統合"

# 2. 決定論的検証
python3 scripts/validate_researchos.py

# 3. ベンチマークの再実行と照合
python3 -c "from gitswarm.benchmarks.benchmark import run_benchmarks; print(run_benchmarks())"
python3 gitswarm/benchmarks/benchmark.py --check

# 4. readout の2スコープ比較
python3 gitswarm/readout.py
python3 gitswarm/readout.py --all-paths

# 5. 回帰テスト
python3 -m unittest discover -s tests -v
```

---

## 9. 結論

前セッションの**文献調査としての結論は概ね妥当**である。Stateless Harness と Git による推論の累積は、一次資料で支持される。役割分離と `Informed-By` のプロトコルも機能している。

しかし、**ローカル模擬実験の定量成果物は信頼できず、出典メタデータには事実誤認があった**。本監査はそれらを是正し、再発を防ぐテストと CI を追加した。

最も重要な教訓は、ResearchOS 自身が掲げる原則の通り、**「多数決や自己申告ではなく、一次資料と再実行に接地する」**ことである。今回の監査で、その原則が実際に機能することを確認した。

---

*本レポートは `Auditor-01` による独立検証の記録である。履歴コミットは書き換えていない。数値はすべて 2026-10-19 時点の再実行結果に基づく。*
