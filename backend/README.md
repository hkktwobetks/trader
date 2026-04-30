## ブローカー統合

ブローカーは `src/broker/base.py` の抽象レイヤーで切り替え可能。
`BROKER` 環境変数で `paper` または `moomoo` を指定する。

---

### LLM（シグナル抽出）

ツイートなどのテキストからティッカー・売買方向・信頼度を抽出するために LLM を使用する。
`LLM_PROVIDER` 環境変数で実装を切り替える。

#### Groq（デフォルト推奨）

無料枠で高速に動作する。`llama-3.3-70b-versatile` がデフォルトモデル。

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=gsk_xxxxxxxx          # Groq API キー
OPENAI_API_BASE=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
```

#### Ollama（ローカルモデル）

```bash
ollama pull qwen3:14b
ollama serve
```

```bash
LLM_PROVIDER=ollama
OPENAI_API_BASE=http://127.0.0.1:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen3:14b
```

推奨モデル：
- `qwen3:14b`：品質・速度バランスが良い
- `qwen3:30b`：VRAM に余裕があれば抽出精度が上がる

#### OpenAI 互換サーバー（その他）

```bash
LLM_PROVIDER=local_openai
OPENAI_API_BASE=http://127.0.0.1:11434/v1
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=your-model
```

---

### Moomoo OpenD

> 日本の moomoo/FUTU JP アカウントは `MOOMOO_LOGIN_REGION=jp`、`MOOMOO_SECURITY_FIRM=auto` の設定が必要。

#### 前提
- OpenD をローカル起動し、ペーパー取引以上のアクセスが可能なアカウントでサインイン済みであること。
- バックエンドから OpenD に到達できること（デフォルト: `127.0.0.1:11111`）。

#### 環境変数

```bash
BROKER=moomoo
BROKER_ENV=SIMULATE              # REAL にすると本番取引
TWITTER_BROKER_ENV=REAL          # Twitter シグナルの発注先
DEXTER_BROKER_ENV=SIMULATE       # Dexter シグナルの発注先
TWITTER_AUTO_TRADE_ENABLED=true
DEXTER_AUTO_TRADE_ENABLED=false
MARKET=US                        # US / JP / HK
MOOMOO_OPEND_HOST=127.0.0.1
MOOMOO_OPEND_PORT=11111
MOOMOO_LOGIN_REGION=jp
MOOMOO_SECURITY_FIRM=auto
MOOMOO_PREFERRED_ACC_TYPE=auto   # CASH / MARGIN / DERIVATIVES
MOOMOO_TRADE_PASSWORD_MD5=<取引パスワードの MD5>
MOOMOO_ACC_ID=<任意。アカウント ID を固定する場合>
SYNC_INTERVAL_MINUTES=5
```

シークレットは `backend/.env.local` に記載し、`backend/.env` はコミット用テンプレートとして保持する。

#### Docker 起動

```bash
# リポジトリルートから
docker compose --profile moomoo up -d opend
```

`opend` サービスは `moomoo` プロファイルに属しており、`--profile moomoo` を付けた場合のみ起動する。
Docker では `opend` がバックエンドのネットワーク名前空間を共有（`network_mode: "service:backend"`）するため、
バックエンドは `127.0.0.1:11111` で OpenD に接続する。

ログイン用の変数を `backend/.env.local` に設定する：

```bash
MOOMOO_LOGIN_ACCOUNT=your_account
MOOMOO_LOGIN_PASSWORD_MD5=your_password_md5
MOOMOO_LOGIN_REGION=jp
MOOMOO_SECURITY_FIRM=auto
MOOMOO_TRADE_PASSWORD_MD5=your_trade_password_md5
MOOMOO_LANG=en
MOOMOO_LOG_LEVEL=info
```

#### 状態同期

手動同期：

```bash
curl -X POST http://127.0.0.1:8000/sync
```

状態エンドポイント：

```bash
GET /orders
GET /positions
GET /executions
GET /pnl
```

定期同期（sync_worker が OpenD の起動完了を待ってから開始）：

```bash
docker compose --profile moomoo up -d sync_worker
```

sync_worker は `SYNC_INTERVAL_MINUTES` おきに `POST /sync` を呼び出し、注文・約定・ポジション・PnL を更新する。

#### 接続テスト

```bash
cd backend
./scripts/run_moomoo_connection_test.sh
```

#### MD5 生成（OpenD ログインパスワード）

```bash
./scripts/generate_md5.sh "your_password"
```

---

### Twitter ワーカー

```bash
TWITTER_USERS=snatchan_comm       # 監視するアカウント（カンマ区切りで複数指定可）
POLL_INTERVAL_SEC=30
X_AUTH_TOKEN=<auth_token>
X_CT0=<ct0>
```

Cookie は `/settings/twitter-cookies` エンドポイントまたはダッシュボード（`/dashboard`）から登録できる。
`auth_token` と `ct0` はブラウザの DevTools（Application > Cookies > x.com）から取得する。

Twitter の GraphQL エンドポイント ID が変わった場合は環境変数で上書きできる：

```bash
TW_EP_USER_TWEETS=naBcZ4al-iTCFBYGOAMzBQ
TW_EP_USER_BY_SCREENNAME=sLVLhk0bGj3MVFEKTdax1w
```

---

### Dexter ブリッジ

Dexter は別プロセスの調査エージェント。出力を `source=dexter` としてシステムに取り込む。

手動投入：

```bash
cd backend
python scripts/post_dexter_signal.py '$AAPL BUY swing trade idea from Dexter'
```

Dexter を 1 回実行してシグナルを自動投入：

```bash
export DEXTER_DIR=/path/to/dexter
cd backend
python scripts/run_dexter_signal.py "Find one US large-cap momentum trade for today"
```

定期実行（dexter_worker プロファイル）：

```bash
export DEXTER_DIR=/path/to/dexter
export DEXTER_QUERY="Find one US large-cap momentum trade for today"
docker compose --profile dexter up -d dexter_worker
```

`DEXTER_POLL_INTERVAL_SEC` おきに Dexter を実行し、`NO_SIGNAL` 以外の出力を `/signals` に投入する。

---

### Paper ブローカー

`BROKER=paper` はローカルの SQLite DB 上で動作するシミュレーション実装。
OpenD は不要で、システム全体の動作確認に使用する。
