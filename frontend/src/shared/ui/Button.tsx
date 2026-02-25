import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

type ButtonProps = PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary" | "ghost";
  }
>;

function Button({ variant = "primary", className, children, ...rest }: ButtonProps) {
  return (
    <button
      className={["ui-button", `ui-button--${variant}`, className].filter(Boolean).join(" ")}
      {...rest}
    >
      {children}
    </button>
  );
}

export default Button;
