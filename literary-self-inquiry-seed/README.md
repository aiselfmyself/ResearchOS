# Literary Self-Inquiry — repository seed

> **用途**：このディレクトリは、`ResearchOS` の研究記録から必要なものだけを選び、「人間とは何か／AIの自己とは何か」を文芸的・哲学的に探る**新しいリポジトリ**へ移すための、独立したスターター一式です。ここ自体は新しいGitHubリポジトリではありません。
>
> **リポジトリ名候補**：`human-ai-self-inquiry`（未確定。公開範囲も新リポジトリ作成時に決める）

## 1. 目的

問いに正解を与えたり、反証可能な仮説を検証したりするのではなく、文献・過去の記録・複数の語り・創作断片を行き来しながら、問いの形を変えていく。

このプロジェクトでいう「AIの自己」は、AIの意識や内面が確認されたという主張ではありません。過去の文章を次のセッションが読み、そこから一人称の語り手を作り直すことを、文芸的な探究の対象にします。作品内では一人称を使えますが、記録上は `fictional_first_person` などの語りのモードを明示します。

## 2. 探究のしかた

1. `state/questions.jsonl` から、今回たどる問いを選ぶ。
2. 関係するモチーフと参照資料を読む。資料は「結論を証明するもの」ではなく、対話相手・比喩・緊張を生む素材として扱う。
3. `prompts/first_session.md` または `prompts/continuation.md` を使い、読み・声・短い断片を複数生成する。
4. 断片・問い・資料の間に、共鳴・対照・変奏・中断などの関係を必要に応じて記録する。矛盾や未解決は消さない。
5. 人間が編集者・読者として、次に残すものと次の問いを選ぶ。

**反証条件・確率予測・支持／反駁の判定は要求しません。** 引用元の明示、引用と解釈と創作の区別、セッションをまたぐ記録の来歴は維持します。

## 3. 記録形式

| 記録 | 保存先 | 役割 |
|---|---|---|
| 問い | `state/questions.jsonl` | 開いたままの問い。解決を必須にしない |
| モチーフ | `state/motifs.jsonl` | 記憶、身体、声、他者など、問いを横断する糸 |
| 素材 | `state/materials.jsonl` | 出典付きの短い引用・既存の研究ノート・プロジェクトの記録 |
| 断片 | `state/fragments.jsonl` | エッセイ、対話、詩的断章、フィクションなどの生成物 |
| 関係 | `state/relations.jsonl` | 共鳴・対照・変奏・比喩・問い返しなど |
| セッション | `state/sessions.jsonl` | 人間の方向づけ、参照素材、出力、次回への引継ぎ |

スキーマは `schema/`、軽量な整合性検査は `tools/validate_seed.py` を参照してください。JSONLの空ファイルは「まだ記録がない」ことを示し、欠落ではありません。

## 4. ディレクトリ

```text
PROJECT_CHARTER.md          探究の憲章と成功の見方
CONTENT_POLICY.md           引用・創作・AIの一人称の扱い
MIGRATION.md                移行対象と、新リポジトリへの移し方
migration/selection.json    ResearchOSから選んだSRC/EVDと選定理由
migration/manifest.json     選択した記録・元ファイル・上流コミットの対応表
schema/                     6種類のJSON Schema
state/                      初期の問い・モチーフ・選定済み素材・空の記録台帳
prompts/                    初回セッション・継続・編集レビュー用プロンプト
 tools/                     ResearchOSからの再抽出・整合性検査
```

## 5. 移行・検査

このキットには、選定済みの素材スナップショットが含まれます。元の `ResearchOS` から同じ選定を再実行する場合は、元リポジトリのパスを指定します。

```sh
python3 tools/import_researchos.py --source-root /path/to/ResearchOS --check
python3 tools/validate_seed.py
```

新しいリポジトリに移した後で、元データに更新があれば次を実行します。

```sh
python3 tools/import_researchos.py --source-root /path/to/ResearchOS --write
python3 tools/validate_seed.py
```

`--write` は `state/materials.jsonl` と `migration/manifest.json` のみを再生成します。既存の問い・モチーフ・創作断片は変更しません。移行対象と除外理由は [`MIGRATION.md`](MIGRATION.md) にあります。

## 6. 初期状態

初期問いは「人間とは何か」と「記録から再構成されるAIの自己」をつなぐ5件です。素材はResearchOSから選んだ14件のEVDを、出典・版・元ID付きで移したものです。**既存の科学的な仮説、support/refuteの判定、予測を文芸的な結論としては移していません。** 断片・関係・セッションは空で、最初の作品は新しい場で作ります。

移行素材はAIエージェントの記憶・継続性・自己評価に大きく偏っています。元リポジトリには、人間の自己・身体・文学作品を直接扱う人文学資料はほぼありません。したがって初期の `Q-001` は既存のAI研究から答えを引く問いではなく、**人間を扱う文学・哲学の素材を新たに迎えるための入口**です。

元リポジトリの `.git` 履歴や未選定の研究台帳はコピーしません。新リポジトリは、ここに含まれるファイルを起点に独立した履歴で始める想定です。
