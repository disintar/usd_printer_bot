import { useEffect, useRef, useState } from "react";

import { AppShell } from "./components/AppShell";
import { BottomNav } from "./components/BottomNav";
import { CouncilAnalyticsScreen } from "./screens/CouncilAnalyticsScreen";
import { AdvisorWeightsModel } from "./lib/advisorWeights";
import { HttpClient } from "./lib/http";
import { TelegramWebAppService } from "./lib/telegram";
import { SessionStorageService } from "./services/SessionStorage";
import { WalletApi } from "./services/WalletApi";
import { AdvisorSelectionScreen } from "./screens/AdvisorSelectionScreen";
import { AssetDetailScreen } from "./screens/AssetDetailScreen";
import { DashboardScreen } from "./screens/DashboardScreen";
import { HistoryScreen } from "./screens/HistoryScreen";
import { PlanScreen } from "./screens/PlanScreen";
import { PortfolioScreen } from "./screens/PortfolioScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { StrategyScreen } from "./screens/StrategyScreen";
import { WelcomeScreen } from "./screens/WelcomeScreen";
import type {
  AdvisorDefinition,
  AdvisorPreferences,
  AdvisorAction,
  AssetAnalysisResponse,
  AssetDetail,
  AssetSummary,
  BalanceResponse,
  OrderHistoryItem,
  PortfolioResponse,
  RiskProfile,
  StartRecommendationsResponse,
  TestAgentsResponse,
  TestTimeResponse,
} from "./types/api";

type RootView =
  | "welcome"
  | "strategy"
  | "advisors"
  | "council"
  | "plan"
  | "dashboard"
  | "portfolio"
  | "history"
  | "settings"
  | "asset";

const api = new WalletApi(
  new HttpClient(import.meta.env.VITE_API_URL ?? "/api", () =>
    SessionStorageService.getToken(),
  ),
);

const DEFAULT_BALANCE: BalanceResponse = {
  cash_usdt: "0",
  equity_usdt: "0",
  total_balance_usdt: "0",
  pnl_percent: "0",
  pnl_absolute: "0",
  assets: [],
};

const DEFAULT_PORTFOLIO: PortfolioResponse = {
  total_balance_usdt: "0",
  pnl_percent: "0",
  pnl_absolute: "0",
  allocation: {},
  assets: [],
};

const TRADEABLE_ASSET_IDS = new Set<string>([
  "TSLAX",
  "HOODX",
  "AMZNX",
  "NVDAX",
  "COINX",
  "GOOGLX",
  "AAPLX",
  "MSTRX",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRiskProfile(value: unknown): value is RiskProfile {
  return value === "low" || value === "medium" || value === "high";
}

function summarizePayloadShape(payload: unknown): unknown {
  if (Array.isArray(payload)) {
    return { type: "array", length: payload.length };
  }
  if (!isRecord(payload)) {
    return { type: typeof payload };
  }
  return Object.fromEntries(
    Object.entries(payload).map(([key, value]) => {
      if (Array.isArray(value)) {
        return [key, `array(len=${value.length})`];
      }
      if (isRecord(value)) {
        return [key, `object(keys=${Object.keys(value).join(",")})`];
      }
      return [key, value === null ? "null" : typeof value];
    }),
  );
}

function hasExpectedPreferencesShape(value: unknown): boolean {
  if (!isRecord(value)) {
    return false;
  }
  return (
    Array.isArray(value.selected_advisors) &&
    isRecord(value.advisor_weights) &&
    typeof value.risk_profile === "string"
  );
}

function withNormalizedAdvisorWeights(
  preferences: unknown,
): AdvisorPreferences {
  const raw = isRecord(preferences) ? preferences : {};
  const selectedAdvisors = Array.isArray(raw.selected_advisors)
    ? raw.selected_advisors.filter(
        (item): item is string =>
          typeof item === "string" && item.trim() !== "",
      )
    : [];
  const riskProfile: RiskProfile = isRiskProfile(raw.risk_profile)
    ? raw.risk_profile
    : "medium";
  const rawWeights = isRecord(raw.advisor_weights)
    ? (raw.advisor_weights as Record<string, number>)
    : undefined;

  return {
    selected_advisors: selectedAdvisors,
    advisor_weights: AdvisorWeightsModel.normalize(
      selectedAdvisors,
      rawWeights,
    ),
    risk_profile: riskProfile,
    onboarding_completed: raw.onboarding_completed === true,
  };
}

function isTradeableAsset(assetId: string): boolean {
  return TRADEABLE_ASSET_IDS.has(assetId.trim().toUpperCase());
}

function normalizeRecommendationAction(
  action: string | null | undefined,
): "buy" | "hold" | "sell" | null {
  const normalizedAction = String(action ?? "").trim().toLowerCase();
  if (normalizedAction === "buy" || normalizedAction === "buy_more") {
    return "buy";
  }
  if (normalizedAction === "hold" || normalizedAction === "sell" ) {
    return normalizedAction;
  }
  return null;
}

function toRecommendationMap(
  actions: Array<AdvisorAction & { verdict?: string }>,
): Record<string, "buy" | "hold" | "sell"> {
  const nextMap: Record<string, "buy" | "hold" | "sell"> = {};
  actions.forEach((item) => {
    const normalizedAssetId = item.asset_id.trim().toUpperCase();
    const normalizedAction = normalizeRecommendationAction(
      item.action ?? item.verdict,
    );
    if (normalizedAssetId === "" || normalizedAction === null) {
      return;
    }
    nextMap[normalizedAssetId] = normalizedAction;
  });
  return nextMap;
}

function withUsdtFromBalance(
  assets: AssetSummary[],
  balance: BalanceResponse,
): AssetSummary[] {
  return assets.map((asset) => {
    if (asset.asset_id.trim().toUpperCase() !== "USDT") {
      return asset;
    }
    return {
      ...asset,
      balance: balance.cash_usdt,
      current_price: "1",
      net_worth: balance.cash_usdt,
      pnl_percent: "0.00",
      pnl_absolute: "0.00",
    };
  });
}

type NetworkMode = "test" | "onchain";

function toOnchainAssetSummaries(balance: BalanceResponse): AssetSummary[] {
  return (balance.assets ?? []).map((asset) => ({
    asset_id: asset.asset_id,
    balance: asset.balance,
    current_price: asset.current_price,
    net_worth: asset.net_worth,
    pnl_percent: asset.pnl_percent,
    pnl_absolute: asset.pnl_absolute,
    mark: "Hold",
  }));
}

function toOnchainPortfolio(balance: BalanceResponse): PortfolioResponse {
  const assets = (balance.assets ?? []).map((asset) => ({
    asset_id: asset.asset_id,
    quantity: asset.balance,
    value_usdt: asset.net_worth,
    allocation_percent: asset.allocation_percent,
  }));
  const allocation = Object.fromEntries(
    assets.map((asset) => [
      asset.asset_id,
      Number.parseFloat(asset.allocation_percent) || 0,
    ]),
  );
  return {
    total_balance_usdt: balance.total_balance_usdt,
    pnl_percent: balance.pnl_percent,
    pnl_absolute: balance.pnl_absolute,
    allocation,
    assets,
  };
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim() !== "") {
    return error.message;
  }
  return fallback;
}

function normalizeDecimalInput(value: string): string {
  return value.replace(/,/g, ".");
}

export function App(): JSX.Element {
  const [applyIosTopInset, setApplyIosTopInset] = useState(false);
  const [view, setView] = useState<RootView>("dashboard");
  const [networkMode, setNetworkMode] = useState<NetworkMode>("test");
  const [username, setUsername] = useState("telegram");
  const [isLoading, setIsLoading] = useState(true);
  const [advisors, setAdvisors] = useState<AdvisorDefinition[]>([]);
  const [preferences, setPreferences] = useState<AdvisorPreferences>({
    selected_advisors: [],
    advisor_weights: {},
    risk_profile: "medium",
    onboarding_completed: false,
  });
  const [depositAmount, setDepositAmount] = useState("1000");
  const [planResult, setPlanResult] =
    useState<StartRecommendationsResponse | null>(null);
  const [balance, setBalance] = useState<BalanceResponse>(DEFAULT_BALANCE);
  const [portfolio, setPortfolio] =
    useState<PortfolioResponse>(DEFAULT_PORTFOLIO);
  const [assets, setAssets] = useState<AssetSummary[]>([]);
  const [testClock, setTestClock] = useState<TestTimeResponse | null>(null);
  const [testPrices, setTestPrices] = useState<Record<string, string>>({});
  const [testAgents, setTestAgents] = useState<TestAgentsResponse | null>(null);
  const [ordersByMode, setOrdersByMode] = useState<
    Record<NetworkMode, OrderHistoryItem[]>
  >({
    test: [],
    onchain: [],
  });
  const [agentsActive, setAgentsActive] = useState<number>(0);
  const [isRefreshingViewData, setIsRefreshingViewData] = useState(false);
  const [isOrdersLoading, setIsOrdersLoading] = useState(false);
  const [hasLoadedOrdersByMode, setHasLoadedOrdersByMode] = useState<
    Record<NetworkMode, boolean>
  >({
    test: false,
    onchain: false,
  });
  const [portfolioRecommendations, setPortfolioRecommendations] = useState<
    Record<string, "buy" | "hold" | "sell">
  >({});
  const [isPortfolioRecommendationsLoading, setIsPortfolioRecommendationsLoading] =
    useState(false);
  const [hasLoadedPortfolioRecommendations, setHasLoadedPortfolioRecommendations] =
    useState(false);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [assetDetail, setAssetDetail] = useState<AssetDetail | null>(null);
  const [assetAnalysis, setAssetAnalysis] =
    useState<AssetAnalysisResponse | null>(null);
  const [assetAnalysisUpdatedAt, setAssetAnalysisUpdatedAt] = useState<
    string | null
  >(null);
  const [tradeAmount, setTradeAmount] = useState("250");
  const [isTopUpModalOpen, setIsTopUpModalOpen] = useState(false);
  const [isTopUpLoading, setIsTopUpLoading] = useState(false);
  const [topUpAddress, setTopUpAddress] = useState("");
  const [topUpCopyState, setTopUpCopyState] = useState<"idle" | "copied">("idle");
  const [isWithdrawalModalOpen, setIsWithdrawalModalOpen] = useState(false);
  const [withdrawalAddress, setWithdrawalAddress] = useState("");
  const [withdrawalAmount, setWithdrawalAmount] = useState("");
  const [isWithdrawalSubmitting, setIsWithdrawalSubmitting] = useState(false);
  const [assetReturnView, setAssetReturnView] = useState<
    "dashboard" | "portfolio" | "plan"
  >("dashboard");
  const didInitRef = useRef(false);
  const dashboardRefreshInFlightRef = useRef(false);
  const dashboardRefreshQueuedRef = useRef(false);
  const hasLoadedPortfolioRecommendationsRef = useRef(false);
  const networkModeRef = useRef<NetworkMode>("test");
  const orders = ordersByMode[networkMode];

  function logError(
    context: string,
    error: unknown,
    details?: Record<string, unknown>,
  ): void {
    const metadata = {
      context,
      mode: import.meta.env.MODE,
      apiBase: import.meta.env.VITE_API_URL ?? "/api",
      view,
      details,
    };
    if (error instanceof Error) {
      console.error(`[App] ${context}`, {
        ...metadata,
        name: error.name,
        message: error.message,
        stack: error.stack,
      });
      return;
    }
    console.error(`[App] ${context}`, { ...metadata, reason: error });
    console.trace(`[App] ${context}`);
  }

  async function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }

  async function callWithRetry<T>(
    label: string,
    request: () => Promise<T>,
    maxAttempts = 2,
    delayMs = 2000,
  ): Promise<T> {
    let lastError: unknown = null;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        return await request();
      } catch (error) {
        lastError = error;
        if (attempt >= maxAttempts) {
          break;
        }
        console.warn(`[App] ${label} failed, retrying`, {
          attempt,
          maxAttempts,
          error,
        });
        await sleep(delayMs);
      }
    }
    throw lastError instanceof Error ? lastError : new Error(`${label} failed`);
  }

  useEffect(() => {
    networkModeRef.current = networkMode;
  }, [networkMode]);

  useEffect(() => {
    if (didInitRef.current) {
      return;
    }
    didInitRef.current = true;
    setApplyIosTopInset(TelegramWebAppService.shouldApplyIosTopInset());
    TelegramWebAppService.initialize();
    void authenticateAndBootstrap();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const sleep = (ms: number): Promise<void> =>
      new Promise((resolve) => {
        window.setTimeout(resolve, ms);
      });

    const pollTime = async (): Promise<void> => {
      while (!cancelled) {
        const token = SessionStorageService.getToken();
        const shouldPoll = view === "dashboard" || view === "portfolio";
        if (token !== null && shouldPoll) {
          const requestMode = networkModeRef.current;
          try {
            if (requestMode === "onchain") {
              const balanceResponse = await api.getOnchainBalance();
              if (!cancelled && networkModeRef.current === requestMode) {
                setBalance(balanceResponse);
                setPortfolio(toOnchainPortfolio(balanceResponse));
                setAssets(toOnchainAssetSummaries(balanceResponse));
              }
            } else {
              const [
                clockResponse,
                pricesResponse,
                assetsResponse,
                balanceResponse,
              ] = await Promise.all([
                api.getTestTime(),
                api.getTestPrices(),
                api.getAssets(),
                api.getBalance(),
              ]);
              if (!cancelled && networkModeRef.current === requestMode) {
                const normalizedAssets = withUsdtFromBalance(
                  assetsResponse.assets,
                  balanceResponse,
                );
                setTestClock({
                  ...clockResponse,
                  server_time_utc_pretty:
                    pricesResponse.server_time_utc_pretty ??
                    clockResponse.server_time_utc_pretty,
                  simulated_time_utc_pretty:
                    pricesResponse.simulated_time_utc_pretty ??
                    clockResponse.simulated_time_utc_pretty,
                });
                setTestPrices(pricesResponse.prices);
                setAssets(normalizedAssets);
                setBalance(balanceResponse);
              }
            }
          } catch {
            // Ignore transient polling errors, full refresh handles hard failures.
          }
        }
        // Wait 5 seconds after previous polling cycle settles.
        await sleep(5000);
      }
    };
    void pollTime();
    return () => {
      cancelled = true;
    };
  }, [view, networkMode]);

  useEffect(() => {
    if (view !== "portfolio") {
      return;
    }

    let cancelled = false;
    let intervalId: number | null = null;

    const loadRecommendations = async (
      showInitialSkeleton: boolean,
    ): Promise<void> => {
      if (showInitialSkeleton) {
        setIsPortfolioRecommendationsLoading(true);
      }

      try {
        const response = await api.getPortfolioRecommendations();
        if (cancelled) {
          return;
        }
        setPortfolioRecommendations(toRecommendationMap(response.actions));
        hasLoadedPortfolioRecommendationsRef.current = true;
        setHasLoadedPortfolioRecommendations(true);
      } catch (error) {
        if (!cancelled) {
          logError("Failed to refresh portfolio recommendations", error, {
            endpoint: "/advisors/recommendations",
          });
        }
      } finally {
        if (!cancelled && showInitialSkeleton) {
          setIsPortfolioRecommendationsLoading(false);
        }
      }
    };

    void loadRecommendations(!hasLoadedPortfolioRecommendationsRef.current);
    intervalId = window.setInterval(() => {
      void loadRecommendations(false);
    }, 30000);

    return () => {
      cancelled = true;
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
    };
  }, [view, networkMode]);

  useEffect(() => {
    if (view !== "dashboard" && view !== "portfolio" && view !== "history") {
      return;
    }
    void refreshDashboard().catch((error: unknown) => {
      logError("Failed to refresh view data", error, {
        view,
        endpoint:
          "/test/balance, /test/portfolio, /test/assets, /test/time, /test/prices, /test/agents, /test/orders",
      });
    });
  }, [view, networkMode]);

  async function authenticateAndBootstrap(): Promise<void> {
    setIsLoading(true);

    try {
      const user = TelegramWebAppService.getUser();
      if (user === null) {
        throw new Error(
          "Telegram user data is unavailable. Set VITE_DEV_TELEGRAM_USER_ID for local development.",
        );
      }

      const auth = await api.authenticateTelegram(user.id, user.username ?? "");
      SessionStorageService.setToken(auth.token);
      setUsername(
        auth.username || user.username || `user${auth.telegram_user_id}`,
      );

      const [advisorsResponse, preferencesResponse, agentsActiveResponse] =
        await Promise.all([
          api.listAdvisors(),
          api.getPreferences(),
          api.getAgentsActive(),
        ]);
      setAgentsActive(agentsActiveResponse.agents_active);

      setAdvisors(advisorsResponse.advisors);
      if (!hasExpectedPreferencesShape(preferencesResponse)) {
        logError(
          "API contract mismatch: /advisors/preferences",
          new Error("Invalid preferences response shape"),
          {
            endpoint: "/advisors/preferences",
            payloadShape: summarizePayloadShape(preferencesResponse),
            payload: preferencesResponse,
          },
        );
      }
      const normalizedPreferences =
        withNormalizedAdvisorWeights(preferencesResponse);
      setPreferences(normalizedPreferences);
      setPlanResult(null);
      setView(
        normalizedPreferences.onboarding_completed ? "dashboard" : "welcome",
      );
    } catch (error) {
      logError("Failed to load mini app", error, {
        endpoint: "/auth/telegram, /advisors/list, /advisors/preferences",
      });
    } finally {
      setIsLoading(false);
    }
  }

  async function ensureOnchainAddress(): Promise<string> {
    try {
      const response = await api.getOnchainAddress();
      return response.address;
    } catch {
      const created = await api.createOnchainWallet();
      return created.address;
    }
  }

  async function refreshOnchainData(): Promise<void> {
    const requestMode = networkModeRef.current;
    const shouldShowOrdersSkeleton = !hasLoadedOrdersByMode[requestMode];
    if (shouldShowOrdersSkeleton) {
      setIsOrdersLoading(true);
    }
    try {
      const [balanceResponse, ordersResponse] = await Promise.all([
        api.getOnchainBalance(),
        api.getOnchainOrders(),
      ]);
      if (networkModeRef.current !== requestMode) {
        return;
      }
      setBalance(balanceResponse);
      setPortfolio(toOnchainPortfolio(balanceResponse));
      setAssets(toOnchainAssetSummaries(balanceResponse));
      setOrdersByMode((current) => ({
        ...current,
        [requestMode]: ordersResponse.orders,
      }));
      setHasLoadedOrdersByMode((current) => ({
        ...current,
        [requestMode]: true,
      }));
    } catch (error) {
      if (networkModeRef.current !== requestMode) {
        return;
      }
      if (
        error instanceof Error &&
        error.message.includes("Onchain wallet not found")
      ) {
        setBalance(DEFAULT_BALANCE);
        setPortfolio(DEFAULT_PORTFOLIO);
        setAssets([]);
        setOrdersByMode((current) => ({
          ...current,
          [requestMode]: [],
        }));
        setHasLoadedOrdersByMode((current) => ({
          ...current,
          [requestMode]: true,
        }));
        return;
      }
      throw error;
    } finally {
      if (networkModeRef.current === requestMode && shouldShowOrdersSkeleton) {
        setIsOrdersLoading(false);
      }
    }
  }

  async function refreshDashboard(): Promise<void> {
    if (dashboardRefreshInFlightRef.current) {
      dashboardRefreshQueuedRef.current = true;
      return;
    }
    const requestMode = networkModeRef.current;
    const shouldShowOrdersSkeleton = !hasLoadedOrdersByMode[requestMode];
    dashboardRefreshInFlightRef.current = true;
    setIsRefreshingViewData(true);
    if (shouldShowOrdersSkeleton) {
      setIsOrdersLoading(true);
    }
    try {
      if (requestMode === "onchain") {
        if (networkModeRef.current !== requestMode) {
          return;
        }
        await refreshOnchainData();
        return;
      }
      const [
        balanceResponse,
        portfolioResponse,
        assetsResponse,
        clockResponse,
        pricesResponse,
        agentsResponse,
        ordersResponse,
      ] = await Promise.all([
        api.getBalance(),
        api.getPortfolio(),
        api.getAssets(),
        api.getTestTime(),
        api.getTestPrices(),
        api.getTestAgents(),
        api.getOrders(),
      ]);
      const savedStartRecommendations = await api
        .getSavedStartRecommendations()
        .catch(() => null);
      const normalizedAssets = withUsdtFromBalance(
        assetsResponse.assets,
        balanceResponse,
      );
      if (networkModeRef.current !== requestMode) {
        return;
      }
      setBalance(balanceResponse);
      setPortfolio(portfolioResponse);
      setAssets(normalizedAssets);
      setTestClock(clockResponse);
      setTestPrices(pricesResponse.prices);
      setTestAgents(agentsResponse);
      setOrdersByMode((current) => ({
        ...current,
        [requestMode]: ordersResponse.orders,
      }));
      setHasLoadedOrdersByMode((current) => ({
        ...current,
        [requestMode]: true,
      }));
      if (savedStartRecommendations !== null) {
        setPlanResult(savedStartRecommendations);
      }
    } finally {
      dashboardRefreshInFlightRef.current = false;
      setIsRefreshingViewData(false);
      if (networkModeRef.current === requestMode && shouldShowOrdersSkeleton) {
        setIsOrdersLoading(false);
      }
      if (dashboardRefreshQueuedRef.current) {
        dashboardRefreshQueuedRef.current = false;
        void refreshDashboard();
      }
    }
  }

  async function openTopUpModal(): Promise<void> {
    setIsTopUpModalOpen(true);
    setTopUpCopyState("idle");
    setIsTopUpLoading(true);
    try {
      const address = await ensureOnchainAddress();
      setTopUpAddress(address);
    } catch (error) {
      logError("Failed to load onchain address", error, {
        endpoint: "/onchain/address, /onchain/wallet/create",
      });
      setIsTopUpModalOpen(false);
    } finally {
      setIsTopUpLoading(false);
    }
  }

  async function copyTopUpAddress(): Promise<void> {
    if (topUpAddress.trim() === "") {
      return;
    }
    try {
      await navigator.clipboard.writeText(topUpAddress);
      setTopUpCopyState("copied");
      window.setTimeout(() => setTopUpCopyState("idle"), 1800);
    } catch (error) {
      logError("Failed to copy onchain address", error, {
        addressPresent: topUpAddress.trim() !== "",
      });
    }
  }

  async function submitWithdrawal(): Promise<void> {
    const normalizedAddress = withdrawalAddress.trim();
    const normalizedAmount = withdrawalAmount.trim();
    if (normalizedAddress === "" || normalizedAmount === "") {
      return;
    }
    setIsWithdrawalSubmitting(true);
    try {
      await api.withdrawOnchain(normalizedAmount, normalizedAddress);
      setIsWithdrawalModalOpen(false);
      setWithdrawalAddress("");
      setWithdrawalAmount("");
      await refreshDashboard();
    } catch (error) {
      logError("Onchain withdrawal failed", error, {
        endpoint: "/onchain/withdraw",
        amount: normalizedAmount,
        destinationAddress: normalizedAddress,
      });
    } finally {
      setIsWithdrawalSubmitting(false);
    }
  }

  function handleSelectNetworkMode(nextMode: NetworkMode): void {
    if (nextMode === networkModeRef.current) {
      return;
    }
    setBalance(DEFAULT_BALANCE);
    setPortfolio(DEFAULT_PORTFOLIO);
    setAssets([]);
    setNetworkMode(nextMode);
  }

  function toggleAdvisor(advisorId: string): void {
    const isSelected = preferences.selected_advisors.includes(advisorId);
    if (isSelected) {
      const nextSelected = preferences.selected_advisors.filter(
        (item) => item !== advisorId,
      );
      setPreferences({
        ...preferences,
        selected_advisors: nextSelected,
        advisor_weights: AdvisorWeightsModel.defaults(nextSelected),
      });
      return;
    }
    if (preferences.selected_advisors.length >= 3) {
      console.warn("[App] You can select up to three advisors.");
      return;
    }
    const nextSelected = [...preferences.selected_advisors, advisorId];
    setPreferences({
      ...preferences,
      selected_advisors: nextSelected,
      advisor_weights: AdvisorWeightsModel.defaults(nextSelected),
    });
  }

  function updateAdvisorWeight(advisorId: string, nextWeight: number): void {
    const currentWeight = preferences.advisor_weights[advisorId] ?? 0;
    if (Math.round(currentWeight) !== Math.round(nextWeight)) {
      TelegramWebAppService.hapticSelectionChanged();
    }

    setPreferences({
      ...preferences,
      advisor_weights: AdvisorWeightsModel.updateWeight(
        preferences.selected_advisors,
        preferences.advisor_weights,
        advisorId,
        nextWeight,
      ),
    });
  }

  async function generatePortfolio(): Promise<void> {
    const totalWeight = Math.round(
      preferences.selected_advisors.reduce(
        (sum, advisorId) => sum + (preferences.advisor_weights[advisorId] ?? 0),
        0,
      ),
    );
    if (preferences.selected_advisors.length !== 3 || totalWeight !== 100) {
      console.warn(
        "[App] Select three advisors to reach 100% before continuing.",
      );
      return;
    }

    setIsLoading(true);
    setView("council");

    try {
      console.info("[App] /advisors/preferences request", {
        selected_advisors: preferences.selected_advisors,
        advisor_weights: preferences.advisor_weights,
        risk_profile: preferences.risk_profile,
      });
      const savedPreferences = await api.updatePreferences(
        preferences.selected_advisors,
        preferences.advisor_weights,
        preferences.risk_profile,
      );
      console.info("[App] /advisors/preferences response", savedPreferences);
      setPreferences(withNormalizedAdvisorWeights(savedPreferences));
      console.info("[App] /advisors/start request", {
        deposit_amount: depositAmount,
        risk_profile: preferences.risk_profile,
      });
      const result = await callWithRetry(
        "/advisors/start",
        () =>
          api.getStartRecommendations(depositAmount, preferences.risk_profile),
        2,
        2000,
      );
      console.info("[App] /advisors/start response", result);
      try {
        const agentsResponse = await callWithRetry(
          "/test/agents",
          () => api.getTestAgents(),
          2,
          2000,
        );
        console.info("[App] /test/agents response", agentsResponse);
        setTestAgents(agentsResponse);
      } catch (agentsError) {
        logError("Failed to sync agents after start", agentsError, {
          endpoint: "/test/agents",
        });
      }
      setPlanResult(result);
      setView("plan");
    } catch (error) {
      logError("Failed to generate portfolio", error, {
        endpoint: "/advisors/preferences, /advisors/start",
        selectedAdvisors: preferences.selected_advisors,
        advisorWeights: preferences.advisor_weights,
        riskProfile: preferences.risk_profile,
        depositAmount,
      });
      setView("strategy");
    } finally {
      setIsLoading(false);
    }
  }

  async function continueFromAdvisors(): Promise<void> {
    const totalWeight = Math.round(
      preferences.selected_advisors.reduce(
        (sum, advisorId) => sum + (preferences.advisor_weights[advisorId] ?? 0),
        0,
      ),
    );
    if (preferences.selected_advisors.length !== 3 || totalWeight !== 100) {
      console.warn(
        "[App] Select three advisors to reach 100% before continuing.",
      );
      return;
    }

    setIsLoading(true);
    try {
      const savedPreferences = await api.updatePreferences(
        preferences.selected_advisors,
        preferences.advisor_weights,
        preferences.risk_profile,
      );
      setPreferences(withNormalizedAdvisorWeights(savedPreferences));
      const agentsResponse = await api.getTestAgents();
      setTestAgents(agentsResponse);
      setView("strategy");
    } catch (error) {
      logError("Failed to sync advisor team", error, {
        endpoint: "/advisors/preferences, /test/agents",
        selectedAdvisors: preferences.selected_advisors,
        advisorWeights: preferences.advisor_weights,
        riskProfile: preferences.risk_profile,
      });
      setView("strategy");
    } finally {
      setIsLoading(false);
    }
  }

  async function inspectAsset(
    assetId: string,
    returnView: "dashboard" | "portfolio" | "plan" = "dashboard",
  ): Promise<void> {
    if (assetId.trim().toUpperCase() === "USDT") {
      return;
    }
    setIsLoading(true);
    setView("council");

    try {
      const [detailResponse, analysisResponse] = await Promise.all([
        api.getAssetDetail(assetId),
        api.getAssetAnalysis(assetId),
      ]);
      setSelectedAssetId(assetId);
      setAssetDetail(detailResponse);
      setAssetAnalysis(analysisResponse);
      setAssetAnalysisUpdatedAt(new Date().toISOString());
      setAssetReturnView(returnView);
      setView("asset");
    } catch (error) {
      logError("Failed to load asset analysis", error, {
        endpoint: "/test/asset/:id, /advisors/analysis",
        assetId,
      });
      setView(returnView);
    } finally {
      setIsLoading(false);
    }
  }

  async function executeTrade(side: "buy" | "sell"): Promise<void> {
    if (selectedAssetId === "") {
      return;
    }
    if (!isTradeableAsset(selectedAssetId)) {
      return;
    }
    setIsLoading(true);

    try {
      if (side === "buy") {
        await api.buyAsset(selectedAssetId, tradeAmount);
      } else {
        await api.sellAsset(selectedAssetId, tradeAmount);
      }
      await inspectAsset(selectedAssetId);
      await refreshDashboard();
    } catch (error) {
      logError("Trade failed", error, {
        endpoint: side === "buy" ? "/test/buy" : "/test/sell",
        side,
        selectedAssetId,
        tradeAmount,
      });
      window.alert(
        errorMessage(
          error,
          "Request failed. Please make sure your wallet has enough TON for gas.",
        ),
      );
      setIsLoading(false);
    }
  }

  async function executePortfolioTrade(
    side: "buy" | "sell",
    assetId: string,
    amountUsdt: string,
  ): Promise<void> {
    const normalizedAssetId = assetId.trim();
    if (normalizedAssetId === "") {
      return;
    }
    const normalizedAmount = amountUsdt.trim();
    if (normalizedAmount === "") {
      return;
    }
    if (!isTradeableAsset(normalizedAssetId)) {
      return;
    }

    setIsLoading(true);
    try {
      if (networkMode === "onchain") {
        if (side === "buy") {
          await api.buyOnchain(normalizedAssetId, normalizedAmount);
        } else {
          const currentAsset = assets.find(
            (item) =>
              item.asset_id.trim().toUpperCase() ===
              normalizedAssetId.trim().toUpperCase(),
          );
          const currentPrice = Number.parseFloat(currentAsset?.current_price ?? "0");
          if (!Number.isFinite(currentPrice) || currentPrice <= 0) {
            throw new Error("Current asset price is unavailable");
          }
          const quantity = (
            Number.parseFloat(normalizedAmount) / currentPrice
          ).toFixed(6);
          await api.sellOnchain(normalizedAssetId, quantity);
        }
      } else if (side === "buy") {
        await api.buyAsset(normalizedAssetId, normalizedAmount);
      } else {
        await api.sellAsset(normalizedAssetId, normalizedAmount);
      }
      await refreshDashboard();
    } catch (error) {
      logError("Portfolio trade failed", error, {
        endpoint:
          networkMode === "onchain"
            ? side === "buy"
              ? "/onchain/buy"
              : "/onchain/sell"
            : side === "buy"
              ? "/test/buy"
              : "/test/sell",
        side,
        assetId: normalizedAssetId,
        amountUsdt: normalizedAmount,
        networkMode,
      });
      window.alert(
        errorMessage(
          error,
          "Request failed. Please make sure your wallet has enough TON for gas.",
        ),
      );
      throw error;
    } finally {
      setIsLoading(false);
    }
  }

  async function addTestFunds(): Promise<void> {
    const input = window.prompt(
      "Top up amount in USDT (max 1000)",
      depositAmount,
    );
    if (input === null) {
      return;
    }
    const parsed = Number.parseFloat(input.trim());
    if (!Number.isFinite(parsed) || parsed <= 0) {
      console.warn("[App] Deposit amount must be a positive number.");
      return;
    }
    const cappedAmount = Math.min(parsed, 1000);
    const normalizedAmount = cappedAmount.toFixed(2);
    setDepositAmount(normalizedAmount);

    setIsLoading(true);
    try {
      await api.deposit(normalizedAmount);
      await refreshDashboard();
    } catch (error) {
      logError("Deposit failed", error, {
        endpoint: "/test/deposit",
        depositAmount: normalizedAmount,
      });
    } finally {
      setIsLoading(false);
    }
  }

  function startOnboarding(): void {
    setPreferences({
      ...preferences,
      selected_advisors: [],
      advisor_weights: {},
    });
    setView("advisors");
  }

  async function reopenOnboarding(): Promise<void> {
    setIsLoading(true);
    try {
      const resetPreferences = await api.resetOnboarding();
      setPreferences(withNormalizedAdvisorWeights(resetPreferences));
      setPlanResult(null);
      setView("welcome");
    } catch (error) {
      logError("Failed to reset onboarding", error, {
        endpoint: "/advisors/onboarding/reset",
      });
    } finally {
      setIsLoading(false);
    }
  }

  function renderCurrentView(): JSX.Element {
    if (isLoading) {
      return (
        <div className="app-launch-loader" aria-label="Loading application">
          <div className="app-launch-loader-mark" />
        </div>
      );
    }
    if (view === "welcome") {
      return (
        <WelcomeScreen
          agentsActive={agentsActive}
          onContinue={startOnboarding}
          username={username}
        />
      );
    }
    if (view === "strategy") {
      return (
        <StrategyScreen
          depositAmount={depositAmount}
          onDepositChange={setDepositAmount}
          onBack={() => setView("advisors")}
          onNext={() => void generatePortfolio()}
          onRiskChange={(riskProfile: RiskProfile) =>
            setPreferences({ ...preferences, risk_profile: riskProfile })
          }
          riskProfile={preferences.risk_profile}
        />
      );
    }
    if (view === "council") {
      return <CouncilAnalyticsScreen />;
    }
    if (view === "advisors") {
      return (
        <AdvisorSelectionScreen
          advisorWeights={preferences.advisor_weights}
          advisors={advisors}
          onContinue={() => void continueFromAdvisors()}
          onToggle={toggleAdvisor}
          onWeightChange={updateAdvisorWeight}
          selectedAdvisorIds={preferences.selected_advisors}
        />
      );
    }
    if (view === "plan" && planResult !== null) {
      return (
        <PlanScreen
          advisorWeights={preferences.advisor_weights}
          advisors={advisors}
          onGoDashboard={() => setView("dashboard")}
          onInspectAsset={(assetId: string) =>
            void inspectAsset(assetId, "plan")
          }
          result={planResult}
          selectedAdvisors={preferences.selected_advisors}
          testAgents={testAgents}
        />
      );
    }
    if (view === "portfolio") {
      return (
        <PortfolioScreen
          assets={assets}
          cashUsdt={balance?.cash_usdt ?? "0"}
          hasLoadedRecommendations={hasLoadedPortfolioRecommendations}
          isRecommendationsLoading={isPortfolioRecommendationsLoading}
          isRefreshingAssets={isRefreshingViewData}
          isTradingEnabled
          networkMode={networkMode}
          onInspectAsset={(assetId: string) =>
            void inspectAsset(assetId, "portfolio")
          }
          onBuy={(assetId, amountUsdt) => {
            return executePortfolioTrade("buy", assetId, amountUsdt);
          }}
          onSell={(assetId, amountUsdt) => {
            return executePortfolioTrade("sell", assetId, amountUsdt);
          }}
          pnlPercent={balance?.pnl_percent ?? "0"}
          pnlAbsolute={balance?.pnl_absolute ?? "$0.00"}
          recommendations={portfolioRecommendations}
          testClock={testClock}
          testPrices={testPrices}
          planResult={planResult}
          portfolio={portfolio}
        />
      );
    }
    if (view === "history") {
      return (
        <HistoryScreen
          isLoading={isOrdersLoading && !hasLoadedOrdersByMode[networkMode]}
          onBack={() => setView("settings")}
          orders={orders}
        />
      );
    }
    if (view === "settings") {
      return (
        <SettingsScreen
          advisors={advisors}
          onOpenHistory={() => setView("history")}
          onOpenOnboarding={() => void reopenOnboarding()}
          riskProfile={preferences.risk_profile}
          selectedAdvisorIds={preferences.selected_advisors}
        />
      );
    }
    if (view === "asset" && assetDetail !== null) {
      return (
        <AssetDetailScreen
          analysis={assetAnalysis}
          analysisUpdatedAt={assetAnalysisUpdatedAt}
          detail={assetDetail}
          onBack={() => setView(assetReturnView)}
          onBuy={() => void executeTrade("buy")}
          onSell={() => void executeTrade("sell")}
          onTradeAmountChange={setTradeAmount}
          tradeAmount={tradeAmount}
          tradeDisabled={!isTradeableAsset(assetDetail.asset_id)}
        />
      );
    }
    return (
      <DashboardScreen
        advisors={advisors}
        advisorWeights={preferences.advisor_weights}
        balance={balance}
        networkMode={networkMode}
        onSelectNetworkMode={handleSelectNetworkMode}
        onDeposit={() => void addTestFunds()}
        onOpenInvest={() => setView("portfolio")}
        onOpenTopUp={() => void openTopUpModal()}
        onOpenWithdrawal={() => setIsWithdrawalModalOpen(true)}
        onRefresh={() => void refreshDashboard()}
        portfolio={portfolio}
        selectedAdvisors={preferences.selected_advisors}
        startRecommendations={planResult}
        testAgents={testAgents}
        testClock={testClock}
        testPrices={testPrices}
      />
    );
  }

  return (
    <div
      className={`app-root${applyIosTopInset ? " telegram-ios-top-inset" : ""}`}
    >
      <AppShell>
        {renderCurrentView()}
      </AppShell>
      {isTopUpModalOpen ? (
        <div className="modal-overlay" onClick={() => setIsTopUpModalOpen(false)}>
          <div className="modal-content" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Top up Onchain Wallet</h3>
              <button
                className="close-button"
                onClick={() => setIsTopUpModalOpen(false)}
                type="button"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-info">
                Please transfer USDT to this address.
              </p>
              <p className="modal-info muted">
                Reminder: keep more than 0.5 TON in the wallet to cover blockchain gas fees.
              </p>
              {isTopUpLoading ? (
                <p className="modal-info muted">Preparing wallet address...</p>
              ) : (
                <>
                  <div className="address-card">
                    <p className="address-label">Your onchain address</p>
                    <p className="address-value">{topUpAddress}</p>
                  </div>
                  <button className="ghost-button modal-secondary" onClick={() => void copyTopUpAddress()} type="button">
                    {topUpCopyState === "copied" ? "Copied" : "Copy address"}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      ) : null}
      {isWithdrawalModalOpen ? (
        <div className="modal-overlay" onClick={() => setIsWithdrawalModalOpen(false)}>
          <div className="modal-content" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Withdraw USDT</h3>
              <button
                className="close-button"
                onClick={() => setIsWithdrawalModalOpen(false)}
                type="button"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="modal-body">
              <input
                className="modal-text-input"
                inputMode="decimal"
                onChange={(event) =>
                  setWithdrawalAmount(normalizeDecimalInput(event.target.value))
                }
                placeholder="Amount in USDT"
                type="text"
                value={withdrawalAmount}
              />
              <textarea
                className="modal-textarea"
                onChange={(event) => setWithdrawalAddress(event.target.value)}
                placeholder="Destination address"
                rows={4}
                value={withdrawalAddress}
              />
            </div>
            <div className="modal-actions">
              <button
                className="cta-button"
                disabled={
                  isWithdrawalSubmitting ||
                  withdrawalAmount.trim() === "" ||
                  withdrawalAddress.trim() === ""
                }
                onClick={() => void submitWithdrawal()}
                type="button"
              >
                {isWithdrawalSubmitting ? "Submitting..." : "Submit withdrawal"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {view !== "welcome" &&
      view !== "strategy" &&
      view !== "advisors" &&
      view !== "council" &&
      view !== "plan" &&
      view !== "asset" ? (
        <BottomNav
          activeView={
            view === "portfolio"
              ? "portfolio"
              : view === "history"
                ? "history"
              : view === "settings"
                ? "settings"
                : "dashboard"
          }
          onSelect={(nextView) => {
            if (nextView === "portfolio") {
              setView("portfolio");
              return;
            }
            if (nextView === "history") {
              setView("history");
              return;
            }
            if (nextView === "settings") {
              setView("settings");
              return;
            }
            setView("dashboard");
          }}
        />
      ) : null}
    </div>
  );
}
