# moomoo OpenAPI リファレンス

Python SDK `moomoo-openapi` の公開 API を機能別にまとめたもの。  
接続には `OpenD` デーモンが必要（`MOOMOO_OPEND_HOST:MOOMOO_OPEND_PORT`）。

---

## コンテキストクラス

| クラス | 用途 |
|--------|------|
| `OpenQuoteContext` | 行情（相場データ）全般 |
| `OpenSecTradeContext` | 株式・ETF・オプション取引 |
| `OpenFutureTradeContext` | 先物取引（SecTrade と同じインターフェース） |

---

## 1. 行情 API（OpenQuoteContext）

### 1-1. 購読・リアルタイム配信

| メソッド | 説明 |
|----------|------|
| `subscribe(code_list, subtype_list)` | 銘柄のリアルタイムデータ購読開始（QUOTE / K_1M / TICKER / ORDER_BOOK など） |
| `unsubscribe(code_list, subtype_list)` | 購読解除 |
| `unsubscribe_all()` | 全購読解除 |
| `query_subscription()` | 現在の購読状況一覧 |

### 1-2. 株価・スナップショット

| メソッド | 説明 |
|----------|------|
| `get_stock_quote(code_list)` | リアルタイム株価（購読済みが必要）：始値・高値・安値・終値・出来高・売買代金 |
| `get_market_snapshot(code_list)` | 市場スナップショット：ひとつの呼び出しで複数銘柄の板・出来高・52週高安等をまとめて取得 |

### 1-3. Kライン

| メソッド | 説明 |
|----------|------|
| `get_cur_kline(code, num, ktype)` | 直近 N 本の Kライン（1分〜月次、最大 1,000 本） |
| `request_history_kline(code, start, end, ktype, autype)` | 期間指定の歴史 Kライン（ダウンロード不要） |
| `get_history_kl_quota()` | 歴史 Kライン 使用済みクォータ確認 |

### 1-4. 分時・ティック・板情報

| メソッド | 説明 |
|----------|------|
| `get_rt_data(code)` | 当日の分時データ（時間足 1 分単位） |
| `get_rt_ticker(code, num)` | 直近 N 件の逐笔（ティック）データ |
| `get_order_book(code, num)` | リアルタイム板情報（bid/ask 各 N 段） |
| `get_broker_queue(code)` | 経紀人（ブローカー別）注文キュー |

### 1-5. 市場・取引日

| メソッド | 説明 |
|----------|------|
| `get_global_state()` | OpenD 接続状態・市場開閉・ログインユーザー情報 |
| `get_market_state(code_list)` | 指定銘柄のマーケット状態（開場前 / 取引中 / 取引後 等） |
| `request_trading_days(market, start, end)` | 指定市場・期間の取引日カレンダー |

### 1-6. 銘柄情報

| メソッド | 説明 |
|----------|------|
| `get_stock_basicinfo(market, stock_type)` | 指定市場の銘柄基本情報（名称・上場所・時価総額等） |
| `get_code_change(code_list)` | コード変更・並行取引の一時コード情報 |
| `get_ipo_list(market)` | IPO一覧（申込期間・公開価格・上場日等） |
| `get_rehab(code)` | 権利落ち・分割情報（配当落ち日・比率等） |
| `get_future_info(code_list)` | 先物契約情報（期限・取引単位・証拠金率等） |
| `get_holding_change_list(code, holder_category)` | 大株主持株変動履歴（米株のみ） |

### 1-7. 板块（セクター・指数）

| メソッド | 説明 |
|----------|------|
| `get_plate_list(market, plate_class)` | 板块集合配下のサブ板块一覧 |
| `get_plate_stock(plate_code)` | 板块内の銘柄一覧 |
| `get_owner_plate(code_list)` | 銘柄が属する板块一覧 |
| `get_referencestock_list(code, reference_type)` | 関連銘柄リスト（同業他社・A/H 株リンク等） |

### 1-8. オプション・ワラント

| メソッド | 説明 |
|----------|------|
| `get_option_expiration_date(code)` | 原資産銘柄のオプション満期日一覧 |
| `get_option_chain(code, start, end, option_type)` | オプションチェーン（コール/プット・各満期・ストライク一覧） |
| `get_warrant(stock_owner, ...)` | 香港カバードワラント・CBBCの一覧と詳細（権利行使価格・乖離率等） |

### 1-9. 資金フロー

| メソッド | 説明 |
|----------|------|
| `get_capital_flow(code)` | 個別株への資金流入・流出（大型・中型・小型別） |
| `get_capital_distribution(code)` | 個別株の資金分布（超大口・大口・中口・小口の比率） |

### 1-10. スクリーニング（条件選股）

| メソッド | 説明 |
|----------|------|
| `get_stock_filter(market, filter_list)` | 財務・価格・出来高等の条件で銘柄スクリーニング |
| `get_derivative_unusual(...)` | デリバティブ異動スクリーナー（SkillWrap API） |
| `get_financial_unusual(...)` | 財務指標異動スクリーナー（SkillWrap API） |
| `get_technical_unusual(...)` | テクニカル指標異動スクリーナー（SkillWrap API） |

### 1-11. ウォッチリスト・アラート

| メソッド | 説明 |
|----------|------|
| `get_user_security_group()` | マイ銘柄グループ一覧 |
| `get_user_security(group_name)` | グループ内の銘柄一覧 |
| `modify_user_security(op, code_list)` | ウォッチリストへの追加・削除 |
| `set_price_reminder(code, op, ...)` | 価格アラートの新規作成・変更・削除・有効化/無効化 |
| `get_price_reminder(code)` | 設定済み価格アラート一覧 |

### 1-12. その他

| メソッド | 説明 |
|----------|------|
| `get_user_info()` | ログインユーザー情報（UID・権限等） |
| `get_delay_statistics()` | API レイテンシ統計（接続品質確認用） |
| `verification()` | キャプチャ認証（ログイン時の画像認証対応） |
| `set_handler(handler)` | プッシュデータの非同期コールバック登録 |

---

## 2. 取引 API（OpenSecTradeContext / OpenFutureTradeContext）

### 2-1. 口座管理

| メソッド | 説明 |
|----------|------|
| `get_acc_list()` | 保有口座一覧（REAL / SIMULATE、マーケット別） |
| `unlock_trade(password_md5)` | 取引ロック解除（全取引 API の呼び出し前に必要） |
| `accinfo_query(trd_env)` | 口座残高・買付余力・証拠金・純資産等 |
| `get_acc_cash_flow(...)` | 口座の入出金・配当・手数料等のキャッシュフロー |
| `get_margin_ratio(code_list)` | 銘柄別の証拠金比率 |

### 2-2. ポジション

| メソッド | 説明 |
|----------|------|
| `position_list_query(...)` | 保有ポジション一覧（銘柄・数量・平均単価・含み損益等） |

### 2-3. 注文

| メソッド | 説明 |
|----------|------|
| `place_order(price, qty, code, trd_side, order_type, ...)` | 発注（指値・成行・逆指値・トレーリング等） |
| `modify_order(modify_order_op, order_id, qty, price, ...)` | 注文の変更（価格・数量の修正） |
| `cancel_all_order()` | 全注文一括キャンセル |
| `order_list_query(...)` | 当日の有効注文一覧 |
| `history_order_list_query(start, end, ...)` | 過去注文履歴 |
| `acctradinginfo_query(code, trd_side, ...)` | 最大買付・売付可能数量の照会 |
| `order_fee_query(order_id_list)` | 注文ごとの手数料照会 |

### 2-4. 約定

| メソッド | 説明 |
|----------|------|
| `deal_list_query(...)` | 当日の約定一覧 |
| `history_deal_list_query(start, end, ...)` | 過去の約定履歴 |

---

## 3. 注文タイプ（OrderType）

| 値 | 説明 |
|----|------|
| `NORMAL` | 指値注文 |
| `MARKET` | 成行注文 |
| `ABSOLUTE_LIMIT` | 絶対指値（香港向け） |
| `AUCTION` | オークション（寄り付き成行） |
| `AUCTION_LIMIT` | オークション指値 |
| `SPECIAL_LIMIT` | 特殊指値 |
| `STOP` | 逆指値（指値） |
| `STOP_LIMIT` | 逆指値（指値・上限あり） |
| `MARKET_IF_TOUCHED` | タッチ成行 |
| `LIMIT_IF_TOUCHED` | タッチ指値 |
| `TRAILING_STOP` | トレーリングストップ（成行） |
| `TRAILING_STOP_LIMIT` | トレーリングストップ（指値） |

---

## 4. 主なサブスクリプション種別（SubType）

| 値 | 説明 |
|----|------|
| `QUOTE` | リアルタイム株価 |
| `ORDER_BOOK` | 板情報 |
| `TICKER` | 逐笔（ティック） |
| `RT_DATA` | 分時データ |
| `K_1M / K_5M / K_15M / K_30M / K_60M` | 分足Kライン |
| `K_DAY / K_WEEK / K_MON` | 日足・週足・月足Kライン |
| `BROKER` | ブローカーキュー |

---

## 5. 対応マーケット

| 定数 | 市場 |
|------|------|
| `Market.HK` | 香港（株・ETF・ワラント・CBBC・オプション） |
| `Market.US` | 米国（NYSE・NASDAQ・AMEX・株・ETF・オプション・先物） |
| `Market.SH / Market.SZ` | 中国本土（上海・深圳） |
| `Market.SG` | シンガポール |
| `Market.JP` | 日本 |
| `Market.AU` | オーストラリア |

---

## 6. 利用上の注意

- `TrdEnv.REAL` / `TrdEnv.SIMULATE` で本番・シミュレーションを切り替え
- 取引前に必ず `unlock_trade(password_md5)` が必要
- `subscribe()` は同時購読数に上限あり（アカウントプランによる）
- 歴史 Kライン は月ごとにクォータ制限あり（`get_history_kl_quota()` で確認）
- インスタンスは使い終わったら `ctx.close()` で明示的に閉じること
