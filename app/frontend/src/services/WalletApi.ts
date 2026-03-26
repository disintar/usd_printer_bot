import { HttpClient } from "../lib/http";
import type {
  AdvisorDefinition,
  AdvisorPreferences,
  AgentsActiveResponse,
  AssetAnalysisResponse,
  AssetDetail,
  AssetsResponse,
  BalanceResponse,
  DepositResponse,
  OnchainWalletResponse,
  OnchainWithdrawResponse,
  PortfolioRecommendationsResponse,
  PortfolioResponse,
  RiskProfile,
  OrdersResponse,
  StartRecommendationsResponse,
  TestAgentsResponse,
  TestAgentReasoningResponse,
  TestPricesResponse,
  TestTimeResponse,
  TelegramAuthResponse,
  TradeResponse,
} from "../types/api";

export class WalletApi {
  private readonly client: HttpClient;

  public constructor(client: HttpClient) {
    this.client = client;
  }

  public authenticateTelegram(
    telegramUserId: number,
    username: string,
  ): Promise<TelegramAuthResponse> {
    return this.client.post<
      TelegramAuthResponse,
      { telegram_user_id: number; username: string }
    >("/auth/telegram", { telegram_user_id: telegramUserId, username });
  }

  public listAdvisors(): Promise<{ advisors: AdvisorDefinition[] }> {
    return this.client.get("/advisors/list");
  }

  public getPreferences(): Promise<AdvisorPreferences> {
    return this.client.get("/advisors/preferences");
  }

  public updatePreferences(
    selectedAdvisors: string[],
    advisorWeights: Record<string, number>,
    riskProfile: RiskProfile,
  ): Promise<AdvisorPreferences> {
    return this.client.post<
      AdvisorPreferences,
      {
        selected_advisors: string[];
        advisor_weights: Record<string, number>;
        risk_profile: RiskProfile;
      }
    >("/advisors/preferences", {
      selected_advisors: selectedAdvisors,
      advisor_weights: advisorWeights,
      risk_profile: riskProfile,
    });
  }

  public resetOnboarding(): Promise<AdvisorPreferences> {
    return this.client.post<AdvisorPreferences, Record<string, never>>(
      "/advisors/onboarding/reset",
      {},
    );
  }

  public getStartRecommendations(
    depositAmount: string,
    riskProfile: RiskProfile,
  ): Promise<StartRecommendationsResponse> {
    return this.client.post<
      StartRecommendationsResponse,
      { deposit_amount: string; risk_profile: RiskProfile }
    >("/advisors/start", {
      deposit_amount: depositAmount,
      risk_profile: riskProfile,
    });
  }

  public getSavedStartRecommendations(): Promise<StartRecommendationsResponse> {
    return this.client.get("/advisors/start");
  }

  public getPortfolioRecommendations(): Promise<PortfolioRecommendationsResponse> {
    return this.client.post<
      PortfolioRecommendationsResponse,
      Record<string, never>
    >("/advisors/recommendations", {});
  }

  public getBalance(): Promise<BalanceResponse> {
    return this.client.get("/test/balance");
  }

  public getOnchainBalance(): Promise<BalanceResponse> {
    return this.client.get("/onchain/balance");
  }

  public getOnchainAddress(): Promise<{ address: string }> {
    return this.client.get("/onchain/address");
  }

  public createOnchainWallet(): Promise<OnchainWalletResponse> {
    return this.client.post<OnchainWalletResponse, Record<string, never>>(
      "/onchain/wallet/create",
      {},
    );
  }

  public withdrawOnchain(
    amountUsdt: string,
    destinationAddress: string,
  ): Promise<OnchainWithdrawResponse> {
    return this.client.post<
      OnchainWithdrawResponse,
      { amount_usdt: string; destination_address: string }
    >("/onchain/withdraw", {
      amount_usdt: amountUsdt,
      destination_address: destinationAddress,
    });
  }

  public buyOnchain(assetId: string, amountUsdt: string): Promise<TradeResponse> {
    return this.client.post<
      TradeResponse,
      { asset_id: string; amount_usdt: string }
    >("/onchain/buy", {
      asset_id: assetId,
      amount_usdt: amountUsdt,
    });
  }

  public sellOnchain(assetId: string, quantity: string): Promise<TradeResponse> {
    return this.client.post<
      TradeResponse,
      { asset_id: string; quantity: string }
    >("/onchain/sell", {
      asset_id: assetId,
      quantity,
    });
  }

  public getTestTime(): Promise<TestTimeResponse> {
    return this.client.get("/test/time");
  }

  public getTestPrices(): Promise<TestPricesResponse> {
    return this.client.get("/test/prices");
  }

  public getTestAgents(): Promise<TestAgentsResponse> {
    return this.client.get("/test/agents");
  }

  public getTestAgentsReasoning(
    assetId: string,
  ): Promise<TestAgentReasoningResponse> {
    return this.client.get(
      `/test/agents/reasoning?asset_id=${encodeURIComponent(assetId)}`,
    );
  }

  public deposit(amount: string): Promise<DepositResponse> {
    return this.client.post<DepositResponse, { amount: string }>(
      "/test/deposit",
      { amount },
    );
  }

  public getPortfolio(): Promise<PortfolioResponse> {
    return this.client.get("/test/portfolio");
  }

  public getOrders(): Promise<OrdersResponse> {
    return this.client.get("/test/orders");
  }

  public getOnchainOrders(): Promise<OrdersResponse> {
    return this.client.get("/onchain/orders");
  }

  public getAssets(): Promise<AssetsResponse> {
    return this.client.get("/test/assets");
  }

  public getAssetDetail(assetId: string): Promise<AssetDetail> {
    return this.client.get(`/test/asset/${assetId}`);
  }

  public getAssetAnalysis(assetId: string): Promise<AssetAnalysisResponse> {
    return this.client.get(
      `/advisors/analysis?asset_id=${encodeURIComponent(assetId)}`,
    );
  }

  public buyAsset(assetId: string, amountUsdt: string): Promise<TradeResponse> {
    return this.client.post<
      TradeResponse,
      { asset_id: string; amount_usdt: string }
    >("/test/buy", {
      asset_id: assetId,
      amount_usdt: amountUsdt,
    });
  }

  public sellAsset(
    assetId: string,
    amountUsdt: string,
  ): Promise<TradeResponse> {
    return this.client.post<
      TradeResponse,
      { asset_id: string; amount_usdt: string }
    >("/test/sell", {
      asset_id: assetId,
      amount_usdt: amountUsdt,
    });
  }

  public getAgentsActive(): Promise<AgentsActiveResponse> {
    return this.client.get("/agents/active");
  }
}
