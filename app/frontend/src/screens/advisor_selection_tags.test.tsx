import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AdvisorSelectionScreen } from "./AdvisorSelectionScreen";

describe("advisor selection primary tag filters", () => {
  it("shows only fixed primary tag pills and filters by primary_tag", () => {
    render(
      <AdvisorSelectionScreen
        advisors={[
          {
            id: "warren_buffett",
            name: "Warren Buffett",
            category: "serious",
            role: "Long-term value investor",
            style: ["value"],
            tags: ["value", "fundamentals"],
            primary_tag: "investments",
          },
          {
            id: "wolf",
            name: "Wolf (Wall Street)",
            category: "playful",
            role: "Aggressive sales and momentum",
            style: ["aggressive"],
            tags: ["sales"],
            primary_tag: "films",
          },
        ]}
        advisorWeights={{}}
        selectedAdvisorIds={[]}
        onToggle={() => undefined}
        onWeightChange={() => undefined}
        onContinue={() => undefined}
      />,
    );

    expect(screen.queryByText("💰 Investments")).not.toBeNull();
    expect(screen.queryByText("🏢 Business")).not.toBeNull();
    expect(screen.queryByText("📚 Books")).not.toBeNull();
    expect(screen.queryByText("🎬 Films")).not.toBeNull();
    expect(screen.queryByText("🧠 Anime")).not.toBeNull();
    expect(screen.queryByText("🎮 Games")).not.toBeNull();
    expect(screen.queryByText("#Value")).toBeNull();

    fireEvent.click(screen.getByText("🎬 Films"));
    expect(screen.queryByText("Wolf (Wall Street)")).not.toBeNull();
    expect(screen.queryByText("Warren Buffett")).toBeNull();
  });
});
