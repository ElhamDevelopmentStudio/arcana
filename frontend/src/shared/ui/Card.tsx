import type { PropsWithChildren, ReactNode } from "react";

type CardProps = PropsWithChildren<{
  title: string;
  subtitle?: string;
  action?: ReactNode;
  testId?: string;
}>;

function Card({ title, subtitle, action, children, testId }: CardProps) {
  return (
    <section className="ui-card" data-testid={testId}>
      <header className="ui-card__header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p className="ui-card__subtitle">{subtitle}</p> : null}
        </div>
        {action}
      </header>
      <div className="ui-card__body">{children}</div>
    </section>
  );
}

export default Card;
