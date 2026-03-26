export type AdvisorWeights = Record<string, number>;

export class AdvisorWeightsModel {
  public static defaults(selectedAdvisorIds: string[]): AdvisorWeights {
    const safeSelectedAdvisorIds = this.toSafeAdvisorIds(selectedAdvisorIds);
    if (safeSelectedAdvisorIds.length === 0) {
      return {};
    }
    if (safeSelectedAdvisorIds.length === 1) {
      return { [safeSelectedAdvisorIds[0]]: 33 };
    }
    if (safeSelectedAdvisorIds.length === 2) {
      return { [safeSelectedAdvisorIds[0]]: 33, [safeSelectedAdvisorIds[1]]: 33 };
    }
    if (safeSelectedAdvisorIds.length === 3) {
      return {
        [safeSelectedAdvisorIds[0]]: 33,
        [safeSelectedAdvisorIds[1]]: 33,
        [safeSelectedAdvisorIds[2]]: 34
      };
    }

    const equal = this.roundToTwo(100 / safeSelectedAdvisorIds.length);
    const weights: AdvisorWeights = {};
    let runningTotal = 0;
    safeSelectedAdvisorIds.forEach((advisorId, index) => {
      if (index === safeSelectedAdvisorIds.length - 1) {
        weights[advisorId] = this.roundToTwo(100 - runningTotal);
        return;
      }
      weights[advisorId] = equal;
      runningTotal = this.roundToTwo(runningTotal + equal);
    });
    return weights;
  }

  public static normalize(selectedAdvisorIds: string[], advisorWeights: AdvisorWeights | null | undefined): AdvisorWeights {
    const safeSelectedAdvisorIds = this.toSafeAdvisorIds(selectedAdvisorIds);
    if (safeSelectedAdvisorIds.length === 0) {
      return {};
    }
    const safeAdvisorWeights = this.toSafeWeights(advisorWeights);
    const scoped = safeSelectedAdvisorIds.map((advisorId) =>
      Math.max(0, Number(safeAdvisorWeights[advisorId] ?? 0))
    );
    const total = scoped.reduce((sum, item) => sum + item, 0);
    if (!Number.isFinite(total) || total <= 0) {
      return this.defaults(safeSelectedAdvisorIds);
    }

    const normalized: AdvisorWeights = {};
    let runningTotal = 0;
    safeSelectedAdvisorIds.forEach((advisorId, index) => {
      if (index === safeSelectedAdvisorIds.length - 1) {
        normalized[advisorId] = this.roundToTwo(100 - runningTotal);
        return;
      }
      const percent = this.roundToTwo((scoped[index] / total) * 100);
      normalized[advisorId] = percent;
      runningTotal = this.roundToTwo(runningTotal + percent);
    });

    return normalized;
  }

  public static updateWeight(
    selectedAdvisorIds: string[],
    advisorWeights: AdvisorWeights,
    advisorId: string,
    requestedWeight: number
  ): AdvisorWeights {
    const safeSelectedAdvisorIds = this.toSafeAdvisorIds(selectedAdvisorIds);
    if (!safeSelectedAdvisorIds.includes(advisorId)) {
      return this.normalize(safeSelectedAdvisorIds, advisorWeights);
    }

    if (safeSelectedAdvisorIds.length === 1) {
      return { [advisorId]: 100 };
    }

    const clampedWeight = this.clamp(this.roundToTwo(requestedWeight), 0, 100);
    const current = this.normalize(safeSelectedAdvisorIds, advisorWeights);
    const remaining = this.roundToTwo(100 - clampedWeight);
    const otherIds = safeSelectedAdvisorIds.filter((item) => item !== advisorId);
    const otherTotal = otherIds.reduce((sum, item) => sum + (current[item] ?? 0), 0);

    const updated: AdvisorWeights = {
      [advisorId]: clampedWeight
    };

    if (otherTotal <= 0) {
      const evenShare = this.roundToTwo(remaining / otherIds.length);
      let runningTotal = clampedWeight;
      otherIds.forEach((otherId, index) => {
        if (index === otherIds.length - 1) {
          updated[otherId] = this.roundToTwo(100 - runningTotal);
          return;
        }
        updated[otherId] = evenShare;
        runningTotal = this.roundToTwo(runningTotal + evenShare);
      });
      return this.normalize(safeSelectedAdvisorIds, updated);
    }

    let runningTotal = clampedWeight;
    otherIds.forEach((otherId, index) => {
      if (index === otherIds.length - 1) {
        updated[otherId] = this.roundToTwo(100 - runningTotal);
        return;
      }
      const nextWeight = this.roundToTwo(((current[otherId] ?? 0) / otherTotal) * remaining);
      updated[otherId] = nextWeight;
      runningTotal = this.roundToTwo(runningTotal + nextWeight);
    });

    return this.normalize(safeSelectedAdvisorIds, updated);
  }

  private static roundToTwo(value: number): number {
    return Math.round(value * 100) / 100;
  }

  private static clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value));
  }

  private static toSafeAdvisorIds(selectedAdvisorIds: string[]): string[] {
    if (!Array.isArray(selectedAdvisorIds)) {
      return [];
    }
    return selectedAdvisorIds.filter((advisorId) => typeof advisorId === "string" && advisorId.trim() !== "");
  }

  private static toSafeWeights(advisorWeights: AdvisorWeights | null | undefined): AdvisorWeights {
    if (advisorWeights === null || advisorWeights === undefined) {
      return {};
    }
    if (typeof advisorWeights !== "object" || Array.isArray(advisorWeights)) {
      return {};
    }
    return advisorWeights;
  }
}
