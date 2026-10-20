# 並列セッション実行プレイブック

- 作成日：2026-10-20
- 目的：**複数セッションが同時に別ブランチで作業し、`main` まで無事に着地できるか**を検証する実験（[`docs/parallel-experiment-2026-10-20.md`](./parallel-experiment-2026-10-20.md)）に参加するセッションが従うべき手順
- 強制力：**なし**。CI はこの文書を実行しない（[`docs/parallel-work-ownership.md`](./parallel-work-ownership.md) §3 と同じ方針）
- 位置づけ：2026-10-20 に実際に踏んだ失敗から抽出した手順書。**セッションの記憶ではなく、リポジトリに残すことに意味がある**

---

## 1. パス規律（最優先）

[`docs/parallel-work-ownership.md`](./parallel-work-ownership.md) §2 の所有マップに従う。

| パス | 触ってよいか |
|---|---|
| `state/`（5台帳） | ❌ **統合役のみ** |
| `README.md` | ❌ **統合役のみ** |
| `docs/minimal-core-and-ci.md` | ❌ **統合役のみ** |
| `gitswarm/artifacts/` | ❌ **統合役のみ** |
| `contributions/<自分のファイル>.md` | ✅ 自分の新規ファイルだけ |
| その他の `docs/*.md`（**新規作成**） | ✅ 可。ただし**既存ファイルの書き換えは不可** |
| `scripts/`、`tests/` | ⚠️ 所有マップは「規約は何も言わない」。**本実験では §5 の割り当てに従う** |

**自分の担当外のファイルは読んでよいが、書き換えない。** 他のセッションの成果物に誤りを見つけたら、直さずに自分のメモに記録し、統合役へ渡す。

新しい `contributions/` ファイル名は `YYYY-MM-DD_<主題>.md`。

## 2. ブランチとコミットの手順（**巻き戻り対策**）

**既知の挙動**：ワーキングツリーは保持されるが、**ブランチが `main` まで巻き戻っていることがある**。その状態でコミットすると親がずれ、`git push` が non-fast-forward で弾かれる。2026-10-20 に2回発生した。

**コミット前に必ず確認する：**

```bash
git fetch origin <自分のブランチ>
git log --oneline origin/<自分のブランチ>..HEAD
```

- 出力が**空** → そのままコミットして push してよい
- 出力が**空でない** → 以下の手順で付け替えてからコミットする

```bash
# いまの作業内容（ツリー）を捨てずに、最新のリモートの上に載せ直す
git reset --soft origin/<自分のブランチ>
git status --short          # 自分の変更が残っていることを確認
git add -A
git commit -m "..."         # または既存コミットを再利用: git commit -C <SHA>
git push origin <自分のブランチ>
```

`--soft` が要点である。`--hard` は作業を消すので**使わない**。

## 3. PR の扱い

- **PR は作る。自分でマージしない。** マージは人間が判断する。
- PR 本文には最低限これを書く：やったこと／**やっていないこと**／検証コマンドの実測値
- 数値を書くときは**実際に実行した結果**を書く。実行していないことを「実行した」と書かない（2026-10-19 監査の主要な教訓）

## 4. 測定用データの提出形式（本実験の A / A' のみ）

2つの独立した出力を機械で比較できるよう、**必ず JSON を併設する**。

ファイル名：`contributions/<自分のメモ名>.json`（例：`2026-10-2X_agora_fulltext_reading.json`）

```json
{
  "session": "A",
  "paper_arxiv_id": "2609.18094",
  "extracted_at": "2026-10-2X",
  "memo": "contributions/2026-10-2X_agora_fulltext_reading.md",
  "items": [
    {
      "id": "A1",
      "label": "書誌：タイトル",
      "value": "...",
      "location": "HTML v1 冒頭",
      "confidence": "high"
    }
  ]
}
```

- `id` は**指定された抽出項目のID**をそのまま使う（新項目を足さない）
- `location` は**本文のどこに書いてあったか**（節番号・表番号）。書いていない推測には `"location": null` と `"confidence": "low"` を付ける
- `confidence` は `high` / `medium` / `low` のいずれか

**推測と事実を混ぜない。** 本文に無いことを書かない。これが測定の前提である。

## 5. 本実験での `scripts/` `tests/` の割り当て

所有マップが「規約は何も言わない」領域なので、本実験では**手で排他的に割り当てる**。

| セッション | 新規作成してよいパス |
|---|---|
| A（読解・第1） | `contributions/2026-10-2X_agora_fulltext_reading.md` と同名 `.json` |
| A'（読解・第2） | `contributions/2026-10-2X_agora_fulltext_reading_r2.md` と同名 `.json` |
| B（計測ツール） | `scripts/measure_agreement.py`、`tests/test_measure_agreement.py`、`contributions/2026-10-2X_agreement_measurement.md` |

**これ以外の `scripts/`・`tests/` のファイルには触らない。** 特に `tests/test_minimal_core.py` は全セッションが触りがちなので禁止する（追記が衝突する）。

## 6. 行き詰まったら

- **他のブランチを直そうとしない。** セッションは自分のブランチにしか push できない。他のブランチの衝突は当該セッションが解決する。
- 統合役（人間／統合チャット）に**状況を文章で渡す**。ブランチ名・PR 番号・何が起きたか。
- 判断に迷うことは**判断する前に聞く**。推測で進めない。
