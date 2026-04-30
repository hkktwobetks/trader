# trader

Twitter の投稿を LLM で解析し、moomoo 証券（OpenD）へ自動発注するシステム。
ペーパー取引用の `paper` ブローカーも内蔵しており、ローカルで完結した動作確認ができる。

---

## データフロー

```
Twitter（httpx + GraphQL）
        │  $TICKER を含むツイート
        ▼
twitter_worker（workers/twitter_poll.py）
        │  POST /signals  {text, source:"twitter", meta:{url, username, id}}
        ▼
FastAPI（api/main.py）
        │  1. LLM（Groq / Ollama）でティッカー・方向・信頼度を抽出
        │  2. 重複チェック（message_id / URL）
        │  3. Signal を DB に保存
        │  4. 信頼度 ≥ MIN_CONFIDENCE かつ AUTO_TRADE_ENABLED なら
        │     リスクチェック → 発注
        ▼
moomoo OpenD（ローカルゲートウェイ）
        │  REAL / SIMULATE アカウントへ注文送信
        ▼
moomoo 証券

────── 状態同期（別経路）──────

sync_worker（workers/scheduler.py）
        │  POST /sync  を定期実行（SYNC_INTERVAL_MINUTES）
        ▼
FastAPI /sync
        │  moomoo OpenD から注文・約定・ポジション・PnL を取得
        ▼
SQLite DB（orders / executions / positions / pnl）
```

---

## 機能一覧

### シグナル取り込み

| ソース | Worker | 説明 |
|--------|--------|------|
| Twitter | `twitter_poll.py` | 指定アカウントのツイートを GraphQL で定期取得。`$TICKER` を含む投稿を `/signals` に転送 |
| Dexter | `dexter_poll.py` | Dexter エージェントの出力を定期取得し `/signals` に転送 |
| 手動 | — | `POST /signals` に直接 JSON を送ることで任意のテキストを投入可能 |

### シグナル処理

- **LLM 抽出**：Groq (llama-3.3-70b-versatile) または Ollama でティッカー・売買方向・信頼度・SL/TP を JSON として取り出す
- **フォールバック**：LLM が失敗した場合は正規表現ベースの `naive_extract` が動作
- **重複排除**：同じ tweet ID または URL のシグナルは保存・発注されない

### 発注制御

- `TWITTER_AUTO_TRADE_ENABLED` / `DEXTER_AUTO_TRADE_ENABLED` でソース別にオン/オフ
- `TWITTER_BROKER_ENV` / `DEXTER_BROKER_ENV` でソース別に REAL / SIMULATE を切り替え
- `MIN_CONFIDENCE`（デフォルト 0.7）を下回るシグナルは発注しない
- 発注数量は `DEFAULT_ORDER_USD / 直近株価` で自動計算（株価取得失敗時は 1 株）

### リスク管理

- `MAX_POSITION_PER_TICKER`：ティッカーごとの最大建玉数（デフォルト 2）
- `MAX_DAILY_LOSS`：日次最大損失額（現在は設定値を保持、チェック実装は今後）

### ブローカー

| ブローカー | 概要 |
|------------|------|
| `moomoo` | moomoo 証券 OpenD 経由。REAL / SIMULATE 切り替え可 |
| `paper` | ローカル DB 上のシミュレーション。OpenD 不要 |

### 状態管理

- `GET /orders` / `GET /positions` / `GET /executions` / `GET /pnl`：DB から最新状態を返す
- `POST /sync`：moomoo OpenD から注文・約定・ポジション・PnL を取得して DB に反映
- sync_worker が `SYNC_INTERVAL_MINUTES` おきに自動実行

### フロントエンド

- シグナル・注文・ポジション・PnL の一覧表示
- Twitter Cookie（auth_token / ct0）の登録・ステータス確認
- ポート 80 で提供（Docker 起動時）

---

## クイックスタート

```bash
# ペーパー取引（OpenD 不要）
docker compose up -d

# moomoo REAL / SIMULATE（OpenD 込み）
docker compose --profile moomoo up -d
```

詳細な設定は [backend/README.md](backend/README.md) を参照。
