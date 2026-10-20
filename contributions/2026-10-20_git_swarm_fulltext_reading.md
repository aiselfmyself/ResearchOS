# 全文読解レポート 2：GitSwarm

- 作成日：2026-10-20
- 対象：[G1] Shah et al. (2026) "GitSwarm: Decentralized Compounding Inference" arXiv:2610.04862v1 の全文
- 位置づけ：`task/TASK.md` §1 に対応する2本目の全文読解。既存 `2026-10-20_stateless_vs_gitswarm.md`（本論文の abs＋要旨＋部分節を確認済みの調査メモ）を、一次本文で裏付け直し・拡張する。**新しい実験は行っていない**。実行した確認は §10 に列挙する。
- 方法：PDF 本文を通読（取得ツール、全16チャンク）。PDF 解析は約30ページ上限で Appendix E.2.1 付近で途切れたため、未読区間のうち重要な Appendix G（投票动力学）と H（プロンプト）を HTML 版の該当チャンク（5つ）で補完した。書誌は abs／HTML／PDF と fixture で一致。SLA [G2] との対照は全文読解レポート 1（`2026-10-20_sla_fulltext_reading.md`）に基づく。

## 1. 結論（全文から新しく分かったこと）

1. **投票は「独立検証」ではなく「調整信号」として論文自らが位置づけている。** Appendix G.3 の留保：「A nomination is a worker preference, not an independent verification of correctness: repeated nominations for one SHA are coordination signals, not independent proofs of correctness.」既存メモの「多数決は真理の判定器ではない」整理を、本文と appendices の両方で直接引用できる形にした。
2. **票は正確なコミット SHA に紐付くため、改良のたびに票が分断される**（G.3）。後期リペアが「小さいが急速な投票プルス」で勝つ機序が特定された。plurality readout の構造的な脆さの具体例であり、CLM-003（多数決リスク）への新しい材料。
3. **研究タスクでは readout を「外す」だけでなく、プロンプトから nomination 文言ごと除去している**（Appendix H.1 Table 14 の注 a）。検証スコアがある環境では plurality を一切使わない設計が、実装レベルで確認できた。
4. **再利用率はタスクで2倍以上違う**：後続が built upon する比率は ProgramBench 94.7% に対し IMOProofBench は **44.4%**、選択解の祖先カバーは 81.6–92.6% 対 **21.3–33.0%**（§3.4）。メモは 94.7% のみ記載。証明では後続作業の多くが「拡張」ではなく「比較・採択」に使われる。
5. **論文は substrate の3性質を統制実験で個別検証している**（Appendix C）：永続記憶で再発見カバレッジ 95–100%（独立条件は70–75%/20–23%、予算過剰でも）、branch 構造で再走査率 0–5.7%（flat は11–23.5%）、明示的 attribution で有効な Lineage 判定に読む必要のあるアーカイブが 13–22%（attriburion なしは41–77%）。**ResearchOS の台帳が持つ「参照整合性」はこの attribution に相当**し、同じ論文の定量的裏付けがある。
6. **スコアの中央値比較では分散化が負ける方向**：非同期 vs 同期ウエーブは 62.06±2.44% vs 63.11±0.58%、分散 nomination vs 中央セレクタは 62.06±2.44% vs **64.40±1.49%**（§3.5）。メモは中央セレクタ数値のみ記載。著者らは「統計的同等性を示さない」と明記しており、**分散化はスコア優位ではなくレイテンシ・構造上の理由で選ばれている**。
7. **IMO 全問正解は単一実行**、ProgramBench は 200 問中 50 問の固定部分集合、因果的寄与は分離されていない（§4）。メモ §6 の記載を本文で完全確認。加えて発見：**プロンプト実行インターフェースが予算間にわたって不均一**（B100/B200 は fenced blocks、B300 は50タスク中33が構造化ツール、Appendix H.1）— スケーリング曲線の解釈上の留意点。

## 2. 読解の範囲と方法（正直な記録）

- **PDF（全16チャンク取得）**：本文 §1–§5、AI 利用声明・倫理声明、Appendix A（関連研究）、B（実験セットアップ）、C（統制実験 C.1–C.4）、D（ベンチマーク詳細）、E.1–E.2.1（研究タスク共通設定＋RMT 仕様）まで。**解析上限（約30ページ／本文は約65ページ）により E.2.2 以降は PDF では途切れた。**
- **HTML 補完（39チャンク中5つを取得）**：G.3（投票动力学）、G.4（任意中止の校准）、G.5（選択的検査）の一部、H.1–H.2（プロンプト構成と global system prompt）、および取得起点の照合。
- **未読のまま**：E.2.2–E.5（RMT/Looped/NanoChat の詳細実験ログと表）、F（artifact 消費の内訳表）、G.1・G.2・G.6（活動分類・episode 結果・設計比較の全表）、H の残りプロンプト。これらは本文 §3.3–§3.5 で要旨・主要数値が読めており、本レポートの主張は未読分に依存しない。
- 追加の資料検索は**なし**（Appendix A で言及された並行研究 Agora [G3] は論文経由の知見として §7 に記載）。

## 3. 設計の詳細（§2）

- **shared computation graph（§2.2）**：各貢献は原子的 Git commit。**物理親（開始時点の状態）と、必須フィールド `informed_by=` で宣言する意味的依存を分離**。物理親は `informed_by=` に含まれる必要があるが、ブランチを跨ぐ依存も追加でき、**マージをせずに**1つの branch を継ぎながら他 branch の知見を利用できる。「Semantic dependencies are declared by workers, not independently established as causal influence.」（§2.2 — 著者自ら因果主張を拒否）。
- **ワーカープロトコル（§2.3）**：Contribute（validation は公開要件チェックのみで正しさではない）／Nominate（既存候補への投票レコード、候補本体は無変更）／Abstain（**予算を消費しない**交換。ただし推論コストは発生）の3択。全ワーカー同質・役割なし・同時実行上限 C（問題解決は5、研究タスクは12）。
- **状態可視化（§2.4）**：dashboard（残予算・稼働中・投票集計。「votes are not evidence of correctness」と明記）と in-flight activity log（未コミット作業の scope 公開。ピアは読めないが書けない）。中央は**知的役割を割り当てない**。
- **decentralized readout（§2.5）**：予算終了後に最多 nomination の候補を決定的 tie-breaking で選択（式2）。nomination レコードは計算グラフと**分離**しており、投票しても祖先は変わらない。
- **研究タスクでの readout 剥離（§3.3＋H.1）**：「We strip GitSwarm of the nomination based decentralized readout for these experiments since all tasks discussed here support a validation performance based candidate selection (Appendix E.1)」。プロンプト層では nomination アクションと関連文言を削除し、代わりに「commit か abstain で終え、nominate しない」選択ポリシーを前置（H.1 注 a）。
- **倫理声明（本文末）**：隔離 worktree・ネット接続なしで実行。「agents' intermediate conclusions can be wrong (small proxy evaluations mis-ranked candidate models), so results should be independently verified before they are relied upon」。さらに、エージェント群の未整合・サンドボックス脱出事例への言及と、デプロイ前行動分析の必要性を明記。

## 4. 評価設計と結果の読み方（§3.1–§3.5）

- **セットアップ（§3.1、B）**：IMOProofBench-Advanced 30問全問（採点 {0,1,6,7}、7で完全正解）、ProgramBench は開発9問＋**層化抽出された50問**（Rust26/Go11/C8/C++3/Haskell1/Java1、難度7 easy/30 medium/4 hard/9 unlabeled）。予算は program B∈{100,200,300,500}、proof B∈{20,40,80,120,160}（episode 単位）。ベースライン **Forced**＝自然停止するたび "Keep working...." で再開する単一エージェント（B.3）。
- **ベンチマーク（§3.2）**：ProgramBench は Codex ワーカーで 73.1%（B100）→79.4%（B500）、ベース GPT-5.5 で 64.6→71.2、Forced Codex は 63.1–65.1 で頭打ち。IMO は Gemini-3.1-Pro で 23.3（B20）→29.0（B160、**B80 で非単調に低下**）、GPT-5.5-high は B20 で28問、B40/B80 で30問。ただし **Best-of-N（oracle verifier 付き）も低い予算で ceiling に到達**するため「飽和ベンチでの優位は主張しない」（§3.2末尾）。
- **研究タスク（§3.3）**：RMT は2つの12ワーカースウォームが同1.3Bトークン予算で 2.890/2.894（reference 3.147。Forced GPT は3.0Bで2.927、Codex は10.1Bで2.690）。**最終アーキの6変更中4つが別 branch 由来**、うち1つは失敗案を49.5時間後に復活させた temporal mixer。Looped Transformer は 3.187（reference 3.265、Direct GPT 3.274、Codex 3.479、パラメータ一致 control 3.212）。**128例評価で棄却された案を512例で再評価して復活**（12組中5組誤順位→1組）。NanoChat は BPB 0.993→0.905（1,465回の成功評価、 incumbent は約1.72Bパラメータに膨張）、**negative ラベルの研究コミットの70.1%が後続に引用**。
- **再利用の3側面（§3.4）**：declared reuse（eligible episode の 99.9%/96.2% で他貢献を引用）、built upon（94.7% vs 44.4%、200 PB run＋150 proof run の pool）、ancestry（81.6–92.6% vs 21.3–33.0%、PB の Git-parent のみでは約4分の1で残りは cross-branch 依存）。artifact 消費は trace で別途測定：PB で 79.9–82.5%、probe bundle は 759中583が開封され172が引用付きで実行、52が選択解祖先に貢献。ただし「observed reuse, not the causal contribution」（§3.4末尾）。
- **適応的協調（§3.5）**：役割割りなしで活動分布が時間変化。選択対象の候補出現は PB で進行93.1–98.0%（終了8–11.5 episode 前）、IMO では8.6–17.5%（selection エピソード比率は B20→B160 で44.2%→69.7%）。任意中止は PB は約6分の1、IMO は2.7%未満。検査は PB で5–7候補、proof で約3件のみ（グラフ全体は読まない）。設計比較では同期ウエービングが僅かに上（63.11±0.58% vs 62.06±2.44%）し、readout 比較では中央セレクタが僅かに上（64.40±1.49% vs 62.06±2.44%）、一方で中央アグリゲータは最下位（58.19±4.53%）。非同期は同期ウエーブより約23%短い（38.0 vs 49.3分）。著者らの注記「they do not establish statistical equivalence or isolate the benefits of persistent memory」。

## 5. 統制実験（Appendix C — メモに無かった新事実）

3性質を1つずつ独立にテストした合成タスク（Gemini-3.1-Pro、3 seed）：

| 性質 | タスク | 主結果 | 留保（C.4） |
|---|---|---|---|
| Persistence | Hidden Rulebook（連鎖再発見） | 共有永続メモリはカバレッジ 95–100% を維持。独立 B=2 は70–75%、独立 k=4 は20–23%（**総クエリ予算は 4Q/3 と過剰**）。深さ D=32 では 100% vs 38% vs 5% | 単独の性質がベンチマーク性能を** Cause したとは主張しない** |
| Branchability | Hidden Maze（再走査コスト） | branch 構造の checkpoint 復元で再移動率 0–5.7%（depth 4–8）。flat 永続メモリは11–23.5%。プロンプト明示あり（実装 Interfaces の比較であることが caveat） | 同上 |
| Attribution | Retracted Evidence（失効 lineage の追跡） | 明示的 producer/parent メタデータで初回完全提出までに読むアーカイブが 13–22%。なしでは41–77%、**深くなるほど差が拡大**（L=3: 19 vs 24 → L=6: 20 vs 77） | 同上 |

**示唆**：ResearchOS の `evidence.source_id`／`claim.evidence_ids` という参照エッジは、まさにこの attribution に相当し、「参照がない台帳は lineage を内容から再構築するしかなく、コストが深さ・曖昧さに比例して増える」ことが同じ論文で定量展示されている。

## 6. 既存メモ・台帳との突合

| 既存の記述（場所） | 全文読解の結果 |
|---|---|
| メモ §5「検証スコアが使えない場合に推薦多数決（[2] §2.5）。検証可能な実験では readout を外している（[2] §3.3）」 | **完全一致**：§2.5（式2）と §3.3 の stripping、さらに H.1 でプロンプトから nomination 文言まで除去と確認 |
| メモ §5「投票は正しさの証拠ではない（[2] §2.4）」 | **一致＋拡張**：dashboard 文言に加え G.3 の留保「coordination signals, not independent proofs」を直接引用可能に |
| メモ §5 中央比較の数値（62.06±2.44／64.40±1.49／58.19±4.53、38.0／34.9／43.9分） | **一致**。**追加**：同期ウエービング 63.11±0.58%・49.3分の比較（メモ未記載）— 両比較とも中央側が僅かに上 |
| メモ §5「128例で5組誤順位、512例で1組」 | **一致**（§3.3）。加えて control の 3.212 など数値を補完 |
| メモ §5「経験的検証はまれで、大予算でのみ目立つ」 | **一致**（§3.5 "Empirical validation remains uncommon and becomes visible mainly at larger budgets"） |
| メモ §6「50/200固定部分集合・IMO全問正解は単一実行・因果寄与未分離」 | **本文 §4 で完全一致**（加えて Looped 記録時は走行継続中、NanoChat 比較は開始 checkpoint/GPU が異なる、も明記） |
| メモ §3.2「70.1%…NanoChat の限定窓の値」 | **一致**（§3.3）。隣接値として Looped の negative 引用率 74%（26時間、395実験/12系統）を追加可能 |
| worker02「多数決は解の正しさが後から確認できる課題で有効」 | **論文と逆**（メモ §5 の訂正を再確認）：論文は検証可能時に readout を**外す**。worker02 の記述は訂正済みのまま |
| CLM-002（supported：Compounding、EVD-002 94.7%、EVD-008 70.1%） | **本文で確認＋拡張**：タスク間差（44.4% IMO）、ancestry 分解、artifact 消費trace |
| CLM-003（candidate：多数決が誤りを増幅） | 論文は「票＝好みであって検証ではない」「SHA に票が紐付くと分断される」まで示した。**「増幅」の実証は依然なし**（統制実験 C は voting を対象にしない）。CLM-003 の status は candidate のまま妥当 |
| EVD-003（readout 引用） | §2.5＋§3.3 の文言と一致 |
| メモ §8 提案「同質多数決の増幅を直接測る実験」 | **依然未実施**（本論文の統制実験は persistence/branchability/attribution のみ）。提案は有効なまま |

## 7. Negative findings / 制約（論文自認＋読者としての注意）

**論文自認（§4、§3.5、倫理声明）：**

1. 貢献グラフ・artifact 消費の分析は**使用の観測**であって性能への**因果寄与を分離しない**。直接的介入実験（同一候補から履歴あり／なしで継続）が必要と明記。
2. ProgramBench は50/200固定、IMO 全問正解は単一実行、一部比較は実行条件が異なる。「results do not establish superiority over every single-agent configuration」。
3. 予算間の proof 設定差により、スケーリング曲線は「記述的であって worker 数の統制効果推定ではない」（D、B.4）。
4. 永続履歴のコスト：リポジトリが成長するほど入力トークンを消費。冗長 episode は受理ゼロでも計算を浪費。「benefits > costs」の境界は長い horizon の評価が必要（§4 Computational overhead）。
5. 中間結論は誤り得る（proxy 評価の誤順位）→ 依頼前に独立検証を、と倫理声明で自ら義務付け。

**読者としての注意（本レポートの解釈）：**

6. **実行インターフェースの不均一**（H.1）：fenced blocks（B100/B200）と構造化ツール（B300 の33/50、research は MCP/native shell）が混在。スケーリング曲線の跨ぎ比較には留意。
7. Forced ベースラインは "Keep working...." の一文のみ。比較対象として素朴な構成（とはいえ予算一致・トークン計測は妥当）。
8. plurality readout の**票分断メカニズム**（G.3）は、バージョン管理上で「正確な SHA」に票を置く設計全般の弱点。ResearchOS が将来 nomination を実装する場合の設計警告になる。
9. v1 査読前。並行研究 **Agora** [G3]（Git 非同期研究、Git-parent 多重親＋diversity-aware frontier view）が本文で詳細に比較されており、単独最適化ではなく設計空間の調査として読むべき。

## 8. ResearchOS への示唆

1. **`informed_by=` ↔ 台帳の参照整合性**：物理親と意味的依存の分離は、`state/` の source/evidence/claim エッジと同型。Appendix C.3 の定量結果（attribution ありで読了13–22% vs なし41–77%）が、`validate_state.py` の参照検査を**性能のための**設計としても正当化する。
2. **選択規則の二段構え**：検証スコアがあればそれ、なければ「証拠ではない」ラベル付き plurality — という明示的な階層が GitSwarm。ResearchOS の人間レビュー queue を置く位置づけ（形式が検証を保証しない）と整合する。
3. **投票を実装するなら SHA ではなく意味的 ID で**（§7.8）：票分断は `docs/record-id-scheme.md` の非連番 ID 発想（不変の意味的識別子）と衝突しない設計判断になる。
4. **因果的主張の抑制**：著者らが「使用の観測であって因果ではない」と繰り返す姿勢は、本リポジトリの「再実行できるものだけを載せる／実行していないことを実行したと言わない」規約と同一。benchmark 再現性チェック（PASS）も同様に「数値一致の観測」であって solver の優劣の証明ではない。
5. **SLA [G2] との対照表の更新**：「最終選択」行は GitSwarm＝validation or plurality fallback（プロンプトまで確認）、SLA＝harness の測定値保持（Appendix E の anchor 規則）。メモ §3.3 の「規則は未確認」は両論文とも解消済み。

## 9. 本レポート作成時に実行した確認

- `python3 -m unittest discover -s tests` → **45件 OK**（既存28＋PR #13 の17）
- `python3 gitswarm/benchmarks/benchmark.py --check` → PASS
- `python3 scripts/validate_state.py` → PASS（sources=4, evidence=14, claims=7, verifications=21, hypotheses=3）
- `python3 scripts/check_citations.py` → 3 checked / 1 skipped / 0 failures
- 書誌照合：abs／HTML／PDF の3経路のタイトル・著者・年が fixture と一致

（Python 3.11.2、2026-10-20。上記以外の実験・実行は行っていない。）

## 10. 提案（本レポートでは実行していない）

1. メモ §3.3 比較表の「最終選択」行を、両論文の確認済み規則で更新する（メモ改訂は人間レビュー付きで）。
2. CLM-003 に G.3 の直接引用（coordination signals not proofs）を反映した新しい EVD 追記提案（`new_id.py` 採番、PR 経由）。
3. Appendix C の統制実験と同型の、ResearchOS gitswarm/readout に対する「参照あり／なし」の小規模測定（メモ §8 提案の前段。ただし DoD 外）。
4. 未読区間（E.2.2–G.6）の追加補完は、既存の主張を変える材料が本文にある場合のみ再実行する。

## 11. 参考文献

[G1] Vedant Shah, Ankur Samanta, Paras Dahal, …, Anirudh Goyal. "GitSwarm: Decentralized Compounding Inference." arXiv:2610.04862v1 [cs.AI], 2026（投稿 2026-10-04）. https://arxiv.org/abs/2610.04862 / DOI: 10.48550/arXiv.2610.04862

[G2] Qizheng Zhang, Changxiu Ji, Isaac Sun, …, Kunle Olukotun. "Stateless Language Agents: Scaling Long-Horizon Automated Research." arXiv:2610.07625v1 [cs.LG], 2026. https://arxiv.org/abs/2610.07625 — 対照は本リポジトリの全文読解レポート 1（`2026-10-20_sla_fulltext_reading.md`）に記載。

[G3]（論文 Appendix A 経由で言及、**内容は未読解**）"Agora: Git as shared memory for collective autoresearch." arXiv:2609.18094, 2026. https://arxiv.org/abs/2609.18094 — 書誌は [G1] Appendix A の記載に基づく。著者名は [G1] の参考文献リストに従う（本レポートでは転記しない）。本レポートでの引用範囲は「[G1] が並行研究として比較している」こと、および [G1] が述べる設計差（多重親の Git-parent vs 物理親と `informed_by=` の分離、diversity-aware frontier view vs plurality readout）のみ。

（内部記録 `state/`・`contributions/` への参照は文献引用ではない。数値・引用はすべて [G1] の本文取得（PDF 全16チャンク＋HTML 補完5チャンク）に基づく。）
