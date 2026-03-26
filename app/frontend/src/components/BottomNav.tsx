interface BottomNavProps {
  activeView: "dashboard" | "portfolio" | "history" | "settings";
  onSelect: (view: "dashboard" | "portfolio" | "history" | "settings") => void;
}

export function BottomNav(props: BottomNavProps): JSX.Element {
  return (
    <nav className="nav-shell">
      <button
        className={props.activeView === "portfolio" ? "nav-item active" : "nav-item"}
        onClick={() => props.onSelect("portfolio")}
        type="button"
      >
        <span className="material-symbols-outlined">analytics</span>
        <span>Invest</span>
      </button>
      <button
        className={props.activeView === "history" ? "nav-item active" : "nav-item"}
        onClick={() => props.onSelect("history")}
        type="button"
      >
        <span className="material-symbols-outlined">receipt_long</span>
        <span>Orders</span>
      </button>
      <button
        className={props.activeView === "dashboard" ? "nav-item active" : "nav-item"}
        onClick={() => props.onSelect("dashboard")}
        type="button"
      >
        <span className="material-symbols-outlined">home</span>
        <span>Home</span>
      </button>
      <button
        className={props.activeView === "settings" ? "nav-item active" : "nav-item"}
        onClick={() => props.onSelect("settings")}
        type="button"
      >
        <span className="material-symbols-outlined">settings</span>
        <span>Settings</span>
      </button>
    </nav>
  );
}
