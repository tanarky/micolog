setup手順
-------------------------------------

1. Change "app.yaml.sample" to "app.yaml"
2. Replace "Application: mlog " as "Application: <your Google App ID>"
3. Upload micolog use "Google App Engine Launcher"

todo
-------------------------------------

- cache policy

  - 何がKey？

- 記事投稿後のF5対策

- fresh press ?

- theme files 削除？

  - のちのちの拡張ができれば、若干便利かも

- url_forが欲しい

  - Recent CommentsのURLが変

- コメントのcheckimgは本当はもっとちゃんとやらないとだめ

  - Cookieではなく、Javascriptによるvalidateをいれたい

- 食べログtrackback送れない -> なくても食べログ投稿できるかも？

  - blog.allow_trackback
  - entry.allow_trackback

解決
-------------------------------------

- permanent link URL をid(必須)＋日付&slug(任意)に -> 以下のように変更

  - 記事URL: /YYYY/MM/ID/SLUG
  - ページURL: /page/SLUG
  - 記事のKEYはIDにする
  - ページのKEYはSLUGにする

- コメント機能不具合 -> ログイン時はチェックしない仕様だったので常にチェックするように変更済み

  - テンプレート上で、blog変数がちゃんととれていない疑惑
  - コメントメールアドレス形式
  - コメントメール飛んでない
  - siteを入力しないと URLが変になる
  - コメント数字チェックが効かない

    - 演算 -> 計算間違っても意味なし
    - クライアント演算 -> そもそも式が表示されない

- python27 -> 断念

一般権限
-------------------------------------

- 記事を書く
- 記事
- ページ
- リンク
- カテゴリー
- コメント
- ファイル

Admin権限
-------------------------------------

- 記事を書く
- 記事
- ページ
- リンク
- カテゴリー
- コメント
- ファイル
- 設定
- プラグイン
- キャッシュ
- 作者
