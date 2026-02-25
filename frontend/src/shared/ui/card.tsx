import type { PropsWithChildren, ReactNode } from "react";

import {
  Card as UiCard,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type CardProps = PropsWithChildren<{
  title: string;
  subtitle?: string;
  action?: ReactNode;
  testId?: string;
}>;

function Card({ title, subtitle, action, children, testId }: CardProps) {
  return (
    <UiCard className="ui-card" data-testid={testId}>
      <CardHeader className="ui-card__header">
        <div className="space-y-1">
          <CardTitle>{title}</CardTitle>
          {subtitle ? <CardDescription className="ui-card__subtitle">{subtitle}</CardDescription> : null}
        </div>
        {action}
      </CardHeader>
      <CardContent className="ui-card__body">{children}</CardContent>
    </UiCard>
  );
}

export default Card;
