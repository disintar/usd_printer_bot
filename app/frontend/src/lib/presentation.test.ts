import { describe, expect, it } from "vitest";

import { Presentation } from "./presentation";

describe("Presentation", () => {
  it("builds advisor initials from names", () => {
    expect(Presentation.advisorInitials("Warren Buffett")).toBe("WB");
    expect(Presentation.advisorInitials("Pavel Durov")).toBe("PD");
    expect(Presentation.advisorInitials("Tyler")).toBe("T");
  });

  it("maps advisor tags to stable accent tones", () => {
    expect(Presentation.advisorAccent(["value", "quality"])).toBe("mint");
    expect(Presentation.advisorAccent(["growth", "tech"])).toBe("blue");
    expect(Presentation.advisorAccent(["macro"])).toBe("amber");
    expect(Presentation.advisorAccent(["unknown"])).toBe("slate");
  });

  it("maps marks to action tones", () => {
    expect(Presentation.signalTone("BUY")).toBe("buy");
    expect(Presentation.signalTone("HOLD")).toBe("hold");
    expect(Presentation.signalTone("SELL")).toBe("sell");
    expect(Presentation.signalTone("neutral")).toBe("watch");
  });
});
