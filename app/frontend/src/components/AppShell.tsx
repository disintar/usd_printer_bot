import type { PropsWithChildren, ReactNode } from "react";

interface AppShellProps extends PropsWithChildren {
  actions?: ReactNode;
}

export function AppShell(props: AppShellProps): JSX.Element {
  return (
    <div className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      {props.actions !== undefined ? <div className="shell-actions">{props.actions}</div> : null}
      <main className="app-main">{props.children}</main>
    </div>
  );
}
