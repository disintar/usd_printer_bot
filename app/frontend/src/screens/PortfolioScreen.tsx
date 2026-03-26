import { Formatters } from "../lib/formatters";
import { Presentation } from "../lib/presentation";
import aaplxIcon from "../assets/asset-icons/aaplx.svg";
import amznxIcon from "../assets/asset-icons/amznx.svg";
import coinxIcon from "../assets/asset-icons/coinx.png";
import defaultIcon from "../assets/asset-icons/default.png";
import googlxIcon from "../assets/asset-icons/googlx.png";
import hoodxIcon from "../assets/asset-icons/hoodx.svg";
import mstrxIcon from "../assets/asset-icons/mstrx.png";
import nvdaxIcon from "../assets/asset-icons/nvdax.png";
import qqqxIcon from "../assets/asset-icons/qqqx.png";
import spyxIcon from "../assets/asset-icons/spyx.png";
import tslaxIcon from "../assets/asset-icons/tslax.png";
import type {
  AssetSummary,
  PortfolioResponse,
  StartRecommendationsResponse,
  TestTimeResponse,
} from "../types/api";
import { useMemo, useState } from "react";

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

interface PortfolioScreenProps {
  portfolio: PortfolioResponse;
  assets: AssetSummary[];
  cashUsdt: string;
  networkMode?: "test" | "onchain";
  isTradingEnabled?: boolean;
  recommendations?: Record<string, "buy" | "hold" | "sell">;
  isRecommendationsLoading?: boolean;
  hasLoadedRecommendations?: boolean;
  isRefreshingAssets?: boolean;
  planResult: StartRecommendationsResponse | null;
  testClock: TestTimeResponse | null;
  testPrices: Record<string, string>;
  onInspectAsset: (assetId: string) => void;
  onBuy: (assetId: string, amountUsdt: string) => Promise<void>;
  onSell: (assetId: string, amountUsdt: string) => Promise<void>;
  pnlPercent: string;
  pnlAbsolute: string;
}

const ASSET_ICONS: Record<string, string> = {
  AAPLX: aaplxIcon,
  NVDAX: nvdaxIcon,
  TSLAX: tslaxIcon,
  COINX: coinxIcon,
  GOOGLX: googlxIcon,
  AMZNX: amznxIcon,
  HOODX: hoodxIcon,
  MSTRX: mstrxIcon,
  QQQX: qqqxIcon,
  SPYX: spyxIcon,
};

const DEFAULT_ICON = defaultIcon;

function getAssetIcon(assetId: string): string {
  return ASSET_ICONS[assetId.toUpperCase()] ?? DEFAULT_ICON;
}

function isTradeableAsset(assetId: string): boolean {
  return TRADEABLE_ASSET_IDS.has(assetId.trim().toUpperCase());
}

function hasPositiveBalance(balance: string): boolean {
  return toNumber(balance) > 0;
}

function canInspectAsset(assetId: string): boolean {
  return assetId.trim().toUpperCase() !== "USDT";
}

function isUsdtAsset(assetId: string): boolean {
  return assetId.trim().toUpperCase() === "USDT";
}

function normalizeDecimalInput(value: string): string {
  return value.replace(/,/g, ".");
}

function resolvePrice(
  assetId: string,
  fallbackPrice: string,
  testPrices: Record<string, string>,
): string {
  const fromPolling = testPrices[assetId];
  if (typeof fromPolling === "string" && fromPolling.trim() !== "") {
    return fromPolling;
  }
  return fallbackPrice;
}

function toNumber(value: string): number {
  const parsed = Number.parseFloat(value);
  if (Number.isFinite(parsed)) {
    return parsed;
  }
  return 0;
}

function getAssetRecommendation(
  assetId: string,
  recommendations: Record<string, "buy" | "hold" | "sell">,
  hasLoadedRecommendations: boolean,
): "buy" | "hold" | "sell" | null {
  const normalizedAssetId = assetId.trim().toUpperCase();
  const recommendation = recommendations[normalizedAssetId];
  if (recommendation !== undefined) {
    return recommendation;
  }
  if (hasLoadedRecommendations && isTradeableAsset(normalizedAssetId)) {
    return "hold";
  }
  return null;
}

interface TradeModalProps {
  assetId: string;
  side: "buy" | "sell";
  currentPrice: string;
  maxBuyUsdt: string;
  maxSellQuantity: string;
  onConfirm: (amountUsdt: string) => Promise<void>;
  onClose: () => void;
}

function TradeModal(props: TradeModalProps): JSX.Element {
  const [amount, setAmount] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const maxBuyRaw = Number.parseFloat(props.maxBuyUsdt);
  const maxSellRaw = Number.parseFloat(props.maxSellQuantity);
  const maxBuy = Number.isFinite(maxBuyRaw) ? Math.max(maxBuyRaw, 0) : 0;
  const maxSell = Number.isFinite(maxSellRaw) ? Math.max(maxSellRaw, 0) : 0;
  const currentPriceRaw = Number.parseFloat(props.currentPrice);
  const currentPrice = Number.isFinite(currentPriceRaw) && currentPriceRaw > 0
    ? currentPriceRaw
    : 0;
  const maxAllowedAmount = props.side === "buy" ? maxBuy : maxSell * currentPrice;
  const amountRaw = Number.parseFloat(amount);
  const amountValue = Number.isFinite(amountRaw) ? amountRaw : 0;
  const isAmountPositive = amountValue > 0;
  const exceedsMax = isAmountPositive && amountValue > maxAllowedAmount;
  const isConfirmDisabled = isLoading || !isAmountPositive || exceedsMax;

  const handleConfirm = async (): Promise<void> => {
    if (isConfirmDisabled) return;
    setIsLoading(true);
    try {
      await props.onConfirm(amount);
      props.onClose();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={props.onClose}>
      <div
        className="modal-content trade-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3>
            {props.side === "buy" ? "Buy" : "Sell"} {props.assetId}
          </h3>
          <button
            className="close-button"
            onClick={props.onClose}
            type="button"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <div className="modal-body">
          <p className="modal-info">
            Current Price:{" "}
            <strong>{Formatters.currency(props.currentPrice)}</strong>
          </p>
          <p className="modal-info muted">
            Max {props.side === "buy" ? "Buy" : "Sell"}:{" "}
            <strong>
              {Formatters.currency(maxAllowedAmount)}
            </strong>
          </p>
          <div className="amount-input-wrapper">
            <span className="currency-prefix">$</span>
            <input
              type="text"
              inputMode="decimal"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(normalizeDecimalInput(e.target.value))}
              className="amount-input"
            />
          </div>
          <div className="quick-amounts">
            {[25, 50, 75, 100].map((pct) => {
              const quickAmount = ((maxAllowedAmount * pct) / 100).toFixed(2);
              return (
                <button
                  key={pct}
                  className="quick-amount-btn"
                  onClick={() => setAmount(quickAmount)}
                  type="button"
                >
                  {pct}%
                </button>
              );
            })}
          </div>
          {exceedsMax ? (
            <p className="modal-info muted">
              Entered amount exceeds max available:{" "}
              <strong>{Formatters.currency(maxAllowedAmount)}</strong>
            </p>
          ) : null}
        </div>
        <div className="modal-actions">
          <button
            className={`cta-button ${props.side === "sell" ? "ghost-button" : ""}`}
            onClick={handleConfirm}
            disabled={isConfirmDisabled}
            type="button"
          >
            {isLoading
              ? "Processing..."
              : `${props.side === "buy" ? "Buy" : "Sell"} ${props.assetId}`}
          </button>
        </div>
      </div>
    </div>
  );
}

export function PortfolioScreen(props: PortfolioScreenProps): JSX.Element {
  const [tradeModal, setTradeModal] = useState<{
    assetId: string;
    side: "buy" | "sell";
  } | null>(null);
  const recommendations = props.recommendations ?? {};
  const isRecommendationsLoading = props.isRecommendationsLoading ?? false;
  const hasLoadedRecommendations = props.hasLoadedRecommendations ?? false;
  const isRefreshingAssets = props.isRefreshingAssets ?? false;
  const isTradingEnabled = props.isTradingEnabled ?? true;
  const networkMode = props.networkMode ?? "test";
  const sortedAssets = useMemo(() => {
    return [...props.assets].sort((left, right) => {
      const leftNetWorth = toNumber(left.net_worth);
      const rightNetWorth = toNumber(right.net_worth);
      if (rightNetWorth !== leftNetWorth) {
        return rightNetWorth - leftNetWorth;
      }
      return left.asset_id.localeCompare(right.asset_id);
    });
  }, [props.assets]);

  const handleBuy = async (
    assetId: string,
    amountUsdt: string,
  ): Promise<void> => {
    await props.onBuy(assetId, amountUsdt);
  };

  const handleSell = async (
    assetId: string,
    amountUsdt: string,
  ): Promise<void> => {
    await props.onSell(assetId, amountUsdt);
  };

  return (
    <div className="screen portfolio-screen">
      <header className="topbar compact-topbar">
        <div className="brand-row">
          <div className="brand-mark round">
            <span className="material-symbols-outlined">trending_up</span>
          </div>
          <div className="brand-copy">
            <strong>Portfolio Breakdown</strong>
            <span>Live Allocation View</span>
          </div>
        </div>
        <div className="address-pill">{props.assets.length} assets</div>
      </header>

      <section className="stack">
        <div className="asset-list">
          <p className="screen-copy asset-list-hint">Click on ticker to analyze</p>
          <div className="assets-table-head" aria-hidden="true">
            <span className="assets-table-head-icon">Icon</span>
            <span className="assets-table-head-center">Ticker</span>
            <span className="assets-table-head-right">Net Worth</span>
            <span className="assets-table-head-center">Current Price</span>
            <span className="assets-table-head-right">PnL %</span>
            <span className="assets-table-head-center">Amount</span>
            <span className="assets-table-head-right">PnL Absolute</span>
          </div>
          {sortedAssets.map((asset) => {
            const recommendation = getAssetRecommendation(
              asset.asset_id,
              recommendations,
              hasLoadedRecommendations,
            );
            const shouldShowRecommendationSkeleton =
              isRecommendationsLoading && !hasLoadedRecommendations;

            return (
              <div key={asset.asset_id} className="asset-item-wrapper">
                <button
                  className="asset-item"
                  disabled={!canInspectAsset(asset.asset_id)}
                  onClick={() => {
                    if (!canInspectAsset(asset.asset_id)) {
                      return;
                    }
                    props.onInspectAsset(asset.asset_id);
                  }}
                  type="button"
                >
                  <div className="asset-logo-wrapper">
                    {isUsdtAsset(asset.asset_id) ? (
                      <div
                        aria-label={asset.asset_id}
                        className="asset-icon asset-icon-placeholder"
                      >
                        $
                      </div>
                    ) : (
                      <img
                        alt={asset.asset_id}
                        className="asset-icon"
                        loading="lazy"
                        src={getAssetIcon(asset.asset_id)}
                      />
                    )}
                  </div>
                  <div className="asset-info">
                    <div className="asset-title-row">
                      <p className="asset-name">{asset.asset_id}</p>
                      {shouldShowRecommendationSkeleton ? (
                        <span
                          aria-label={`Loading recommendation for ${asset.asset_id}`}
                          className="recommendation-pill recommendation-pill-skeleton"
                        />
                      ) : recommendation !== null ? (
                        <span className={`recommendation-pill ${recommendation}`}>
                          {recommendation.toUpperCase()}
                        </span>
                      ) : null}
                    </div>
                    <div className="asset-meta-row">
                      <span className="asset-price">
                        {Formatters.currency(
                          resolvePrice(
                            asset.asset_id,
                            asset.current_price,
                            props.testPrices,
                          ),
                        )}
                      </span>
                    </div>
                    <div className="asset-meta-row">
                      <span className="asset-balance">
                        {asset.balance} {asset.asset_id}
                      </span>
                    </div>
                  </div>
                  <div className="asset-pricing">
                    <span className="asset-value">
                      {Formatters.currency(asset.net_worth)}
                    </span>
                    <span
                      className={`asset-pnl-percent ${Presentation.signalTone(asset.mark)}`}
                    >
                      {asset.pnl_percent}%
                    </span>
                    <span className="asset-pnl-absolute">
                      {Formatters.currency(asset.pnl_absolute)}
                    </span>
                  </div>
                </button>
                <div className="asset-actions">
                  <button
                    className="action-btn buy-btn"
                    disabled={!isTradingEnabled || !isTradeableAsset(asset.asset_id)}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!isTradingEnabled || !isTradeableAsset(asset.asset_id)) {
                        return;
                      }
                      setTradeModal({ assetId: asset.asset_id, side: "buy" });
                    }}
                    type="button"
                  >
                    Buy
                  </button>
                  <button
                    className="action-btn sell-btn"
                    disabled={
                      !isTradingEnabled ||
                      !isTradeableAsset(asset.asset_id) ||
                      !hasPositiveBalance(asset.balance)
                    }
                    onClick={(e) => {
                      e.stopPropagation();
                      if (
                        !isTradeableAsset(asset.asset_id) ||
                        !isTradingEnabled ||
                        !hasPositiveBalance(asset.balance)
                      ) {
                        return;
                      }
                      setTradeModal({ assetId: asset.asset_id, side: "sell" });
                    }}
                    type="button"
                  >
                    Sell
                  </button>
                  {!isTradeableAsset(asset.asset_id) ? (
                    <span className="asset-action-note">
                      Not tradeable
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })}
          {props.assets.length === 0 && isRefreshingAssets ? (
            <article className="screen-card">
              <div className="portfolio-empty-skeleton" />
              <div className="portfolio-empty-skeleton short" />
            </article>
          ) : null}
          {props.assets.length === 0 && !isRefreshingAssets ? (
            <article className="screen-card">
              <p className="screen-copy">
                No assets returned by `/test/assets` yet.
              </p>
            </article>
          ) : null}
        </div>
      </section>

      <section className="time-footer">
        <p className="time-info">
          Server: {props.testClock?.server_time_utc_pretty ?? "UTC n/a"}
        </p>
        <p className="time-info">
          Simulated: {props.testClock?.simulated_time_utc_pretty ?? "UTC n/a"}
        </p>
        <p className="time-info muted">
          Prices refresh from backend every 5 seconds
        </p>
      </section>

      {isTradingEnabled && tradeModal && (
        (() => {
          const tradeAsset = props.assets.find(
            (asset) =>
              asset.asset_id.trim().toUpperCase() ===
              tradeModal.assetId.trim().toUpperCase(),
          );
          return (
        <TradeModal
          assetId={tradeModal.assetId}
          side={tradeModal.side}
          currentPrice={resolvePrice(
            tradeModal.assetId,
            tradeAsset?.current_price ?? "0",
            props.testPrices,
          )}
          maxBuyUsdt={props.cashUsdt}
          maxSellQuantity={tradeAsset?.balance ?? "0"}
          onConfirm={(amount) =>
            tradeModal.side === "buy"
              ? handleBuy(tradeModal.assetId, amount)
              : handleSell(tradeModal.assetId, amount)
          }
          onClose={() => setTradeModal(null)}
        />
          );
        })()
      )}
    </div>
  );
}
