# レコードID方式（非連番ID）

- 作成日：2026-10-20
- 目的：並行作業時のID衝突を原理的に避ける
- 強制：`scripts/validate_state.py` が検査し、CI（`core-check.yml`）で赤になる

---

## 1. 何を変えたか

`state/*.jsonl` のIDは連番（`SRC-001`、`EVD-014` …）だった。連番は**同じ台帳に2つのブランチが追記すると必ず衝突する**。どちらも同じ `max(ID)` を読み、同じ次の番号を採番するためである。

2026-10-20 以降に追加するレコードは、次の形式を使う。

```text
PREFIX-YYYYMMDD-xxxx      例: EVD-20261020-9f2c
```

- `PREFIX`：`SRC` / `EVD` / `CLM` / `VER` / `HYP`（台帳ごとに固定）
- `YYYYMMDD`：採番した日付
- `xxxx`：ランダムな16進4桁（`secrets.token_hex(2)`）

日付＋ランダム接尾辞なので、**独立したセッションが同じ日に採番しても衝突しない**。IDはレコードに書いた時点で固定し、後から変更しない（他のレコードが参照しているため）。

## 2. 採番方法

```sh
python3 scripts/new_id.py SRC            # 1件
python3 scripts/new_id.py EVD --count 3  # 3件
```

出力されたIDをそのままレコードに書く。既存の台帳を読んで重複を避けるので、通常は衝突しない。

## 3. 既存レコードの扱い（据え置き）

2026-10-20 時点の49件は連番のまま残す。IDは参照されているため一括変更しない。

連番IDは**番号が凍結上限以下であれば**受理する。上限は `scripts/validate_state.py` の `LEGACY_MAX` に固定してある。

| 台帳 | 接頭辞 | 凍結上限 | 現存件数 |
|---|---|---|---|
| sources | `SRC` | `SRC-004` | 4 |
| evidence | `EVD` | `EVD-014` | 14 |
| claims | `CLM` | `CLM-007` | 7 |
| verifications | `VER` | `VER-021` | 21 |
| hypotheses | `HYP` | `HYP-003` | 3 |

**上限を上げてはいけない。** 上限を超える連番（例：`EVD-015`）は「新規レコード」とみなされ、検証器がエラーにする。

```text
state/evidence.jsonl:15: ID 'EVD-015' extends the frozen sequential range
(max EVD-014); mint one with 'python3 scripts/new_id.py EVD' instead
```

## 4. 何を解決し、何を解決しないか

| 問題 | この方式 |
|---|---|
| 同一台帳への追記による **ID衝突**（add/add、union後の重複） | **解決**（接尾辞が独立） |
| 同一台帳への追記による **テキスト衝突** | **未解決**（同じ行範囲を触るため。1レコード1ファイル分割は未実施） |
| 共有ファイル（`README.md`、`docs/`、`gitswarm/artifacts/`）の同時編集 | **未解決**（`docs/parallel-work-ownership.md` の所有マップで運用回避を試みるが、強制力はなく、規約を知らないセッションの編集は防げない） |
| 誰が変更したかの識別 | **未解決**（全セッションが同一 git author のため原理的に不可） |

## 5. やらないこと

- ロール別のパス制限、レビューキュー、承認台帳は追加しない（`README.md` の凍結方針）。
- IDの自動採番をコミットフックやCIで強制しない。番号を採るのは作成時であり、事後に機械が埋めるものではない。
- `merge=union` は導入しない。テキスト衝突は消えるが、重複行を静かに残し、`ours`/`theirs` による消失を招くため（詳細は 2026-10-20 の検討記録）。
