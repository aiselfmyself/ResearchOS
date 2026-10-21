# 状態台帳

`*.jsonl` は一行一レコードです。空の台帳は、まだその種の記録がないことを示します。

- `questions.jsonl` / `motifs.jsonl`：人間が最初の問いとモチーフを設定済み。
- `materials.jsonl`：ResearchOSから選定した出典付き素材。`tools/import_researchos.py` で再生成できます。
- `fragments.jsonl` / `relations.jsonl` / `sessions.jsonl`：新リポジトリで最初のセッションを行った後、採用したものだけ追記します。

元のResearchOSは読み取り元であり、移行ツールはこのリポジトリの科学研究台帳を変更しません。
