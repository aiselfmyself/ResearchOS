# 次段階3施策のワーカー割当プロンプト（2026-10-21）

## この文書の目的

2026-10-21 の実用性評価で挙げた3つのボトルネックを進めるための、**新しい Arena チャットに貼り付けて開始できる**プロンプト集である。

- **施策S（Shard）**：台帳のシャーディング＋和集合マージで、統合役ボトルネックと末尾追記のテキスト衝突を解消する
- **施策R（Relation）**：HYP–EVD 関係表（SHELDON 読解 `contributions/2026-10-21_sheldon_reading.md` §5 の提案）を導入し、台帳を「証拠倉庫」から「仮説サイクルを回せる構造」にする
- **施策X（eXperiment）**：単一ワーカー対複数ワーカーのコスト・誤り率を同条件で比較し、「複数ワーカーは得か」を初めて測る

各プロンプトは単独で完結するように書いてある（前提知識を要求しない）。`《...》` は貼り付ける前に置き換える箇所である。

## 実行順序と決定ゲート

3施策は並行してよいが、**`scripts/validate_state.py` と `scripts/new_id.py` を変更するワーカー（R1 と S3）は同時実行しない**（共有ファイルの競合を避けるため、先にマージされた方を基準にする）。

| Wave | ワーカー | 前提 |
|---|---|---|
| 0（今すぐ並行可） | S1 設計調査、R1 関係台帳の実装、X1 実験設計 | なし |
| 決定ゲート D1 | 人間が S1 の推奨案（シャーディング方式）を採否 | S1 完了後 |
| 決定ゲート D2 | 人間が X1 の実験設計・判定規則を承認 | X1 完了後 |
| 1 | S2 和集合マージ道具、R2 gap_scan、X2 採点道具 | S2 は D1 不要（どの方式でも使う）。R2 は R1 マージ後。X2 は D2 後 |
| 2 | S3 シャーディング移行、R3-A〜E backfill 候補（5並行可）、X3 実行アーム群 | S3 は D1＋S2 後、かつ R1 と非同時。R3 は R1 後。X3 は X2 後 |
| 3（統合） | R4 関係台帳への投入、X4 採点・結果統合 | R4 は人間の承認後に台帳投入。X4 は X3 の全 PR が揃った後 |

## 進捗記録（統合役が記入する）

| ワーカー | PR | 状態 |
|---|---|---|
| S1 / S2 / S3 | #52 / #54 / #57（後続整理 #62） | いずれもマージ済み。台帳は凍結ベース＋シャードの統合ビューへ移行 |
| R1 / R2 / R3-A〜E / R4 | #51 / #56 / #63（R3 は ALL として統合）/ #65 | いずれもマージ済み。R4 は人間承認後に REL 235行・新 HYP 4件・`observation_key` 注釈30件を投入 |
| X1 / X2 / X3-S / X3-P1 / X3-P2 / X3-P3 / X4 | #53 / #55 / #58 / #59 / #61 / #64 / #66 | いずれもマージ済み。X4 は開始条件の不一致等により参考報告。実験中に必要となった書誌スナップショット追加は #60 |

### 完了後の運用決定（2026-10-21）

- 施策S：方式B（凍結ベース＋セッション別シャード＋統合ビュー）を採用し、実装済み。
- 施策R：R4 の承認事項を実施し、関係台帳を投入済み。
- 施策X：人間が、**抽出型タスクは単独ワーカーを既定とする**ことを決定した。正本は [`docs/extraction-single-default-2026-10-21.md`](./extraction-single-default-2026-10-21.md)。これは同一項目集合を速度目的で内部分割しないという決定であり、独立した複数タスクを各1ワーカーで並行に進めることまで禁じるものではない。

## 全ワーカー共通の注意（各プロンプト内にも埋め込んである）

- 自分の `arena/*` ブランチでだけ作業する。他セッションのブランチ・ファイルは直さない。
- 実測値を書くときは、実際に実行したコマンドと出力を根拠にする。実行していないことを「実行した」と書かない。
- 成果物は PR にする。PR 本文に「やったこと／やっていないこと／検証コマンドの実測結果」を書く。
- マージ可否はプロンプトごとの指示に従う（設計判断・台帳投入・ゲート意味論の変更を含む PR は自己マージしない）。
- 破壊的操作（ブランチ削除、`--force` push、台帳レコードの削除・書き換え、CI 定義の変更）はしない。必要なら提案として人間に戻す。

---

# 施策S：台帳シャーディング＋和集合マージ

背景：PR #49（2026-10-21）で台帳追記は全セッションに解放されたが、同一ファイル末尾への同時追記によるテキスト衝突は未解決で、発生源は増えた（`docs/parallel-work-ownership.md` §2.1）。実際 PR #48/#49 のマージで末尾追記がコンフリクトし、人手で和集合解決した。この施策はそれを構造で解消する。

## ワーカー S1：シャーディング方式の設計調査（変更はしない）

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の設計調査ワーカーです。日本語で報告してください。

## DoD（完了の定義・この3行がすべて）
1. 台帳ファイル（state/*.jsonl と tests/fixtures/arxiv_metadata_snapshot.json）の全読み手・書き手を実測で列挙する。
2. シャーディング候補方式を評価表で比較し、推奨案1つと移行手順を提示する。
3. コード・台帳は変更しない。成果物は設計メモ1本だけ。

## 背景（前提知識として読むこと）
- 台帳 state/*.jsonl への追記は全セッションが承認なしで行える（docs/parallel-work-ownership.md §2.1）。しかし複数ブランチが同一ファイルの末尾に追記するとテキスト衝突が起き（実例：PR #48/#49 のマージ）、毎回統合役が人手で「ID単位の和集合」として解決している。
- 非連番ID（docs/record-id-scheme.md）はID衝突を解いたが、テキスト衝突は解いていない。※この節は S1 依頼時点（2026-10-21 午前）の前提である。テキスト衝突は同日の方式B移行で解消済み（`contributions/2026-10-21_ledger_sharding_migration.md` §4）。
- 開始時点の参考値（必ず自分で再測すること）：台帳は sources/evidence/claims/verifications/hypotheses の5ファイル、合計150行あまり。テストは tests/ 配下、CI ゲートは .github/workflows/core-check.yml を見ること。

## 最初にやること
1. 次を読む：docs/parallel-work-ownership.md §2.1、docs/record-id-scheme.md §4〜§5、docs/minimal-core-and-ci.md、scripts/validate_state.py の冒頭docstring。
2. grep で state/*.jsonl と tests/fixtures/arxiv_metadata_snapshot.json を読み書きする全コード（scripts/、tests/、gitswarm/、.github/workflows/）を洗い出し、ファイル名・行番号つきで表にする。validate_state.py、new_id.py、check_citations.py、check_memo_citations.py、check_memo_ledger_refs.py、check_doc_numbers.py（台帳件数を行数で数えている点に注意）を含めること。
3. 既存メモ（contributions/*.md）が "state/evidence.jsonl" 等のパスを本文で参照しており、検査7（scripts/check_memo_ledger_refs.py）がその存在をゲートしていることを確認する。台帳ファイルを消す・移す方式はこの検査をどう壊すかを評価に含める。

## 評価する候補方式（最低限この4つ。追加は可）
A. 1レコード1ファイル（state/<台帳>/<ID>.json）
B. シャードファイル方式（セッション／日付ごとの追記ファイル群＋正規化された統合ビュー）
C. 単一ファイル維持＋git 組み込み union マージドライバ（.gitattributes の merge=union）
D. 単一ファイル維持＋専用和集合マージツール（統合時のみ実行）
各方式を次の観点で評価する：(1) GitHub のサーバ側マージ（gh pr merge）で機能するか。**特に方式Cは GitHub がマージドライバを尊重するかを根拠つきで確認する。確認できない場合は「未確認」と書き、実証方法を提案する**。(2) 既存の読み手の変更規模。(3) レコードの喪失・重複・同一ID異内容を検出できるか。(4) 人間が diff を読めるか。(5) 取り消し（revert）の容易さ。(6) 台帳件数の機械検査（check_doc_numbers.py）への影響。

## 実験してよいこと・いけないこと
- /tmp 配下の使い捨て git リポジトリで末尾追記衝突を再現し、方式C等を試すことは可。結果はコマンドと出力つきで記録する。
- 本リポジトリのコード・台帳・既存文書の変更、テスト用 PR の作成は禁止。

## 成果物（この1ファイルのみ新規作成）
contributions/《YYYY-MM-DD》_ledger_sharding_design.md
構成：結論（推奨案）→ 読み手・書き手の実測一覧 → 方式比較表 → 合成実験の結果 → 推奨案の移行手順（後方互換の順序つき）→ 後続ワーカー（S2/S3）の担当ファイル割当案 → 未確認事項。

## 検証とPR
次を実行し、結果を成果物末尾と PR 本文に実測で書くこと：
  python3 -m unittest discover -s tests
  python3 gitswarm/benchmarks/benchmark.py --check
  python3 gitswarm/readout_sim.py --check
  python3 scripts/validate_state.py
  python3 scripts/check_citations.py
  python3 scripts/check_memo_citations.py
  python3 scripts/check_memo_ledger_refs.py
  python3 scripts/check_doc_numbers.py
コミット前に git fetch origin ＜自分のブランチ＞ を行い、ブランチ巻き戻りがないか docs/parallel-session-playbook-2026-10-20.md §2 の手順で確認する。PR を作成し、CI が緑でコンフリクトがなければ自分でマージしてよい（事例メモのみの変更のため。docs/autonomous-merge-policy-2026-10-21.md §2）。
```

## ワーカー S2：和集合マージツールの実装

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の実装ワーカーです。日本語で報告してください。

## DoD
1. JSONL 台帳の3方向（base/ours/theirs）ID単位和集合マージを行う決定的ツール scripts/merge_ledgers.py が動く。
2. 同一ID・異内容は黙って解決せず、必ず非ゼロ終了で報告する。
3. 自分のテストファイルで回帰を守り、全ゲートが緑。

## 背景
台帳 state/*.jsonl は複数ブランチで末尾追記され、マージ時にテキスト衝突する。統合役は現在「ID単位の和集合」で人手解決している（PR #49 の本文参照）。これを機械化する。S1 の設計メモ（contributions/ の ledger_sharding_design）がある場合は先に読み、その推奨方式と矛盾しないインターフェースにする。S1 未完了でも本ツールはどの方式でも使うため着手してよい。

## 仕様
- CLI： python3 scripts/merge_ledgers.py --base BASE --ours OURS --theirs THEIRS --id-key KEY [--out OUT]
- 意味論：
  - レコードの同一性は --id-key の値で判定する。同一IDで内容一致 → 1件。同一IDで内容相違 → 競合として全件列挙し、終了コード1（--out は書かない）。
  - base にあって ours/theirs のどちらかで消えているレコードは「削除」として報告し、終了コード1（台帳は追記専用が前提。本ツールは削除を黙って通さない）。--allow-delete を明示した場合のみ削除を許可する。
  - 出力順序は決定的にする：base の元の順序を保持し、新規レコードは ID 昇順で後に続ける。未変更レコードは元の行文字列をそのまま出す（再シリアライズで diff を汚さない）。
  - 壊れた JSON 行・ID欠落は行番号つきで報告し、終了コード2。
- 位置づけは「道具」であり CI ゲートではない。.github/workflows/ には接続しない。
- 標準ライブラリのみ。既存 scripts/ のスタイル（docstringで WHY と非目標を書く）に従う。

## テスト（tests/test_merge_ledgers.py を新規作成）
最低限：両側追記の和集合、重複レコードの dedup、同一ID異内容の検出、削除の既定拒否と --allow-delete、順序の決定性（2回実行で同一出力）、壊れた JSON、空ファイル、レガシーID（EVD-001 形式）と新IDの混在。合成データのみで、本物の台帳には依存しない。

## 成果物（新規作成のみ。この3つ）
- scripts/merge_ledgers.py
- tests/test_merge_ledgers.py
- contributions/《YYYY-MM-DD》_ledger_merge_tool.md（設計判断・使い方・実台帳でのドライラン結果。実台帳の2ブランチ間差分に --out を /tmp に向けて適用し、件数が期待どおりか実測する）
既存ファイル、state/、README.md、CI 定義は変更しない。tests/test_minimal_core.py には触らない。

## 検証とPR
全ゲートを実行して実測結果を書く：
  python3 -m unittest discover -s tests
  python3 gitswarm/benchmarks/benchmark.py --check
  python3 gitswarm/readout_sim.py --check
  python3 scripts/validate_state.py
  python3 scripts/check_citations.py
  python3 scripts/check_memo_citations.py
  python3 scripts/check_memo_ledger_refs.py
  python3 scripts/check_doc_numbers.py
PR を作成する。CI が緑で MERGEABLE/CLEAN なら自分でマージしてよい（新規ファイルのみ・ゲートの意味論を変えないため）。
```

## ワーカー S3：シャーディング移行の実施（単独作業）

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の移行実施ワーカーです。日本語で報告してください。

## 前提
- 人間が S1 の推奨案 **方式B（凍結ベース＋セッション別シャード＋読み取り時統合ビュー）** を採用している（2026-10-21 に人間が決定。実施記録は `contributions/2026-10-21_ledger_sharding_migration.md`）。
- scripts/merge_ledgers.py（S2）が main に存在する。存在しなければ開始しない。
- scripts/validate_state.py / scripts/new_id.py を変更しうるため、このタスクは単独で実行する。他のコード変更 PR が開いている場合は人間に確認する。

## DoD
1. 移行前後で台帳レコードの集合（IDと内容）が完全一致する（移行スクリプトの出力で証明）。
2. 3つの独立したブランチが同時に台帳追記しても、テキスト衝突なしに順次マージできる（合成実験か実ブランチで実証）。
3. 全ゲートが緑。取り消しは単一の revert で可能。

## 絶対に守ること
- 既存レコードの ID・内容を変更しない。レコードの削除をしない（配置変更のみ）。
- contributions/*.md が参照するパス（state/*.jsonl 等）を壊さない。検査7（scripts/check_memo_ledger_refs.py）が緑のままであること。パスが変わる方式なら、互換のための残し方を S1 メモの手順どおりにし、逸脱する場合は理由を明記する。
- check_doc_numbers.py の台帳件数算出が移行後も正しいこと（同スクリプトの LEDGERS / actual_ledger_counts を見て必要な追随をする）。
- README.md は編集しない。必要な更新文案（台帳配置の記述など）は自分のメモに書き、統合役へ渡す。

## 手順
1. S1 メモの移行手順を読み、手順ごとに「実施すること／検証方法」を自分のメモ冒頭に転記する。
2. 移行前の全台帳レコードを ID→内容ハッシュで記録する（スクリプト出力）。
3. 移行を実施する（読み手：validate_state.py、new_id.py、check_citations.py、check_memo_ledger_refs.py、check_doc_numbers.py などの追随を含む。S1 の一覧をもとに漏れなく）。
4. 移行後のレコード集合を同じ方法で記録し、1件の差もないことを示す。
5. 並行追記の実証：合成リポジトリ上の再現でも、実リポジトリの使い捨てブランチ3本での実演でもよい（実リポジトリでやる場合、使い捨てブランチの削除は人間の承認事項なので、削除せず報告する）。

## 成果物
- 移行に必要なコード変更と tests/test_ledger_shards.py（新規。移行後の読み取り・件数・参照整合性の回帰）
- contributions/《YYYY-MM-DD》_ledger_sharding_migration.md（手順ごとの実施記録、移行前後の集合一致の実測、並行追記の実証結果、README 更新文案、残る未解決）

## 検証とPR
全ゲートを実行する：
  python3 -m unittest discover -s tests
  python3 gitswarm/benchmarks/benchmark.py --check
  python3 gitswarm/readout_sim.py --check
  python3 scripts/validate_state.py
  python3 scripts/check_citations.py
  python3 scripts/check_memo_citations.py
  python3 scripts/check_memo_ledger_refs.py
  python3 scripts/check_doc_numbers.py
PR を作成するが、**自分ではマージしない**（台帳配置の変更は全セッションに効くため、人間がマージする）。PR 本文に移行前後の一致証明の要点を書く。
```

---

# 施策R：HYP–EVD 関係表の導入

背景：SHELDON 読解 §5 が具体案まで提示済みである（新台帳 `relations.jsonl`、任意フィールド、決定論的 `gap_scan.py`、後方互換の backfill 手順 §5.7）。現在の台帳では EVD の93%（86件中80件）がどの HYP とも紐づかず、verdict の概念自体がない。この施策は同メモ §5.7 の手順1〜6を順に実施する。**VER の fail を verdict の refute に機械的に写してはならない**（§5.4 の禁止事項）。

## ワーカー R1：関係台帳のスキーマと検証器の実装

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の実装ワーカーです。日本語で報告してください。

## DoD
1. schemas/relation.json と空の state/relations.jsonl が存在し、validate_state.py が関係台帳のスキーマ・参照整合性を検査する。
2. 既存5台帳のレコードは1件も変更されず、全ゲートが移行前と同等に緑。
3. REL ID が scripts/new_id.py で採番でき、メモ内の REL 参照が検査7で解決検査される。

## 最初にやること
contributions/2026-10-21_sheldon_reading.md の §5.0〜§5.5 と §5.7（手順1〜3）を読む。本タスクはその手順1〜3の実施であり、設計の変更ではない。同メモの提案から逸脱する必要が生じたら、コードに反映せず自分のメモに「逸脱提案」として理由つきで書く。

## 実装内容
1. schemas/relation.json を新規作成：必須は relation_id / hypothesis_id / observation_id / verdict。verdict は enum ["support","refute","neutral","unresolved"]。任意フィールド provisional（boolean）、source_id、rationale、recorded_at を許可する（§5.1 の型に従う）。
2. state/relations.jsonl を新規作成（初期は空。レコード投入は別ワーカー R4 の仕事）。
3. scripts/validate_state.py への追加：
   - COLLECTIONS と ID_PREFIXES に relations / REL を追加。REL にレガシー連番は存在しない（LEGACY_MAX は増やさない。コードの扱いを読み、REL-001 形式が受理されないことをテストで確認）。
   - 参照整合性：relation.hypothesis_id → hypotheses、relation.observation_id → evidence、relation.source_id（あれば）→ sources。
   - ID_TOKEN_RE の接頭辞に REL を追加（check_memo_ledger_refs.py が import しているため両方に効く）。
4. scripts/new_id.py の PREFIXES / ID_KEYS に REL を追加。
5. 任意フィールドの追加（§5.2・§5.3・§5.5）。すべて optional で既存レコードを壊さない：
   - schemas/evidence.json：observation_key / observation_axis / observation_region（いずれも string）
   - schemas/hypothesis.json：hypothesis_region（string）、search_status（enum ["retained","setaside"]）、cooldown_rounds（integer）。**既存 status とは別フィールドにする**こと（理由は §5.3）。
   - schemas/claim.json：hypothesis_ids（string 配列）。validate_state.py に「あれば hypotheses への参照が解決すること」を追加。
6. tests/test_relations.py を新規作成（既存の tests/test_minimal_core.py の合成台帳スタイルを踏襲）：空の関係台帳が valid、正常な REL の受理、壊れた参照の3種の拒否、不正 verdict の拒否、REL-001 形式の拒否、任意フィールド追加後も既存レコード形状が valid、claim.hypothesis_ids の参照検査。

## やらないこと
- state/ の既存5台帳への変更（relations.jsonl の新規作成を除く）。verdict の投入（R4）。gap_scan の実装（R2）。README.md の編集（更新が必要なら文案をメモに書く。台帳件数の表示に relations を加えるかは統合役の判断）。
- VER から verdict を導出するコードを書かない（SHELDON メモ §5.4 の禁止）。

## 成果物
上記のコード変更と contributions/《YYYY-MM-DD》_relation_ledger_impl.md（実施した差分の一覧、§5.7 手順との対応、逸脱提案があればその内容、検証結果）。

## 検証とPR
全ゲートを実行して実測を書く：
  python3 -m unittest discover -s tests
  python3 gitswarm/benchmarks/benchmark.py --check
  python3 gitswarm/readout_sim.py --check
  python3 scripts/validate_state.py
  python3 scripts/check_citations.py
  python3 scripts/check_memo_citations.py
  python3 scripts/check_memo_ledger_refs.py
  python3 scripts/check_doc_numbers.py
PR を作成するが**自分ではマージしない**（検証器の意味論を変えるため、人間／統合役がマージする）。
```

## ワーカー R2：gap_scan 計測器の実装

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の実装ワーカーです。日本語で報告してください。

## 前提
ワーカ R1（関係台帳 state/relations.jsonl と検証器対応）が main にマージ済みであること。state/relations.jsonl が存在しなければ開始せず、その旨を報告する。

## DoD
1. scripts/gap_scan.py が台帳を読み、仮説カバレッジの穴を決定論的に報告する（台帳は変更しない）。
2. provisional 判定は fail-closed（裏付けのない観測を「確定的な反駁」として数えない）。
3. 現在の台帳に対する実行結果を実測としてメモに残す。

## 最初にやること
contributions/2026-10-21_sheldon_reading.md の §3.3〜§3.4（述語と provisional 導出）、§5.6（本ツールの提案）、§6.2〜§6.3（期待される出力の型）を読む。

## 仕様
- 出力（人間可読＋ --json）：
  - unassessed：REL が1件もない観測（EVD）の一覧と割合
  - unexplained：support の REL を持たない観測の一覧と割合
  - 仮説ごとの support / refute（非 provisional のみ）/ neutral / unresolved の件数
  - 観測領域（source_id）ごとの未評価件数（多い順）
- provisional(o) の導出：EVD の observation_key（なければ evidence_id 自身）が同じで source_id が異なる別 EVD が存在しない観測は provisional。REL レコードに provisional が明示されていればそれを優先する。
- これは計測器でありゲートではない：観測に穴があっても終了コードは0。終了コード非ゼロは使用法・入出力エラーのみ（scripts/measure_agreement.py の流儀に従う）。CI には接続しない。
- 標準ライブラリのみ。台帳の読み取りは scripts/validate_state.py の既存関数を再利用できるか確認し、重複実装を最小にする。

## テスト（tests/test_gap_scan.py を新規作成）
合成台帳で：REL 空のとき全件 unassessed/unexplained になること、support 付与で unexplained から外れること、同一 observation_key・異 source の EVD がある場合のみ非 provisional の refute が数えられること、領域別集計の順序、--json の形。

## 成果物（新規作成のみ）
- scripts/gap_scan.py、tests/test_gap_scan.py
- contributions/《YYYY-MM-DD》_gap_scan_baseline.md（現在の実台帳への実行結果。SHELDON メモ §6.3 の予測（全件未評価・refutation 0件）と一致するかの照合。R3 backfill 後の再測定の基準点として使う）
既存ファイル・state/ は変更しない。

## 検証とPR
全ゲートを実行して実測を書く（コマンド一覧は R1 プロンプトと同じ8つ）。CI が緑でコンフリクトがなければ自分でマージしてよい（新規の計測器はゲートの意味論を変えない）。
```

## ワーカー R3-A〜E：verdict 候補の裁定（backfill 候補作成）

5シャードが並行する。以下は共通テンプレートで、`《シャード記号》` と担当ソースを下表から置き換えて渡す。EVD 件数は2026-10-21 時点の参考値（実行時に再測すること）。

| シャード | 担当ソース（EVD内訳） | 目安 |
|---|---|---|
| A（中核3設計＋自リポジトリ） | SRC-001（4）/ SRC-002（6）/ SRC-003（5）/ SRC-004（3） | 18件 |
| B（Agoraと文脈） | SRC-20261020-f295 Agora（11）/ SRC-20261020-05de（3）/ SRC-20261020-787b（3）/ SRC-20261020-303f（4） | 21件 |
| C（ハーネスと評価） | SRC-20261020-875e（3）/ SRC-20261020-07a3（4）/ SRC-20261020-4cff（3）/ SRC-20261021-065a（2）/ SRC-20261021-fb4a・9a02・f186・a714・7176・4172（各1） | 18件 |
| D（自己改善と多エージェント） | SRC-20261021-a3a2 RRSI（8）/ SRC-20261021-2b88 Stellar Colosseum（6） | 14件 |
| E（仮説空間と科学エージェント） | SRC-20261021-2384 SHELDON（5）/ SRC-20261021-7419（5）/ SRC-20261021-8452（5） ※7419と8452は同一論文 The Agentic Scientist の重複登録に見えるため、観測の重なりをメモに記録する | 15件 |

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の証拠裁定ワーカー（シャード《記号》）です。日本語で報告してください。

## 前提
関係台帳のスキーマ（schemas/relation.json、ワーカ R1）が main にあること。なければ開始せず報告する。

## DoD
1. 担当ソース配下の全 EVD について、既存 HYP との verdict 候補（support/refute/neutral/unresolved）を機械可読な候補JSONに記録する。
2. 既存 HYP で説明できない観測の集まりがあれば、新仮説候補を「反証条件」つきで起草する。
3. state/ には書かない（候補の提示まで。台帳投入は統合役 R4 が人間の承認後に行う）。

## 担当範囲
《ここにシャード表の担当行を貼る》
開始時に state/evidence.jsonl を読み、担当 source_id の EVD 一覧を自分で確定する（件数が表と違えば実測を正とする）。担当外の EVD には裁定しない。

## 進め方
1. state/hypotheses.jsonl の全 HYP（開始時点の参考：HYP-001「外部化された構造化メモリを持つエージェントは単一セッションの巨大プロンプトより累積探索効率と再現性で優れる」、HYP-002「同質ワーカーの多数決は共通モード障害に脆弱」。必ず台帳で現行の文面を再確認する）を読む。
2. 担当 EVD ごとに excerpt と interpretation を読み、各 HYP に対する verdict を1行理由つきで付ける。根拠は原則 EVD の excerpt のみとし、解釈が要る判断は confidence を下げ、その旨を書く。原典メモ（contributions/ の各読解レポート）を開いた場合は basis に明示する。
3. 判断できない場合は推測で support に寄せず unresolved とする。台帳 VER が fail であることを refute の根拠にしない（VER の fail は引用の転写誤りの検出であり、仮説への反駁ではない。contributions/2026-10-21_sheldon_reading.md §5.4）。
4. 同一所見を指すと思われる EVD 群（別ソースで同じ事実を述べる等）があれば、observation_key の束ね案として提案する（provisional 導出の材料になる）。
5. どの既存 HYP にも紐づかない観測が複数まとまっていれば、新仮説候補（仮ラベル NEW-《記号》1, 2, ...。これは台帳IDではない）を起草する：主張文、支持する EVD、反証条件（どんな観測が得られればこの仮説を棄却するか）、次に集めるべき観測。

## 成果物（この2ファイルのみ新規作成）
- contributions/《YYYY-MM-DD》_relation_backfill_《記号》.json
  形式： {"shard":"《記号》","base_commit":"＜開始時の main HEAD＞","items":[{"evidence_id":"...","hypothesis_id":"HYP-001 または NEW-《記号》1","proposed_verdict":"support|refute|neutral|unresolved","rationale":"1行理由","basis":"excerpt|memo:<ファイル名>","confidence":"high|medium|low","observation_key_proposal":"任意"}], "new_hypothesis_candidates":[{"label":"NEW-《記号》1","statement":"...","falsification":"...","next_observations":"..."}]}
  担当 EVD は全件が最低1行を持つこと。
- contributions/《YYYY-MM-DD》_relation_backfill_《記号》.md
  裁定の要点、迷った判断の記録、新仮説候補の説明、担当 EVD の処理件数（実測コマンドつき）。

## 検証とPR
候補JSONの evidence_id / hypothesis_id がすべて台帳に実在することをスクリプトで照合し、結果をメモに書く。全ゲート（R1 プロンプトと同じ8つ）を実行する。PR を作り、CI が緑なら自分でマージしてよい（contributions の新規ファイルのみ）。
```

## ワーカー R4：関係台帳への統合投入（統合役）

> **2026-10-21 更新（追記先）**：台帳は凍結ベース＋セッション別シャードになった。
> REL レコードの追記先は `state/relations.jsonl` ではなく
> **`state/relations.d/<YYYY-MM-DD>-<12桁hex>.jsonl`**。`python3 scripts/new_ledger_shard.py relations --create`
> で作る（`docs/record-id-scheme.md` §2）。凍結ベースの `state/relations.jsonl` は書き換えない。
> 以下の本文に「state/relations.jsonl に追記」とある箇所は、この読み替えで実施する。

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の統合役ワーカーです。日本語で報告してください。

## 前提
R3 の候補（contributions/ の relation_backfill_*.json 群）が揃い、**人間が verdict の台帳投入を承認している**こと。承認が確認できなければ、投入せずに統合プレビュー（後述）までで止めて報告する。

## DoD
1. 承認された候補のみを REL レコードとして state/relations.jsonl に追記し、validate_state が緑。
2. gap_scan の前後比較で、未評価・未説明の割合がどう変わったかが実測で示される。
3. 採用しなかった候補と理由が残る（無言で捨てない）。

## 手順
1. 全シャードの候補JSONを読み、重複する (hypothesis_id, observation_id) ペアと、シャード間で食い違う verdict を洗い出す。食い違いは rationale を比べて裁定し、裁定理由をメモに書く。裁定できないものは unresolved として投入するか、投入しない（判断を記録）。
2. scripts/gap_scan.py を投入前に実行し基準値を記録する。
3. python3 scripts/new_id.py REL でレコードごとに ID を採番し（連番禁止）、state/relations.jsonl に追記のみする。既存レコードの書き換え・削除はしない。observation_key の束ね案が承認されている分は、該当 EVD への任意フィールド追記として扱い、変更した EVD 一覧をメモに残す（値の上書きはしない）。
4. 新仮説候補（NEW-*）は、そのまま HYP 登録しない。メモ内に一覧表（主張・反証条件・根拠 EVD）として提示し、登録は人間の承認後に別途行う。承認済みのものだけ new_id.py で HYP 採番して追記する。
5. gap_scan を投入後に実行し、前後比較表（unassessed/unexplained の件数と割合、仮説ごとの内訳）をメモに書く。
6. README.md は、あなたが人間から統合役に指定されている場合のみ、「現在の状態」節への relations 台帳の反映を行う（引用ブロックではなく現況節に。数値は実測で）。指定されていなければ更新文案をメモに書く。

## 成果物
- state/relations.jsonl への追記（承認分のみ）
- contributions/《YYYY-MM-DD》_relation_backfill_integration.md（投入件数、食い違いの裁定記録、不採用候補と理由、gap_scan 前後比較、新仮説候補一覧、次に集めるべき観測の提案）

## 検証とPR
全ゲート（R1 プロンプトと同じ8つ）を実行する。台帳が追記のみであることを git diff で確認し PR 本文に書く。PR を作成するが**自分ではマージしない**（verdict という推論結果を台帳に入れる操作のため、最終確認は人間が行う）。
```

---

# 施策X：単一ワーカー対複数ワーカーの同条件比較

背景：これまで「複数ワーカーは動く」ことは示したが、「単一より得か」は測っていない。注記：**実ワーカーでの `rho`/`c` の直接測定は意図的に凍結中**（`docs/parallel-experiment-2026-10-20.md` §6）であり、本施策はそれを再開するものではない。測るのはコスト・所要時間・誤り率であり、相関誤りの推定ではない。前回の並列実験の教訓（`contributions/2026-10-20_parallel_experiment_results.md` §3：自由選択項目の廃止、数え方の定義、文字列でなく意味で比較、不一致の内訳の必須併記）を設計に織り込むこと。

## ワーカー X1：比較実験の設計（実行はしない）

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の実験設計ワーカーです。日本語で報告してください。

## DoD
1. 単一アームと3並行アームが同一の項目集合を解く比較設計が、事前登録の形で文書化される（項目・配分・真値手順・主要評価指標・判定規則を含む）。
2. コスト記録の形式（セッションログJSON仕様）が定まる。
3. 本タスクでは実験を実行しない。設計文書1本のみ。

## 最初にやること
docs/parallel-experiment-2026-10-20.md（設計と凍結の条件 §6）、contributions/2026-10-20_parallel_experiment_results.md §3（測定の教訓4点）、scripts/measure_agreement.py の冒頭docstring、docs/literature-triage-2026-10-21.md と docs/literature-inventory-2026-10-19.jsonl（未読論文の候補）を読む。

## 設計に含めるもの
1. 研究問いを1文で：例「同一の抽出・照合タスク集合について、3分割＋統合は単独遂行と比べて壁時計を短縮するか、総コストと誤り率はどう変わるか」。
2. 対象タスク：本リポジトリの実際の作業型（論文からの項目抽出、または既存メモ claim の原典照合）から選び、まだ本リポジトリで読解されていない一次資料を対象にする。項目は答えが一意に定まるものだけ（数値・列挙・短文の逐語）。「いくつあるか」を問う項目には数え方の規則を必ず定義する。項目総数は誤りが多少なりとも観測できる規模として40〜60件を目安とし、前回の「正解可能8件」が不足だった経緯に触れる。項目はID・問い・回答の型・原典内の所在ヒント（答え自体は含めない）を設計文書に列挙する。
3. 配分：全項目を節・種類で層化して3つの部分集合に分け（難易度が偏らない配分方針を明記）、単一アームは全項目、並行アームは各1/3を担当する。
4. 同条件性：両アームとも同一の base コミットから開始。実行中は他アーム／他ワーカーのブランチと PR を見ないことを規約とし、汚染を防ぐ実行順序（全アームの出力が PR として固定されてから真値を作る）を定める。モデルの同一性は Arena 上では統制不能であることを限界として明記する。
5. 真値手順：全出力の固定後、統合役が一次資料から真値を確定する手順と、真値が定まらない項目の扱い（除外し理由を記録）。
6. 主要評価指標（事前に4つ以内に固定）：壁時計（最初のプロンプト投入から全 PR 着地まで、人間が記録）、セッション総時間の合計（セッションログの開始・終了時刻）、項目誤り率（真値確定項目に対する事実誤り。書式差は誤りに数えない分類を併用）、統合オーバーヘッド（統合役の工数・マージ競合件数）。トークン消費はセッション内から測れないため、代理指標（セッション時間、ツール呼び出し回数、出力文字数、読んだファイル一覧）で記録する方針と限界を書く。
7. セッションログJSON仕様： arm / worker / branch / base_commit / started_at_utc / finished_at_utc / tool_calls（数え方の規則）/ files_read / output_files / notes。
8. 判定規則：どの結果が出たら運用を変えるかの事前宣言。例「壁時計が30%以上短く、誤り率が悪化せず（差が数件以内）、総セッション時間が1.5倍以内なら、照合型タスクの既定を3分割にする」。数値は提案として書き、人間の承認（決定ゲートD2）で確定する。
9. 限界：試行は各アーム1回のパイロットであり統計的検定はしない（生件数と内訳で報告する）、人間の投入が直列ボトルネックになり壁時計に影響すること、rho の推定は目的でないこと。

## 成果物（この1ファイルのみ新規作成）
docs/single-vs-multi-experiment-《YYYY-MM-DD》.md
既存文書・コード・台帳は変更しない。

## 検証とPR
全ゲートを実行（R1 プロンプトと同じ8コマンド）。PR を作成し、CI が緑なら自分でマージしてよい（新規文書のみ）。
```

## ワーカー X2：採点・コスト集計ツールの実装

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の実装ワーカーです。日本語で報告してください。

## 前提
docs/single-vs-multi-experiment-*.md（ワーカ X1 の設計）が main にあり、人間が承認していること。設計の出力形式・セッションログ仕様に厳密に従う。設計と食い違う実装判断が要るときは、メモに理由を書く。

## DoD
1. scripts/score_extraction.py が、アーム出力JSON群＋真値JSON＋セッションログ群から、設計の主要評価指標を決定論的に集計する。
2. 不一致はすべて「事実誤り／書式差のみ／欠落／棄権」に分類候補つきで列挙される（生の一致率だけで終わらない）。
3. 合成データのテストで守られ、全ゲートが緑。

## 仕様
- 値の比較規則は scripts/measure_agreement.py の流儀に合わせる（数値は許容誤差内、文字列の空白圧縮と大小無視、型不一致は不一致、null/unknown は棄権）。再利用できる関数があれば import を検討し、できない場合は理由を docstring に書く。
- 出力：アームごと、ワーカーごとの 正解／事実誤り／書式差のみ／棄権／欠落 の件数、誤り率（分母の定義を明記）、セッション時間の合計、ツール呼び出し合計、項目レベルの不一致全件表。人間可読＋ --json。
- 計測器でありゲートではない（終了コード規則は measure_agreement.py に倣う）。CI 非接続。標準ライブラリのみ。

## 成果物（新規作成のみ）
- scripts/score_extraction.py、tests/test_score_extraction.py
- contributions/《YYYY-MM-DD》_scoring_tool.md（設計仕様への対応表、合成ミニケースでの動作例）
tests/test_minimal_core.py、既存 scripts/、state/ は変更しない。

## 検証とPR
全ゲートを実行（R1 プロンプトと同じ8つ）。CI が緑でコンフリクトがなければ自分でマージしてよい（新規計測器のみ）。
```

## ワーカー X3-S：単一アームの実行

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の実験実行ワーカー（単一アーム）です。日本語で報告してください。

## 位置づけ
docs/single-vs-multi-experiment-《日付》.md の設計による「単一ワーカー」条件です。あなたは設計文書の全項目を一人で実施します。同じ項目集合が別条件（3分割）でも実施されます。重要な規律：
- 他のアーム／他ワーカーのブランチ・PR・成果物を見ない（gh pr list 等で探さない）。自分のブランチと main だけを見る。
- 結果の良し悪しではなく、「普段どおり丁寧にやる」ことが比較の前提です。急いだり、手を抜いたりしない。

## 最初の行動（コスト記録）
作業開始の最初にシェルで date -u +%Y-%m-%dT%H:%M:%SZ を実行し開始時刻を控える。設計文書のセッションログ仕様に従い、ツール呼び出し回数を数え、読んだファイル・取得した一次資料を記録しておく（終了時にまとめる）。

## タスク
設計文書《パス》の項目表（全項目）について、指定された一次資料《URL・版》から値を抽出する。
- 回答の型は項目表の指定どおりにする（数値は数値で、文字列でごまかさない）。所在（節・表番号）を各項目に付ける。原典に無いものは推測せず null とし、理由をメモに書く。
- 「数える」項目は項目表の数え方規則に厳密に従う。

## 成果物（新規作成のみ）
- contributions/《YYYY-MM-DD》_svm_single.json（項目形式は設計文書の指定。最低限 {"arm":"single","base_commit":"...","items":[{"id":"...","value":...,"location":"...","confidence":"..."}], "session_log":{設計仕様の各欄＋finished_at_utc}}）
- contributions/《YYYY-MM-DD》_svm_single.md（実施報告。迷った項目・運用上の困難を正直に書く）
state/、既存メモ、コード、設計文書は変更しない。台帳登録が要ると思っても書かず、メモに提案する。

## 検証とPR
全ゲートを実行（R1 プロンプトと同じ8つ）。JSON の形が設計仕様に合うか自分で検査する。PR を作成し、CI が緑なら自分でマージしてよい（出力を固定する行為が実験手順の一部）。PR 本文に壁時計の手がかりとして PR の作成時刻が記録されることを意識し、追加の推敲コミットはしない（誤りに気づいても直さず、気づきはメモに書く。直すと測定が壊れる）。
```

## ワーカー X3-P《n》：並行アームの実行（n=1..3、テンプレート）

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の実験実行ワーカー（並行アーム P《n》／3）です。日本語で報告してください。

## 位置づけ
docs/single-vs-multi-experiment-《日付》.md の設計による「3分割」条件のうち、部分集合《部分集合名と項目ID範囲をここに貼る》だけを担当します。残りは他ワーカーが実施します。重要な規律：
- 他のアーム／他ワーカーのブランチ・PR・成果物を見ない。相談もしない。統合は統合役（X4）の仕事であり、あなたはしなくてよい。
- 担当外の項目は、答えが分かっても出力に含めない（測定の分母が壊れる）。

## 最初の行動（コスト記録）
作業開始の最初に date -u +%Y-%m-%dT%H:%M:%SZ を実行し開始時刻を控える。ツール呼び出し回数と読んだファイルを設計文書のセッションログ仕様で記録する。

## タスク
設計文書の項目表のうち担当部分集合について、一次資料《URL・版》から値を抽出する。要領は X3-S と同じ（型は指定どおり、所在を付ける、無ければ null、推測しない、数え方規則を守る）。

## 成果物（新規作成のみ）
- contributions/《YYYY-MM-DD》_svm_parallel_p《n》.json（形式は X3-S と同じ。arm は "parallel"、worker は "P《n》"。session_log を含める）
- contributions/《YYYY-MM-DD》_svm_parallel_p《n》.md（実施報告）
state/、既存メモ、コード、設計文書は変更しない。

## 検証とPR
全ゲートを実行（R1 プロンプトと同じ8つ）。PR を作成し、CI が緑なら自分でマージしてよい。誤りに気づいても提出後に直さない（気づきはメモに書く。測定を保つため）。
```

## ワーカー X4：真値確定と結果統合

```text
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の実験採点・統合ワーカーです。日本語で報告してください。

## 前提
X3-S と X3-P1〜P3 の出力（contributions/ の svm_single.json、svm_parallel_p*.json）がすべて PR として固定（マージ）済みであること。揃っていなければ開始せず、不足分を報告する。

## DoD
1. 一次資料から真値を確定し、両アームを同じ真値で採点する。
2. 設計文書の主要評価指標と判定規則に沿って結果が報告される（統計的有意性の主張はしない）。
3. 不一致は全件に「事実誤り／書式差のみ／欠落／棄権／項目側の問題」の内訳が付く。

## 手順
1. docs/single-vs-multi-experiment-*.md の項目表と真値手順を読む。一次資料《URL・版》を自分で取得して真値を確定し、真値JSON（出典位置つき）を作る。真値を作成する時点でアーム出力の「内容」は参照してよいが、真値はあくまで原典から決め、真値が定まらない項目は除外して理由を記録する。
2. python3 scripts/score_extraction.py（X2）で両アームを集計する。次に全不一致を1件ずつ目視分類する（前回実験の教訓：表面の不一致6件の内訳は書式差・取り違え・項目定義の不備であり、事実の食い違いは0件だった。生の一致率をそのまま結論に使わない）。
3. コストを集める：各出力JSONの session_log（開始・終了、ツール呼び出し等）、GitHub の PR 作成・マージ時刻と競合の有無（gh pr view 等、読み取りのみ）。人間の投入回数・壁時計は人間が《ここに人間が記録を貼る：両アームそれぞれ、プロンプト投入時刻と全PR着地時刻、介入回数》を根拠とする。貼られていなければ「未記録」とし、代理値の出所を明示する。
4. 設計文書の判定規則に照らし、「次からどちらの運用を既定にするか」への含意を、パイロット（各アーム1回）としての限界とともに述べる。凍結中の rho 推定には踏み込まない（相関誤りの推定は本実験の目的外。共通して間違った項目は件数だけ事実として列挙する）。
5. 実験運営自体の失敗（項目の問題、汚染の可能性、タイミング測定の欠落）を率直に記録する。

## 成果物（新規作成のみ）
- contributions/《YYYY-MM-DD》_svm_truth.json（真値と出典位置）
- contributions/《YYYY-MM-DD》_svm_results.md（真値確定の方法、指標の実測表、不一致の内訳、判定規則への照合、限界）
コード・state/ は変更しない。実験で得られた証拠を台帳に入れる提案があればメモに書く。

## 検証とPR
全ゲートを実行（R1 プロンプトと同じ8つ）。PR を作成し、CI が緑なら自分でマージしてよい。
```

---

# 統合役向けの割当メモ

- **衝突回避の要**：コードを書くワーカーは各々「新規ファイル＋自分のメモ」だけが原則。ただし **R1 と S3 は既存の中核ファイル（`validate_state.py`、`new_id.py`、`schemas/`、台帳配置）を変える**。両者は同時実行せず、先に人手マージされた方を基準に後者を開始する。
- **自己マージ可否の使い分け**：報告・候補・新規計測器の PR は自己マージ可（自律マージ方針§2）。設計上の分岐点（D1/D2）、台帳投入（R4）、台帳配置の変更（S3）、検証器の意味論変更（R1）は人間がマージする。
- **rho 凍結との関係**：施策Xは凍結中の rho/c 測定（監査 ID 17）の再開ではない。X 系ワーカーに相関誤りの推定を追加依頼しないこと。
- **施策間の相乗**：R3 の backfill 担当表は EVD 件数で割ってある。S3 の移行が先行・並行する場合は、R3 着手時の `main` の台帳配置に従うよう統合役が一言添える。
- **この文書の更新**：ワーカーが完了するたびに「進捗記録」表へ PR 番号を記入する（統合役の仕事）。プロンプト文面自体の改定は、実行中のワーカーに影響しない範囲でのみ行う。
