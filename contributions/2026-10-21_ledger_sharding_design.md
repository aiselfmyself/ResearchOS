# 台帳・書誌スナップショットのシャーディング設計調査

- 作成日：2026-10-21
- 調査対象：`state/*.jsonl` の研究5台帳と `tests/fixtures/arxiv_metadata_snapshot.json`
- 調査範囲：`scripts/`、`tests/`、`gitswarm/`、`.github/workflows/` の読取・書込経路、現行CI、既存メモのパス参照
- 制約：本調査ではコード、台帳、既存文書を変更していない。成果物は本ファイル1本のみ。

## 1. 結論（推奨案）

**方式B（不変の既存ファイルをベース・シャードとして残し、以後は一意なセッション／バッチ・シャードへ追加し、読み取り時に決定的な統合ビューを作る）を推奨する。** `state/*.jsonl` と arXiv スナップショットの両方に適用する。

実装時の具体像：

- 既存の5つのJSONLと `tests/fixtures/arxiv_metadata_snapshot.json` は**移動・削除せず、初期のベース・シャードとして凍結**する。既存パスを残すことが、検査7および台帳内のパス検査との後方互換の要件である。
- 新しい台帳レコードは、既存JSONLへ追記せず、台帳ごとのサイドカー置き場に**新しいファイル**として追加する。1つのセッション／作業バッチにつき1ファイルとし、ファイル名には日付だけでなく十分長いランダムな識別子を含める。既存シャードは再編集しない。
- スナップショットも既存JSONを凍結し、新規の書誌エントリを別のサイドカー・ファイルに置く。エントリの取得日・取得方法などの由来はシャード側に保持する。
- 読み手はベース＋サイドカーを読み、IDまたは arXiv ID で順序を安定化した**メモリ上の統合ビュー**を使う。統合ビューを追跡対象の単一JSONL/JSONとして再生成・コミットしない。コミットする集約ファイルを作ると、そのファイルが再び共有末尾追記の衝突点になる。
- 同一IDの重複は、内容が同じでも場所を報告して検査エラーにする。同じIDで内容が異なる場合も、どちらかを黙って選ばず、明示的なエラーにする。

方式Bを選ぶ理由は、別々の新規パスへの追加がGitHubの通常のファイル単位マージで共存でき、レコード単位に全履歴を分割する方式Aより既存154レコードの大量移設が不要だからである。さらに、現行JSONLとスナップショットのパスを物理的に残せる。これは「既存の全読者を変更せずに済む」という意味ではない。読者は必ず統合ビューを使うよう更新するが、既存パスを消したり改名したりする移行は避けられる。

このメモでは実装・移行は行わない。特に `merge=union` は導入しない。GitHubサーバーでの現行挙動をこのリポジトリのPRで実験しておらず、下記の公開根拠は非対応を示す一方で、直接の現行サーバー実験ではないためである。

判断の前提として、`docs/parallel-work-ownership.md` §2.1 は全セッションの台帳追記とID採番を許可し、既存レコードの削除・書換えには承認を求めている。`docs/record-id-scheme.md` §4–5 はID衝突とテキスト衝突を区別し、unionの導入を見送っている。`docs/minimal-core-and-ci.md` §2 と実際のworkflowは、8つの再実行可能なCIゲート（特にゲート4・5・7・8）を現状の検査線としている。本案は追記の許可を変えず、同じ書込み先を共有しない設計を比較する。

## 2. 読み手・書き手の実測一覧

### 2.1 現在のデータ量（本作業ツリーで再計測）

| ファイル／台帳 | 非空JSONLレコード／fixtureエントリ | 実測ファイル行数 |
|---|---:|---:|
| `state/sources.jsonl` | 23 | 23 |
| `state/evidence.jsonl` | 86 | 86 |
| `state/claims.jsonl` | 9 | 9 |
| `state/verifications.jsonl` | 34 | 34 |
| `state/hypotheses.jsonl` | 2 | 2 |
| **JSONL合計** | **154** | **154** |
| `tests/fixtures/arxiv_metadata_snapshot.json` | **22件（22個の異なる arXiv ID）** | **365** |

スナップショットは10,924バイト。台帳行数はすべて非空行数と一致した。開始時の参考値「150行あまり」と整合するが、計画時の数字ではなく上記の現物を使用する。

### 2.2 台帳ファイル（5ファイル）の読み手

| 読み手 | 対象 | 実測した読取箇所・役割 |
|---|---|---|
| `scripts/validate_state.py` | 5台帳すべて | `COLLECTIONS` が5パスを列挙（49–60行）、`load_jsonl` がUTF-8テキストを読みJSONLを解析（101–121行）、`run_all_checks` が全ファイルをスキーマ・ID一意性・参照整合性検査へ渡す（364–385行）。通常出力の件数も再読込して数える（389–404行）。 |
| `scripts/new_id.py` | PREFIXで選ばれた1台帳 | `PREFIXES` が対応表を持つ（33–47行）。`_existing_ids` が既存IDを読む（50–64行）、`main` が対象を決めて読み（105–110行）、採番IDは**標準出力へ表示するだけ**（112–115行）。台帳へ書き込まない。 |
| `scripts/check_citations.py` | `state/sources.jsonl` | デフォルトパスは43行、`load_ledger` が行単位で読む（74–85行）。オフライン照合の `main` は読み込んだ sources をスナップショットと照合する（255–266行）。 |
| `scripts/check_memo_ledger_refs.py` | 5台帳すべて | `validate_state.COLLECTIONS` を反復して各IDを読取・索引化する（89–105行、実読取98–104行）。 |
| `scripts/check_doc_numbers.py` | 5台帳すべて | 台帳名とファイルの対応表（81–87行）。`actual_ledger_counts` は各JSONLの**非空行数**を実測する（167–175行）。レコード件数ではなく行数を数えているため、シャード後は必ず変更が必要。 |
| `scripts/holdout_eval.py` | 5台帳すべて（間接） | `run_memo_ledger_refs` が `check_memo_ledger_refs.load_ledger_ids()` を呼ぶ（179–193行）。これはCIゲートではなく診断器だが、既定の全検査実行時に現行台帳を読む。 |
| `tests/test_minimal_core.py` | 5台帳すべて | 全台帳検証を実行（235–239行）。個別の実データ検査（242、258、275行）と、全台帳を走査するテスト（356–358、518–525行）もある。 |
| `tests/test_check_citations.py` | `state/sources.jsonl` | `SOURCES` の定義は34行。実台帳とfixtureを使う統合テスト（73–86行、特に80–82行）。異常系では一時ディレクトリ内の合成JSONLを読む。 |
| `tests/test_check_memo_ledger_refs.py` | 5台帳すべて（間接） | 実リポジトリ全体のスキャン（64–70行）が全台帳を索引化する。テスト用ID取得ヘルパーは該当台帳を直接読む（41–50行）。 |
| `tests/test_check_doc_numbers.py` | 5台帳すべて | 件数テストが各JSONLを直接読み、非空行数と `actual_ledger_counts` を比較する（76–82行）。 |
| `tests/test_holdout_eval.py` | 5台帳すべて（間接） | 実リポジトリの全検査器を評価するテスト（234–249、265–269行）が `holdout_eval.run_memo_ledger_refs` 経由で台帳索引を読む。 |
| `.github/workflows/core-check.yml` | 上記スクリプトをCIで実行 | `run:` は49–71行に8つ。台帳を直接パースするシェル処理はないが、ゲート4（59行）、ゲート5（62行）、ゲート7（68行）、ゲート8（71行）が上記読者をCIから実行する。 |

### 2.3 arXivスナップショットの読み手

| 読み手 | 実測した読取箇所・役割 |
|---|---|
| `scripts/check_citations.py` | デフォルトfixtureは44行。`load_fixture` がJSONオブジェクトと `entries` を読む（88–96行）。オフライン実行は257行から呼ぶ。 |
| `scripts/check_memo_citations.py` | デフォルトfixtureは68–70行、CLI引数は315–320行。通常モードで `cc.load_fixture(args.fixture)` を呼ぶ（368–377行）。独自ローダーではなく上記 `check_citations.load_fixture` を利用する。 |
| `scripts/holdout_eval.py` | `run_memo_citations` が既定fixtureを読む（162–176行）。現状 `check_memo_citations` に `load_fixture` がないため、フォールバックでJSON全体を直接読む166行目が実際の経路。シャード化後は共通ローダーに揃える必要がある。 |
| `tests/test_check_citations.py` | fixture定数は33行。実データ照合およびローダーテスト（73–86行、80行）。テスト用の改変fixture作成時には実fixtureを読み（146、176行）、一時ディレクトリに複製している。 |
| `tests/test_check_memo_citations.py` | fixture定数は38行。実メモ照合と網羅性検査（66–79行、73行）、実fixtureを指定した異常系（336–347行）。 |
| `tests/test_holdout_eval.py` | 全検査器を評価する実リポジトリテスト（234–249、265–269行）が `holdout_eval.run_memo_citations` 経由で既定fixtureを読む。 |
| `.github/workflows/core-check.yml` | コメントがスナップショットを説明（10–15行）。ゲート5・6のコマンド（62、65行）が間接的にfixtureを読む。workflow自体はファイルを開かない。 |

両citation checkerの `--live` は手動専用のオンライン照合で、スナップショットを読まずAPIを使う。現行CI（62、65行）は `--live` なしなので、fixture読み込みが通常経路である。

### 2.4 書き手、似ているだけの参照、パス検査

- `scripts/`、`tests/`、`gitswarm/`、`.github/workflows/` をI/O呼出しと対象パスで検索し、関連箇所をコードで確認した範囲では、**追跡対象の5台帳または本fixtureを書き換える実行コードは0件**。`new_id.py` はIDを表示するだけである。
- テスト内の書込みはテスト専用一時パスのみ。例：`tests/test_check_citations.py` の合成台帳・fixture（65–67、90–95、146–151、176–190行）、`tests/test_check_memo_citations.py` の一時fixture（304–312、358–362行）。追跡中のファイルへの書込みではない。
- `gitswarm/` には `state/` への言及があるが、実測した `gitswarm/readout.py:10` はスコープ説明のdocstringであり、台帳・スナップショット読取りではない。ベンチマーク／readoutの成果物I/Oは `gitswarm/artifacts/` で、対象外。
- `scripts/check_ownership.py` と `tests/test_ownership.py` は `state/claims.jsonl` 等を**パス文字列として分類**するだけで、ファイル内容を読まない。誤って読者に数えないためこの区別を明記する。
- `validate_state.py` の `PATH_TOKEN_RE` は `state/` と `tests/` のファイルパスも対象にし（300–303行）、台帳内の散文にあるパスの実在を `check_cross_references` で確認する（318–361行）。検査7の `check_memo_ledger_refs.py` は同じ正規表現を再利用し、各メモ中のパスが `ROOT / path` として存在しなければ dangling path にする（148–154行）。
- 本設計メモを作成する直前に既存メモだけを実測したところ、`contributions/*.md` に台帳パスが**33回・7ファイル**（sources 11、evidence 10、claims 4、verifications 7、hypotheses 1）、fixtureパスが**22回・12ファイル**あった。さらに台帳内の2ファイルにfixtureパスが32回ある。台帳やfixtureを削除・改名すれば、コード読取りだけでなく検査7の既存メモ参照とゲート4の台帳内パス検査も失敗する。検査7は「存在するか」だけを確認するので、旧JSONLをベース・シャードとして残せばパスゲートは維持できる。ただし旧パスが統合ビューそのものではなくなることは、後続の説明で明示する必要がある。

## 3. 方式比較

| 観点 | A. 1レコード1ファイル | B. セッション／バッチ・シャード＋統合ビュー（推奨） | C. `.gitattributes` `merge=union` | D. 専用の和集合マージツール |
|---|---|---|---|---|
| (1) GitHubサーバー側 `gh pr merge` | **通常は可**。別IDなら別パスの追加で競合しない。同じIDなら同じファイルパスにadd/add競合が出る。 | **可**。枝ごとに異なる新規シャードパスだけを追加し、統合ビューをコミットしないことが条件。 | **サーバー側は未確認／非対応として扱う**。ローカルGitで効くことは確認したが、GitHubの公開根拠はユーザー定義attributesを考慮しない旨。現行サーバーでの直接実験はしていない。 | **ツール単独では不可**。統合時にツールをローカル実行し、その解決結果をPRブランチへコミット／pushして競合を解消した後なら通常の `gh pr merge` が可能。 |
| (2) 既存読み手の変更規模 | **大**。全5台帳の列挙・読取をディレクトリ走査へ変更。検証器、採番器、引用検査、メモ参照検査、件数検査と各テストが対象。 | **中～大**。同じ読者を共通の統合ローダーへ寄せる必要があるが、154既存レコードの再配置は不要。fixture読者も共通ローダー化する。 | **ほぼなし**。ファイル形式は維持。 | **読者はほぼなし**。ただしマージ手順・専用ツール・その回帰テストを追加する。 |
| (3) 喪失・重複・同一ID異内容の検出 | 全ファイルをIDで横断検査すれば重複と異内容を検出可能。同じIDの同一パス競合はGitも止める。ファイル欠落は外部の期待一覧がない限り単独では検出できない。 | 全シャードの横断検査で重複・異内容・出所パスを報告できる。独立した追加パスは通常のマージで両方保持される。期待されていたがコミットされなかった記録の検出には別マニフェストが必要。 | `union` はIDを理解しない。別ID行は保持するが、同じIDの異内容も両方残して競合を隠す。後続validatorが動けば重複IDは検出できるが、マージ時点では解決にならない。fixtureのようなJSON文書は構文破壊もありうる。 | ID/arXiv IDをキーにした実装なら、同一内容の重複も異内容も明示的に検出して停止可能。ツールが両側／基底をすべて読んだことをテストしないと、誤った片側選択や入力漏れを検出できない。 |
| (4) 人間がdiffを読む | 1ファイル1レコードで局所的。ただし現行154件の移設はファイル一覧が増える。 | 1セッション／バッチごとの追加で作業単位が読める。統合ビューを追跡しなければdiffは追加ファイルだけ。 | 単一ファイルで差分は読めるが、競合マーカーが消えた後に重複・不正JSONを見落としやすい。 | 単一ファイルの追加行を見られる。順序を安定化し基底順を保つ実装が必要。 |
| (5) 取り消し | 追加ファイルのrevertは簡単。参照元が後続コミットにある場合は参照も合わせて戻す。ID再利用は不可。 | 追加シャード単位のrevertが簡単。参照・引用が後続にある場合は同様に協調して戻す。既存ベースは不変。 | コミット／マージ全体のrevertは可能だが、後続の同一ファイル追記や自動統合結果と干渉しやすい。 | ツールが作った解決コミットまたは元PRのrevertが可能。単一ファイルを再び調整する可能性がある。 |
| (6) `check_doc_numbers.py` | **変更必須**。現在は5つの `.jsonl` の非空行数を数える（167–175行）。レコードファイル数／有効レコード数へ変更し、既存テストも更新する。 | **変更必須**。ベース＋全シャードのレコード数を数える。ベースJSONLだけの行数では不足する。 | 行数計測はそのまま。ただし重複行を件数として数えるので、件数一致はIDの正しさを保証しない。 | 行数計測はそのまま。ツールが重複排除・異内容停止を行う場合でも、件数検査自体は意味検査ではない。 |

**パス後方互換の注意**：Aをそのまま実施して既存JSONLを移動・削除すると、上記33件の既存メモ内台帳パスと台帳内のパス検査が失敗する。旧JSONLを凍結ベースとして残してAの新規ファイルを足す案は可能だが、読み手は両形式を扱う必要があり、実質的にはBの「ベース＋追加シャード」移行に近づく。fixtureの旧JSONパスも同様に残す必要がある。

### CのGitHubサーバー根拠と未確認範囲

GitHub Docsは、PRに残ったマージ競合はマージをブロックし、より複雑なものはローカルで解決してpushする必要があると説明する（[GitHub Docs: Merge conflicts](https://docs.github.com/en/pull-requests/reference/merge-conflicts)）。GitHub Communityの `merge=union` 要望スレッドには、GitHub Supportの過去の回答として「GitHubはユーザー定義 `.gitattributes` を考慮しない」とする回答が転載されている（[Discussion #9288](https://github.com/orgs/community/discussions/9288)）。またKubernetesは、GitHubサーバーがPRをマージする経路でunion driverを使わないとして属性を取り除いた（[Kubernetes PR #70576](https://github.com/kubernetes/kubernetes/pull/70576)）。これらはサーバー側に依存しない設計にすべき根拠である。

ただし、Support回答は古い回答の転載であり、GitHub Docsの現行マージ方法ページは `merge=union` の現行対応可否を明記していない。**本調査では本リポジトリのテストPRを作成しておらず、現行GitHub.comのmergeability計算／`gh pr merge` が属性を無視することを直接実測してはいない。したがって現行サーバーの直接確認は「未確認」**と記録する。運用上は非対応として扱う。確証が必要なら、後日、管理者承認のもとで本リポジトリと分離した使い捨てGitHubリポジトリに基底JSONLと `merge=union` を置き、2枝が異なる行を末尾追記した状態で、PRの `mergeable` / `mergeStateStatus` とサーバーマージ結果を観測する。これは提案のみで、本調査では実施していない。

## 4. 合成実験（すべて `/tmp` の使い捨てGitリポジトリ）

本リポジトリのコード・台帳・fixture・PRには触れていない。実験ルートは `/tmp/researchos-ledger-exp-zlac8ilv`。合成ベースを作り、`append-a` と `append-b` が同じJSONLの末尾へ異なるIDを追加し、fixtureの `entries` に異なるarXiv IDを追加する形を再現した。以下の実験出力では、実在しない一時リポジトリ内パスを `<...>` のテンプレート表記に、合成IDを `TEST-ID-*` に置き換えている（作業ツリーの検査7が一時パス／IDを実在パス／IDと誤認しないようにするため）。

### 4.1 デフォルトGitの末尾追記

実行コマンド（作業ブランチ `append-a`、合成リポジトリ内）：

```sh
git merge --no-edit append-b
```

実測出力：

```text
Auto-merging state/evidence.jsonl
CONFLICT (content): Merge conflict in state/evidence.jsonl
Auto-merging tests/fixtures/arxiv_metadata_snapshot.json
CONFLICT (content): Merge conflict in tests/fixtures/arxiv_metadata_snapshot.json
Automatic merge failed; fix conflicts and then commit the result.
```

終了コード1。行末追記の台帳とJSON fixtureの両方で競合した。

### 4.2 `merge=union`（ローカルGitのみ）

両ファイルに属性を設定して同じコマンドを実行した結果：

```text
[union] git merge --no-edit append-b -> exit 0
Auto-merging state/evidence.jsonl
Auto-merging tests/fixtures/arxiv_metadata_snapshot.json
Merge made by the 'ort' strategy.
 state/evidence.jsonl                        | 1 +
 tests/fixtures/arxiv_metadata_snapshot.json | 7 +++++++
 2 files changed, 8 insertions(+)
ledger_ids: EVD-001,TEST-ID-A,TEST-ID-B
fixture_parse=INVALID: Expecting ',' delimiter at line 24
```

ローカルのJSONLでは両方の異なるIDが残った。一方、同じ `arxiv_metadata_snapshot.json` を2枝で整形し直してentriesを加えた合成fixtureは、union後に**不正JSON**になった。同一ID・異なる本文の追加を別の合成unionリポジトリで試すと、Gitは終了コード0でマージし、同じIDの2行が残った（`duplicate_ids=['TEST-ID-C']`、excerptは `A` と `B`）。つまりunionはID重複を解決せず、衝突を正常終了で隠す。

### 4.3 推奨Bの合成配置

基底の5台帳／fixture相当ファイルは変更せず、2枝がそれぞれ異なるシャードファイルを新規追加して、同じ通常のコマンドを実行した。

```text
[shards] git merge --no-edit append-b -> exit 0
Merge made by the 'ort' strategy.
 state/<ledger>.d/<batch>.jsonl                     |  1 +
 .../<fixture>.parts/<batch>.json                  | 13 +++++++++++++
 2 files changed, 14 insertions(+)
 create mode 100644 state/<ledger>.d/<batch>.jsonl
 create mode 100644 tests/fixtures/<fixture>.parts/<batch>.json
normalized_ledger_ids: EVD-001,TEST-ID-A,TEST-ID-B
normalized_fixture_ids: 2600.00001,2600.00002,2600.00003
legacy_paths_preserved: True True
```

これはパスが分かれれば標準マージで両方の追加を保持できることの合成実証であり、GitHubサーバーの実験ではない。実験名の枝ラベルは説明用。実運用では枝名・日付だけに依存せず、セッション／バッチごとに衝突確率の低いランダムなパス要素を使い、既存シャードを追記編集しない。

### 4.4 DのIDキー付き専用ツール（合成ステージファイル）

デフォルトマージでできたGit indexのstage 1/2/3をインラインPythonで読み、JSONLは `evidence_id`、fixtureは `arxiv_id` で和集合化した。基底順を保持して新規分をキー順に追加し、ヘッダーまたは同じキーの内容が異なれば停止する設計にした。解決後に両ファイルを `git add` し `git commit --no-edit` でコミットした出力：

```text
[dedicated keyed union] index stages 1/2/3; status before commit=M  state/evidence.jsonl; M  tests/fixtures/arxiv_metadata_snapshot.json
resolved ledger IDs: EVD-001,TEST-ID-A,TEST-ID-B
resolved fixture IDs: 2600.00001,2600.00002,2600.00003
fixture_parse=valid; merge_commit_created=yes
[dedicated keyed union] conflicting same-ID payload -> same ID has different content: TEST-ID-C
```

これは一時コードの概念実験で、リポジトリにマージツールを追加したわけではない。適切なツールならCより誤りを検出できるが、競合解決用の追加コミットと統合役の実行を要するため、サーバーが直接マージできるBより運用ステップが残る。

## 5. 推奨案の移行手順（後方互換を先にする）

1. **現状を固定・記録する。** 既存JSONL 5ファイルとfixtureのハッシュ、上表の件数を記録する。既存の内容・名前・配置をこの段階では変えない。
2. **まず読み取り側に後方互換を追加する。** 共通の台帳ローダーを導入し、現行フラットJSONLだけでも同じ結果を返し、将来はベース＋サイドカーをまとめて返すようにする。`validate_state.py` は全シャード横断でスキーマ・ID一意性・参照整合性を検証し、重複IDなら2つの出所を報告する。読み手のこの変更をマージする前に新シャードを書き始めない。
3. **台帳の全読者を同じビューへ切り替える。** `new_id.py` は統合済みID集合と衝突確認し、`check_citations.py` は統合済みsourcesを照合し、`check_memo_ledger_refs.py` は統合済みID集合を検査する。`check_doc_numbers.py` は現在の非空行数を数える方式から、ベース＋全シャードの有効レコード件数へ切り替える。検査7用の既存JSONLパスは残す。
4. **fixtureの読取互換も追加する。** 共通スナップショットローダーが既存JSONとサイドカーentriesを統合する。`check_memo_citations.py` は同ローダーを使い続け、`holdout_eval.py` のJSON直読も共通ローダーに置き換える。明示的に一時fixtureパスを渡すテストは、サイドカーなしの単一fixtureとして動かせることを保つ。
5. **読み手とCIをテストしてから書き手の手順を切り替える。** ベースだけの後方互換、ベース＋2シャード、同一ID重複、同一ID異内容、dangling cross-reference、fixture内arXiv ID重複、fixtureヘッダー差分をテストする。2つの新規シャードを別枝で作る合成Gitマージもテストする。8つの現行CIゲートを緑にしてから、新規レコードをシャードへ書く運用を開始する。
6. **追記方法と件数説明を更新する。** `docs/record-id-scheme.md` と `docs/parallel-work-ownership.md` の新規レコード追加先・既存ID確認手順を、凍結ベース＋新規シャードに合わせる。`docs/minimal-core-and-ci.md` の件数検査の説明も、行数ではなく統合レコード数と記す。既存メモの履歴的な記述を機械的に一括書換えしない。
7. **古いパスは削除せず、互換ベースとして維持する。** 検査7はパスの存在をゲートしており、本設計メモ作成前の既存メモ実測で台帳パス33回、fixtureパス22回がある。台帳レコードにもfixtureへのパス参照がある。`state/*.jsonl` とfixtureの既存パスを削除する場合は、別途パス参照の互換方法と歴史メモの扱いを決める必要がある。初回移行では行わない。なお、パス存在検査だけでは旧ファイルが統合ビューだとは保証しないため、以後の説明では「凍結ベース」と明記する。
8. **revert手順を固定する。** 通常の追加は1シャード単位でrevertできる。後続レコードがそのIDを参照している場合は参照元も含めたrevert／訂正を行い、採番済みIDを再利用しない。読み手変更のrollbackが必要になった場合も、既存ベースはそのままなので新規シャード導入前の状態へ戻せる。

## 6. 後続ワーカー（S2/S3）の担当ファイル割当案

両者の編集衝突を避けるため、共有ローダーの入出力契約を先に固定し、以下のファイルを同時に編集しない。新しい共通ローダーの実ファイル名は実装担当が選び、本メモでは未作成パスを指定しない。

| 担当 | 担当ファイル | 完了条件 |
|---|---|---|
| **S2：台帳ストレージ／検証** | `scripts/validate_state.py`、`scripts/new_id.py`、`scripts/check_citations.py`、`scripts/check_memo_ledger_refs.py`、`scripts/check_doc_numbers.py`、`tests/test_minimal_core.py`、`tests/test_check_citations.py`、`tests/test_check_memo_ledger_refs.py`、`tests/test_check_doc_numbers.py` | 5台帳をベース＋シャードから同じ順序で読む。ID重複／異内容の検出と出所報告。採番は全シャードを照合。文書件数ゲートは全レコードを数え、既存フラット形式だけでも通る。 |
| **S3：書誌fixture／下流読者** | `scripts/check_memo_citations.py`、`scripts/holdout_eval.py`、`tests/test_check_memo_citations.py`、`tests/test_holdout_eval.py` | 既存fixture＋追加シャードを共通ローダーから読む。アーカイブ済みbase pathを消さず、同じarXiv IDの重複・異内容・header差分を黙って選ばない。 |
| **統合役（直列化）** | `docs/record-id-scheme.md`、`docs/parallel-work-ownership.md`、`docs/minimal-core-and-ci.md`、必要な場合のみ `.github/workflows/core-check.yml` | S2/S3の読取互換が緑になってから手順・説明を更新し、CIゲート数と実行コマンドを変えない。追加書込みの開始順をPR本文に明記する。 |

`check_citations.py` は台帳とfixtureの両方に触れるためS2の単独担当とし、S3は同ファイルを編集せず、そのローダー契約を利用する。テスト・コードの割当が変わる場合も、`tests/test_minimal_core.py` の共有編集を避けて担当を明示し直す。

## 7. 未確認事項

- **GitHub.com現行サーバーでの `merge=union` 実動作**：公開根拠は非対応を示すが、本調査は直接のPRマージ実験をしていない。上記3節の別リポジトリ実証案を参照。
- **サイドカー命名の最終形式とランダム要素の長さ**：日付だけでは同日並行セッションで衝突するため不可。実装時に十分なエントロピーと同一枝内の追記禁止を明文化する。
- **fixtureの `capture_note` 等のヘッダー意味論**：複数取得時刻を含む統合ビューの表示値をどう扱うかは未決。個別エントリの由来は各シャードに保存し、基底ヘッダーを黙って最新値に上書きしない方針が安全。
- **旧パスの長期的意味**：初回移行では既存パスを削除せず検査ゲートを保つが、旧JSONLが全レコード一覧ではなく凍結ベースになることを、どの既存文書へ注記するかは統合役が決める。
- **方式Aへの全面移設／永続的なフラット＋シャード併存の選択**：154件を一括で個別ファイル化する利益は、本調査の実測規模では方式Bの低い移行リスクを上回らないと判断した。将来の件数・ツール要件が変われば再評価する。

## 8. 検証コマンドと実測結果

以下はこのメモを含む作業ツリーで実行した結果。**指定8コマンドはすべて終了コード0**。合成マージ実験は上記4節のとおり `/tmp` のみで実施し、本リポジトリのコード・台帳・fixtureには変更なし。

| コマンド | 実測結果 |
|---|---|
| `python3 -m unittest discover -s tests` | `Ran 243 tests in 5.739s`、`OK`（終了コード0） |
| `python3 gitswarm/benchmarks/benchmark.py --check` | `PASS: benchmark artifact matches a fresh execution`（0） |
| `python3 gitswarm/readout_sim.py --check` | `PASS: readout-sim artifact matches a fresh execution`（0） |
| `python3 scripts/validate_state.py` | `PASS: research ledgers valid (sources=23, evidence=86, claims=9, verifications=34, hypotheses=2)`（0） |
| `python3 scripts/check_citations.py` | `summary: 22 arXiv source(s) checked, 1 skipped, 0 failure(s)`（0） |
| `python3 scripts/check_memo_citations.py` | `summary: 24 memo(s) scanned, 61 arXiv citation(s) checked, 3 skipped, 0 failure(s)`（0） |
| `python3 scripts/check_memo_ledger_refs.py` | `summary: 24 memo(s) scanned, 0 dangling reference(s), 5 archived ID reference(s)`（0） |
| `python3 scripts/check_doc_numbers.py` | `actual: tests=243 gates=8 sources=23 evidence=86 claims=9 verifications=34 hypotheses=2`; `summary: 2 doc(s) scanned, 0 stale number(s)`（0） |

テスト実行時に負例テスト由来の `nope.md` と未知detectorのエラー文が標準エラーへ出たが、テスト全体の終了結果は上記のとおり `OK`。
