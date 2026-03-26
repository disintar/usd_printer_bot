import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardScreen } from "./DashboardScreen";
import { PlanScreen } from "./PlanScreen";

describe("agent sync display", () => {
  it("renders council cards only from backend selected advisors", () => {
    render(
      <PlanScreen
        advisorWeights={{
          warren_buffett: 40,
          pavel_durov: 35,
          ray_dalio: 25,
        }}
        advisors={[
          {
            id: "warren_buffett",
            name: "Warren Buffett",
            category: "serious",
            role: "Long-term value investor",
            style: ["value first"],
            tags: ["value"],
            primary_tag: "investment",
          },
          {
            id: "pavel_durov",
            name: "Pavel Durov",
            category: "serious",
            role: "Product and growth strategist",
            style: ["growth"],
            tags: ["growth"],
            primary_tag: "investment",
          },
          {
            id: "ray_dalio",
            name: "Ray Dalio",
            category: "serious",
            role: "Macro allocator",
            style: ["macro"],
            tags: ["macro"],
            primary_tag: "investment",
          },
        ]}
        onGoDashboard={() => undefined}
        onInspectAsset={() => undefined}
        result={{
          buy_recommendations: [],
          advisor_summaries: [
            { advisor_id: "warren_buffett", summary: "Buy AAPLx on valuation gap." },
            { advisor_id: "pavel_durov", summary: "Buy GOOGLx momentum continuation." },
            { advisor_id: "ray_dalio", summary: "Balance downside with macro hedge." },
          ],
        }}
        selectedAdvisors={["warren_buffett", "pavel_durov", "ray_dalio"]}
        testAgents={{
          active_agents: ["Buy", "Cover", "Sell", "Short", "Hold"],
          selected_agents: ["Buy", "Cover", "Sell", "Short", "Hold"],
          allocation: {
            Buy: 20,
            Cover: 20,
            Sell: 20,
            Short: 20,
            Hold: 20,
          },
        }}
      />,
    );

    expect(screen.queryByText("3/3 backend agents active")).not.toBeNull();
    expect(screen.queryByText("Weight Source")).toBeNull();
    expect(screen.queryByText("Buy")).toBeNull();
    expect(screen.queryByText("Hold")).toBeNull();
    expect(screen.queryByText("Warren Buffett")).not.toBeNull();
    expect(screen.queryByText("Pavel Durov")).not.toBeNull();
    expect(screen.queryByText("Ray Dalio")).not.toBeNull();
    expect(screen.queryByText(/Buy GOOGLx momentum continuation/i)).not.toBeNull();
  });

  it("renders dashboard fundamental agents count from backend selected advisors", () => {
    render(
      <DashboardScreen
        balance={{
          cash_usdt: "0",
          equity_usdt: "0",
          total_balance_usdt: "1000",
          pnl_percent: "0",
          pnl_absolute: "0",
        }}
        onDeposit={() => undefined}
        onOpenInvest={() => undefined}
        onRefresh={() => undefined}
        portfolio={{
          total_balance_usdt: "1000",
          pnl_percent: "0",
          pnl_absolute: "0",
          allocation: {},
          assets: [],
        }}
        startRecommendations={null}
        selectedAdvisors={["warren_buffett", "pavel_durov", "ray_dalio"]}
        advisorWeights={{
          warren_buffett: 40,
          pavel_durov: 35,
          ray_dalio: 25,
        }}
        testAgents={{
          active_agents: ["warren_buffett", "pavel_durov", "ray_dalio"],
          selected_agents: ["warren_buffett", "pavel_durov", "ray_dalio"],
          allocation: {
            warren_buffett: 40,
            pavel_durov: 35,
            ray_dalio: 25,
          },
        }}
        testClock={null}
        testPrices={{}}
      />,
    );

    expect(screen.queryByText("3/3 Active")).not.toBeNull();
    expect(screen.queryByText("5/5 Active")).toBeNull();
    expect(screen.queryByText("Buy")).toBeNull();
    expect(screen.queryByText("Hold")).toBeNull();
  });
});
