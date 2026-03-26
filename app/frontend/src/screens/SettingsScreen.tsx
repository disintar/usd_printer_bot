import { AdvisorIcon } from "../components/AdvisorIcon";
import { Formatters } from "../lib/formatters";
import type { AdvisorDefinition, RiskProfile } from "../types/api";

interface SettingsScreenProps {
  advisors: AdvisorDefinition[];
  selectedAdvisorIds: string[];
  riskProfile: RiskProfile;
  onOpenOnboarding: () => void;
  onOpenHistory: () => void;
}

export function SettingsScreen(props: SettingsScreenProps): JSX.Element {
  return (
    <div className="screen settings-screen">
      <header className="topbar compact-topbar">
        <div className="brand-row">
          <div className="brand-mark round">
            <span className="material-symbols-outlined">settings</span>
          </div>
          <div className="brand-copy">
            <strong>Settings</strong>
            <span>Fund controls</span>
          </div>
        </div>
      </header>

      <section className="screen-card">
        <div className="settings-row" style={{ justifyContent: "space-between" }}>
          <div>
            <strong>Risk profile</strong>
            <p className="settings-note">This mandate affects future advisor recommendations.</p>
          </div>
          <span className="signal-pill hold">{Formatters.titleCase(props.riskProfile)}</span>
        </div>
      </section>

      <section className="screen-card">
        <strong>Selected advisors</strong>
        <div className="chip-row" style={{ marginTop: 14 }}>
          {props.selectedAdvisorIds.map((advisorId) => {
            const advisor = props.advisors.find((item) => item.id === advisorId);
            return (
              <span key={advisorId} className="chip advisor-chip">
                <AdvisorIcon advisorId={advisorId} tablerIcon={advisor?.tabler_icon} size={14} stroke={2} />
                {advisor?.name ?? advisorId}
              </span>
            );
          })}
        </div>
      </section>

      <button className="cta-button" onClick={props.onOpenOnboarding} type="button">
        Re-open onboarding
      </button>
      <button className="ghost-button" onClick={props.onOpenHistory} type="button">
        Open history
      </button>
    </div>
  );
}
