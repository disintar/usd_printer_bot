export class Formatters {
  private static readonly ADVISOR_NAME_OVERRIDES: Record<string, string> = {
    v: "V (V for Vendetta)",
    v_cyberpunk: "V (Cyberpunk 2077)",
    wolf: "Wolf (Wall Street)"
  };

  public static currency(value: string | number): string {
    const numericValue = typeof value === "string" ? Number(value) : value;
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2
    }).format(numericValue);
  }

  public static percent(value: string | number): string {
    const numericValue = typeof value === "string" ? Number(value) : value;
    return `${numericValue.toFixed(2)}%`;
  }

  public static compactNumber(value: string | number): string {
    const numericValue = typeof value === "string" ? Number(value) : value;
    return new Intl.NumberFormat("en-US", {
      notation: "compact",
      maximumFractionDigits: 1
    }).format(numericValue);
  }

  public static titleCase(value: string): string {
    return value
      .split(/[_\s-]+/)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  public static advisorDisplayName(advisorId: string, advisorName: string): string {
    const override = this.ADVISOR_NAME_OVERRIDES[advisorId];
    if (override !== undefined) {
      return override;
    }
    return advisorName;
  }
}
