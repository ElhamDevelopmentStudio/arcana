import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

type FieldProps = {
  label: string;
  hint?: string;
};

export function TextField({ label, hint, ...props }: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="ui-field">
      <span className="ui-field__label">{label}</span>
      <input className="ui-input" {...props} />
      {hint ? <span className="ui-field__hint">{hint}</span> : null}
    </label>
  );
}

export function SelectField({
  label,
  hint,
  children,
  ...props
}: FieldProps & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <label className="ui-field">
      <span className="ui-field__label">{label}</span>
      <select className="ui-input" {...props}>
        {children}
      </select>
      {hint ? <span className="ui-field__hint">{hint}</span> : null}
    </label>
  );
}

export function TextareaField({
  label,
  hint,
  ...props
}: FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <label className="ui-field">
      <span className="ui-field__label">{label}</span>
      <textarea className="ui-input ui-input--textarea" {...props} />
      {hint ? <span className="ui-field__hint">{hint}</span> : null}
    </label>
  );
}
