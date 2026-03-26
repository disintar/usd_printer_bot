import { useEffect, useMemo, useState } from "react";
import type { JSX } from "react";

const PIPELINE_STEPS: string[] = [
  "Evaluating Assets",
  "Calculating Weights",
  "Optimizing Portfolio",
];

function formatElapsed(milliseconds: number): string {
  const safeMs = Math.max(0, Math.floor(milliseconds));
  const minutes = Math.floor(safeMs / 60000);
  const seconds = Math.floor((safeMs % 60000) / 1000);
  const ms = safeMs % 1000;
  return `${minutes.toString().padStart(2, "0")}:${seconds
    .toString()
    .padStart(2, "0")}.${ms.toString().padStart(3, "0")}s`;
}

export function CouncilAnalyticsScreen(): JSX.Element {
  const [elapsedMs, setElapsedMs] = useState(0);
  useEffect(() => {
    const startedAt = performance.now();
    let animationFrameId = 0;
    const tick = (): void => {
      setElapsedMs(performance.now() - startedAt);
      animationFrameId = window.requestAnimationFrame(tick);
    };
    animationFrameId = window.requestAnimationFrame(tick);
    return () => {
      window.cancelAnimationFrame(animationFrameId);
    };
  }, []);
  const elapsedPretty = useMemo(() => formatElapsed(elapsedMs), [elapsedMs]);

  return (
    <div className="screen council-analytics-screen">
      <header className="topbar compact-topbar topbar-step-only">
        <div className="step-progress">
          <div className="step-track">
            <span style={{ width: "100%" }} />
          </div>
          <span className="step-pill">Step 3 of 3</span>
        </div>
      </header>

      <section className="stack">
        <h1 className="screen-title">
          Council <span className="accent">Analytics</span>
        </h1>
        <p className="screen-copy">
          Your AI council is analyzing markets, evaluating positions, and
          optimizing your portfolio strategy...
        </p>
      </section>

      <section className="screen-card council-analytics-card">
        <div className="council-analytics-head">
          <div className="brand-mark round council-loader-mark">
            <span className="material-symbols-outlined">autorenew</span>
          </div>
          <div>
            <strong>Generating Portfolio Plan</strong>
            <p className="screen-copy">
              Processing selected advisors, risk profile, and test-market data.
            </p>
          </div>
        </div>

        <div className="council-progress-track">
          <span className="council-progress-fill" />
        </div>
        <div className="council-wait-timer" aria-live="polite">
          <span className="council-wait-precise">{elapsedPretty}</span>
        </div>

        <div className="council-steps">
          {PIPELINE_STEPS.map((step, index) => (
            <div className="council-step-row" key={step}>
              <span className={index === 0 ? "dot pulse" : "dot"} />
              <span className={index === 0 ? "council-step-label active" : "council-step-label"}>
                {step}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
