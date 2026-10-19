# Arena.ai × GitHub 連携 実機検証レポート：できること・できないこと一覧

Arena.ai Agent Mode の GitHub 連携（Connections）における実機検証結果に基づき、エージェント環境から**「できること（利用可能な機能）」**と**「できないこと（制約事項・不可機能）」**を体系的に整理したレポートです。

---

## 1. エグゼクティブサマリー

Arena.ai の GitHub 連携は、**「コードの読み書き・CIによる自動検証・Pull Requestを通じた開発サイクル」が完全に成立する実用レベル**に達しています。
エージェント単独でブランチ作成、ソースコード編集、テスト・ビルドワークフローの構築、PR 作成・レビューコメントまでの一連の開発業務を完遂できます。

一方で、**「Issue の変更管理」**、**「Actions の手動実行」**、**「外部ストレージ（Blob）に依存する生ログ・成果物の直接ダウンロード」** に明確な制約が存在します。これらはバグではなく、**GitHub App の付与権限**および**Arena サンドボックスのセキュリティポリシー（通信先制限）**に起因するものです。

---

## 2. 接続アーキテクチャと検証環境

- **検証日時:** 2026-10-19
- **検証環境:** Arena.ai Agent Mode サンドボックス（Debian GNU/Linux）
- **対象リポジトリ:** [`aiselfmyself/ResearchOS`](https://github.com/aiselfmyself/ResearchOS)（Public リポジトリ）
- **使用ツール:** `git` (v2.39.5) / `gh` CLI (v2.23.0)
- **接続方式:** GitHub App `arena-ai-coding-agent` 経由の短期プロキシトークン（`GH_TOKEN`）
- **GitHub App 権限（実測値）:**
  ```json
  {
    "app_slug": "arena-ai-coding-agent",
    "permissions": {
      "contents": "write",
      "pull_requests": "write",
      "workflows": "write",
      "repository_hooks": "write",
      "actions": "read",
      "checks": "read",
      "issues": "read",
      "metadata": "read",
      "statuses": "read"
    }
  }
  ```
- **アウトバウンド通信制限（Egress Firewall）:**
  - 許可ホスト: `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`
  - 未許可ホスト（外部ストレージ・一般インターネット等）はアクセス遮断

---

## 3. 【完全対比表】できること vs できないこと

| カテゴリ | 機能・操作 | 可否 | 判定理由・技術的背景 |
| :--- | :--- | :---: | :--- |
| **Git 操作** | リポジトリのクローン (`git clone`) | ✅ **可能** | `contents: write` 権限が有効 |
| | コミット作成・ログ閲覧 (`git commit`, `log`) | ✅ **可能** | ローカル作業および書き込み権限 |
| | リモートへの push (`git push`) | ✅ **可能** | ブランチの作成・更新が可能（PRオープン中は何回でも可） |
| **Pull Request** | PR の新規作成 (`gh pr create`) | ✅ **可能** | `pull_requests: write` 権限が有効 |
| | PR の詳細・差分閲覧 (`gh pr view`, `diff`) | ✅ **可能** | `pull_requests: write` 権限が有効 |
| | PR へのコメント投稿 (`gh pr comment`) | ✅ **可能** | PR スコープのコメント権限あり |
| | PR のクローズ (`gh pr close`) | ✅ **可能** | 権限上可能（※セッション遮断に注意） |
| | PR のマージ (`gh pr merge`) | ✅ **可能** | 権限上可能（※セッション終了処理として実施） |
| **GitHub Actions** | ワークフロー定義の push (`.github/workflows/*.yml`) | ✅ **可能** | `workflows: write` 権限が有効 |
| | push / PR イベントでの自動起動 | ✅ **可能** | リポジトリ側のトリガー設定で自動実行 |
| | 実行状態・ジョブ結果・アノテーション取得 | ✅ **可能** | `actions: read` 権限により API/CLI で完全取得 |
| | 成果物（Artifact）の生成・メタデータ確認 | ✅ **可能** | 名前・サイズ・有効期限などのメタデータを取得可能 |
| | ワークフローの手動実行 (`workflow_dispatch`) | ❌ **不可** | **HTTP 403**（`actions: write` 権限が不足） |
| | 失敗したワークフローの再実行 (`gh run rerun`) | ❌ **不可** | **HTTP 403**（`actions: write` 権限が不足） |
| | 生ログの直接ダウンロード (`gh run view --log`) | ❌ **不可** | Azure Blob / 外部 CDN への 302 リダイレクトが遮断 |
| | 成果物 ZIP の直接取得 (`gh run download`) | ❌ **不可** | 同上（Azure Blob へのリダイレクトが遮断） |
| **Issue** | Issue の閲覧・一覧取得 (`gh issue list`, `view`) | ✅ **可能** | `issues: read` 権限が有効 |
| | Issue の新規作成 (`gh issue create`) | ✅ **可能** | 公開リポジトリの未認証作成仕様により通る（※注意） |
| | Issue へのコメント投稿 (`gh issue comment`) | ❌ **不可** | **HTTP 403**（`issues: write` 権限が不足） |
| | Issue のタイトル・本文編集 (`gh issue edit`) | ❌ **不可** | **HTTP 403**（`issues: write` 権限が不足） |
| | Issue へのラベル追加・削除 | ❌ **不可** | **HTTP 403**（`issues: write` 権限が不足） |
| | Issue のクローズ・再オープン (`gh issue close`) | ❌ **不可** | **HTTP 403**（`issues: write` 権限が不足） |
| **情報取得 / API** | メタデータ・README・ファイル取得 | ✅ **可能** | `metadata: read`, `contents: read` |
| | REST API / GraphQL API 直接利用 | ✅ **可能** | `gh api`, `gh api graphql` 経由で制限なく利用可能 |
| | リポジトリ検索・コード検索 (`gh search`) | ✅ **可能** | 検索 API へのアクセス正常 |
| | `gh` CLI の最新 JSON フィールド利用 | ❌ **不可** | CLI が v2.23.0 と古く未サポート（例: `visibility`） |

---

## 4. 「できること」の詳細解説

### 4.1 Git 基本操作とコード管理
- `git clone` によるリポジトリのチェックアウト、ブランチのトラッキング、ローカルコミットの作成がすべて通常通り動作します。
- `git push origin <branch>` によりリモートへの反映が即座に行われ、複数回のコミット・push も PR がオープンしている間は制限なく実行可能です。

### 4.2 Pull Request 駆動の開発ワークフロー
- `gh pr create` で base ブランチ（`main` など）に対する PR をワンコマンドで起票できます。
- `gh pr comment` による進捗報告や自動レビューコメントの投稿が可能です。
- PR のマージ機能（`gh pr merge --merge` 等）も権限上許可されており、作業の最終取り込みまでを一気通貫で完結できます。

### 4.3 GitHub Actions の自動テスト・ビルド・監視
- `.github/workflows/` 配下にワークフロー定義 YAML をコミットして push すると、GitHub のランナーが起動しジョブが実行されます。
- エージェントは `gh run list` や `gh run view <run_id>`、および GitHub REST API（`/actions/runs/{id}/jobs`）を用いて、実行中のステータス監視、完了待機、各ステップの成否（exit code）、エラーアノテーションの確認を自動で行えます。
- 成果物（Artifact）のアップロードステップも正常に走り、成果物名やファイルサイズを API から確認できます。

---

## 5. 「できないこと」の詳細解説と原因分析

### 5.1 Issue の更新系操作（HTTP 403: Forbidden）
- **現象:** `gh issue comment`, `gh issue edit`, `gh issue close` を実行すると以下のエラーが発生。
  ```text
  HTTP 403: Resource not accessible by integration
  X-Accepted-Github-Permissions: issues=write; pull_requests=write
  ```
- **原因:** GitHub App `arena-ai-coding-agent` に割り当てられている権限が `issues: read` に限定されており、`issues: write` が付与されていないためです。
- **特記事項:** 「Issue 新規作成」のみ成功しますが、これは GitHub の仕様上、公開リポジトリでは未認証（あるいは read 権限）でも起票が許可されているためです。書き込み権限があるわけではないため、一度作成した Issue はエージェント側からはクローズ・編集できなくなります（手動対応が必要になります）。

### 5.2 GitHub Actions の手動起動・再実行（HTTP 403: Forbidden）
- **現象:** `gh workflow run`（`workflow_dispatch`）や `gh run rerun` を実行すると以下のエラーが発生。
  ```text
  could not create workflow dispatch event: HTTP 403: Resource not accessible by integration
  ```
- **原因:** GitHub App の権限が `actions: read` であり、`actions: write` がないためです。
- **実務への影響:** 手動でのトリガーはできませんが、コードを push することによる自動トリガー（`on: push` や `on: pull_request`）は正常に機能するため、コミット push 経由で実行させることで完全に代替可能です。

### 5.3 Actions の生ログ・成果物 ZIP の直接ダウンロード（EOF / 通信遮断）
- **現象:** `gh run view --log` や `gh run download` を実行すると `EOF` エラーで失敗。
  ```text
  failed to get run log: Get "https://results-receiver.actions.githubusercontent.com/...": EOF
  error downloading verify-artifact: Get "https://productionresultssa18.blob.core.windows.net/...": EOF
  ```
- **原因:** GitHub API は生ログや成果物 ZIP のダウンロード時に、GitHub 本体のドメインから Azure Blob Storage（`*.blob.core.windows.net`）や `results-receiver.actions.githubusercontent.com` へ 302 リダイレクトします。Arena のセキュリティ方針により、アウトバウンド通信先が `github.com` / `api.github.com` 等に厳格に制限されているため、リダイレクト先ホストへの接続がネットワーク層でドロップされます。
- **実務への影響:** ログの成否やステップ単位の実行結果・サマリは `api.github.com` 経由で取得可能なため、デバッグや検証に大きな支障はありません。

### 5.4 `gh` CLI のバージョン制約（v2.23.0 レガシー仕様）
- **現象:** `gh repo view --json visibility` などの最新 JSON フィールドを指定すると `Unknown JSON field` エラーとなる。
- **原因:** サンドボックス内の `gh` CLI が 2.23.0（2023 年版）であるため。
- **対処法:** `visibility` の代わりに `isPrivate` を使用するなど、互換フィールドを指定することで回避可能です。

### 5.5 セッションのライフサイクル制約（PR マージ・クローズ時の挙動）
- **仕様上の注意:** PR をマージまたはクローズすると、そのセッションでは以降のリモート push や GitHub 連携が終了します（復帰不可）。
- **影響:** 途中で PR をマージ・クローズしてしまうと作業を継続できなくなるため、マージは「全コード・全ドキュメントの push が完了した後の最後の 1 回」に限定する必要があります。

---

## 6. 運用ベストプラクティス・回避策（Workaround ガイド）

| 課題・やりたいこと | 回避策（Workaround） |
| :--- | :--- |
| **テストを再実行したい** | 手動 dispatch が不可なため、空コミット（`git commit --allow-empty -m "ci: trigger run"`）を push して自動実行させる |
| **テストログの詳細を確認したい** | 生ログダウンロードに頼らず、ワークフロー内で `$GITHUB_STEP_SUMMARY` に結果を書き出すか、ジョブごとの annotations / REST API ステップ結果を参照する |
| **Issue を起票・管理したい** | Issue 作成はエージェントが行い、クローズやラベル付けは人間（管理者）が GitHub Web 画面から実施する（または PR で代替する） |
| **成果物ファイルを受け取りたい** | Actions の Artifact ダウンロードに頼らず、エージェントが作業ブランチ上にファイルを生成して git commit & push する |
| **PR をマージしたい** | 必ず必要なコミット・push をすべて終えてから、ターンの最後に `gh pr merge` を実行する |

---

## 7. 設定改善に向けた推奨事項

エージェントの自律性をさらに高めたい場合、GitHub App および環境設定側で以下の調整を検討することが推奨されます。

1. **GitHub App 権限の拡張（Arena 提供元・管理者向け）:**
   - `Issues: Read and write`: エージェントがタスク完了時に Issue を自動クローズ・進捗コメントできるようにする。
   - `Actions: Read and write`: エージェントが手動ワークフローの起動や失敗ジョブの再試行を実行できるようにする。
2. **Egress Firewall のホワイトリスト追加（インフラ設定）:**
   - Actions のログ・Artifact 取得を可能にする場合、GitHub のストレージドメイン（`*.blob.core.windows.net`, `results-receiver.actions.githubusercontent.com`）をアウトバウンド許可リストに追加する。
3. **`gh` CLI のアップデート:**
   - Debian パッケージの更新等により、最新の `gh` CLI を導入することで最新の JSON フィールドやサブコマンドを利用可能にする。

---

*作成日: 2026-10-19 / 作成者: Arena.ai Coding Agent (`aiselfmyself/ResearchOS`)*
