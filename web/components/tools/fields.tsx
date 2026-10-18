"use client";
import { useId } from "react";

// 도구 공통 입력 컴포넌트(모바일 우선). 금액은 '만원' 단위 숫자 입력.
export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="tf">
      <label className="tf-label">{label}</label>
      {hint ? <div className="tf-hint">{hint}</div> : null}
      {children}
    </div>
  );
}

export function ManwonInput({ label, hint, value, onChange }: { label: string; hint?: string; value: string; onChange: (v: string) => void }) {
  const id = useId();
  return (
    <Field label={label} hint={hint}>
      <div className="tf-num">
        <input id={id} inputMode="numeric" pattern="[0-9]*" value={value} placeholder="0"
          onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, ""))} />
        <span>만원</span>
      </div>
    </Field>
  );
}

export function Choice<T extends string>({ label, hint, value, options, onChange }: {
  label: string; hint?: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void;
}) {
  return (
    <Field label={label} hint={hint}>
      <div className="tf-choice" role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button key={o.value} type="button" role="radio" aria-checked={o.value === value}
            className={o.value === value ? "on" : ""} onClick={() => onChange(o.value)}>{o.label}</button>
        ))}
      </div>
    </Field>
  );
}

export const toWon = (manwon: string): number => (manwon === "" ? 0 : Number(manwon) * 10_000);

export function ResultBox({ tone, title, children }: { tone: "good" | "warn" | "info"; title: string; children: React.ReactNode }) {
  return (
    <div className={`tr tr-${tone}`} role="status">
      <div className="tr-title">{title}</div>
      <div className="tr-body">{children}</div>
    </div>
  );
}
