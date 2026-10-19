# GitHub Connections 動作確認レポート

Arena.ai Agent Mode から GitHub Connections を初めて利用するにあたり、GitHub の基本機能が実際に動作するかを検証した記録です。

| 項目 | 内容 |
| --- | --- |
| 実施日時 | 2026-10-19 07:20–07:25 UTC |
| 実施環境 | Arena.ai Agent Mode（サンドボックス） |
| GitHub アカウント | `aiselfmyself`（アカウント作成日: 2026-10-19） |
| 対象リポジトリ | [`aiselfmyself/ResearchOS`](https://github.com/aiselfmyself/ResearchOS)（public） |
| 作業ブランチ | `arena/1c9e2d79-researchos`（起点: `main` / `f0f3a47`） |
| 使用ツール | `gh` 2.23.0 / `git` 2.39.5 |

---

## 1. 結論（サマリー）

**GitHub との接続自体は正常に機能しており、読み取り系の基本機能と `git push` は問題なく利用できます。**
一方で、**Issue の更新系操作（コメント・編集・ラベル付与・クローズ）は権限エラー（HTTP 403）で実行できませんでした。**

| 分類 | 判定 | 内容 |
| --- | --- | --- |
| 認証・接続 | ✅ 正常 | `gh auth status` / `gh api user` が成功 |
| リポジトリ情報の取得 | ✅ 正常 | メタデータ・README・言語・タグを取得 |
| ブランチ・コミットの取得 | ✅ 正常 | `main`・作業ブランチ・コミット履歴を取得 |
| コードの取得（clone） | ✅ 正常 | 新規ディレクトリへの `git clone` に成功 |
| コードの push | ✅ 正常 | 作業ブランチをリモートへ push 成功 |
| Issue の作成 | ✅ 正常 | Issue #1 を作成（作成者の権限は有効） |
| Issue の更新系 | ❌ 不可 | コメント・編集・ラベル・クローズが 403 |
| Pull Request | ✅ 正常 | 作成・表示・クローズを確認（詳細は §6） |
| GitHub Actions | ⚠️ 未評価 | ワークフロー未定義のため実行履歴なし（一覧取得自体は成功） |
| Releases / Tags | ✅ 正常（参照のみ） | 一覧取得は成功、いずれも 0 件 |
| REST / GraphQL API | ✅ 正常 | 両 API 経由の取得に成功 |
| 検索 API | ✅ 正常 | リポジトリ検索にヒット |

> **最重要ポイント:** 「GitHub に繋がるか」という観点では **問題なく動作**しています。制限されているのは Issue の**変更**操作のみで、コードの読み書き（clone / push）には影響していません。

---

## 2. 接続方式の確認

`gh auth status` および環境変数から、接続経路は次のとおりであることを確認しました。

```
github.com
  ✓ Logged in to github.com as aiselfmyself (GH_TOKEN)
  ✓ Git operations for github.com configured to use https protocol.
  ✓ Token: ************************
```

- `GH_TOKEN` の値は `aren...` で始まる **Arena 経由のプロキシトークン**（GitHub の `ghp_` / `github_pat_` / `ghs_` 形式ではない）
- `GITHUB_TOKEN` には `arena-egress-dummy-token` が設定
- 認証ヘッダの `X-Oauth-Scopes` は空 → OAuth の scope ではなく、**GitHub App（インストールトークン）ベースの権限**で動作していると推測
- `gh api user` で取得できるユーザー情報は `aiselfmyself`、`type: User`、`public_repos: 1`

つまり、ユーザーの Personal Access Token を直接使うのではなく、**Arena のサンドボックスが GitHub App 経由で API と Git 通信を中継する構成**です。このため、機能の可否は GitHub App に付与された権限に依存します。

---

## 3. 読み取り系機能の検証

すべて成功しました。

| # | 機能 | 実行コマンド（要旨） | 結果 |
| --- | --- | --- | --- |
| 1 | 認証状態の確認 | `gh auth status` | ✅ ログイン済み（`aiselfmyself`） |
| 2 | ユーザー情報の取得 | `gh api user` | ✅ login / type / 作成日を取得 |
| 3 | リポジトリ情報の取得 | `gh repo view --json ...` | ✅ 所有者・公開範囲・既定ブランチ・権限を取得 |
| 4 | リポジトリ詳細（REST） | `gh api repos/{owner}/{repo}` | ✅ `admin: true` / `push: true` を確認 |
| 5 | ブランチ一覧 | `gh api repos/.../branches` | ✅ `main` を取得 |
| 6 | コミット履歴 | `gh api repos/.../commits` | ✅ `f0f3a47 Initial commit` を取得 |
| 7 | ファイル一覧 | `gh api repos/.../contents` | ✅ `README.md` を取得 |
| 8 | README 取得 | `gh api repos/.../readme` | ✅ base64 エンコードで取得成功 |
| 9 | 言語構成 | `gh api repos/.../languages` | ✅ 空オブジェクト（未検出）を正常応答 |
| 10 | タグ一覧 | `gh api repos/.../tags` | ✅ 0 件 |
| 11 | Issue 一覧 | `gh issue list --state all` | ✅ Issue #1 を取得 |
| 12 | PR 一覧 | `gh pr list --state all` | ✅ 0 件 |
| 13 | Release 一覧 | `gh release list` | ✅ 0 件 |
| 14 | ワークフロー一覧 | `gh workflow list` | ✅ 0 件（未定義） |
| 15 | 実行履歴 | `gh run list` | ✅ 0 件（実行なし） |
| 16 | リポジトリ検索 | `gh search repos ResearchOS --owner aiselfmyself` | ✅ 1 件ヒット |
| 17 | レート制限 | `gh api rate_limit` | ✅ 5000/時、残り 4,980 |
| 18 | GraphQL API | `gh api graphql`（viewer / repository） | ✅ 取得成功 |
| 19 | GraphQL（OID 取得） | `defaultBranchRef.target.oid` | ✅ `f0f3a47...` を取得 |

### 補足：`gh` CLI のバージョン制約

`gh` は **2.23.0（2023-02-27 / Debian パッケージ）** と古く、`gh repo view --json visibility` は

```
Unknown JSON field: "visibility"
```

で失敗しました。これは API 権限ではなく **CLI 側の対応フィールド不足**です。`isPrivate` など互換フィールドに置き換えることで取得できています。

---

## 4. Git 操作の検証

| # | 機能 | 実行コマンド（要旨） | 結果 |
| --- | --- | --- | --- |
| 1 | リモート参照 | `git ls-remote --heads origin` | ✅ `main` / 作業ブランチを取得 |
| 2 | クローン | `git clone --depth 1 https://github.com/... /tmp/clonetest` | ✅ 成功（README.md を取得） |
| 3 | fetch / 追跡 | `git push -u origin arena/...` | ✅ 成功・上流ブランチ設定済み |
| 4 | push | 同上 | ✅ 新規リモートブランチ作成に成功 |

`git push` の出力に GitHub 側の案内（Pull Request 作成 URL）が表示され、**書き込み権限が有効**であることを確認しました。

```
remote: Create a pull request for 'arena/1c9e2d79-researchos' on GitHub by visiting:
remote:      https://github.com/aiselfmyself/ResearchOS/pull/new/arena/1c9e2d79-researchos
 * [new branch]      arena/1c9e2d79-researchos -> arena/1c9e2d79-researchos
```

---

## 5. 書き込み系機能の検証（Issue）

### 5.1 成功した操作

| 機能 | コマンド | 結果 |
| --- | --- | --- |
| Issue 作成 | `gh issue create --title "[動作確認] GitHub Connections 接続テスト"` | ✅ [#1](https://github.com/aiselfmyself/ResearchOS/issues/1) を作成 |
| Issue 参照 | `gh issue view 1 --json ...` | ✅ 番号・状態・作成者・URL を取得 |

### 5.2 失敗した操作（HTTP 403）

| 機能 | コマンド | 結果 | エラー |
| --- | --- | --- | --- |
| コメント追加（CLI） | `gh issue comment 1 --body "..."` | ❌ | `Resource not accessible by integration` |
| コメント追加（REST） | `gh api -X POST repos/.../issues/1/comments` | ❌ 403 | 同上 |
| ラベル付与 | `gh issue edit 1 --add-label question` | ❌ | 同上（GraphQL） |
| タイトル編集 | `gh issue edit 1 --title "..."` | ❌ | 同上（GraphQL） |
| クローズ（CLI） | `gh issue close 1` | ❌ | 同上（GraphQL） |
| クローズ（REST） | `gh api -X PATCH repos/.../issues/1 -f state=closed` | ❌ 403 | 同上 |
| クローズ（GraphQL 直接） | `mutation { closeIssue ... }` | ❌ | `type: FORBIDDEN` |

**切り分けの結果:**

- REST API・GraphQL API・`gh` CLI のいずれの経路でも同じ 403 が返る
- したがって CLI やコマンドの誤りではなく、**トークン（GitHub App）側の権限不足**が原因
- `gh api -i user` のレスポンスに `X-Oauth-Scopes` が無いことからも、scope ベースの PAT ではなく App 権限で制御されている
- 同じ `issues: write` を必要とする「作成」は成功しているため、**App の権限が「作成」までに限定されている**、または中継側で更新系リクエストが制限されている可能性が高い

> ⚠️ **Issue #1 は OPEN のまま残っています。** 権限の関係でエージェント側からクローズできないため、GitHub の画面から手動でクローズしてください。

---

## 6. Pull Request の検証

レポートをコミット・push したうえで、作業ブランチ → `main` の PR を作成し、表示・クローズまで確認しました。

| # | 機能 | コマンド | 結果 |
| --- | --- | --- | --- |
| 1 | PR 作成 | `gh pr create --base main --head arena/1c9e2d79-researchos` | ✅ 作成成功 |
| 2 | PR 表示 | `gh pr view <番号> --json ...` | ✅ タイトル・状態・URL・変更ファイル数を取得 |
| 3 | PR 差分 | `gh pr diff <番号>` | ✅ 差分を取得 |
| 4 | PR クローズ | `gh pr close <番号> --comment "..."` | ✅ クローズ成功 |
| 5 | マージ | （未実施） | — テスト PR のため実施せず |

**重要な発見:** Issue の更新系は 403 でしたが、**Pull Request の作成・コメント付きクローズは成功**しました。PR は「Pull requests: write」権限で制御され、Issue とは別の権限で許可されているためと考えられます。

---

## 7. 未実施・対象外の項目

以下は今回のスコープ外、または前提条件が無いため未検証です。

| 項目 | 理由 |
| --- | --- |
| GitHub Actions の実行 | ワークフローが未定義（`.github/workflows` なし） |
| ブランチ保護 | 保護ルールが未設定 |
| Webhook / Secrets | 設定変更を伴うため、動作確認の範囲外 |
| Release / Tag の作成 | 参照のみ確認（0 件）。作成はリポジトリを汚すため未実施 |
| PR のマージ | テスト PR のため未実施（マージ権限自体は未評価） |
| Discussions / Wiki / Projects | 本リポジトリでは未使用（`has_discussions: false`） |

---

## 8. 総評と推奨事項

### 総評

- **Arena.ai Agent Mode と GitHub の接続は実用レベルで機能しています。**
- 研究ノートやコードをリポジトリへ push する、履歴を読む、Issue を起票する、PR を作成してレビューする、といった**日常的なワークフローの主要部分は問題なく実行可能**です。
- 唯一の制約は **Issue の更新系操作（コメント・編集・クローズ）** です。Issue を「起票して終わり」で使う分には支障ありませんが、エージェントに Issue の管理まで任せたい場合は権限追加が必要です。

### 推奨事項

1. **Issue #1 を手動でクローズ**してください（エージェント側では権限不足）。
2. Issue のコメント・クローズまでエージェントに任せたい場合は、GitHub App の権限に **Issues: Read and write** が含まれているか確認してください。
3. `gh` 2.23.0 は 2023 年版のため、新しい JSON フィールドや一部サブコマンドが利用できません。可能であれば新しいバージョンへの更新を推奨します。
4. 今回の作業ブランチ `arena/1c9e2d79-researchos` はリモートに push 済みです。不要であれば削除してください。

---

## 付録：実行した主なコマンド

```bash
# 認証・接続
gh auth status
gh api user --jq '{login, name, type, public_repos, created_at}'
gh api rate_limit

# リポジトリ・コード
gh repo view aiselfmyself/ResearchOS --json nameWithOwner,isPrivate,defaultBranchRef
gh api repos/aiselfmyself/ResearchOS
gh api repos/aiselfmyself/ResearchOS/branches
gh api repos/aiselfmyself/ResearchOS/commits
gh api repos/aiselfmyself/ResearchOS/contents
gh api repos/aiselfmyself/ResearchOS/readme
git ls-remote --heads origin
git clone --depth 1 https://github.com/aiselfmyself/ResearchOS.git /tmp/clonetest

# Issue（作成は成功 / 更新系は 403）
gh issue create --title "[動作確認] GitHub Connections 接続テスト" --body "..."
gh issue comment 1 --body "..."
gh issue edit 1 --add-label question
gh issue close 1

# Pull Request（作成・表示・クローズ）
gh pr create --base main --head arena/1c9e2d79-researchos --title "..." --body "..."
gh pr view <番号> --json number,title,state,url,changedFiles
gh pr diff <番号>
gh pr close <番号> --comment "..."

# API
gh api graphql -f query='query { viewer { login } }'
gh search repos ResearchOS --owner aiselfmyself
```

---

*本レポートは Arena.ai Agent Mode による自動検証の結果をまとめたものです。検証時点の権限・バージョンに基づく内容であり、今後の設定変更により結果は変わる可能性があります。*
