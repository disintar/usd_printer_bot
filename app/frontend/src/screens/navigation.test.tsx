import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlanScreen } from "./PlanScreen";
import { PortfolioScreen } from "./PortfolioScreen";

describe("asset navigation from screens", () => {
  it("opens asset detail from generated plan rows", () => {
    const onInspectAsset = vi.fn();

    render(
      <PlanScreen
        advisorWeights={{ warren_buffett: 100 }}
        advisors={[]}
        onGoDashboard={() => undefined}
        onInspectAsset={onInspectAsset}
        result={{
          buy_recommendations: [
            {
              asset_id: "NVDA",
              allocation_percent: "35",
              verdict: "buy",
              reason: "High conviction",
            },
          ],
          advisor_summaries: [],
        }}
        selectedAdvisors={["warren_buffett"]}
      />,
    );

    fireEvent.click(screen.getByText("NVDA"));
    expect(onInspectAsset).toHaveBeenCalledWith("NVDA");
  });

  it("opens asset detail from portfolio rows", () => {
    const onInspectAsset = vi.fn();
    const onBuy = vi.fn();
    const onSell = vi.fn();

    render(
      <PortfolioScreen
        assets={[
          {
            asset_id: "AAPLx",
            balance: "1.5",
            current_price: "200.00",
            net_worth: "300.00",
            pnl_percent: "5.0",
            pnl_absolute: "15.00",
            mark: "Buy",
          },
        ]}
        onInspectAsset={onInspectAsset}
        onBuy={onBuy}
        onSell={onSell}
        cashUsdt="1000"
        pnlPercent="3.5"
        pnlAbsolute="$42.00"
        testClock={null}
        testPrices={{}}
        planResult={null}
        portfolio={{
          total_balance_usdt: "1200",
          pnl_percent: "3.5",
          pnl_absolute: "42",
          allocation: {},
          assets: [],
        }}
      />,
    );

    fireEvent.click(screen.getByText("AAPLx"));
    expect(onInspectAsset).toHaveBeenCalledWith("AAPLx");
  });

  it("enables sell for tradeable assets with non-zero balance", () => {
    render(
      <PortfolioScreen
        assets={[
          {
            asset_id: " AAPLx ",
            balance: "1.5",
            current_price: "200.00",
            net_worth: "300.00",
            pnl_percent: "5.0",
            pnl_absolute: "15.00",
            mark: "Buy",
          },
        ]}
        onInspectAsset={() => undefined}
        onBuy={async () => undefined}
        onSell={async () => undefined}
        cashUsdt="1000"
        pnlPercent="3.5"
        pnlAbsolute="$42.00"
        testClock={null}
        testPrices={{}}
        planResult={null}
        portfolio={{
          total_balance_usdt: "1200",
          pnl_percent: "3.5",
          pnl_absolute: "42",
          allocation: {},
          assets: [],
        }}
      />,
    );

    const sellButtons = screen.getAllByRole("button", { name: "Sell" }) as HTMLButtonElement[];
    expect(sellButtons.some((button) => button.disabled === false)).toBe(true);
  });
});
