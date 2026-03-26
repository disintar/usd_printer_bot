import type { PropsWithChildren, ReactNode } from "react";

interface SectionCardProps extends PropsWithChildren {
  title: string;
  subtitle?: string;
  aside?: ReactNode;
}

export function SectionCard(props: SectionCardProps): JSX.Element {
  return (
    <section className="section-card">
      <div className="section-card-header">
        <div>
          <h2>{props.title}</h2>
          {props.subtitle !== undefined ? <p>{props.subtitle}</p> : null}
        </div>
        {props.aside}
      </div>
      {props.children}
    </section>
  );
}
