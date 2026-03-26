import { AdvisorIcon } from "../components/AdvisorIcon";
import { Formatters } from "../lib/formatters";
import { Presentation } from "../lib/presentation";
import type { AssetAnalysisResponse, AssetDetail, AdvisorNote } from "../types/api";

interface AssetDetailScreenProps {
  detail: AssetDetail;
  analysis: AssetAnalysisResponse | null;
  analysisUpdatedAt: string | null;
  tradeAmount: string;
  onTradeAmountChange: (value: string) => void;
  onBuy: () => void;
  onSell: () => void;
  tradeDisabled?: boolean;
  onBack: () => void;
}

function normalizeDecimalInput(value: string): string {
  return value.replace(/,/g, ".");
}

interface CouncilRow {
  advisorId: string;
  advisorName: string;
  thought: string;
}

function toSparklinePath(points: Array<{ price: string; timestamp: string }>): string {
  const numericValues = points
    .map((point) => Number(point.price))
    .filter((value) => Number.isFinite(value));

  if (numericValues.length < 2) {
    return "M 0 34 L 80 28 L 160 30 L 240 16 L 320 22";
  }

  const width = 320;
  const height = 46;
  const minimum = Math.min(...numericValues);
  const maximum = Math.max(...numericValues);
  const span = maximum - minimum || 1;

  return numericValues
    .map((value, index) => {
      const x = (index / (numericValues.length - 1)) * width;
      const y = height - ((value - minimum) / span) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildCouncilRows(detail: AssetDetail, analysis: AssetAnalysisResponse | null): CouncilRow[] {
  if ((analysis?.advisor_notes ?? []).length > 0) {
    return (analysis?.advisor_notes ?? []).map((note) => ({
      advisorId: note.advisor_id,
      advisorName: note.name,
      thought: note.thought,
    }));
  }

  const notesById = new Map<string, AdvisorNote>((analysis?.advisor_notes ?? []).map((note) => [note.advisor_id, note]));
  const rowsFromMarks = Object.entries(detail.agent_marks).map(([advisorId]) => {
    const note = notesById.get(advisorId);
    return {
      advisorId,
      advisorName: note?.name ?? Formatters.titleCase(advisorId),
      thought: note?.thought ?? detail.advisor_thought
    };
  });

  if (rowsFromMarks.length > 0) {
    return rowsFromMarks;
  }

  return (analysis?.advisor_notes ?? []).map((note) => ({
    advisorId: note.advisor_id,
    advisorName: note.name,
    thought: note.thought
  }));
}

function formatLastUpdated(value: string | null): string {
  if (value === null) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "n/a";
  }
  return parsed.toLocaleString("en-GB", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });
}

export function AssetDetailScreen(props: AssetDetailScreenProps): JSX.Element {
  const recommendation = props.analysis?.recommendation ?? props.detail.mark;
  const recommendationTone = Presentation.signalTone(recommendation);
  const sparklinePath = toSparklinePath(props.detail.net_worth_chart);
  const councilRows = buildCouncilRows(props.detail, props.analysis);

  return (
    <div className="screen asset-screen">
      <header className="topbar compact-topbar">
        <button className="brand-row plain-button" onClick={props.onBack} type="button">
          <span className="material-symbols-outlined">arrow_back</span>
          <strong className="brand-inline">xStocks</strong>
        </button>
        <div className="address-pill">0x...4f2a</div>
      </header>

      <section className="asset-hero">
        <div className="asset-main-head">
          <div className="asset-logo large">{props.detail.asset_id.slice(0, 2)}</div>
          <div>
            <h1 className="asset-title">{props.detail.asset_id} Corp.</h1>
            <p className="asset-subtle">NASDAQ: {props.detail.asset_id}</p>
          </div>
        </div>
        <div className="asset-price-row">
          <h2>{Formatters.currency(props.detail.net_worth)}</h2>
          <span className={`signal-pill ${recommendationTone}`}>{Formatters.percent(props.detail.pnl_percent)}</span>
        </div>
        <article className="spark-card">
          <span className="eyebrow">7D Performance</span>
          <svg className="sparkline" viewBox="0 0 320 52">
            <path d={sparklinePath} fill="none" stroke="currentColor" strokeWidth="2.4" />
          </svg>
        </article>
      </section>

      <section className="screen-card trade-card">
        <div className="section-head">
          <h2 className="section-title">Execute Trade</h2>
          <span className={`signal-pill ${recommendationTone}`}>{recommendation.toUpperCase()}</span>
        </div>
        <div className="inline-row amount-input-row">
          <span className="screen-title accent">$</span>
          <input
            aria-label="Trade amount"
            inputMode="decimal"
            onChange={(event) =>
              props.onTradeAmountChange(normalizeDecimalInput(event.target.value))
            }
            type="text"
            value={props.tradeAmount}
          />
        </div>
        <div className="action-grid split">
          <button className="cta-button" disabled={props.tradeDisabled} onClick={props.onBuy} type="button">
            Buy
          </button>
          <button className="ghost-button" disabled={props.tradeDisabled} onClick={props.onSell} type="button">
            Sell
          </button>
        </div>
        {props.tradeDisabled ? (
          <p className="asset-note">This asset is not tradeable.</p>
        ) : null}
      </section>

      <section className="stack">
        <article className="screen-card council-result-card">
          <span className="eyebrow">Council Result</span>
          <h3 className={`council-result-title ${recommendationTone}`}>
            {recommendation.toUpperCase()}
          </h3>
          <p className="advisor-description">
            {props.analysis?.summary ?? props.detail.advisor_thought}
          </p>
        </article>

        <div className="section-head">
          <h2 className="section-title">Fundamental Council Marks</h2>
        </div>
        <div className="marks-table asset-council-list">
          {councilRows.map((row) => (
            <article className="council-card asset-council-card" key={row.advisorId}>
              <div className="advisor-identity">
                <span className="advisor-inline-icon">
                  <AdvisorIcon advisorId={row.advisorId} />
                </span>
                <strong>{row.advisorName}</strong>
              </div>
              <p className="advisor-description">
                <strong>Reasoning:</strong> {row.thought}
              </p>
            </article>
          ))}
        </div>
      </section>
      <section className="time-footer">
        <p className="time-info">Last update: {formatLastUpdated(props.analysisUpdatedAt)}</p>
      </section>
    </div>
  );
}
