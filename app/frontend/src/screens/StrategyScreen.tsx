import type { RiskProfile } from "../types/api";

interface StrategyScreenProps {
  depositAmount: string;
  riskProfile: RiskProfile;
  onDepositChange: (value: string) => void;
  onRiskChange: (value: RiskProfile) => void;
  onNext: () => void;
  onBack: () => void;
}

function normalizeDecimalInput(value: string): string {
  return value.replace(/,/g, ".");
}

interface RiskOption {
  id: RiskProfile;
  label: string;
  description: string;
  icon: string;
}

const RISK_OPTIONS: RiskOption[] = [
  {
    id: "low",
    label: "Low",
    description: "Stable growth, minimal volatility. Blue-chip and stable positions.",
    icon: "shield"
  },
  {
    id: "medium",
    label: "Medium",
    description: "Balanced exposure. Established leaders and L2 ecosystems.",
    icon: "balance"
  },
  {
    id: "high",
    label: "High",
    description: "Maximum growth. DeFi protocols and emerging high-beta themes.",
    icon: "trending_up"
  }
];

const PRESET_AMOUNTS: string[] = ["500", "1000", "5000", "10000"];

function toPresetLabel(value: string): string {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return `$${value}`;
  }
  if (numericValue >= 1000) {
    return `$${numericValue / 1000}k`;
  }
  return `$${numericValue}`;
}

export function StrategyScreen(props: StrategyScreenProps): JSX.Element {
  const parsedAmount = Number(props.depositAmount);
  const sliderValue = Number.isFinite(parsedAmount) && parsedAmount > 0 ? Math.min(parsedAmount, 50000) : 1000;

  return (
    <div className="screen strategy-screen">
      <header className="topbar compact-topbar topbar-step-only">
        <div className="step-progress">
          <div className="step-track">
            <span style={{ width: "66%" }} />
          </div>
          <span className="step-pill">Step 2 of 3</span>
        </div>
      </header>

      <section className="stack">
        <h1 className="screen-title">
          Set Your <span className="accent">Strategy</span>
        </h1>
        <p className="screen-copy">
          Configure your risk appetite and initial capital so your advisor council can generate a first optimized
          portfolio.
        </p>
      </section>

      <section className="stack">
        <div className="section-head">
          <h2 className="section-title">Risk Tolerance</h2>
        </div>
        <div className="risk-stack">
          {RISK_OPTIONS.map((option) => {
            const isSelected = props.riskProfile === option.id;
            return (
              <button
                key={option.id}
                className={isSelected ? "risk-card active" : "risk-card"}
                onClick={() => props.onRiskChange(option.id)}
                type="button"
              >
                <div className="risk-card-head">
                  <div className="risk-icon">
                    <span className="material-symbols-outlined">{option.icon}</span>
                  </div>
                  <div>
                    <div className="risk-name">{option.label}</div>
                    <p className="screen-copy">{option.description}</p>
                  </div>
                  {isSelected ? (
                    <span className="material-symbols-outlined risk-check">check_circle</span>
                  ) : null}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="screen-card amount-card">
        <div className="section-head">
          <h2 className="section-title">Investment Amount</h2>
        </div>
        <div className="inline-row amount-input-row">
          <span className="screen-title accent">$</span>
          <input
            aria-label="Deposit amount"
            inputMode="decimal"
            onChange={(event) =>
              props.onDepositChange(normalizeDecimalInput(event.target.value))
            }
            type="text"
            value={props.depositAmount}
          />
        </div>
        <input
          className="range-input"
          max="50000"
          min="100"
          onChange={(event) => props.onDepositChange(event.target.value)}
          step="100"
          type="range"
          value={sliderValue}
        />
        <div className="summary-head">
          <span className="muted">Min $100</span>
          <span className="muted">Max $50k</span>
        </div>
        <div className="chip-row amount-presets">
          {PRESET_AMOUNTS.map((value) => (
            <button
              key={value}
              className={props.depositAmount === value ? "preset-button active" : "preset-button"}
              onClick={() => props.onDepositChange(value)}
              type="button"
            >
              {toPresetLabel(value)}
            </button>
          ))}
        </div>
      </section>

      <section className="stack">
        <button className="cta-button" onClick={props.onNext} type="button">
          Generate Portfolio
          <span className="material-symbols-outlined">auto_awesome</span>
        </button>
        <button className="ghost-link" onClick={props.onBack} type="button">
          Back to team selection
        </button>
      </section>
    </div>
  );
}
