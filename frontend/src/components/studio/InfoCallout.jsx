import { Info } from "lucide-react";

export function InfoCallout({ text }) {
  return (
    <div className="es-card p-3 flex items-start gap-2 border-white/10 bg-white/[0.02]">
      <Info className="w-4 h-4 text-[#A1A1AA] mt-0.5 shrink-0" />
      <p className="text-xs text-[#A1A1AA]">{text}</p>
    </div>
  );
}
