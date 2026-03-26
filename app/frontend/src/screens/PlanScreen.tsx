import { AdvisorIcon } from "../components/AdvisorIcon";
import { Formatters } from "../lib/formatters";
import type { AdvisorDefinition, StartRecommendationsResponse, TestAgentsResponse } from "../types/api";

interface PlanScreenProps {
  result: StartRecommendationsResponse;
  advisors: AdvisorDefinition[];
  selectedAdvisors: string[];
  advisorWeights: Record<string, number>;
  testAgents?: TestAgentsResponse | null;
  onGoDashboard: () => void;
  onInspectAsset: (assetId: string) => void;
}

interface AllocationRow {
  assetId: string;
  percent: number;
  action: string;
  reason: string;
}

interface CouncilRow {
  advisorId: string;
  advisorName: string;
  advisorRole: string;
  tablerIcon?: string;
  weightPercent: number;
  reasoning: string;
}

const SEGMENT_TONES: string[] = ["segment-primary", "segment-secondary", "segment-tertiary", "segment-muted"];

interface LegacyRecommendation {
  asset_id?: string;
  allocation_percent?: string;
  action?: string;
  rationale?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeKey(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function getBuyRecommendations(result: StartRecommendationsResponse): Array<Record<string, unknown>> {
  const asUnknown = result as unknown;
  if (!isRecord(asUnknown)) {
    return [];
  }
  if (Array.isArray(asUnknown.buy_recommendations)) {
    return asUnknown.buy_recommendations.filter((item): item is Record<string, unknown> => isRecord(item));
  }
  if (Array.isArray(asUnknown.recommendations)) {
    return asUnknown.recommendations.filter((item): item is Record<string, unknown> => isRecord(item));
  }
  return [];
}

function extractSummaryText(item: Record<string, unknown>): string {
  const candidates = [
    item.summary,
    item.reasoning,
    item.reason,
    item.thought,
  ];
  for (const candidate of candidates) {
    const text = String(candidate ?? "").trim();
    if (text !== "") {
      return text;
    }
  }
  return "";
}

function parsePercent(value: string): number {
  const parsedValue = Number(value);
  if (!Number.isFinite(parsedValue)) {
    return 0;
  }
  return Math.max(parsedValue, 0);
}

function makeRows(result: StartRecommendationsResponse): AllocationRow[] {
  const rows = getBuyRecommendations(result).map((item) => {
    const legacy = item as LegacyRecommendation;
    const assetId = String(item.asset_id ?? "").trim();
    if (assetId === "") {
      return null;
    }
    return {
      assetId,
      percent: parsePercent(String(item.allocation_percent ?? "0")),
      action: String(item.verdict ?? legacy.action ?? "hold").trim(),
      reason: String(item.reason ?? legacy.rationale ?? "").trim(),
    };
  }).filter((item): item is AllocationRow => item !== null);

  if (rows.length === 0) {
    return [
      {
        assetId: "CASH",
        percent: 100,
        action: "hold",
        reason: "No allocation data yet.",
      }
    ];
  }

  const normalizedRows = rows.map((row) => ({
    ...row,
    reason: row.reason || "No reasoning provided.",
  }));

  const totalPercent = normalizedRows.reduce((sum, row) => sum + row.percent, 0);
  const remainder = Math.round(Math.max(0, 100 - totalPercent));
  if (remainder > 0) {
    normalizedRows.push({
      assetId: "CASH",
      percent: remainder,
      action: "hold",
      reason: "Reserved for liquidity and tactical rebalancing.",
    });
  }

  return normalizedRows;
}

function toForecast(percent: number): string {
  const forecast = Math.max(1.2, percent / 8);
  return `+${forecast.toFixed(1)}%`;
}

function formatPercentValue(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  if (!Number.isFinite(rounded)) {
    return "0";
  }
  if (Number.isInteger(rounded)) {
    return String(rounded);
  }
  return rounded.toFixed(2).replace(/\.?0+$/, "");
}

function makeCouncilRows(
  advisors: AdvisorDefinition[],
  selectedAdvisors: string[],
  advisorWeights: Record<string, number>,
  result: StartRecommendationsResponse,
  testAgents: TestAgentsResponse | null,
): CouncilRow[] {
  if (selectedAdvisors.length === 0) {
    return [];
  }
  const advisorsById = new Map<string, AdvisorDefinition>(advisors.map((advisor) => [advisor.id, advisor]));
  const advisorNameById = new Map<string, string>(
    selectedAdvisors.map((advisorId) => [
      advisorId,
      advisorsById.get(advisorId)?.name ?? Formatters.titleCase(advisorId),
    ]),
  );
  const summaries = Array.isArray((result as unknown as Record<string, unknown>).advisor_summaries)
    ? ((result as unknown as Record<string, unknown>).advisor_summaries as Array<Record<string, unknown>>)
    : [];
  const summariesByNormalizedKey = new Map<string, string>();
  const unassignedSummaries: string[] = [];
  for (const item of summaries) {
    const summaryText = extractSummaryText(item);
    if (summaryText === "") {
      continue;
    }
    const rawIdCandidates = [
      String(item.advisor_id ?? "").trim(),
      String(item.advisor_name ?? "").trim(),
      String(item.name ?? "").trim(),
    ].filter((candidate) => candidate !== "");
    let assigned = false;
    for (const rawCandidate of rawIdCandidates) {
      const normalizedCandidate = normalizeKey(rawCandidate);
      if (normalizedCandidate === "") {
        continue;
      }
      summariesByNormalizedKey.set(normalizedCandidate, summaryText);
      assigned = true;
    }
    if (!assigned) {
      unassignedSummaries.push(summaryText);
    }
  }

  const backendAllocation = testAgents?.allocation ?? {};
  const globalSummaryFallback = String(
    (result as unknown as Record<string, unknown>).summary
      ?? (result as unknown as Record<string, unknown>).reasoning
      ?? "",
  ).trim();
  let fallbackSummaryIndex = 0;
  return selectedAdvisors.map((advisorId) => ({
    advisorId,
    advisorName: Formatters.advisorDisplayName(
      advisorId,
      advisorsById.get(advisorId)?.name ?? Formatters.titleCase(advisorId)
    ),
    advisorRole: advisorsById.get(advisorId)?.role ?? "Advisor",
    weightPercent: Math.max(
      0,
      Number(advisorWeights[advisorId] ?? backendAllocation[advisorId] ?? 0)
    ),
    reasoning: (() => {
      const idKey = normalizeKey(advisorId);
      const advisorName = advisorNameById.get(advisorId) ?? "";
      const nameKey = normalizeKey(advisorName);
      const fromId = summariesByNormalizedKey.get(idKey);
      if (fromId) {
        return fromId;
      }
      const fromName = summariesByNormalizedKey.get(nameKey);
      if (fromName) {
        return fromName;
      }
      const nextSummary = unassignedSummaries[fallbackSummaryIndex];
      if (typeof nextSummary === "string" && nextSummary.trim() !== "") {
        fallbackSummaryIndex += 1;
        return nextSummary;
      }
      if (globalSummaryFallback !== "") {
        return globalSummaryFallback;
      }
      return "Summary is being prepared.";
    })(),
  }));
}

export function PlanScreen(props: PlanScreenProps): JSX.Element {
  const testAgents = props.testAgents ?? null;
  const rows = makeRows(props.result);
  const councilRows = makeCouncilRows(
    props.advisors,
    props.selectedAdvisors,
    props.advisorWeights,
    props.result,
    testAgents,
  );
  const recommendationRows = rows.filter((row) => row.assetId !== "CASH");
  const totalForecast = recommendationRows.reduce((sum, row) => sum + Number(toForecast(row.percent).replace("+", "").replace("%", "")), 0);

  return (
    <div className="screen plan-screen">
      <section className="stack">
        <h1 className="screen-title">Your Optimized Portfolio</h1>
        <p className="screen-copy">Tailored by your selected AI council for maximum stability and growth.</p>
      </section>

      <section className="screen-card allocation-card">
        <div className="allocation-head">
          <div>
            <span className="eyebrow">Asset Distribution</span>
            <h2 className="section-title">Target Allocation</h2>
          </div>
          <div className="forecast-pill">
            <span className="material-symbols-outlined">trending_up</span>
            +{totalForecast.toFixed(1)}% Est.
          </div>
        </div>

        <div className="allocation-bar">
          {rows.map((row, index) => (
            <button
              aria-label={`Inspect ${row.assetId}`}
              className={`allocation-segment ${SEGMENT_TONES[index] ?? SEGMENT_TONES[SEGMENT_TONES.length - 1]}`}
              key={row.assetId}
              onClick={() => {
                if (row.assetId !== "CASH") {
                  props.onInspectAsset(row.assetId);
                }
              }}
              style={{ width: `${row.percent}%` }}
              type="button"
            >
              {row.assetId}
            </button>
          ))}
        </div>

        <div className="allocation-legend">
          {rows.map((row, index) => (
            <div className="legend-row" key={`${row.assetId}-legend`}>
              <span className={`legend-dot ${SEGMENT_TONES[index] ?? SEGMENT_TONES[SEGMENT_TONES.length - 1]}`} />
              <span className="muted">
                {row.percent}% {row.assetId === "CASH" ? "Stable" : row.assetId}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="stack">
        <h2 className="section-title">Active Agent Council</h2>
        <p className="screen-copy">
          {testAgents !== null
            ? `${props.selectedAdvisors.length}/${props.selectedAdvisors.length} backend agents active`
            : "Loading backend agents..."}
        </p>
        <div className="advisor-list">
          {councilRows.map((row) => {
            return (
              <article className="council-card" key={row.advisorId}>
                <div className="summary-head">
                  <div className="advisor-identity">
                    <span className="advisor-inline-icon">
                      <AdvisorIcon advisorId={row.advisorId} tablerIcon={row.tablerIcon} />
                    </span>
                    <strong>{row.advisorName}</strong>
                  </div>
                  <span className="signal-pill buy">{formatPercentValue(row.weightPercent)}% Allocation</span>
                </div>
                <p className="advisor-description">{row.advisorRole}</p>
                <p className="advisor-description">
                  <strong>Reasoning:</strong> {row.reasoning}
                </p>
              </article>
            );
          })}
        </div>
      </section>

      <button className="cta-button" onClick={props.onGoDashboard} type="button">
        Activate & Deposit
      </button>
    </div>
  );
}
