import { Input } from "../ui/input";

export function FieldInput({ label, value, onChange, onBlur, testId, type = "text" }) {
  return (
    <div>
      <label className="es-label block mb-1.5">{label}</label>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        data-testid={testId}
        className="bg-[#0A0A0A] border-white/10 text-white"
      />
    </div>
  );
}
