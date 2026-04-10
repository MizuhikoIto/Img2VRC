# VRC Photo Slideshow Exporter

Piwigo に保存された VRC 世界旅行写真からランダムに 15 枚を選び、GitHub Pages などで公開しやすい静的スライドショー一式を生成するためのリポジトリです。

現段階の初期構築では、以下を提供します。

- `scripts/build_random_slides.py`
  指定ディレクトリを再帰走査して画像を抽出し、公開用画像・`index.html`・`manifest.json`・`updated_at.txt` を生成します。
- `scripts/deploy_github_pages.sh`
  生成済みの公開ディレクトリを GitHub Pages 用リポジトリへ反映するためのたたき台です。
- `config/example.env`
  動作設定の環境変数例です。

## 現在の前提

- 画像ソースは `/var/www/smartworks/vrcwt/www/photo/upload` 配下です
- サブディレクトリを再帰的に探索します
- 手動実行前提です
- 公開用ディレクトリの例は `public/` です
- 画像は相対パスで参照する `index.html` を生成します

## 必要環境

- Python 3.9 以上
- `Pillow`
- `git`

`Pillow` が未導入の場合は例として以下で導入できます。

```bash
python3 -m pip install Pillow
```

## 初期セットアップ

1. 必要に応じて仮想環境を作成します
2. `config/example.env` を参考に環境変数を設定します
3. `Pillow` をインストールします
4. ビルドスクリプトを実行します

例:

```bash
set -a
source config/example.env
set +a

python3 scripts/build_random_slides.py
```

## 生成物

デフォルトでは以下を生成します。

- `public/01.jpg` から `public/15.jpg`
- `public/index.html`
- `public/manifest.json`
- `public/updated_at.txt`
- `logs/build_random_slides-<timestamp>.log`

## 主な設定値

`config/example.env` の主な項目です。

- `PIWIGO_GALLERY_DIR`
  元画像ディレクトリ
- `SLIDE_COUNT`
  抽出枚数
- `MAX_EDGE_PX`
  画像の長辺上限
- `JPEG_QUALITY`
  JPEG 品質
- `OUTPUT_STAGING_DIR`
  中間生成物の保持先
- `OUTPUT_PUBLISH_DIR`
  最終公開ディレクトリ
- `PUBLIC_BASE_URL`
  将来の公開 URL 用メタデータ
- `CUSTOM_DOMAIN`
  GitHub Pages の `CNAME` に書き込む独自ドメイン。未使用なら空欄

## build_random_slides.py の挙動

- 対応拡張子: `jpg`, `jpeg`, `png`, `webp`
- ランダムに候補をシャッフルし、変換失敗時は後続候補で補充
- EXIF 向きを補正
- 長辺を `MAX_EDGE_PX` 以下に縮小
- JPEG に統一して保存
- staging で組み立てた後に publish へ反映
- 標準出力とログファイルの両方へ記録
- `--dry-run` では書き込みを行わず、候補選定と計画のみ確認

ヘルプ:

```bash
python3 scripts/build_random_slides.py --help
```

## GitHub Pages 反映

`scripts/deploy_github_pages.sh` は以下の前提で使う想定です。

- 生成済みの `public/` を別リポジトリへ push する
- 認証は環境変数で与える
- Pages 対象ブランチをクリーンに更新する

例:

```bash
set -a
source config/example.env
set +a

scripts/deploy_github_pages.sh
```

現時点では認証未設定でも、スクリプトの構成と必要環境変数を確認できます。

## random.php の扱い

参考資料として `random.php` を確認した結果、今回の要件では全面再利用はしません。

再利用できる考え方:

- Piwigo 側で公開可視性を考慮した「ランダム候補 ID を得る」という発想
- 一度の抽出数に上限を設け、結果リストを作る流れ

独自実装にすべき部分:

- 画像ファイルを直接再帰探索する部分
- 15 枚ぴったりの公開用画像生成
- リサイズ・JPEG 変換
- `index.html` / `manifest.json` / `updated_at.txt` の生成
- staging と publish の分離
- ログ出力
- GitHub Pages 向け反映

理由:

- `random.php` は Piwigo の DB と権限制御に依存し、返すのは画像 URL ではなく「Piwigo の index へのリダイレクト先」です
- 今回はローカルに存在する画像ファイル群から静的公開物を作る要件なので、処理単位が異なります

## 今後の拡張候補

- 直近採用画像を `state/` に保存し、同じ写真の連続採用を減らす
- Piwigo DB からメタデータを併用する
- systemd timer / cron 設定例を追加する
- GitHub Actions や別公開先への差し替えをしやすくする
