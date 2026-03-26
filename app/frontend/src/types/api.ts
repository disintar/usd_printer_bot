export interface ApiEnvelope<TData> {
  status: "ok" | "error";
  data?: TData;
  message?: string;
}

export interface TelegramAuthResponse {
  token: string;
  telegram_user_id: number;
  username: string;
}

export interface AgentsActiveResponse {
  agents_active: number;
}

export interface AdvisorDefinition {
  id: string;
  name: string;
  category: string;
  role: string;
  style: string[];
  tags: string[];
  primary_tag: string;
  tabler_icon?: string;
}

export interface AdvisorPreferences {
  selected_advisors: string[];
  advisor_weights: Record<string, number>;
  risk_profile: RiskProfile;
  onboarding_completed: boolean;
}

export type RiskProfile = "low" | "medium" | "high";

export interface AdvisorAction {
  asset_id: string;
  action: string;
  reason: string;
}

export interface BuyRecommendation {
  asset_id: string;
  allocation_percent: string;
  verdict: "buy" | "hold" | "sell";
  reason: string;
}

export interface AdvisorSummary {
  advisor_id: string;
  summary: string;
}

export interface StartRecommendationsResponse {
  buy_recommendations: BuyRecommendation[];
  advisor_summaries: AdvisorSummary[];
}

export interface BalanceResponse {
  cash_usdt: string;
  equity_usdt: string;
  total_balance_usdt: string;
  pnl_percent: string;
  pnl_absolute: string;
  assets?: AssetBalance[];
}

export interface AssetBalance {
  asset_id: string;
  balance: string;
  current_price: string;
  net_worth: string;
  pnl_percent: string;
  pnl_absolute: string;
  allocation_percent: string;
}

export interface TestTimeResponse {
  server_time_utc: string;
  server_time_utc_pretty?: string;
  simulated_time_utc: string;
  simulated_time_utc_pretty?: string;
  test_time_warp_enabled: boolean;
  window_days: number;
  hours_per_tick: number;
}

export interface TestPricesResponse {
  prices: Record<string, string>;
  server_time_utc?: string;
  server_time_utc_pretty?: string;
  simulated_time_utc?: string;
  simulated_time_utc_pretty?: string;
}

export interface TestAgentsResponse {
  active_agents: string[];
  selected_agents: string[];
  allocation: Record<string, number>;
}

export interface TestAgentReasoningResponse {
  asset_id: string;
  reasoning: string[];
  recommendation: string;
}

export interface PortfolioAsset {
  asset_id: string;
  quantity: string;
  value_usdt: string;
  allocation_percent: string;
}

export interface PortfolioResponse {
  total_balance_usdt: string;
  pnl_percent: string;
  pnl_absolute: string;
  allocation: Record<string, number>;
  assets: PortfolioAsset[];
}

export interface AssetSummary {
  asset_id: string;
  balance: string;
  current_price: string;
  net_worth: string;
  pnl_percent: string;
  pnl_absolute: string;
  mark: string;
}

export interface AssetsResponse {
  assets: AssetSummary[];
}

export interface AssetDetail {
  asset_id: string;
  balance: string;
  current_price: string;
  net_worth: string;
  pnl_percent: string;
  pnl_absolute: string;
  mark: string;
  advisor_thought: string;
  net_worth_chart: Array<{ price: string; timestamp: string }>;
  agent_marks: Record<string, string>;
}

export interface PortfolioRecommendationsResponse {
  actions: AdvisorAction[];
}

export interface AdvisorNote {
  advisor_id: string;
  name: string;
  thought: string;
}

export interface AssetAnalysisResponse {
  asset_id: string;
  recommendation: "buy" | "hold" | "sell";
  summary: string;
  advisor_notes: AdvisorNote[];
}

export interface DepositResponse {
  deposited: string;
  new_balance: string;
}

export interface OnchainWalletResponse {
  address: string;
  version?: string;
}

export interface OnchainWithdrawResponse {
  order_id: number;
  side: string;
  asset_id: string;
  quantity: string;
  price: string;
  notional: string;
  status: string;
  destination_address: string;
  tx_hash: string;
}

export interface TradeResponse {
  order_id: number;
  side: string;
  asset_id: string;
  quantity: string;
  price: string;
  notional: string;
  realized_pnl: string;
  realized_pnl_percent: string;
  status: string;
}

export interface OrderHistoryItem {
  order_id: number;
  side: "buy" | "sell";
  asset_id: string;
  quantity: string;
  price: string;
  notional: string;
  realized_pnl: string;
  realized_pnl_percent: string;
  status: string;
  created_at: string;
}

export interface OrdersResponse {
  orders: OrderHistoryItem[];
}
