# AGENTS.md
Project: VRC World Travel Random Photo Slideshow Exporter

## 目的
自宅サーバ上の Piwigo に保存されている VRC世界旅行の写真群から、定期的にランダムで15枚を選出し、
VRChat から取得可能な静的画像セットとして外部公開用ディレクトリへ書き出す。

最終的には GitHub Pages に公開し、VRChat ワールド側から固定URL群または manifest を通じて読み込み、
ランダムスライドショーとして利用できるようにする。

---

## このプロジェクトで実現したいこと

### 必須要件
- Piwigo上の全写真を対象にランダムで15枚選ぶ
- VRChatで扱いやすいサイズ・形式に変換する
- 公開用の静的ファイルとして出力する
- 定期実行できるようにする
- 失敗時に原因を追いやすいログを残す
- 途中失敗で公開物が壊れないようにする

### 推奨要件
- 毎回同じ写真ばかり出にくいようにする
- 横長・縦長が混在しても破綻しにくいようにする
- manifest.json を生成できるようにする
- 公開先を GitHub Pages 以外にも差し替えやすい構成にする

---

## 重要な前提
- VRChat 側では、HTMLではなく「画像そのもののURL」が必要
- URLリダイレクト依存は避ける
- 画像は静的ファイルとして公開する
- 一時生成物と公開物は分離する
- 公開更新はアトミックに近い形で行う
- 画像の長辺は原則 2048px 以下
- JPEGを基本とし、必要があれば品質を調整する
- 同一URL上書きによるキャッシュ問題を将来的に考慮する

---

## スコープ
このプロジェクトの担当範囲は以下。

1. Piwigo内の写真候補取得
2. ランダム抽出
3. 画像リサイズ・再圧縮
4. 公開用ディレクトリ生成
5. manifest.json 生成（任意だが対応しやすくする）
6. GitHub Pages 用の配布物更新
7. cron / systemd timer 等による定期実行
8. ログ出力と失敗時の保全

担当範囲外:
- VRChatワールド側のUdon実装そのもの
- Piwigo本体の改造
- GitHubアカウント作成
- DNS設定変更
- allowlist仕様変更への対処

---

## 推奨構成
実装言語は Python を優先する。
理由:
- 画像処理に Pillow を使いやすい
- JSON生成が容易
- ログやファイル処理が素直
- 将来の拡張がしやすい

想定ディレクトリ例:

project/
- AGENTS.md
- README.md
- config/
  - example.env
- scripts/
  - build_random_slides.py
  - deploy_github_pages.sh
- output/
  - staging/
  - publish/
- logs/
- state/

---

## 実装方針

### 写真選定
優先順位:
1. 既存の random.php の内部ロジックを安全に再利用できるなら再利用
2. 難しい場合は、Piwigo のDBまたは画像一覧から独自にランダム抽出
3. HTMLスクレイピング依存は最後の手段

### 画像変換
- 長辺を 1920〜2048px に収める
- JPEG品質はまず 82〜88 を目安
- EXIF の向きがある場合は正規化する
- 変換失敗した画像はスキップし、別候補を補充する
- 15枚未満にならないようにする

### 出力形式
最低限の出力:
- 01.jpg ～ 15.jpg

将来拡張向け:
- manifest.json
- updated_at.txt

manifest.json 例:
```json
{
  "generated_at": "2026-04-10T10:00:00+09:00",
  "count": 15,
  "images": [
    "01.jpg",
    "02.jpg",
    "03.jpg"
  ]
}
````

### デプロイ

GitHub Pages は FTP ではなく、原則として Git で更新する。

* deploy 用ブランチ、または Pages 対象ブランチへ push
* 認証は Personal Access Token または deploy key を使う
* 認証情報はコードやAGENTS.mdに直書きしない
* secrets は環境変数または外部設定ファイルで管理する

### 定期実行

* cron または systemd timer を使う
* 例: 1日1回、または数時間おき
* 同時多重実行を防ぐロックを入れる
* 前回実行中なら二重起動しない

### ログ

* 標準出力だけでなくログファイルにも残す
* 少なくとも以下を記録:

  * 開始時刻
  * 選定枚数
  * 選ばれた元画像
  * 変換成功/失敗
  * publish成否
  * git push成否
  * 終了時刻

---

## 安全ルール

* 元画像を破壊しない
* 公開中ディレクトリをいきなり上書きしない
* staging で生成完了後に publish へ反映する
* 認証情報をリポジトリへ commit しない
* 失敗時に前回公開物を消さない
* shell command は危険な rm -rf を乱用しない
* 例外時は黙殺せずログに残す

---

## Codex への具体指示

### まず確認・調査すること

1. Piwigo の写真実体がどこにあるか
2. random.php が何を返すか

   * HTMLか
   * 画像URLか
   * リダイレクトか
3. Piwigo DB が参照可能か
4. GitHub Pages 用リポジトリの更新方法
5. 実行環境に Python / Pillow / git があるか

### 実装時の優先順位

1. 「ローカルで15枚を書き出せる」まで作る
2. 次にリサイズと manifest 生成
3. 次に GitHub Pages 反映
4. 最後に定期実行とログ整備

### 生成してほしいファイル

* README.md
* scripts/build_random_slides.py
* scripts/deploy_github_pages.sh
* config/example.env
* systemd timer または cron 設定例
* .gitignore

### build_random_slides.py に期待すること

* 設定ファイルまたは環境変数で動作する
* dry-run オプションを持つ
* 出力先を切り替えられる
* 画像選定元を差し替えやすい
* 例外時に非0で終了する

### deploy_github_pages.sh に期待すること

* publish ディレクトリだけを安全に反映する
* git status が壊れていても原因が追える
* commit message に生成日時を含めてもよい
* 認証情報は環境変数依存にする

---

## 設定値の想定

環境変数例:

* PIWIGO_BASE_DIR
* PIWIGO_GALLERY_DIR
* PIWIGO_RANDOM_PHP
* PIWIGO_DB_HOST
* PIWIGO_DB_NAME
* PIWIGO_DB_USER
* PIWIGO_DB_PASSWORD
* OUTPUT_STAGING_DIR
* OUTPUT_PUBLISH_DIR
* SLIDE_COUNT
* MAX_EDGE_PX
* JPEG_QUALITY
* GITHUB_REPO_URL
* GITHUB_BRANCH
* GITHUB_TOKEN
* PUBLIC_BASE_URL

---

## 実装上の判断基準

* random.php 再利用が複雑なら、独自抽出へ切り替える
* HTML解析が必要なら、DB参照またはファイル直接走査の方を優先する
* 可搬性よりも、まずは今の自宅サーバで確実に動くことを優先する
* ただし認証情報と公開物の扱いは雑にしない

---

## 完了条件

以下を満たしたら第一段階完了とみなす:

* コマンド1発で15枚の公開用画像が生成される
* 生成ログが残る
* GitHub Pages へ更新できる
* 定期実行設定が可能
* 失敗しても前回公開物が残る

---

## 禁止事項

* 認証情報のハードコード
* 元画像の直接上書き
* random.php の出力形式を決め打ちした雑な実装
* 例外無視
* 公開物を生成途中のまま露出すること

## 公開リポジトリ用の情報管理ルール

このリポジトリは公開される前提で扱うこと。
以下の情報は、ソースコード、README、サンプル設定、ログ、コメント、コミット対象ファイル、生成物に含めないこと。

### 含めてはいけない情報
- サーバ内の絶対パス
  - 例: /var/www/..., /home/..., /root/...
- 実在するLinuxユーザー名
- 実在するホスト名、ドメイン構成、内部URL
- SSH接続情報
- APIキー、トークン、パスワード
- 実運用中の秘密情報
- ローカル環境依存の設定値
- 実際のログファイル内容
- 実在ディレクトリ構造が推測しやすい記述

### 代わりに使う表現
- /path/to/piwigo/upload
- /path/to/project
- your-username
- your-repo-name
- example.com
- YOUR_GITHUB_TOKEN
- /path/to/output

### 実装ルール
- README やサンプル設定では、必ずプレースホルダを使うこと
- 実環境の値は config/example.env ではなく、非公開の .env にのみ置くこと
- ログや state ファイルは Git に含めないこと
- 生成物にデバッグ情報や元画像の絶対パスを書かないこと
- state ファイルに保存する元画像一覧は、必要最小限にし、公開対象にしないこと
