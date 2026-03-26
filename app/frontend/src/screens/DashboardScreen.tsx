import { AdvisorIcon } from "../components/AdvisorIcon";
import { Formatters } from "../lib/formatters";
import type {
  AdvisorDefinition,
  BalanceResponse,
  StartRecommendationsResponse,
  PortfolioResponse,
  TestAgentsResponse,
  TestTimeResponse,
} from "../types/api";

interface DashboardScreenProps {
  balance: BalanceResponse;
  networkMode?: "test" | "onchain";
  portfolio: PortfolioResponse;
  testClock: TestTimeResponse | null;
  testPrices: Record<string, string>;
  testAgents: TestAgentsResponse | null;
  startRecommendations: StartRecommendationsResponse | null;
  advisors?: AdvisorDefinition[];
  selectedAdvisors: string[];
  advisorWeights: Record<string, number>;
  onSelectNetworkMode?: (mode: "test" | "onchain") => void;
  onRefresh: () => void;
  onDeposit: () => void;
  onOpenInvest: () => void;
  onOpenTopUp?: () => void;
  onOpenWithdrawal?: () => void;
}

interface ActionButton {
  id: string;
  label: string;
  icon: string;
  onClick: () => void;
}

export function DashboardScreen(props: DashboardScreenProps): JSX.Element {
  const networkMode = props.networkMode ?? "test";
  const selectedAgents =
    props.selectedAdvisors.length > 0
      ? props.selectedAdvisors
      : (props.testAgents?.selected_agents ?? []);
  const allAgentsCount = selectedAgents.length;
  const allocation =
    Object.keys(props.advisorWeights).length > 0
      ? props.advisorWeights
      : (props.testAgents?.allocation ?? {});
  const advisorsById = new Map<string, AdvisorDefinition>(
    (props.advisors ?? []).map((advisor) => [advisor.id, advisor]),
  );
  const summariesByAdvisorId = new Map<string, string>(
    (props.startRecommendations?.advisor_summaries ?? [])
      .map(
        (item) =>
          [
            String(item.advisor_id ?? "").trim(),
            String(item.summary ?? "").trim(),
          ] as const,
      )
      .filter(([advisorId, summary]) => advisorId !== "" && summary !== ""),
  );
  const topSymbols = ["AAPLx", "NVDAx", "TSLAx", "COINx"];

  const actionButtons: ActionButton[] = [
    {
      id: "refresh",
      label: "Refresh",
      icon: "refresh",
      onClick: props.onRefresh,
    },
    ...(networkMode === "onchain"
      ? [
          {
            id: "topup",
            label: "Top up",
            icon: "south",
            onClick: props.onOpenTopUp ?? (() => undefined),
          },
          {
            id: "withdrawal",
            label: "Withdrawal",
            icon: "north_east",
            onClick: props.onOpenWithdrawal ?? (() => undefined),
          },
        ]
      : [
          {
            id: "invest",
            label: "Invest",
            icon: "analytics",
            onClick: props.onOpenInvest,
          },
        ]),
  ];

  const topPricesLine = topSymbols
    .map((symbol) => {
      const price = props.testPrices[symbol];
      if (price === undefined) {
        return null;
      }
      return `${symbol} ${Formatters.currency(price)}`;
    })
    .filter((item): item is string => item !== null)
    .join(" · ");

  return (
    <div className="screen dashboard-screen">
      <section className="network-switch">
        <button
          className={`switch-pill${networkMode === "onchain" ? " active" : ""}`}
          onClick={() => props.onSelectNetworkMode?.("onchain")}
          type="button"
        >
          Onchain
        </button>
        <button
          className={`switch-pill${networkMode === "test" ? " active" : ""}`}
          onClick={() => props.onSelectNetworkMode?.("test")}
          type="button"
        >
          Test
        </button>
      </section>

      <section className="hero-balance editorial dashboard-plain-hero">
        <p className="screen-copy">Total Balance</p>
        <h1 className="hero-value">
          {Formatters.currency(props.balance.total_balance_usdt)}
        </h1>
        <div className="inline-row center">
          <span className="signal-pill buy">
            {Formatters.percent(props.balance.pnl_percent)}
          </span>
          <span className="muted">
            {Formatters.currency(props.balance.pnl_absolute)}
          </span>
        </div>
      </section>

      <section
        className={
          networkMode === "test"
            ? "action-grid action-grid-test"
            : "action-grid"
        }
      >
        {actionButtons.map((item) => (
          <button
            className="action-button dashboard-plain-action"
            key={item.id}
            onClick={item.onClick}
            type="button"
          >
            <div className="action-icon">
              <span className="material-symbols-outlined">{item.icon}</span>
            </div>
            <span>{item.label}</span>
          </button>
        ))}
      </section>

      <section className="stack">
        <div className="section-head">
          <h2 className="section-title">Fundamental AI Agents</h2>
          <div className="inline-row">
            <span className="chip">
              {selectedAgents.length}/{allAgentsCount} Active
            </span>
          </div>
        </div>
        <div className="advisor-carousel">
          {selectedAgents.map((agentId) => (
            <article className="screen-card advisor-panel" key={agentId}>
              <div className="summary-head">
                <span className="chip">Agent</span>
                <span className="signal-pill buy">
                  {Math.round(Number(allocation[agentId] ?? 0))}% Weight
                </span>
              </div>
              <div className="advisor-name-row">
                <span className="advisor-inline-icon">
                  <AdvisorIcon
                    advisorId={agentId}
                    tablerIcon={advisorsById.get(agentId)?.tabler_icon}
                  />
                </span>
                <h3>
                  {Formatters.advisorDisplayName(
                    agentId,
                    Formatters.titleCase(agentId),
                  )}
                </h3>
              </div>
              <p className="summary-copy">
                {advisorsById.get(agentId)?.role ?? "Advisor"}
              </p>
              <p className="summary-copy">
                <strong>Reasoning:</strong>{" "}
                {summariesByAdvisorId.get(agentId) ??
                  "Reasoning is not available yet."}
              </p>
            </article>
          ))}
          {selectedAgents.length === 0 ? (
            <article className="screen-card advisor-panel">
              <h3>No Active Agents</h3>
              <p className="summary-copy">
                Agent selection is empty for this account.
              </p>
            </article>
          ) : null}
        </div>
      </section>

      <section className="home-meta">
        <p className="screen-copy">
          Server: {props.testClock?.server_time_utc_pretty ?? "UTC n/a"}
          <br />
          Simulated: {props.testClock?.simulated_time_utc_pretty ?? "UTC n/a"}
        </p>
      </section>
    </div>
  );
}
