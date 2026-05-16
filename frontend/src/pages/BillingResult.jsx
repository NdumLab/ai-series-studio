import { Link } from "react-router-dom";
import { CheckCircle2, XCircle } from "lucide-react";
import { Button } from "../components/ui/button";

export function BillingSuccess() {
  return (
    <BillingResult
      icon={<CheckCircle2 className="w-8 h-8 text-[#34C759]" />}
      title="Test credits processing"
      message="Stripe sent the checkout result to the backend webhook. Your wallet updates after the test webhook is received and verified."
    />
  );
}

export function BillingCancel() {
  return (
    <BillingResult
      icon={<XCircle className="w-8 h-8 text-[#FFCC00]" />}
      title="Checkout canceled"
      message="No credits were added and no payment was completed."
    />
  );
}

function BillingResult({ icon, title, message }) {
  return (
    <div className="max-w-md mx-auto es-fade">
      <div className="es-card p-6 text-center">
        <div className="w-14 h-14 mx-auto rounded-md bg-white/5 border border-white/10 flex items-center justify-center mb-4">
          {icon}
        </div>
        <h1 className="font-display text-2xl font-bold mb-2">{title}</h1>
        <p className="text-sm text-[#A1A1AA] mb-5">{message}</p>
        <Button asChild className="bg-[#FF3B30] hover:bg-[#FF453A] text-white">
          <Link to="/settings">Back to settings</Link>
        </Button>
      </div>
    </div>
  );
}
