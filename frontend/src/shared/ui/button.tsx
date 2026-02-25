import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

import { Button as UiButton } from "@/components/ui/button";

type ButtonProps = PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary" | "ghost";
  }
>;

function Button({ variant = "primary", className, children, ...rest }: ButtonProps) {
  const uiVariant = variant === "primary" ? "default" : variant === "secondary" ? "secondary" : "ghost";

  return (
    <UiButton variant={uiVariant} className={className} {...rest}>
      {children}
    </UiButton>
  );
}

export default Button;
