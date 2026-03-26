# dbablo - Custodial Wallet Service

A Django-based custodial wallet service with Telegram authentication and a terminal UI interface.

All onchain operations in this project run on **TON** (The Open Network).

## Architecture

- **Backend**: Django REST API (`wallet` app)
- **TUI**: Textual-based terminal interface (`tui/`)
- **Bot**: Telegram bot for authentication (`bot/`)

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start Backend

```bash
# Run migrations (first time only)
python manage.py migrate

# Start Django server
python manage.py runserver 0.0.0.0:8000
```

The API will be available at `http://localhost:8000`

### 3. Start Telegram Bot (optional, for real Telegram auth)

```bash
source .venv/bin/activate
export TELEGRAM_BOT_TOKEN="your-bot-token"
export BACKEND_URL="http://localhost:8000"
python -m bot.telegram_bot
```

The bot handles `/start` commands for Telegram Login Widget authentication.

### 4. Start TUI

```bash
source .venv/bin/activate
python -m tui
```

The TUI will connect to `http://localhost:8000` by default. To use a different URL:

```bash
python -m tui --url http://your-server:8000
```

To bypass Telegram login with an existing session token:

```bash
python -m tui --url http://localhost:8000 --token <session_token>
```

## Testing

```bash
source .venv/bin/activate

# Run all tests
python manage.py test wallet.tests
python -m pytest tui/tests/ bot/tests/ -v
```

## Components

### Backend API Endpoints

**Health & Info:**
- `GET /health` - Health check
- `GET /bot/info` - Get bot info (username, first_name, login URL)

**Authentication:**
- `POST /auth/telegram` - Authenticate with Telegram user ID
- `POST /auth/telegram/widget` - Telegram Login Widget verification
- `POST /auth/pending` - Create pending auth token
- `GET /auth/pending/<token>` - Check pending auth status
- `POST /auth/complete` - Complete pending auth (called by bot)
- `GET /auth/session/<token>` - Validate session

**Wallet (requires auth):**
- `GET /test/balance` - Get wallet balance with PnL
- `GET /test/address` - Get deterministic test address
- `POST /test/deposit` - Deposit USDt
- `POST /test/withdraw` - Withdraw USDt
- `POST /test/transfer` - Transfer to another user

**Trading (requires auth):**
- `GET /test/assets` - List all supported assets
- `GET /test/asset/<id>` - Get asset detail
- `GET /test/positions` - Get open positions
- `POST /test/buy` - Place buy order
- `POST /test/sell` - Place sell order
- `GET /test/orders` - Get order history
- `GET /test/order/<id>` - Get specific order
- `GET /test/prices` - Get all asset prices

**AI Agents (requires auth):**
- `GET /test/agents` - Get AI agents info
- `POST /test/agents/select` - Select active agents
- `GET /test/agents/allocation` - Get agent allocation
- `POST /test/agents/allocation` - Update allocation
- `GET /test/agents/reasoning?asset_id=X` - Get agent reasoning

**Advisors (requires auth):**
- `GET /advisors/list` - List configured adviser personas
- `GET /advisors/preferences` - Get selected advisers + risk profile
- `POST /advisors/preferences` - Update selected advisers + risk profile
- `POST /advisors/start` - Get initial buy plan for deposit amount
- `GET /advisors/analysis` - Get asset analysis
- `POST /advisors/recommendations` - Get portfolio/cash recommendations

**Portfolio (requires auth):**
- `GET /test/portfolio` - Get portfolio summary
- `POST /test/rebalance` - Get rebalancing actions
- `GET /test/risk` - Get risk assessment

**Onchain (TON, requires auth):**
- `POST /onchain/wallet/create` - Create onchain wallet for user
- `POST /onchain/deploy` - Deploy onchain wallet contract
- `GET /onchain/address` - Get user TON wallet address
- `GET /onchain/balance` - Get onchain balances and positions
- `POST /onchain/withdraw` - Withdraw funds onchain
- `POST /onchain/buy` - Execute buy order onchain
- `POST /onchain/sell` - Execute sell order onchain
- `GET /onchain/orders` - List onchain orders
- `GET /onchain/order/<id>` - Get onchain order details

### Supported Assets

- USDt (stablecoin)
- TSLAx, HOODx, AMZNx, NVDAx, COINx, GOOGLx, AAPLx, MSTRx (stock derivatives)

### AI Agents

- **Buy** - Long-term growth agent
- **Cover** - Risk management agent
- **Sell** - Profit-taking agent
- **Short** - Momentum trading agent
- **Hold** - Balance-focused agent

### Advisers

Adviser personas are configured via code and exposed by `/advisors/list`. Per-user adviser selection and risk profile are stored in `AgentPreference`.

Adviser recommendations are converted into UI marks:
- `buy`, `buy_more` → 🟢 Buy
- `sell` → 🔴 Sell
- `hold` → 🟡 Hold

## TUI Interface

### Login Flow

1. Click "Login with Telegram" button
2. TUI creates a pending auth token via backend
3. A browser opens to Telegram bot with login URL
4. User approves login in Telegram
5. Bot notifies backend which stores the auth
6. TUI polls backend for auth completion
7. Dashboard displayed!

### Main Dashboard

The main screen shows:
- Wallet balance (Cash, Equity, Total, PnL)
- Open positions table
- Available assets table
- Asset detail panel

### Navigation

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh data |
| `b` | Buy selected asset |
| `s` | Sell selected asset |
| `d` | Deposit funds |
| `w` | Withdraw funds |
| `t` | Transfer funds |
| `enter` | Generate analytics for selected asset |
| `o` | View orders |
| `p` | View portfolio |
| `escape` | Back (on sub-screens) |

### Color-Coded Marks

- 🟢 **Buy** - Green
- 🔴 **Sell** - Red
- 🟡 **Hold** - Yellow
- 🔵 **Cover** - Cyan
- 🟣 **Short** - Magenta

## Project Structure

```
dbablo/
├── wallet/                  # Django wallet app
│   ├── views/              # API views (modular)
│   │   ├── auth.py        # Authentication views
│   │   ├── bot.py         # Bot info endpoint
│   │   ├── wallet.py      # Balance, deposit, withdraw, transfer
│   │   ├── trading.py     # Assets, positions, orders
│   │   ├── agents.py      # AI agents
│   │   └── portfolio.py   # Portfolio, rebalance, risk
│   ├── services/           # Business logic services
│   │   ├── authentication.py
│   │   ├── auth_sessions.py
│   │   ├── telegram_auth.py
│   │   └── wallet_summary.py
│   ├── models.py           # Database models
│   ├── constants.py        # Constants and prices
│   └── tests/              # API tests
├── tui/                    # Terminal UI
│   ├── screens/            # Textual screens
│   │   ├── login.py       # Login screen
│   │   ├── dashboard.py   # Main dashboard
│   │   ├── orders.py      # Order history
│   │   ├── portfolio.py   # Portfolio view
│   │   └── rebalance.py   # Rebalance recommendations
│   ├── modals/             # Modal dialogs
│   │   ├── order.py       # Buy/sell order
│   │   ├── transfer.py     # Transfer funds
│   │   ├── deposit_withdraw.py
│   │   └── agent_select.py
│   ├── api.py              # API client
│   ├── app.py              # Main app
│   └── session_store.py    # Token persistence
├── bot/                    # Telegram bot
│   └── telegram_bot.py     # Bot implementation
├── config/                  # Django settings
└── README.md
```

## Development

### Adding New Endpoints

1. Create service in `wallet/services/`
2. Create view in `wallet/views/`
3. Add URL route in `wallet/urls.py`
4. Add API method in `tui/api.py`
5. Add tests

### Code Style

- Strict typing everywhere
- Class-based design
- Loguru for structured logging
- Max 400 lines per file

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `unsafe-dev-secret-key` |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Allowed hosts | `*` |
| `TELEGRAM_BOT_TOKEN` | Bot token for auth | (required for bot) |
| `BACKEND_URL` | Backend URL for bot | `http://localhost:8000` |
| `LOG_LEVEL` | Log level for loguru | `INFO` |

## Docker

```bash
# Build
docker build -t dbablo:latest .

# Run
docker run --env-file .env -p 8000:8000 dbablo:latest
```
