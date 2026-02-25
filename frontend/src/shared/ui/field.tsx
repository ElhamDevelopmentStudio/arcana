import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type FieldProps = {
  label: string;
  hint?: string;
};

export function TextField({ label, hint, ...props }: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="ui-field">
      <Label className="ui-field__label">{label}</Label>
      <Input className="ui-input" {...props} />
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
      <Label className="ui-field__label">{label}</Label>
      <Select className="ui-input" {...props}>
        {children}
      </Select>
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
      <Label className="ui-field__label">{label}</Label>
      <Textarea className="ui-input ui-input--textarea" {...props} />
      {hint ? <span className="ui-field__hint">{hint}</span> : null}
    </label>
  );
}
