# 除外した台帳レコード（2026-10-20）

- 作成日：2026-10-20
- 判断：**人間の指示により除外**
- 方針：`main` に残すのは「`main` から再検証できるもの」だけにする（README の「再実行できるものだけを `main` に載せる」）
- 対象：参照先の成果物が `main` に存在しないため再検証できないレコード、および是正済みの欠陥を指すレコード
- 取得方法：これらは git 履歴から復元できる（除外コミットの1つ前を参照）。**本ファイルは内容の写しであり、権威のある記録は git 履歴である。**

除外しても監査の事実は消えない。2026-10-19 の監査が発見した
「手書きベンチマーク」「readout のスコープ依存」「単一プロセスの逐次ロールプレイ」は、
`docs/stagnation-analysis-2026-10-20.md` と `docs/minimal-core-and-ci.md` §1.2 が
由来と対処を記録しており、そちらが一次の記録である。

## claims

### CLM-004

**除外理由**：成果物は 2026-10-20 に実行値で再生成済み（benchmark.py --check PASS）。主張は是正前の状態を指し、現ツリーには当てはまらない。根拠 EVD-005 も是正前にしか存在しない数値を引用する。

```json
{
  "claim_id": "CLM-004",
  "statement": "本リポジトリにコミットされた gitswarm/artifacts/benchmark_matrix.json は、同一コード・同一シードから再計算した値と一致せず、Worker-05 の「5シード比較ベンチマークを実行した」という主張は再現できない。",
  "evidence_ids": [
    "EVD-005",
    "EVD-012"
  ],
  "counterclaim_ids": [],
  "status": "supported",
  "scope": "本リポジトリの GitSwarm 模擬実験",
  "limitations": "Python 3.11.2、seeds=42/100/777/999/2026、random_iterations=500 で再実行。浮動小数点誤差の範囲を超える差異（SA平均で7.3%）。",
  "correction_note": "2026-10-20 の訂正：本主張は是正前の状態を記述した歴史的記録である。同日 gitswarm/artifacts/benchmark_matrix.json は実行値で再生成され、benchmark.py --check は現在 PASS する。したがって本主張は「現時点の main のツリーについては成立しない」。EVD-005 が引用する committed 値はツリー上に現存しない。台帳に時点・失効を表す字段がないため本文注記で対応する。"
}
```

### CLM-005

**除外理由**：再現に必要な worker コミット群（[Worker-01]/[Worker-02]）が main の履歴に存在しない。readout のパス依存性という一般的主張は妥当だが、main からは再検証できない。

```json
{
  "claim_id": "CLM-005",
  "statement": "gitswarm/readout.py の集計値はコミット範囲に依存し、リポジトリ全体を走査すると state/ の ResearchOS 役割コミット（[Worker-01]/[Worker-02]）を混入させ、報告済みの累積推論指標を変化させる。",
  "evidence_ids": [
    "EVD-006"
  ],
  "counterclaim_ids": [],
  "status": "supported",
  "scope": "本リポジトリの GitSwarm readout",
  "limitations": "gitswarm/ にパスを限定すると 7 worker commits / 5 candidates / reuse 100% / negative 100% / ancestry 80% で再現する。",
  "correction_note": "2026-10-20 の注記：本主張の再現に必要な worker コミット群（[Worker-01]/[Worker-02]）は main の履歴に存在しない（最小コア抽出時に除外、docs/minimal-core-and-ci.md §1.2）。したがって limitations に記載された数値は main からは再現できず、古い履歴からのみ検証可能である。readout のパス依存性という一般的主張の妥当性は変わらない。"
}
```

### CLM-007

**除外理由**：根拠 EVD-014 が参照する gitswarm/run_simulation.py が main に存在しない。main からは再検証できない。

```json
{
  "claim_id": "CLM-007",
  "statement": "本リポジトリの GitSwarm 模擬実験は単一エージェントが逐次的に役割を演じるものであり、GitSwarm 論文が前提とする非同期・独立コンテキストのワーカー群の実運用を実証したものではない。",
  "evidence_ids": [
    "EVD-014",
    "EVD-005"
  ],
  "counterclaim_ids": [],
  "status": "supported",
  "scope": "Arena.ai × GitHub 上での GitSwarm 運用可能性評価",
  "limitations": "プロトコルとコミット構造の再現性は示すが、並行性・独立コンテキスト・実規模の探索は未検証。",
  "correction_note": "2026-10-20 の注記：根拠 EVD-014 が参照する gitswarm/run_simulation.py は main から除外された（docs/minimal-core-and-ci.md §1.2）。したがって本主張は main からは再検証できない。結論（模擬実験が単一プロセスの逐次ロールプレイであること）はCLM-004 と同じ 2026-10-19 の監査事実であり、 histories として保持する。"
}
```

## evidence

### EVD-005

**除外理由**：committed 列の値（greedy=5320.14 等）は現ツリーに存在しない。現在のアーティファクトは recomputed 列と一致する。

```json
{
  "evidence_id": "EVD-005",
  "source_id": "SRC-004",
  "section_or_page": "gitswarm/artifacts/benchmark_matrix.json vs gitswarm/benchmarks/benchmark.py",
  "excerpt": "committed mean: greedy=5320.14, random=13150.80, two_opt=4792.40, simulated_annealing=4410.25; recomputed mean (Python 3.11.2, seeds 42/100/777/999/2026, random_iterations=500): greedy=5521.41, random=12279.86, two_opt=4739.72, simulated_annealing=4731.96.",
  "quote_type": "measurement",
  "interpretation": "コミット済みベンチマーク成果物は同一コード・同一シードから再現できない。特に SA の平均は 7.3% 楽観的で、two_opt との差は 0.16% に過ぎない。",
  "confidence": "high",
  "data_points": {
    "committed": {
      "greedy": 5320.14,
      "random": 13150.8,
      "two_opt": 4792.4,
      "simulated_annealing": 4410.25
    },
    "recomputed": {
      "greedy": 5521.41,
      "random": 12279.86,
      "two_opt": 4739.72,
      "simulated_annealing": 4731.96
    },
    "per_seed_actual": {
      "42": {
        "greedy": 5057.938,
        "random": 12454.649,
        "two_opt": 4584.578,
        "simulated_annealing": 4551.257
      },
      "100": {
        "greedy": 5039.797,
        "random": 11773.873,
        "two_opt": 4401.48,
        "simulated_annealing": 4396.027
      },
      "777": {
        "greedy": 6296.501,
        "random": 13337.465,
        "two_opt": 5264.448,
        "simulated_annealing": 5264.448
      },
      "999": {
        "greedy": 5688.167,
        "random": 12252.032,
        "two_opt": 4863.18,
        "simulated_annealing": 4863.18
      },
      "2026": {
        "greedy": 5524.627,
        "random": 11581.285,
        "two_opt": 4584.903,
        "simulated_annealing": 4584.903
      }
    }
  },
  "correction_note": "2026-10-20 の訂正：excerpt の \"committed\" 列（greedy=5320.14, random=13150.80, two_opt=4792.40, simulated_annealing=4410.25）は是正前にコミットされていた値であり、現在の gitswarm/artifacts/benchmark_matrix.json には存在しない。同アーティファクトは 2026-10-20 に実行値で再生成され、現在の値は EVD-005 の \"recomputed\" 列と一致する（greedy=5521.41 等、benchmark.py --check が PASS）。したがって本レコードは「過去にそうだった」ことを示す証拠であり、committed 列は現ツリーから再取得できない。"
}
```

### EVD-006

**除外理由**：unscoped/path-scoped の比較対象である worker コミットが main に存在しない。

```json
{
  "evidence_id": "EVD-006",
  "source_id": "SRC-004",
  "section_or_page": "gitswarm/readout.py (unscoped vs path-scoped)",
  "excerpt": "unscoped: 9 worker commits, 7 candidates, reuse 85.7%, negative reuse 100.0%, winner ancestry 57.1%; path-scoped to gitswarm/: 7 worker commits, 5 candidates, reuse 100.0%, negative reuse 100.0%, winner ancestry 80.0%.",
  "quote_type": "measurement",
  "interpretation": "readout は履歴全体を走査するため、state/ の ResearchOS 役割コミット [Worker-01]/[Worker-02] を混入させ、報告済み指標を変化させる。指標はコミット範囲に依存する。",
  "confidence": "high"
}
```

### EVD-012

**除外理由**：gitswarm/run_simulation.py（コミット 8763d08）は main から除外済み。

```json
{
  "evidence_id": "EVD-012",
  "source_id": "SRC-004",
  "section_or_page": "gitswarm/run_simulation.py, Worker-05 block at 8763d08",
  "excerpt": "The Worker-05 block defines benchmark_code and writes gitswarm/benchmarks/benchmark.py, but then assigns benchmark_summary = {...} with literal numbers and writes it to benchmark_matrix.json. run_benchmarks() is never called. The commit body nevertheless states 'Executed multi-seed verification benchmark across 5 independent problem instances.'",
  "quote_type": "code_inspection",
  "interpretation": "検証ワーカーの実行主張はコードと一致しない。benchmark_matrix.json は実行結果ではなく手書き値である。",
  "confidence": "high",
  "correction_note": "2026-10-20 の注記：参照先のファイルは最小コア抽出（docs/minimal-core-and-ci.md §1.2）により main から除外された。コミット 8763d08 は GitHub 上に現存するが、当該ファイルは main のツリーに存在しないため、本レコードは main からは再検証できない（古い履歴からのみ検証可能）。記述内容の歴史的正確性は変更していない。"
}
```

### EVD-013

**除外理由**：scripts/validate_researchos.py（コミット 8763d08）は main から除外済み。

```json
{
  "evidence_id": "EVD-013",
  "source_id": "SRC-004",
  "section_or_page": "scripts/validate_researchos.py at 8763d08; negative tests",
  "excerpt": "validate_schema() only checks that required keys are present; it does not check types, enums, or array item types. A record with confidence='banana' and year='2026' passes. validate_git_provenance() checks that the cited prefix exists somewhere in git log, not that it is an ancestor of the citing commit.",
  "quote_type": "code_inspection",
  "interpretation": "『スキーマ検査 PASS』は型・列挙・参照祖先の正しさを保証しない。",
  "confidence": "high",
  "correction_note": "2026-10-20 の注記：参照先のファイルは最小コア抽出（docs/minimal-core-and-ci.md §1.2）により main から除外された。コミット 8763d08 は GitHub 上に現存するが、当該ファイルは main のツリーに存在しないため、本レコードは main からは再検証できない（古い履歴からのみ検証可能）。記述内容の歴史的正確性は変更していない。",
  "scope_note": "歴史的監査記録として保持する。対象の scripts/validate_researchos.py は main から除外済みであり、指摘された欠陥（型・列挙・参照祖先を検査しない）は現在の scripts/validate_state.py には当てはまらない（同検証器は型・enum・配列要素型・参照整合性を検査する）。したがって本レコードはいずれの主張にも紐付けない。除外の経緯は docs/minimal-core-and-ci.md §1.2。"
}
```

### EVD-014

**除外理由**：gitswarm/run_simulation.py（コミット 8763d08）は main から除外済み。

```json
{
  "evidence_id": "EVD-014",
  "source_id": "SRC-004",
  "section_or_page": "gitswarm/run_simulation.py (main) at 8763d08",
  "excerpt": "All seven worker commits are created by commit_as_worker() calls inside a single main() process, in a fixed order, with only GIT_AUTHOR_NAME/EMAIL changed per worker. There is no concurrent execution, no separate session, and no independent worker context.",
  "quote_type": "code_inspection",
  "interpretation": "『7つの独立ワーカーエピソード』は単一プロセス内の逐次ロールプレイであり、非同期・独立コンテキストの実証ではない。",
  "confidence": "high",
  "correction_note": "2026-10-20 の注記：参照先のファイルは最小コア抽出（docs/minimal-core-and-ci.md §1.2）により main から除外された。コミット 8763d08 は GitHub 上に現存するが、当該ファイルは main のツリーに存在しないため、本レコードは main からは再検証できない（古い履歴からのみ検証可能）。記述内容の歴史的正確性は変更していない。"
}
```

## verifications

### VER-008

**除外理由**：対象 CLM-004 の除外に伴う。

```json
{
  "verification_id": "VER-008",
  "target_id": "CLM-004",
  "verifier_type": "deterministic",
  "result": "pass",
  "rationale": "Re-executing gitswarm/benchmarks/benchmark.py with the committed solvers and seeds produces means that differ from the committed artifact by 1.1%-7.3%. The committed greedy/random/two_opt minima equal seed-42 single-run values (random at 1000 iterations) rather than 5-seed minima; the committed SA min (4258.86) matches no seed. The discrepancy is reproducible and exceeds floating-point tolerance.",
  "suggested_actions": [
    "Regenerate the artifact from execution (done).",
    "Add a CI drift check (done)."
  ]
}
```

### VER-009

**除外理由**：対象 CLM-005 の除外に伴う。

```json
{
  "verification_id": "VER-009",
  "target_id": "CLM-005",
  "verifier_type": "deterministic",
  "result": "pass",
  "rationale": "Unscoped readout reports 9 worker commits and 85.7%/57.1% metrics; path-scoped to gitswarm/ it reports 7 worker commits and 100%/100%/80%. The difference is caused by ResearchOS [Worker-01]/[Worker-02] commits in state/.",
  "suggested_actions": [
    "Default readout to gitswarm/ path scope (done).",
    "Record scope in the output (done)."
  ]
}
```

### VER-014

**除外理由**：対象 CLM-007 の除外に伴う。

```json
{
  "verification_id": "VER-014",
  "target_id": "CLM-007",
  "verifier_type": "deterministic",
  "result": "pass",
  "rationale": "gitswarm/run_simulation.py creates all seven worker commits sequentially in one process; there is no concurrency or independent context. The claim that the experiment demonstrates asynchronous independent workers is therefore not supported.",
  "suggested_actions": [
    "Describe the experiment as a protocol-level simulation, not a production swarm."
  ],
  "correction_note": "2026-10-20 の注記：参照先のファイルは最小コア抽出（docs/minimal-core-and-ci.md §1.2）により main から除外された。コミット 8763d08 は GitHub 上に現存するが、当該ファイルは main のツリーに存在しないため、本レコードは main からは再検証できない（古い履歴からのみ検証可能）。記述内容の歴史的正確性は変更していない。"
}
```

### VER-016

**除外理由**：対象 HYP-003 の除外に伴う。

```json
{
  "verification_id": "VER-016",
  "target_id": "HYP-003",
  "verifier_type": "deterministic",
  "result": "falsified",
  "rationale": "The committed benchmark artifact is not reproducible from the committed code and seeds (CLM-004). HYP-003 is therefore falsified.",
  "suggested_actions": [
    "Keep the regenerated artifact and CI drift check."
  ]
}
```

### VER-20261020-35a8

**除外理由**：対象 CLM-004 の除外に伴う。

```json
{
  "verification_id": "VER-20261020-35a8",
  "target_id": "CLM-004",
  "verifier_type": "deterministic",
  "result": "warn",
  "rationale": "2026-10-20 時点で gitswarm/artifacts/benchmark_matrix.json は実行値で再生成済みであり、benchmark.py --check は PASS する。したがって「コミット済み成果物が再現できない」という本主張は現在のツリーには当てはまらない。EVD-005 の committed 列は現ツリーに存在しない数値を引用している。是正済みの欠陥を現在形の主張として残さないため注記を追加した（status は歴史的事実として supported を維持）。",
  "suggested_actions": [
    "台帳に時点・失効を表す字段を導入し、是正済みの欠陥を構造的に表現できるようにする。"
  ]
}
```

### VER-20261020-0d06

**除外理由**：対象 CLM-005 の除外に伴う。

```json
{
  "verification_id": "VER-20261020-0d06",
  "target_id": "CLM-005",
  "verifier_type": "deterministic",
  "result": "warn",
  "rationale": "本主張の再現に必要な worker コミット群は main の履歴に存在しない（最小コア抽出で除外）。limitations の数値は main から再現できない。readout のパス依存性という一般的主張は変わらないが、「再実行できるものだけを main に載せる」という方針とは矛盾した状態で残っている。",
  "suggested_actions": [
    "CLM-004/005/007 の扱い（履歴からのみ検証可能な主張を main に残すか）を判断する。"
  ]
}
```

### VER-20261020-4dae

**除外理由**：対象 CLM-007 の除外に伴う。

```json
{
  "verification_id": "VER-20261020-4dae",
  "target_id": "CLM-007",
  "verifier_type": "deterministic",
  "result": "warn",
  "rationale": "根拠 EVD-014 が参照する gitswarm/run_simulation.py は main から除外済みであり、本主張は main から再検証できない。結論自体（模擬実験が単一プロセスの逐次ロールプレイであること）は 2026-10-19 の監査事実として保持する。",
  "suggested_actions": []
}
```

## hypotheses

### HYP-003

**除外理由**：根拠 EVD-005・EVD-012 の除外に伴う。なお本仮説の棄却は是正前のアーティファクトに対するものであり、現在の benchmark は再現可能である。

```json
{
  "hypothesis_id": "HYP-003",
  "statement": "本リポジトリの GitSwarm 模擬実験の定量指標は、同一コード・同一シードで再現可能である。",
  "subtasks": [
    "TASK.md §4: 機械的検証（再実行による再現性）"
  ],
  "status": "falsified",
  "evidence_ids": [
    "EVD-005",
    "EVD-012"
  ],
  "notes": "benchmark_matrix.json は実行値ではなく手書き値だった。再生成と CI ドリフト検査で是正。2026-10-20 の注記：本仮説の棄却は是正前のアーティファクトに対するものである。現在の gitswarm/artifacts/benchmark_matrix.json は実行値で再生成され、benchmark.py --check は PASS する。すなわち「定量指標が再現可能である」という命題は現在のツリーでは成立しており、HYP-003 は歴史的な棄却記録として扱う。"
}
```
