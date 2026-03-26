export type AccentTone = "blue" | "mint" | "amber" | "slate";
export type SignalTone = "buy" | "hold" | "sell" | "watch";

export class Presentation {
  public static advisorInitials(name: string): string {
    return name
      .split(/\s+/)
      .filter((part) => part !== "")
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("")
      .slice(0, 2);
  }

  public static advisorAccent(tags: string[]): AccentTone {
    const normalizedTags = tags.map((tag) => tag.toLowerCase());
    if (normalizedTags.includes("growth") || normalizedTags.includes("founder") || normalizedTags.includes("tech")) {
      return "blue";
    }
    if (normalizedTags.includes("value") || normalizedTags.includes("quality") || normalizedTags.includes("cashflow")) {
      return "mint";
    }
    if (normalizedTags.includes("contrarian") || normalizedTags.includes("macro") || normalizedTags.includes("aggressive")) {
      return "amber";
    }
    return "slate";
  }

  public static signalTone(mark: string | null | undefined): SignalTone {
    const normalizedMark = String(mark ?? "").toLowerCase();
    if (normalizedMark.includes("buy")) {
      return "buy";
    }
    if (normalizedMark.includes("sell")) {
      return "sell";
    }
    if (normalizedMark.includes("hold")) {
      return "hold";
    }
    return "watch";
  }
}
