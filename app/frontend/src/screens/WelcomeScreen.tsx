interface WelcomeScreenProps {
  username: string;
  agentsActive: number;
  onContinue: () => void;
}

interface FeedCard {
  title: string;
  description: string;
  icon: string;
  tone: "primary" | "mint";
}

const FEED_CARDS: FeedCard[] = [
  {
    title: "Financial Statements",
    description:
      "Cross-referenced core fundamental data with historical variance analysis.",
    icon: "account_balance",
    tone: "primary",
  },
  {
    title: "SEC Filings",
    description:
      "Instant parsing of 10-Ks, 10-Qs, and 8-Ks for non-obvious risk disclosures.",
    icon: "description",
    tone: "mint",
  },
  {
    title: "Company News",
    description: "Global sentiment mapping across verified news sources.",
    icon: "newspaper",
    tone: "primary",
  },
  {
    title: "Segmented Financials",
    description:
      "Deep-dive into business unit performance and geographic revenue shifts.",
    icon: "pie_chart",
    tone: "mint",
  },
  {
    title: "Institutional Ownership",
    description:
      "Tracking 13F filings to map elite fund manager accumulation patterns.",
    icon: "groups",
    tone: "mint",
  },
  {
    title: "Financial Metrics",
    description: "Dynamic calculation of valuation and quality ratios.",
    icon: "monitoring",
    tone: "primary",
  },
  {
    title: "Insider Trades",
    description:
      "Identifying predictive buying signals from C-suite executives.",
    icon: "person_search",
    tone: "mint",
  },
  {
    title: "Analyst Estimates",
    description:
      "Consensus vs. agent projections to find alpha in market surprises.",
    icon: "insights",
    tone: "primary",
  },
];

export function WelcomeScreen(props: WelcomeScreenProps): JSX.Element {
  return (
    <div className="screen welcome-screen">
      <header className="topbar landing-topbar">
        <div className="landing-brand">
          <div className="landing-brand-icon">
            <span className="material-symbols-outlined">
              account_balance_wallet
            </span>
          </div>
          <span>PersonalFund</span>
        </div>
        <button
          className="landing-get-started"
          onClick={props.onContinue}
          type="button"
        >
          Get Started
        </button>
      </header>

      <section className="stack landing-hero">
        <div className="landing-intelligence">
          <span className="landing-intelligence-dot">
            <span className="landing-intelligence-ping" />
            <span className="landing-intelligence-core" />
          </span>
          Institutional Intelligence
        </div>

        <h1 className="screen-title">
          Trade xStocks On-chain with your{" "}
          <span className="accent">Elite Council of AI Agents</span>
        </h1>
        <p className="hero-copy">
          Your sovereign Personal Fund performs deep fundamental analysis across
          global markets, powered by an elite council of AI agents.
        </p>

        <button
          className="landing-primary-button"
          onClick={props.onContinue}
          type="button"
        >
          Assemble Your Council
        </button>

        <div className="landing-agents-card">
          <div className="landing-avatar-stack">
            <span>AI1</span>
            <span>AI2</span>
            <span>AI3</span>
          </div>
          <span className="landing-agents-label">
            {props.agentsActive.toLocaleString()}+ Agents Active
          </span>
        </div>
      </section>

      <section className="stack landing-feed">
        <div>
          <h2 className="section-title">Council Data Feed</h2>
          <p className="screen-copy">
            Real-time fundamental signals analyzed by your agents.
          </p>
        </div>

        <div className="landing-feed-grid">
          {FEED_CARDS.map((item) => (
            <article className="feed-card" key={item.title}>
              <div
                className={
                  item.tone === "primary"
                    ? "feed-icon feed-icon-primary"
                    : "feed-icon feed-icon-mint"
                }
              >
                <span className="material-symbols-outlined">{item.icon}</span>
              </div>
              <div>
                <strong>{item.title}</strong>
                <p className="screen-copy">{item.description}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-trust">
        <p>
          <span className="material-symbols-outlined">verified_user</span>
          Sovereign. Private. Institutional Grade.
        </p>
      </section>
    </div>
  );
}
