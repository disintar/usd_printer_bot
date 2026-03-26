# Структура проекта dbablo

## Содержание

1. [Обзор проекта](#1-обзор-проекта)
2. [Архитектура системы](#2-архитектура-системы)
3. [Frontend (React/Vite)](#3-frontend-reactvite)
4. [Backend (Django)](#4-backend-django)
5. [Wallet System - Кошелёк](#5-wallet-system---кошелёк)
6. [AI Hedge Fund - Демо-торговый движок](#6-ai-hedge-fund---демо-торговый-движок)
7. [Core App - Django Core](#7-core-app---django-core)
8. [TUI - Терминальный интерфейс](#8-tui---терминальный-интерфейс)
9. [Конфигурация](#9-конфигурация)

---

## 1. Обзор проекта

**dbablo** — это демо-приложение "Персональный хедж-фонд" (PersonalFund/xStocks), которое позволяет пользователям:

- Выбирать AI-агентов для торговли (моделированных по известным инвесторам)
- Получать рекомендации по портфелю от AI-советников
- Симулировать торговлю акциями в тестовом режиме
- Отслеживать P&L (прибыль/убыток) в реальном времени

**Стек технологий:**
- **Frontend**: React + TypeScript + Vite + Tailwind-подобные стили
- **Backend**: Django + Django REST Framework
- **AI**: LangGraph + Multi-Agent System (18 торговых агентов)
- **База данных**: SQLite (по умолчанию), поддержка PostgreSQL
- **Аутентификация**: Telegram Login Widget / Telegram Auth

---

## 2. Архитектура системы

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Telegram Mini App                            │
│                    (React SPA в WebView)                            │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ HTTP/REST
┌─────────────────────────────────────────────────────────────────────┐
│                     Django Backend (:8000)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │
│  │   wallet/   │  │   core/     │  │ external/ai-hedge-fund/ │   │
│  │   views     │  │   views     │  │     app/backend/        │   │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘   │
│         │                                    │                      │
│         ▼                                    ▼                      │
│  ┌─────────────┐                   ┌─────────────────────────┐   │
│  │  Services   │                   │   LangGraph Multi-Agent │   │
│  │  (orders,   │                   │   (18 analysts + risk    │   │
│  │   assets,   │                   │    manager + portfolio   │   │
│  │   prices)   │                   │    manager)              │   │
│  └─────────────┘                   └─────────────────────────┘   │
│         │                                    │                      │
│         ▼                                    ▼                      │
│  ┌─────────────┐                   ┌─────────────────────────┐   │
│  │  Models     │                   │   Financial APIs       │   │
│  │  (Django ORM)                   │   (FMP, etc.)          │   │
│  └─────────────┘                   └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Директории проекта

| Директория | Назначение |
|------------|------------|
| `app/` | Django проект (settings, urls) |
| `app/frontend/` | React фронтенд (Mini App) |
| `wallet/` | Основное Django app с кошельком, ордерами, позициями |
| `core/` | Django app для healthcheck и домашней страницы |
| `external/ai-hedge-fund/` | AI хедж-фонд с multi-agentLangGraph системой |
| `tui/` | Терминальный UI (Python) для тестирования |
| `bot/` | Telegram бот (заглушка) |
| `config/` | Конфигурационные файлы |
| `k8s/` | Kubernetes манифесты |
| `docker/` | Docker файлы |

---

## 3. Frontend (React/Vite)

### 3.1 Структура файлов

```
app/frontend/src/
├── App.tsx                 # Главный компонент, роутинг по state
├── main.tsx                # Точка входа
├── index.css               # Глобальные стили
├── env.d.ts                # TypeScript env definitions
├── assets/                 # Иконки активов (aaplx.png, etc.)
├── components/             # Переиспользуемые компоненты
│   ├── AdvisorIcon.tsx     # Иконка советника
│   ├── AppShell.tsx        # Обёртка приложения
│   ├── BottomNav.tsx       # Нижняя навигация
│   ├── MetricTile.tsx     # Метрика с иконкой
│   └── SectionCard.tsx    # Секция-карточка
├── lib/                    # Утилиты
│   ├── formatters.ts      # Форматирование валюты, процентов
│   ├── presentation.ts     # Цветовые сигналы (buy/sell/hold)
│   ├── advisorWeights.ts   # Нормализация весов советников
│   ├── http.ts            # HTTP клиент с auth
│   └── telegram.ts        # Telegram WebApp integration
├── screens/                # Все экраны приложения
│   ├── WelcomeScreen.tsx   # Приветствие
│   ├── AdvisorSelectionScreen.tsx  # Выбор советников
│   ├── StrategyScreen.tsx # Риск и депозит
│   ├── CouncilAnalyticsScreen.tsx # Загрузка рекомендаций
│   ├── PlanScreen.tsx     # План портфеля
│   ├── DashboardScreen.tsx # Главный экран
│   ├── PortfolioScreen.tsx # Список активов с торговлей
│   ├── AssetDetailScreen.tsx # Детали актива
│   └── SettingsScreen.tsx # Настройки
├── services/
│   └── WalletApi.ts       # API клиент для бэкенда
├── styles/
│   ├── app.css            # Основные стили (CSS переменные)
│   ├── base.css           # Базовые стили
│   └── *.css              # Дополнительные стили
├── test/                  # Тесты
└── types/
    └── api.ts             # TypeScript типы для API
```

### 3.2 Экраны (Screens)

| Экран | Описание | Переходы |
|-------|----------|----------|
| `WelcomeScreen` | Приветствие, "Start Investing", счётчик агентов | → `advisors` |
| `AdvisorSelectionScreen` | Выбор до 3 советников, веса (должны = 100%) | → `strategy` |
| `StrategyScreen` | Риск (low/med/high), сумма депозита ($100-$50k) | → `council` |
| `CouncilAnalyticsScreen` | Загрузка генерации рекомендаций | → `plan` |
| `PlanScreen` | Рекомендуемый портфель, иконки советников | → `dashboard` |
| `DashboardScreen` | Баланс, P&L, кнопки, агенты, время сервера | ↔ `portfolio`, `settings` |
| `PortfolioScreen` | Таблица активов, Buy/Sell модалки, P&L | → `asset`, `dashboard` |
| `AssetDetailScreen` | График, сигналы советников, торговля | → `dashboard` |
| `SettingsScreen` | Риск профиль, выбранные советники | → `advisors` |

### 3.3 Навигация

**State-based routing** — единый state `view` в App.tsx:

```typescript
type RootView = 
  | "welcome" 
  | "strategy" 
  | "advisors" 
  | "council" 
  | "plan" 
  | "dashboard" 
  | "portfolio" 
  | "settings" 
  | "asset";
```

Переход осуществляется через `setView("screenName")`. **BottomNav** отображается только для `dashboard`, `portfolio`, `settings`.

### 3.4 API клиент (WalletApi.ts)

Все методы возвращают Promise, используют Bearer token auth:

| Метод | Endpoint | Назначение |
|-------|----------|------------|
| `authenticateTelegram()` | `POST /auth/telegram` | Аутентификация Telegram |
| `listAdvisors()` | `GET /advisors/list` | Список AI советников |
| `getPreferences()` | `GET /advisors/preferences` | Сохранённые предпочтения |
| `updatePreferences()` | `POST /advisors/preferences` | Сохранить выбор советников |
| `getStartRecommendations()` | `POST /advisors/start` | Генерация рекомендаций |
| `deposit()` | `POST /test/deposit` | Пополнение тестового счёта |
| `getBalance()` | `GET /test/balance` | Баланс кошелька |
| `getTestPrices()` | `GET /test/prices` | Текущие цены активов |
| `getAssets()` | `GET /test/assets` | Активы с P&L |
| `getPortfolio()` | `GET /test/portfolio` | Позиции портфеля |
| `buyAsset()` | `POST /test/buy` | Купить актив |
| `sellAsset()` | `POST /test/sell` | Продать актив |
| `getTestTime()` | `GET /test/time` | Серверное и симулируемое время |

### 3.5 Состояние приложения

Весь state в **App.tsx** (props drilling, без Context):

```typescript
// Auth & User
const [username, setUsername] = useState("telegram");
const [isLoading, setIsLoading] = useState(true);

// Advisors
const [advisors, setAdvisors] = useState<AdvisorDefinition[]>([]);
const [preferences, setPreferences] = useState<AdvisorPreferences>(...);

// Portfolio
const [balance, setBalance] = useState<BalanceResponse | null>(null);
const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
const [assets, setAssets] = useState<AssetSummary[]>([]);

// Test Mode
const [testClock, setTestClock] = useState<TestTimeResponse | null>(null);
const [testPrices, setTestPrices] = useState<Record<string, string>>({});
const [testAgents, setTestAgents] = useState<TestAgentsResponse | null>(null);

// Trading
const [selectedAssetId, setSelectedAssetId] = useState("");
const [tradeAmount, setTradeAmount] = useState("250");
```

---

## 4. Backend (Django)

### 4.1 Точка входа

```
manage.py
├── app/                    # Django проект
│   ├── settings.py         # Настройки (DB, apps, middleware)
│   └── urls.py             # Главные routes
├── wallet/                 # Главное Django app
│   ├── views/              # API endpoints
│   ├── services/           # Бизнес-логика
│   ├── models.py           # Django ORM модели
│   └── urls.py             # Wallet routes
├── core/                   # Core app (healthcheck)
└── external/ai-hedge-fund/ # AI trading system
```

### 4.2 Wallet App (wallet/)

**Views** (`wallet/views/`):

| View | Endpoint | Описание |
|------|----------|----------|
| `TelegramAuthView` | `POST /auth/telegram` | Аутентификация по Telegram ID |
| `TestBalanceView` | `GET /test/balance` | Баланс с P&L |
| `TestDepositView` | `POST /test/deposit` | Пополнение (max 1M USDT) |
| `TestBuyView` | `POST /test/buy` | Покупка актива |
| `TestSellView` | `POST /test/sell` | Продажа актива |
| `TestAssetsView` | `GET /test/assets` | Список активов |
| `TestAssetDetailView` | `GET /test/asset/<id>` | Детали актива |
| `TestPricesView` | `GET /test/prices` | Цены + время сервера |
| `TestTimeView` | `GET /test/time` | Серверное/симулируемое время |
| `TestPortfolioView` | `GET /test/portfolio` | Позиции портфеля |
| `TestOrdersView` | `GET /test/orders` | История ордеров |
| `AdvisorsListView` | `GET /advisors/list` | Список AI советников |
| `AdvisorStartView` | `GET/POST /advisors/start` | Генерация рекомендаций |

**Services** (`wallet/services/`):

| Service | Описание |
|---------|----------|
| `AuthenticationService` | Telegram auth, token management |
| `OrdersService` | Buy/sell execution, FIFO lots |
| `PositionsService` | Position management, P&L calculation |
| `PortfolioService` | Portfolio summary, equity calculation |
| `WalletSummaryService` | Balance and P&L calculation |
| `PricesService` | Price fetching (FMP API or cache) |
| `AssetsService` | Asset listing with marks |
| `RiskService` | Risk assessment |
| `AIAgentsService` | Agent selection, allocation, reasoning |
| `AdvisorsService` | Advisor registry |
| `TestTimeWarpService` | Simulated time for backtesting |

**Models** (`wallet/models.py`):

| Model | Поля | Описание |
|-------|------|----------|
| `TelegramIdentity` | `telegram_user_id`, `token`, `username` | Связка Telegram ID ↔ token |
| `WalletAccount` | `identity`, `cash_balance`, `initial_cash`, `net_cash_flow` | Счёт пользователя |
| `AssetPosition` | `account`, `asset_id`, `quantity`, `average_entry_price` | Позиция по активу |
| `PositionLot` | `position`, `quantity`, `entry_price`, `remaining_quantity` | FIFO лот |
| `TestOrder` | `account`, `asset_id`, `side`, `quantity`, `price`, `notional` | Исполненный ордер |
| `AgentPreference` | `account`, `selected_agents`, `allocation` | Предпочтения агентов |

### 4.3 Аутентификация

**Два способа:**

1. **Telegram Auth** (`/auth/telegram`):
   - Клиент отправляет `telegram_user_id` + `username`
   - Создаётся/обновляется `TelegramIdentity` и `WalletAccount`
   - Возвращается token для Bearer auth

2. **Telegram Login Widget** (`/auth/telegram/widget`):
   - Верификация через Telegram API
   - Создаётся сессия через `AuthSession`

**Decorator `@require_auth`** — извлекает `Bearer <token>` из заголовка, резолвит в `TelegramIdentity`.

---

## 5. Wallet System - Кошелёк

### 5.1 Пополнение (Deposit)

```
POST /test/deposit { "amount": "1000" }
  → TestDepositView.post()
  → validate_positive_decimal(amount)
  → account.cash_balance += amount
  → account.initial_cash += amount (track deposits separately)
  → Returns: { deposited, new_balance }
```

### 5.2 Покупка (Buy)

```
POST /test/buy { "asset_id": "AAPLx", "quantity": "10" }
  или
POST /test/buy { "asset_id": "AAPLx", "amount_usdt": "2000" }
  → TestBuyView.post()
  → _normalize_asset_id(asset_id) → uppercase
  → validate: asset_id in TRADEABLE_ASSET_IDS
  → If amount_usdt: quantity = amount_usdt / current_price
  → OrdersService.create_buy_order():
      1. price = PricesService.get_price(asset_id)
      2. notional = price * quantity
      3. validate: account.cash_balance >= notional
      4. ATOMIC transaction:
         - account.cash_balance -= notional
         - PositionLot.create(quantity, entry_price=price)
         - Recalc AssetPosition.average_entry_price
         - TestOrder.create(status="filled")
  → Returns: { order_id, side, asset_id, quantity, price, notional, status }
```

### 5.3 Продажа (Sell)

```
POST /test/sell { "asset_id": "AAPLx", "quantity": "5" }
  → TestSellView.post()
  → OrdersService.create_sell_order():
      1. price = PricesService.get_price(asset_id)
      2. ATOMIC transaction:
         - Lock AssetPosition for update
         - FIFO: consume PositionLot oldest-first
         - Update remaining_quantity for each lot
         - Recalc AssetPosition from remaining lots
         - account.cash_balance += notional
         - TestOrder.create(status="filled")
  → Returns: { order_id, side, asset_id, quantity, price, notional, status }
```

### 5.4 FIFO Lot система

При покупке создаётся `PositionLot`:
- `quantity` = сколько куплено
- `entry_price` = цена покупки
- `remaining_quantity` = сколько осталось (для частичных продаж)

При продаже:
1. Блокируется позиция `select_for_update()`
2. Лоты обрабатываются FIFO (oldest first)
3. Из каждого лота вычитается sold quantity
4. Когда `remaining_quantity = 0`, лот полностью закрыт

### 5.5 Price Service

```python
class PricesService:
    @classmethod
    def get_price(cls, asset_id: str) -> Decimal:
        if TEST_TIME_WARP_ENABLED:
            # Симулированное время - цены из TestTimeWarpService
            return TestTimeWarpService.get_price(asset_id)
        else:
            # Реальное время - синхронизация с FMP
            cls.sync_latest_prices()
            return cls._latest_snapshot(asset_id).price
```

---

## 6. AI Hedge Fund - Демо-торговый движок

### 6.1 Обзор архитектуры

**Multi-Agent LangGraph система**, которая:
1. Запускает 18 аналитических агентов параллельно
2. Каждый агент анализирует тикеры по-своему (рост, стоимость, технический анализ и т.д.)
3. Risk Manager рассчитывает волатильность и корреляции
4. Portfolio Manager (с LLM) синтезирует финальные решения

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  start_node ──▶ [Warren Buffett Agent] ──┐                          │
│                [Peter Lynch Agent] ───────┼──▶ risk_management     │
│                [Cathie Wood Agent] ───────┤       agent            │
│                [Technical Analyst] ──────┼──▶ portfolio_          │
│                [Sentiment Analyst] ───────┤      manager           │
│                ... (18 agents max) ───────┘       │                │
│                                                    ▼                │
│                                              [END - JSON decisions]│
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Agent State

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]  # Накапливаем сообщения
    data: Annotated[dict[str, Any], merge_dicts]              # Агрегируем данные
    metadata: Annotated[dict[str, Any], merge_dicts]           # Конфиг (model, etc.)
```

### 6.3 Агенты-аналитики (18 штук)

| Агент | Файл | Стратегия |
|-------|------|-----------|
| `aswath_damodaran` | `damodaran_agent.py` | DCF, стоимость |
| `ben_graham` | `ben_graham_agent.py` | Маржинальная безопасность |
| `warren_buffett` | `buffett_agent.py` | ROE, EPS growth, конкурентное преимущество |
| `cathie_wood` | `cathie_wood_agent.py` | Инновации, долгосрочный рост |
| `peter_lynch` | `peter_lynch_agent.py` | Рост выручки, PEG ratio |
| `michael_burry` | `michael_burry_agent.py` | Корреляция, contrarian |
| `stanley_druckenmiller` | `druckenmiller_agent.py` | Макро, валюта |
| `charlie_munger` | `charlie_munger_agent.py` | Мышление через модели |
| `phil_fisher` | `phil_fisher_agent.py` | Качество управления |
| `joe_magaliff` | `magaliff_agent.py` | Инсайдерские сделки |
| `bill_ackman` | `ackman_agent.py` | Конвертируемые облигации |
| `ray_dalio` | `dalio_agent.py` | Макроэкономика |
| `george_soros` | `soros_agent.py` | Рефлексивность |
| `jim_simmons` | `simmons_agent.py` | Количественный анализ |
| `growth_analyst` | `growth_agent.py` | Рост выручки, маржинальность |
| `technical_analyst` | `technical_analyst_agent.py` | Тренды, паттерны |
| `sentiment_analyst` | `sentiment_analyst_agent.py` | Новостной sentiment |
| `risk_assessment` | `risk_assessment_agent.py` | Оценка риска |

### 6.4 Risk Manager

```python
# Волатильность → лимит позиции
if annualized_vol < 0.15: vol_multiplier = 1.25   # Стабильные акции
elif annualized_vol < 0.30: vol_multiplier = 1.0 - (vol - 0.15) * 0.5
elif annualized_vol < 0.50: vol_multiplier = 0.75 - (vol - 0.30) * 0.5
else: vol_multiplier = 0.50

# Корреляция между тикерами
if avg_correlation >= 0.8: corr_multiplier = 0.70
elif avg_correlation >= 0.6: corr_multiplier = 0.85

# Финальный лимит
position_limit = total_portfolio_value * vol_adjusted_limit_pct * corr_multiplier
```

### 6.5 Portfolio Manager (LLM-powered)

1. Собирает сигналы от всех аналитиков
2. Добавляет ограничения от Risk Manager
3. Формирует prompt для LLM
4. LLM выбирает action: `buy`, `sell`, `short`, `cover`, `hold`

### 6.6 Инструменты (Tools)

| Tool | API | Назначение |
|------|-----|------------|
| `get_prices()` | Financial Datasets API | OHLCV данные |
| `get_financial_metrics()` | Financial Datasets API | PE, PEG, revenue growth |
| `search_line_items()` | Financial Datasets API | Income statement items |
| `get_insider_trades()` | Financial Datasets API | Insider транзакции |
| `get_company_news()` | Financial Datasets API | Новости с sentiment |

### 6.7 Endpoints

| Endpoint | Описание |
|----------|----------|
| `POST /hedge-fund/run` | Запустить trading flow |
| `POST /hedge-fund/backtest` | Запустить backtesting |
| `GET /hedge-fund/agents` | Список агентов |

---

## 7. Core App - Django Core

Минимальное Django app для healthcheck:

```python
# core/urls.py
urlpatterns = [
    path("", home, name="home"),           # GET / → "dbablo backend"
    path("healthz/", healthcheck, name="healthcheck"),  # GET /healthz/ → OK
]
```

---

## 8. TUI - Терминальный интерфейс

Python терминальное приложение для тестирования API без Telegram:

```
tui/
├── __main__.py      # entry point: python -m tui
├── app.py           # Textual app
├── api.py           # WalletApi клиент (httpx)
├── session_store.py # SessionStorage
├── terminal_compat.py
├── utils.py
├── screens/         # Textual screens
└── tests/          # pytest tests
```

**TUI API клиент** — обёртка над httpx с теми же методами что и frontend WalletApi.

---

## 9. Конфигурация

### 9.1 Environment Variables

| Variable | Default | Описание |
|----------|---------|----------|
| `DATABASE_URL` | `db.sqlite3` | SQLite по умолчанию |
| `SECRET_KEY` | `...` | Django secret key |
| `DEBUG` | `false` | Debug mode |
| `ALLOWED_HOSTS` | `*` | CORS |
| `FMP_ENABLED` | `true` | FMP API для цен |
| `FMP_API_KEY` | `...` | Financial Datasets API key |
| `PRICE_CRON_ENABLED` | `true` | Cron для цен |
| `PRICE_CRON_INTERVAL_SECONDS` | `60` | Интервал cron |
| `TEST_TIME_WARP_ENABLED` | `true` | Симуляция времени |
| `TEST_TIME_WARP_INTERVAL_SECONDS` | `1` | Шаг симуляции |

### 9.2 Test Time Warp

Режим симуляции времени для демо-торговли:
- `TEST_TIME_WARP_ENABLED=true` — включает симуляцию
- Каждые `TEST_TIME_WARP_INTERVAL_SECONDS` (по умолчанию 1 сек) симулируется 1 час
- Цены берутся из исторических данных Financial Datasets API
- После 60 тиков (60 часов) происходит reset

```python
# TestTimeWarpService
HOURS_PER_TICK = 1      # 1 час за тик
WINDOW_DAYS = 60        # 60 дней окно исторических данных
```

### 9.3 Start Scripts

| Script | Назначение |
|--------|------------|
| `start_local.sh` | Запуск всего приложения локально |
| `build.sh` | Сборка всех компонентов |
| `build-miniapp.sh` | Сборка frontend |
| `build-ai-hedge-fund-backend.sh` | Сборка AI бэкенда |
| `build-fmp-mcp.sh` | Сборка FMP MCP сервера |

---

## 10. Типичный пользовательский flow

```
1. Открывает Telegram Mini App
   ↓
2. WelcomeScreen → "Start Investing"
   ↓
3. AdvisorSelectionScreen → Выбирает 3 советников (Warren Buffett, Peter Lynch, Growth Analyst)
   ↓
4. StrategyScreen → Risk = "Medium", Deposit = "$5,000"
   ↓
5. CouncilAnalyticsScreen → AI анализирует, генерирует рекомендации
   ↓
6. PlanScreen → Видит рекомендуемый портфель (AAPLx 40%, NVDAx 35%, etc.)
   ↓
7. DashboardScreen → Баланс $5,000, P&L 0%
   ↓
8. PortfolioScreen → Таблица активов
   ↓
9. Кликает "Buy" на AAPLx → TradeModal → Вводит $1000 → Buy
   ↓
10. balance → $4000, assets → AAPLx с position
    ↓
11. Каждую секунду (polling):
    - getTestTime() → server_time, simulated_time
    - getTestPrices() → текущие цены
    - getAssets() → P&L обновляется
    - getBalance() → баланс + P&L
```

---

## 11. Ключевые файлы

| Файл | Назначение |
|------|------------|
| `manage.py` | Django CLI |
| `app/settings.py` | Django настройки |
| `wallet/views/wallet.py` | Основные API endpoints |
| `wallet/views/trading.py` | Trading endpoints (buy/sell) |
| `wallet/services/orders.py` | Логика исполнения ордеров |
| `wallet/services/test_time_warp.py` | Симуляция времени |
| `external/ai-hedge-fund/src/main.py` | LangGraph entry point |
| `external/ai-hedge-fund/src/graph/state.py` | AgentState definition |
| `external/ai-hedge-fund/src/utils/analysts.py` | 18 агентов конфиг |
| `app/frontend/src/App.tsx` | React app state management |

---

*Документация создана на основе анализа исходного кода проекта dbablo.*