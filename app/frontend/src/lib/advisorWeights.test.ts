import { describe, expect, it } from "vitest";

import { AdvisorWeightsModel } from "./advisorWeights";

describe("AdvisorWeightsModel", () => {
  it("returns defaults for one, two and three advisors", () => {
    expect(AdvisorWeightsModel.defaults(["a"])).toEqual({ a: 33 });
    expect(AdvisorWeightsModel.defaults(["a", "b"])).toEqual({ a: 33, b: 33 });
    expect(AdvisorWeightsModel.defaults(["a", "b", "c"])).toEqual({ a: 33, b: 33, c: 34 });
  });

  it("normalizes custom weights to total 100", () => {
    expect(AdvisorWeightsModel.normalize(["a", "b"], { a: 80, b: 10 })).toEqual({ a: 88.89, b: 11.11 });
  });

  it("falls back safely when weights are missing", () => {
    expect(AdvisorWeightsModel.normalize(["a", "b", "c"], undefined)).toEqual({ a: 33, b: 33, c: 34 });
  });

  it("updates one advisor weight and rebalances the rest", () => {
    const updated = AdvisorWeightsModel.updateWeight(
      ["a", "b", "c"],
      { a: 40, b: 30, c: 30 },
      "a",
      55
    );
    expect(updated.a).toBe(55);
    expect(Number((updated.a + updated.b + updated.c).toFixed(2))).toBe(100);
  });
});
