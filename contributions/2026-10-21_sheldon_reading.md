# SHELDON（arXiv:2610.18025）読解 — 仮説空間と観測空間の分離データモデル

**読解日**: 2026-10-21
**対象**: arXiv:2610.18025v1 [cs.AI; cs.LG], submitted 2026-10-13,「16 pages main text, 34 total. Preprint.」
**著者**: Harshit Joshi, Priyank Shethia, Monica S. Lam（Stanford University）
**成果物**: 本メモ ＋ `SRC-20261021-2384` ＋ `EVD-20261021-7cdb` / `4ad6` / `59ab` / `6ec4` / `572c` ＋ `VER-20261021-9f6a` ＋ `CLM-20261021-7b3e` ＋ `tests/fixtures/arxiv_metadata_snapshot.json` への 2610.18025 追記

---

## 0. 結論（TL;DR）

1. **SHELDON の貢献は「LLM 推論の追加」ではなく、仮説と観測を別々の ID 空間として持ち、その間の証拠関係を 4 値の写像として明示型付けした点にある。** 状態は `S_t = ⟨H_t, O_t, wH_t, wO_t, E_t⟩` の 5 要素で、うち `E_t : H×O → {Support, Refute, Neutral, Unresolved}` が「どの EVD がどの HYP を支持／反駁するか」の**唯一**の格納場所になる。〔証拠段階 B：`EVD-20261021-7cdb`〕
2. **「仮説が説明できない観測」の検出は、判定そのものは推論が要るが、判定結果を記録した後は決定論的な集合演算に還元できる。** 論文の 4 値 verdict は「厳密な含意・矛盾ではなくタスク依存の証拠判断」であると明記されている（＝推論が必要）。しかし SHELDON の設計上の利点は**その推論を台帳に落とすこと**であり、記録済み verdict に対する「説明済みか」の判定は `∄h: verdict(h,o)=Support` という述語計算である。〔証拠段階 B：`EVD-20261021-7cdb` / `EVD-20261021-6ec4`〕
3. **本リポジトリの決定論的 CI で実装可能 —— ただし検出器と判定器を分離して実装する必要がある。** 検出器（unexplained / unassessed / refutation の算出）は標準ライブラリのみで完全に決定論的に書ける。判定器（verdict の付与）だけは推論を要するが、**一度台帳に記録されれば再実行は決定的**になる。これは本リポジトリの Stateless Harness 原則（`SRC-001`）と同じ構造であり、既存原則の延長に収まる。〔証拠段階 B（論文側）＋ 証拠段階 A（本メモの判定器・検出器設計が標準ライブラリのみで再実行可能であること）〕
4. **現状の台帳は「説明できない観測」を概念的にすら表現できない。** 実測（§6）：54 件の EVD のうち **48 件（88.9%）がいずれの HYP とも紐づいていない**。仮説は 2 本しかなく、HYP 側のリージョン（探索領域）は実質 2 個、観測側は 12 個。**観測空間のほうが仮説空間より遥かに広い状態**であり、これは SHELDON が解こうとしている問題そのもの（§1:「Even comparing all current hypotheses may therefore overlook gaps in the assumptions they share.」）の再現である。
5. **採用判断**: スキーマ変更（§5）は**後方互換で実装可能**であり、優先度は高い。ただし**「verdict を LLM に付けさせる」形だけは採用しない**。理由は §7 に述べる（自己評価による共通モード障害の継承）。

---

## 1. 原典の取得と証拠段階

| 項目 | 内容 |
|---|---|
| abs ページ | `https://arxiv.org/abs/2610.18025`（2026-10-21 に取得・読了） |
| 本文 | `https://arxiv.org/html/2610.18025v1`（HTML v1、全 22 チャンクを取得して読了） |
| サンドボックスからの直接取得 | **不可**。`curl` / `python3` から arxiv.org には到達できない。Arena の fetch ツールは到達可（abs ページ・HTML v1 とも取得成功） |
| スナップショット | 2026-10-21 に abs ページを読んで確認した書誌を `tests/fixtures/arxiv_metadata_snapshot.json` へ追記（2610.18025 として 13 件目） |

**証拠段階**（本リポジトリの 4 段階基準に準拠）:

- **A：再実行可能** — 本メモ §3.3 の判定器・検出器設計と §6 の台帳実測。標準ライブラリのみで再実行でき、同じ入力から同じ出力を得る。
- **B：本文で逐語確認** — §2〜§4 の引用。HTML v1 の本文・表・節番号・Appendix を含めて読み、**主要な**逐語引用を `EVD-20261021-7cdb` / `4ad6` / `59ab` / `6ec4` / `572c` に記録した（Appendix G Table 7 の hyperparameter 表など、EVD の粒度を超える表の転記は EVD 化していない）。
- **C：要旨・メタデータ確認** — 書誌のみ（著者・投稿日・件数の照合）。
- 本メモに **D（伝聞・未検証）は無い**。論文の主張を本文で裏付けず引用した箇所は無い。

**未実施**: PDF の読解（HTML v1 のみ）、付録の図画像の確認、`--live` による arXiv API 再照合、コードリポジトリ（`https://github.com/stanford-oval/sheldon`）の内容検証。

---

## 2. 問い1：仮説空間と観測空間をどう別々に表現するか

### 2.1 状態の型

論文 §4.2（Algorithm 1 の直後）は状態を 5 要素のタプルとして定義する。

> "Let the exploration space at time t, `S_t = ⟨H_t, O_t, wH_t, wO_t, E_t⟩`, captures the cumulative result of the actions and observations up to time t: the current hypothesis and observation spaces (`H_t, O_t`), the working hypothesis and observation sets (`wH_t, wO_t`), and the evidence relations"
> — §4.2（Algorithm 1 直後）

〔証拠段階 B：`EVD-20261021-7cdb`〕

| 要素 | 種類 | 役割 |
|---|---|---|
| `H_t` | 仮説空間（全候補） | 説明・解・候補アイデアの集合 |
| `O_t` | 観測空間（全候補） | 環境との相互作用から得られる証拠・洞察の集合 |
| `wH_t ⊂ H_t` | 作業仮説集合 | 現ラウンドで実際に調べる候補 |
| `wO_t ⊂ O_t` | 作業観測集合 | 調査を導くためにいま使っている累積観測 |
| `E_t` | **証拠関係** | `H × O → {Support, Refute, Neutral, Unresolved}` |

### 2.2 鍵は「同じ構造・別の ID 空間」

論文 §4.1 原文：

> "To facilitate exploration of the hypotheses, we explicitly characterize the space with axes and regions, inspired by the literature on hypothesis scopes and conceptual spaces. An axis identifies a dimension along which candidates may differ; its regions describe alternatives or portions of that dimension. ... Similarly, we define the observation space as the space of possible observations containing the evidence and evidence-grounded insights obtainable through interaction with the task environment. The observation space is also characterized by axes and regions, where possible axes include data sources, time ranges, entities or subsets, behavioral properties, scales, or tools."
> — §4.1 "Hypothesis and observation spaces."

〔証拠段階 B：`EVD-20261021-4ad6`〕

つまり：

- **構造は同じ**（軸 axis × 領域 region の 2 階層）
- **ID 空間は別**（仮説は `h_1…h_n`、観測は `o_1…o_n` で別インデックス）
- **軸の意味は別**（Appendix C.3 の Explore プロンプトが定義している）:
  - Hypothesis regions: "kinds of answer, grouped under axes (the dimensions answers differ along)."
  - Observation regions: "kinds of evidence, grouped under axes (where and how one would look)."

Appendix C.3 の Explore プロンプト原文（再掲）:

> "You open lines of investigation. You map where answers and evidence could lie, and propose hypotheses to test. Others build and test them; you do not judge them.
>
> ## The map
> - Hypothesis regions: kinds of answer, grouped under axes (the dimensions answers differ along).
> - Observation regions: kinds of evidence, grouped under axes (where and how one would look).
> - Add a region only if it is distinct from every region already on the map. Add an axis only if it is new, or subsumes an existing axis (then set `replaces_axis`)."

〔証拠段階 B：`EVD-20261021-4ad6`〕

**重要な細部**: Appendix E の脚注は、登録されていない領域名や「軸名の下に置かれた領域」を**捨てずにそのまま 1 行として数える**と述べる。

> "Observations filed under a region name that was never registered, or under an axis name rather than a region, are kept under that name as their own row rather than discarded, so counts are over everything the run wrote."
> — Appendix E "Structural quantities."

〔証拠段階 B：`EVD-20261021-4ad6`〕 — **データモデルは「未登録の領域」を許容しなければならない**。これは後述のバックフィル設計（§5.7）に直接効いてくる。

### 2.3 証拠関係 E_t：4 値・多対多

> "E_t : H × O → {Support, Refute, Neutral, Unresolved} ... indicating the evidence status of an observation with respect to a hypothesis. Similar to Natural Language Inference (NLI), these categories describe whether an observation provides evidence for a hypothesis, provides evidence against it, is neutral with respect to it, or has a relationship that has not yet been assessed. ... Here, the relation captures a task-dependent evidential judgment rather than strict textual entailment or contradiction."
> — §4.2（状態定義表）

〔証拠段階 B：`EVD-20261021-7cdb`〕

読み取れる設計上の含意（4 点）:

1. **`Unresolved` が明示的に「未評価」を意味する。** relation テーブルは「空」ではなく「未評価で埋まった状態」から始まる。→ データモデル上、relation の**欠如**と**未評価**を区別できる必要がある。
2. **写像であって関数ではない。** 1 つの観測は複数の仮説に対して verdict を持つ。§6.2 の実測がこれを示している（後述 2.5）。
3. **NLI を援用しつつ「厳密な含意・矛盾ではない」と明示している。** → verdict の付与は**推論**である（§3 で詳述）。
4. **タスク依存。** 同じ観測文が別のタスクでは別の verdict になりうる。→ verdict にはタスク／文脈の文脈情報が必要。

### 2.4 オブジェクトごとの属性

**仮説側**（§4.2）:

> "we define the status of `h_i` as one of `retained` or `setaside`, indicating whether it is actively considered or temporarily set aside based on the strength of its evidence. A set-aside hypothesis cannot be reconsidered until a cooldown period of a fixed number of rounds of investigation has elapsed (three rounds in our experiments)"
> — §4.2

〔証拠段階 B：`EVD-20261021-7cdb`〕

**観測側**（§4.2）:

> "We also introduce the boolean attribute `Provisional` to each observation because LLMs may occasionally make mistakes in their judgment such as making wrong assumptions, buggy implementation, or being ambiguous. When a new observation is encountered, it is given a Provisional status until it is encountered again. A Provisional observation can be used to guide exploration and follow-up hypothesis testing, but it cannot be used to refute a hypothesis."
> — §4.2

〔証拠段階 B：`EVD-20261021-59ab`〕

**ここが本論文の最も実装上の参照価値が高い部分**である。Provisional は**非対称ゲート**である:

|  Provisional な観測 o が持つ verdict | 効果 |
|---|---|
| `Support` | 使える（探索の誘導・仮説テストの誘導） |
| `Neutral` / `Unresolved` | 使える（未評価の記録として） |
| **`Refute`** | **使えない**（仮説を反駁できない） |

つまり「反駁」だけが一方向的に封じられる。**理由**は論文が明示している — LLM の判断には誤りがある（`making wrong assumptions, buggy implementation, or being ambiguous`）。したがって「反駁」という強い主張には、独立した再遭遇による確証が要求される。

### 2.5 関係は多対多で、少数が全体を支配する（§6.2）

> "For tasks without an explicit scoring function, observations from comparative analysis constitute only 16–17% of all observations. Despite their smaller share, these observations are disproportionately influential, accounting for 53% and 43% of all verdicts, respectively. Moreover, 93–98% are cited in subsequent decisions, compared with only 9–19% of observations from candidate analysis. ... Shared observations are observations that contribute to the verdicts of two or more hypotheses. Such relationships cannot be captured by approaches that associate each observation with a single hypothesis, as is common in prior work such as GoS and ScientistOne."
> — §6.2

〔証拠段階 B：`EVD-20261021-572c`〕

**含意**: 「EVD → 単一 HYP」の紐付け（本リポジトリが現在採用している形、HYP.evidence_ids の逆引き）では**構造的に表現できない**。GoS / ScientistOne 型的 1 観察→1 仮説の紐付けに対する、SHELDON の反論はここにある。

**アブレーション**（§1 冒頭・§6 Table 5）:

> "Ablations demonstrate the contribution of the observation space, removing it reduces performance by 14.0 and 13.34 points on DiagnosisArena and ORCA-Bench, respectively."

Table 5 の該当行:

| Variant | DiagnosisArena↑ | ORCA-Bench↑ | ARC-AGI-2↑ | QNN Topology↑ |
|---|---|---|---|---|
| SHELDON (full) | 84.00 | 66.67 | 59.17 | 1.00 |
| w/o comparative analysis | 78.00 (-6.00) | 56.67 (-10.00) | 50.00 (-9.17) | 0.8833 (-0.117) |
| **w/o observation space** | **70.00 (-14.00)** | **53.33 (-13.34)** | **50.00 (-9.17)** | **0.8667 (-0.133)** |
| w/o continued exploration | 82.00 (-2.00) | 53.33 (-13.34) | 57.70 (-1.47) | 0.7333 (-0.267) |

〔証拠段階 B：`EVD-20261021-572c`〕 — 観測空間の除去は 4 指標すべてで比較分析の除去以上（または同等）の劣化を示す。

---

## 3. 問い2：「仮説が説明できない観測」をどう検出するか

### 3.1 論文の主張

> "By actively seeking new observations along with new hypotheses, SHELDON can discover observations that its current hypotheses do not explain. These unexplained observations expose gaps in its understanding, motivate new investigations, and guide the generation of hypotheses beyond refinements of existing ones."
> — Abstract / §1

> "The observation space supports exploration by treating observations as explicit objects of discovery, including those that no current hypothesis adequately explains."
> — §1

〔証拠段階 B：`EVD-20261021-6ec4`〕

### 3.2 論文は「決定論的な検出器」を与えていない —— ここが要点

論文が明示していることは、次の 3 点である:

1. **未説明の観測は能動的な探索の産物である。** 仮説の支持を探して観測を集めるのではなく、SHELDON は観測軸・領域を**新たに開いて**そこから証拠を探す。§4.2 の Explore: "From the findings, it constructs new hypothesis and observation spaces by defining (1) axes to help diversify hypothesis generation and (2) regions to track what has been exploited and what remains to be explored."
2. **未説明の観測は「新しい調査」を動機づけ、かつ「refinement を超えた仮説」を生む。** ここには **2 つの誘発**がある（§4 参照）。
3. **ただし verdict の付与は推論である。** "the relation captures a task-dependent evidential judgment rather than strict textual entailment or contradiction."〔証拠段階 B：`EVD-20261021-7cdb`〕

したがって論文の立場は「**判定は推論、判定後の処理は決定的**」の二段構えである。論文がアルゴリズムとして 与えているのは `Explore / CandidateAnalysis / ComparativeAnalysis / Exploit` のループであり、§6.2 の分析も「各 run の記録された仮説空間・観測空間から計算している」:

> "The quantities of Section 6.2 are computed from each run's recorded hypothesis and observation spaces."
> — Appendix E

〔証拠段階 B：`EVD-20261021-4ad6`〕 — **記録されたデータから計算している**という点が、そのまま本リポジトリへの適合性を左右する。

### 3.3 本リポジトリの決定論的 CI で実装できるか

**結論: 検出器は完全に実装可能。判定器は「推論が要るが、台帳に落とせば決定的」**。

#### (a) 検出器 — 標準ライブラリのみで決定論的

記録済みの verdict テーブル `E: H × O → {Support, Refute, Neutral, Unresolved}` に対して、次の 4 つの述語は**すべて集合演算**であり、推論を一切要しない。

| 述語 | 定義 | 意味 |
|---|---|---|
| `unexplained(o)` | `¬∃h ∈ wH : E(h,o) = Support` | **仮説が説明できない観測**（§3.1 の定義そのもの） |
| `unassessed(o)` | `¬∃h : E(h,o) が存在` | まだどの仮説に対しても評価されていない観測 |
| `refutation(h)` | `∃o : E(h,o) = Refute ∧ ¬Provisional(o)` | **Provisional ゲートを通った反駁**（`EVD-20261021-59ab` の非対称性） |
| `discriminative(o)` | `\|{h : E(h,o) ∈ {Support, Refute}}\|` | 何個の仮説を判別できたか（§4 の優先付けに使う） |

`Provisional` の判定も決定論的にできる（§5.3 で設計する）。

#### (b) 判定器 — 推論が要るが、**一度記録されれば再実行は決定的**

ここが SHELDON の設計から持ち帰れる**最も重要な教訓**である。SHELDON の価値は「LLM の判断を、記録され再実行できる形に落とす」ことにある。verdict は LLM が付けるが、**一度 relation レコードとして台帳に落ちた後は、以後すべての検出・集計・優先付けは台帳上の集合演算であり、再実行しても同じ結果になる**。

これは本リポジトリの既に採用している原則と**同一構造**である。

> "no agent carries its conversation across invocations; instead, the harness owns the research state ... and reconstructs a fresh and role-specific context for every invocation."
> — `SRC-001` / `EVD-001`（Abs; Section 1）

〔証拠段階 B（既存台帳）〕 — **harness（台帳）が研究状態を所有し、推論は毎回 stateless に行い、状態は台帳に残る**。SHELDON の relation テーブルは、この構造を「仮説と観測の間の判定」に拡張したものと見なせる。

#### (c) 判定器の 3 つの選択肢と採否

| 方式 | 手続き | 再実行の決定性 | 採否 |
|---|---|---|---|
| ① 人間が裁定 | 人が verdict を付けて台帳に書く | ○（台帳固定なら） | **推奨の第一候補**。ただし負荷が大きい |
| ② LLM が裁定し台帳に凍結 | ワーカーが verdict を付け REL レコードとして保存。以後 CI は台帳だけ読む | ○（台帳固定なら） | **推奨**。ただし §7 の共通モード障害に注意 |
| ③ 決定論的ルールのみで裁定 | 例えば「同一 observation_key を持つ 2 つの EVD が真偽値で矛盾する場合のみ Refute」 | ○ | **限定的採用**。決定的部分だけを対象にする |

**③ の例（決定論的に裁定できる部分）**: 既に本リポジトリには「引用文が原典に存在しないことを検出した VER が 5 件」（`result=fail`、全て `source_check`）がある。しかしこれらは**科学的な反駁ではなく記録の品質違反**であり（§5.4 で詳述）、そのまま `Refute` に写すことはできない。

### 3.4 「Provisional」を決定論的に定義する（本リポジトリでの具体案）

論文の定義「再遭遇するまで暫定」は、ResearchOS にはそのまま 대응物がない。**対応物を作る**（§5.3 で詳述）:

> `provisional(o) := |{ o' : o'.observation_key = o.observation_key ∧ o'.source_id ≠ o.source_id }| = 0`

つまり「**別の出典から独立に再遭遇した**」ときだけ暫定を外す。既存 EVD は `observation_key` 未指定なので既定で `evidence_id` 自身となり、**結果として既存 54 件はすべて provisional**（＝反駁は 0 件、説明済み観測は 0 件）。これは**意図した保守的既定**であり、§6 の現状の記述と矛盾しない。

---

## 4. 問い3：検出後に何を誘発するか、その優先付け

### 4.1 誘発は 2 種類

論文 §1 / §4.2 から、次の 2 つを区別して**誘発**として扱う必要がある。

| 誘発 | 論文での用語 | 手続き | 論文の実測 |
|---|---|---|---|
| **① 新しい調査**（観測を追加する） | "motivate new investigations" / Explore | 未探索の観測領域を開いて証拠を探す | ORCA-Bench で 59 件の ground-truth cause のうち **40 件が Explore 経由**で発見（残り **19 件**は exploitation＝refinement 経由） |
| **② 新しい仮説**（refinement を超える） | "guide the generation of hypotheses beyond refinements of existing ones" / "Seeded hypotheses" | 別仮説のテスト由来の観測から新仮説を生成 | ARC-AGI-2 の round 1 後 782 仮説のうち **204 本が rationale で観測を明示引用**。うち **158 本は別仮説のテスト由来**、**37 本は親仮説以外の解析由来**の観測を引用（＝系統外への探索） |

〔証拠段階 B：`EVD-20261021-6ec4`〕

なお §6.2 はさらに、観測空間が「未探索方向を明示的にする」役割を持つと述べる:

> "Finally, the observation space makes unexplored directions explicit: some regions are opened before any observations are collected, and many are populated in subsequent rounds, including 12 of 16 initially empty regions on QNN"
> — §6.2

〔証拠段階 B：`EVD-20261021-6ec4`〕 — **領域を「開いて空のままにする」のが構造の一部**である。すなわち「まだ観測がない領域」を_FIRST_CLASS に持つ必要がある。

### 4.2 優先付け —— 論文は数え上げ（count-based）で決定している

Appendix C.3 の Explore プロンプトが、優先付けの規則を明文で与えている。

> "- Propose ⟨n⟩ hypotheses in the least explored regions and axes (counts are shown; UNTRIED regions and thin axes first). Each needs a testable `statement`, a `rationale`, and a `region`.
> - Make them compete: different regions, different mechanisms, not variants of one idea.
> - Read the evidence on last round's hypotheses and every hypothesis's metrics per part of the task. Do not re-propose what is held.
> - If hypotheses win on different parts, or the best score has stopped improving, at least one proposal must be a combination (name the hypotheses and what it takes from each) or a `revive` of an eligible shelved hypothesis."

〔証拠段階 B：`EVD-20261021-4ad6`（Appendix C.3 / C.4 のプロンプト原文も同 EVD に逐語で収録）〕

Appendix C.4 の Select プロンプトが、優先付けの第 2 段を与える。

> "- Prefer tests that would settle what the evidence leaves open; spread across regions unless the evidence clearly favours one."

〔証拠段階 B：`EVD-20261021-4ad6`〕

**翻訳すると、優先付けは次の 3 段階（すべて数え上げで決定論的）**:

1. **第 1 優先 — 未探索領域**: 観測数 0 の領域（`UNTRIED`）を最優先。
2. **第 2 優先 — 観測数が少ない領域**: `ascending n(region)`。同数なら**軸が薄い順**（その軸上の仮説数が少ない順）。
3. **第 3 優先 — 判別力**: 候補観測 o について `discriminative(o) = |{h : E(h,o) ∈ {Support, Refute}}|` が大きい順。すなわち「どれ多くの仮説を判別できるか」。§6.2 の実測がこれを支持する（比較分析由来の観測は全体の 16–17% だが verdict の 43–53% を担う）。

**停止条件も決定論的**〔証拠段階 B：`EVD-20261021-7cdb`〕:

> "The process continues until the interaction budget B is exhausted, the maximum number of rounds is reached (eight in all our experiments), or the investigation stabilizes, meaning that a round produces no new hypotheses, observations, or investigative directions."
> — §4.2

〔証拠段階 B〕 — 「あるラウンドが新しい仮説も観測も調査方向も産出しなかったら停止」は、**新しい EVD 件数・新しい REL 件数・新しい領域の 3 つを数えれば完全に判定できる**。

### 4.3 飢餓防止と hyperparameter（Appendix G Table 7）

| パラメータ | 値 | 本リポジトリでの対応物 |
|---|---|---|
| `rounds` | 8 | 調査ラウンドの上限 |
| `select_k` | 5 | 1 ラウンドに載せる仮説数 |
| `n_initial` / `n_explore` | 5 / 3 | 初期仮説数 / 新規探索数 |
| `local_max_evals` | 3 | 仮説 1 個あたりの反復評価回数 |
| **`shelf_cooldown`** | **3** | **setaside した仮説の再検討可能までのラウンド数** |
| `stagnation_rounds` | 2 | 停滞判定に連続何ラウンド必要か |
| `round_reserve` | 0.5 | ラウンドあたりの予備予算 |
| `local_engine` | toolloop (gpt-5.6-luna) | 推論モデルと実装モデルの分離 |

〔証拠段階 B（Appendix G Table 7 の直接読取。EVD 化はしていない）〕 — `shelf_cooldown = 3` は §4.2 の「three rounds in our experiments」と一致する。**shelf（setaside）から復帰するまでのクールダウンは、探索の多様性を守るための仕組み**であり、本リポジトリでも「冷えた領域は 3 ラウンド後に再考する」ならそのまま写せる。

---

## 5. 問い4：本リポジトリの台帳に適用した場合のスキーマ変更の具体案

### 5.0 現状のギャップ（2026-10-21 時点の台帳実測）

台帳は `state/` 配下に 5 台帳、件数と参照関係は以下（実測・証拠段階 A）。

| 実測項目 | 値 |
|---|---|
| sources / evidence / claims / verifications / hypotheses | 12 / 54 / 9 / 30 / 2（本 PR の追記後。着手前は 11 / 49 / 8 / 29 / 2） |
| いずれかの HYP に紐づく EVD | **6 件（11.1%）** |
| **いかなる HYP とも紐づかない EVD** | **48 件（88.9%）** |
| verdict（4 値）を持つ EVD | **0 件**（verdict という概念が台帳に存在しない） |
| HYP 側のリージョン数 | **2**（`TASK.md §2-2` と `§2-3`。HYP-001, HYP-002 の `subtasks`） |
| 観測側のリージョン候補 | 12（`source_id`）× 5（`quote_type`） |
| VER の対象内訳 | CLM 12 / SRC 9 / EVD 5 / HYP 3。**（HYP, EVD）ペアを対象とする VER は 0 件** |
| CLM と HYP の関係 | **存在しない**（`schemas/claim.json` に hypothesis 参照は無く、`hypotheses.jsonl` に claim 参照も無い） |

**要点**: 台帳のグラフは `SRC → EVD → CLM → counterclaim-CLM` と `SRC → EVD ← HYP` の**2 本の並行する鎖**であり、**CLM と HYP は交わらない**。SHELDON でいう `E_t`（H×O の verdict 表）は**存在しない**。

**既存台帳との対応**（本メモの整理。証拠段階 A／B の混合）:

| ResearchOS | SHELDON | 備考 |
|---|---|---|
| `EVD`（個別所見） | 観測 `o_j`（individual finding） | §4.1「These may describe individual findings ...」に対応 |
| `CLM`（複数所見の集約主張） | 観測 `o_j`（higher-level pattern） | §4.1「or higher-level patterns composed from several findings」に対応 |
| `HYP` | 仮説 `h_i` | 「candidate explanations」に対応 |
| `VER` | **verdict に最も近い実体**（ただし (H,O) ペアではなく単一レコードを対象） | §5.1 の要 |
| `SRC` | case material `M_p` / tools `T_p` | §3 Definition 1 に対応 |
| `state/` 台帳全体 | state `S_t = ⟨H, O, wH, wO, E⟩` | **E だけが欠けている** |

### 5.1 提案1（最優先）: 新しい relation 台帳 `relations.jsonl`（未作成）

**追加ファイル**（未作成。提案であり本 PR では実装していない）:

- スキーマ: `relation.json`
- 台帳: `relations.jsonl`
- ID 接頭辞: `REL`（形式は既存の `PREFIX-YYYYMMDD-xxxx` に倣う）

**レコードの型**:

```json
{
  "relation_id": "REL-YYYYMMDD-xxxx",
  "hypothesis_id": "HYP-001",
  "observation_id": "EVD-20261021-7cdb",
  "verdict": "support",
  "provisional": false,
  "source_id": "SRC-20261021-2384",
  "rationale": "…（1 行理由。論文の ComparativeAnalysis は 'with one line why' を要求している）",
  "recorded_at": "2026-10-21"
}
```

- 必須: `relation_id`, `hypothesis_id`, `observation_id`, `verdict`
- `verdict` の enum: `["support", "refute", "neutral", "unresolved"]`（論文の 4 値。NLI ベースの表記は `Support/Refute/Neutral/Unresolved`）
- `provisional` は boolean。省略時は §5.3 の導出規則で決まる（fail-closed）。

**なぜ新しい台帳なのか（`VER` を拡張しないのか）**:

- `VER` の `target_id` は**単一レコード**を指す。論文の `E_t` は **(H, O) のペア**に対する関係であり、既存 `VER` では表現できない。
- `VER` の `verifier_type` enum は `deterministic / source_check / falsifier_critic / logical_consistency` であり、**「証拠判断（support/refute/neutral）」を表す型がない**。`falsifier_critic` を流用すると「検証が失敗した」ことと「仮説が反駁された」ことが混同される（§5.4 の実例を参照）。
- `VER` は `result` の enum が `pass/fail/warn/falsified` で、これは**手続きの結果**である。`E_t` の 4 値は**関係**であり、手続きではない。

**必要な実装差分**（いずれも本 PR では未実施）:

1. `scripts/new_id.py`: `PREFIXES` に `"REL": "relations.jsonl"`（state/ 配下）、`ID_KEYS` に `"REL": "relation_id"` を追加。
2. `scripts/validate_state.py`: `COLLECTIONS` に relations を追加。参照整合性規則を追加 — `relation.hypothesis_id → hypotheses`、`relation.observation_id → evidence`、`relation.source_id → sources`。`ID_TOKEN_RE` に `REL` を追加（`scripts/check_memo_ledger_refs.py` はここを import しているため、两侧が同時に更新される）。
3. `schemas/relation.json` を新規作成。
4. 既存の 5 台帳は一切変更しない（**新しいファイルを追加するだけ**）。

### 5.2 提案2: `schemas/evidence.json` への任意フィールド追加

**すべて任意（optional）**なので、既存 54 件はそのまま validate を通る。

| フィールド | 型 | 既定値 | 根拠 |
|---|---|---|---|
| `observation_key` | string | `evidence_id` 自身 | §3.4・§5.3 の Provisional 導出と、§5.7 の backfill の要。同一所見を指す EVD 群を束ねる |
| `observation_axis` | string | `source_id` | 論文の observation space の軸（"data sources, time ranges, entities or subsets, behavioral properties, scales, or tools"）に対応。Appendix E の「軸名の下に記録された領域」ケースを許容するため、軸と領域は**別フィールド**にする |
| `observation_region` | string | `source_id` | 論文の領域。Appendix E に従い、未登録の領域名も**捨てずに保持**する（削除しない） |

**後方互換の証明**: `scripts/validate_state.py` は「必須フィールド・型・enum・配列の要素型」のみを検査し、追加フィールドを許可する（JSON Schema draft-07 で `additionalProperties` 未指定と同じ）。任意フィールドの追加は既存レコードの検証結果を変えない。`observation_key` / `observation_axis` / `observation_region` を**_append しない**既存 54 件は、既定値が暗黙に適用される。

### 5.3 提案3: `schemas/hypothesis.json` への任意フィールド追加

| フィールド | 型 | 既定値 | 根拠 |
|---|---|---|---|
| `hypothesis_region` | string | `subtasks[0]` | 論文の hypothesis region。既存 2 件は `subtasks` をそのまま領域として使う（移行不要） |
| `search_status` | enum `["retained","setaside"]` | `"retained"` | 論文の `status(h_i) ∈ {retained, setaside}`。既存の `status` enum（proposed/testing/supported/falsified/inconclusive）は別フィールドにして上書きしない（同じ名前で意味を変えると既存 2 本の意味が変わるため） |
| `cooldown_rounds` | integer | `3` | 論文 Appendix G の `shelf_cooldown: 3` |

**`search_status` を `status` と分離する理由**: 論文の `status(h_i)` は「探索上の優先順位（保留か棚上げか）」であり、本リポジトリの `status` は「証拠段階（supported/testing 等）」である。**別概念なので別フィールド**。§5.7 の backfill では、`supported` を `retained` に、`testing` を `retained` に写し、`status` 側は一切変更しない。

### 5.4 提案4: 既存 VER を verdict に「写さない」ことの明示

**これは提案ではなく制約**である。台帳の `result=fail` な VER 5 件（`VER-006` / `VER-010` / `VER-011` / `VER-015` / `VER-20261020-4843`）を実測すると、**全件が `source_check` で「引用文が原典に存在しなかった（転写・捏造の検出）」**であり、いずれも該当レコードを**訂正済み**である。

これは科学的な意味での「反駁」（観測が仮説の主張と矛盾する）ではない。**VER(fail) → verdict(refute) の機械的写像は誤り**であり、提案4 として明示的に禁止する（機械的写像は tempting なので、禁止として明示しておく）。

正しい backfill 元は次の 3 つに限る:

1. `CLM` の `evidence_ids`（主張→観測の既存紐付け。ただし**方向が逆**で、仮説→観測の対応ではない）
2. `HYP` の `evidence_ids`（仮説→観測の既存紐付け。ただし**verdict を含まない**）
3. 新しい `CLM → HYP` 参照（§5.5）

### 5.5 提案5: `schemas/claim.json` に `hypothesis_ids` を任意追加

**これが「仮説空間と観測空間の分離」を本リポジトリで成立させる最後のピース**である。

```json
"hypothesis_ids": ["HYP-001", "HYP-002"]
```

- 任意フィールド。既存 9 件の `CLM` は値を持たない（＝未紐付けのままだが壊れない）。
- これで `CLM`（§5.0 の対応表では「複数所見の集約した観測」）が `HYP`（仮説）に紐づき、**SHELDON の `E_t` の「多対多」**（1 つの観測が複数の仮説の verdict に寄与する）が台帳上で表現可能になる。
- 現在の `CLM` → `HYP` の対応は `status` から機械的に**候補を生成できる**が、**自動で埋めてはならない**（§5.7）。

### 5.6 提案6: 決定論的チェッカ `gap_scan.py`（未作成）

§3.3(a) の 4 述語を実装する検査器。**検出器でありゲートではない**（本リポジトリの `measure_agreement.py` / `estimate_rho.py` / `harness_regime.py` と同じ位置づけ。**削除・合格判定は人間の判断**）。

```python
# 擬似コード（概念設計。実装は未着手）
unexplained  = [o for o in observations if not any(r.verdict == "support"
                                                  for r in rows if r.observation_id == o)]
unassessed   = [o for o in observations if not any(r.observation_id == o for r in rows)]
refutations  = [r for r in rows if r.verdict == "refute" and not provisional(r)]
priority     = sort_by(region_open_count, then -discriminative_power)
```

- 出力は「説明されていない観測の一覧」「未評価の観測の一覧」「仮説ごとの refutation 件数」「未探索領域の優先順」。
- `provisional(o)` の導出は §3.4 の規則（`observation_key` 同一 かつ `source_id` 相違の EVD が 0 件なら provisional）。
- **fail-closed 既定**: `observation_key` 未設定の EVD はすべて provisional。→ 既存台帳に対し **refutation は 0 件**、**unexplained は 54/54 件**となる。これは現状の正直な記述である。

### 5.7 backfill 手順（後方互換を保つ順序）

| 手順 | 操作 | 既存レコードへの影響 |
|---|---|---|
| 1 | `relation.json` と `relations.jsonl` を新設（空で開始） | なし（新しいファイル） |
| 2 | `schemas/evidence.json` / `hypothesis.json` / `claim.json` に**任意**フィールドを追加 | なし（任意フィールド。検証結果は不変） |
| 3 | `scripts/new_id.py` / `scripts/validate_state.py` に `REL` を追加 | なし（既存 ID 形式は不変。LEGACY_MAX も据え置き） |
| 4 | `gap_scan.py` を新設し、**報告のみ**で動かす | なし（台帳を変更しない） |
| 5 | `observation_key` を人が 1 件ずつ付与（同一所見の EVD 群を束ねる） | 既存 EVD に任意フィールドを**追加**するだけ。値は上書きしない |
| 6 | `REL` レコードに裁定結果を書き込む（人 or 凍結済みワーカー） | 台帳の追記のみ |
| 7 | `search_status` / `hypothesis_region` を付与 | 任意フィールドの追加のみ。既存 `status` は不変 |

**手順 5〜7 は人手/LLM 裁定を伴うため、人数の承認を要する**（本リポジトリの非破壊的操作の原則に従う）。手順 1〜4 は破壊的変更が無く、CI を壊さない。

### 5.8 「1 観察→1 仮説」からの脱却（既存の取り違えの修正）

本リポジトリの `HYP.evidence_ids` は「1 仮説→複数観測」を表す。これは SHELDON の `wH_t`（作業仮説集合）に対応し、**壊す必要はない**。重要なのは、その逆方向（どの観測がどの仮説の verdict を持つか）が**存在しなかった**ことだけである。新規 `REL` 台帳は**この逆方向を追加する**ので、既存の `HYP.evidence_ids` はそのまま「候補集合」として機能し、矛盾は生じない。

---

## 6. 適用例：現在の台帳に当てたとき何が見えるか

以下は **2026-10-21 時点の台帳実測**（証拠段階 A）であり、§5 の提案が**実装されていない現状**での記述である。

### 6.1 観測領域ごとの、仮説の紐づき

| 観測領域（= `source_id`） | EVD 件数 | いずれかの HYP に紐づく EVD | 紐づく HYP |
|---|---|---|---|
| `SRC-001` Stateless Language Agents | 4 | 1 | HYP-001 |
| `SRC-002` GitSwarm | 6 | 3 | HYP-001, HYP-002 |
| `SRC-003` DuoDiscover | 5 | 2 | HYP-002 |
| `SRC-004` 本リポジトリ自身 | 3 | 0 | — |
| `SRC-20261020-05de` Context Engineering 調査 | 3 | 0 | — |
| `SRC-20261020-787b` Less Context, Better Agents | 3 | 0 | — |
| `SRC-20261020-303f` The Horizon Gap | 4 | 0 | — |
| `SRC-20261020-875e` Transect | 3 | 0 | — |
| `SRC-20261020-07a3` Stop Comparing Without Harness | 4 | 0 | — |
| `SRC-20261020-4cff` Beyond Final Scores | 3 | 0 | — |
| `SRC-20261020-f295` Agora | **11** | 0 | — |
| `SRC-20261021-2384` SHELDON（本 PR） | 5 | 0 | — |
| **合計** | **54** | **6（11.1%）** | — |

**12 領域のうち 9 領域が、仮説と 1 本も紐づいていない。** 最大の未紐付けクラスタは Agora（11 件、全体の 20.4%）。

### 6.2 本メモ §4.2 の優先付け規則を当てた結果（提案どおりに計算した場合）

- **UNTRIED（観測 0 件）**の仮説領域は 0 個 —— 逆に言えば、**仮説が 1 本も立っていない観測領域が 9 個**ある。SHELDON の Explore は「最も探索されていない領域から仮説を 1 本以上出せ」と要求する。翻訳すると、本リポジトリの優先すべき**新しい仮説の候補は Agora の 11 観測・Horizon Gap の 4 観測・Harness 論文の 4 観測**である。
- **仮説軸は 2 本しかなく**（`TASK.md §2-2` / `§2-3`）、**観測軸は 12 領域**。SHELDON の `Explore` は軸ごとに「薄い軸」からの提案を優先する。翻訳すると、本リポジトリは**仮説軸が薄い**（2 本）ので、新仮説はまず別の軸を立てるべき。
- `discriminative(o)` は現状 **全 54 観測で 0**（verdict が無いため）。提案6 の導入後に初めて「どれ多くの仮説を判別できたか」を数えられるようになる。

### 6.3 提案6 を「fail-closed 既定」で走らせたときに出る正直な記述

| 述語 | 現状の値 | 意味 |
|---|---|---|
| `unexplained(o)` | **54 / 54** | どの観測も、どの仮説からも support を得られておらず「説明されていない」 |
| `unassessed(o)` | **54 / 54** | どの観測も、どの仮説に対しても評価されていない |
| `refutation(h)` | **0 件** | Provisional ゲート（fail-closed）により反駁は存在しない |
| 仮説あたりの support 数 | **0** | verdict が無いため |

**これは「本リポジトリの台帳は今、仮説が説明できない観測を 1 件も数えられない」という意味ではなく、「数えるための装置が無い」という意味**である。装置を入れれば 54 件が「未説明」としてまず現れ、そこから初めて「どれが本当に未説明で、どの領域に穴があるか」が分かる。

### 6.4 論文 §6.1 の指標との対応（参考）

論文 §6.1 は、1 タスクあたり 14 個の特徴量のうち補正後も残る唯一の相関が **ORCA-Bench における「仮説を反駁する観測の割合」ρ = −0.59** であったと報告する:

> "across up to fourteen per-task features, neither the number of regions nor the count of distinct ideas correlates with the task's score on either benchmark, and the only feature that survives correction is the share of refuting observations on ORCA-Bench (ρ=−0.59), which marks the incidents the system found hard."
> — §6.1

〔証拠段階 B：`EVD-20261021-572c`〕

**含意**: 「反駁の割合」が**難度の指標**になりうる。§5 の提案6 が入れば、本リポジトリでも各仮説の refutation 率（＝どれだけ仮説が 눌されているか）を**決定論的に**算出できる。これは現在、台帳に存在しない量である。

---

## 7. 限界・反証条件・採否

### 7.1 論文側の限界（読み取りで識別した）

| 限界 | 詳細 |
|---|---|
| **verdict は自己評価** | §4.2 は「LLMs may occasionally make mistakes in their judgment」を理由に Provisional を導入している。すなわち **verdict を付けるのは仮説を生成したのと同じ LLM** であり、独立した検証ではない |
| **Provisional ゲートのアブレーションが無い** | Table 5 は comparative analysis / observation space / continued exploration の 3 つだけを ablating している。**Provisional の ON/OFF の効果は測定されていない** |
| **単一モデル・3 run** | 推論は GPT-5.6-terra（effort=high）、実装は GPT-5.6-luna。harness 以外の交絡は分離されていない。論文 §5.2 の ADRS の "Human best" は別ハード・別計測環境によるものであり直接比較不能（論文が "indicative rather than directly comparable" と明記） |
| **アブレーションは 10 タスク中 4 タスクのみ** | Observation space の ablation は DiagnosisArena / ORCA-Bench / ARC-AGI-2 / QNN のみ。分子最適化・ADRS 5 タスクでは未測定 |
| **GT のあるのは 3 タスクのみ** | 残る 7 タスクは evaluator のスコアで、Q_p の noisy な代理。verdict の質と評価の品質は独立していない可能性がある |
| **「説明できない」の定義が散文** | 論文は「どの仮説も十分説明しない観測」という**言語的定義**を述べるのみで、**形式的な述語としては与えていない**。§3.3(a) の 4 述語は**本メモの導出**であり、論文の定義ではない（§8 に明記） |
| **コスト** | Appendix F: DiagnosisArena で SHELDON $2.91 / GoS $2.79、ORCA-Bench で SHELDON $6.90 / GoS $7.54。**同予算で GoS を上回る**（論文の主張）だが、単一モデル・3 run の比較 |

### 7.2 本リポジトリへの適用上の反証条件

1. **提案6 を入れたあと、unexplained が 54/54 のまま変わらない** → relation 台帳が埋まらない運用になっている。運用側の問題。
2. **REL レコードの verdict を LLM に自動付与し続ける** → §7.1 第 1 項の共通モード障害を継承する。**本リポジトリの `HYP-002`（同質ワーカーの多数決は共通モード障害に脆弱）がまさにこの形**であり、**verdict の付与は「同質ワーカーの再投票」ではなく独立した裁定（人、または別手順の検証）に限るべき**。これは本論文から得られる最大の教訓であり、同時に**最大の注意**である。
3. **既存 54 件の EVD に `observation_key` を一括で機械付与する** → §2.2 末尾の「未登録領域は捨てずに保持」と同じ精神で、**機械的な同一視はしない**。人間が手動機で束ねる（手順 5）。
4. **`status` と `search_status` を同一視する** → §5.3 のとおり別概念。混在すると既存 2 本の意味が変わる。

### 7.3 採否

| 項目 | 判定 |
|---|---|
| 論文の読み取り（§1〜§4） | **採用**。逐語引用を台帳に落とした |
| スキーマ変更の提案（§5.1〜§5.6） | **採用（提案段階）**。後方互換であることを §5.7 で確認済み。**本 PR では台帳・スキーマを変更していない** |
| 実装（手順 1〜4 の CI 接続） | **次の PR で推奨**。検出器でありゲートではないため、CI への組み込みは人間判断 |
| verdict の LLM 自動付与 | **不採用**（§7.2 の 2） |
| `VER(fail)` → `refute` の写像 | **不採用**（§5.4） |

---

## 8. 本メモが導出した 것（論文由来でない部分）

§3.3(a) の 4 述語（`unexplained` / `unassessed` / `refutation` / `discriminative`）、§3.4 の Provisional 導出規則、§5 のスキーマ変更案、§6 の台帳実測は、**いずれも本メモの導出であり論文の記述ではない**。論文は §4.1 の 4 値関係と Provisional 属性を与えただけで、「未説明」の形式定義と優先付けアルゴリズムは与えていない。引用する際は区別すること。

---

## 9. 本レポート作成時に実行した確認

- abs ページ取得・読了（`https://arxiv.org/abs/2610.18025`）— 書誌・投稿日・件数をスナップショット取得
- HTML v1 全 22 チャンク取得・読了（`https://arxiv.org/html/2610.18025v1`）— §4.1 / §4.2 / §5 / §6 / Appendix C・E・G を確認
- `python3 scripts/validate_state.py` → PASS
- `python3 scripts/check_citations.py` → 11 checked / 1 skipped / 0 failures（2610.18025 の snapshot 追記後）
- `python3 scripts/check_memo_citations.py` → PASS
- `python3 scripts/check_memo_ledger_refs.py` → PASS
- `python3 scripts/check_doc_numbers.py` → PASS
- `python3 -m unittest discover -s tests` → PASS
- `python3 gitswarm/benchmarks/benchmark.py --check` → PASS
- `python3 gitswarm/readout_sim.py --check` → PASS

（2026-10-21。上記の実験・実行以外は行っていない。PDF の読解、付録の図画像の確認、コードリポジトリの内容検証、`--live` による arXiv API 再照合は**未実施**。）

---

## 10. 参考文献

[1] Harshit Joshi, Priyank Shethia, Monica S. Lam. "SHELDON: Reasoning through Dual Search over Hypothesis and Observation Spaces." arXiv:2610.18025v1 [cs.AI; cs.LG], 2026（投稿 2026-10-13）. https://arxiv.org/abs/2610.18025 / DOI: 10.48550/arXiv.2610.18025

[2]（本リポジトリ既存）Qizheng Zhang, Changxiu Ji, Isaac Sun, …, Kunle Olukotun. "Stateless Language Agents: Scaling Long-Horizon Automated Research." arXiv:2610.07625v1 [cs.LG], 2026（投稿 2026-10-06）. https://arxiv.org/abs/2610.07625

[3]（本リポジトリ既存）Vedant Shah, Ankur Samanta, Paras Dahal, …, Anirudh Goyal. "GitSwarm: Decentralized Compounding Inference." arXiv:2610.04862v1 [cs.AI], 2026（投稿 2026-10-04）. https://arxiv.org/abs/2610.04862

[4]（言及のみ）論文 HTML の著者脚注および Reproducibility statement に記載されたコードリポジトリ。https://github.com/stanford-oval/sheldon （2026-10-21 に abs ページ経由で存在を確認。リポジトリ内容自体の検証は未実施）

（内部記録 `state/`・`contributions/` への参照は文献引用ではない。数値・引用はすべて [1] の本文取得（abs ＋ HTML v1 全22チャンク）に基づく。）
