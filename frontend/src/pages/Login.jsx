import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogIn, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Auth, session } from "../lib/api";

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const isRegister = mode === "register";

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const payload = { email: email.trim(), password };
      const res = isRegister
        ? await Auth.register({ ...payload, name: name.trim() })
        : await Auth.login(payload);
      session.setToken(res.token);
      toast.success(isRegister ? "Account created" : "Signed in");
      navigate("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto es-fade">
      <div className="es-card p-6">
        <div className="flex items-center justify-between gap-3 mb-6">
          <div>
            <p className="es-label mb-2">Private beta</p>
            <h1 className="font-display text-2xl font-bold">
              {isRegister ? "Create account" : "Sign in"}
            </h1>
          </div>
          <div className="w-10 h-10 rounded-md bg-[#FF3B30] flex items-center justify-center">
            {isRegister ? <UserPlus className="w-5 h-5" /> : <LogIn className="w-5 h-5" />}
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {isRegister && (
            <div>
              <label className="es-label block mb-2">Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="bg-[#0A0A0A] border-white/10 text-white"
                required
              />
            </div>
          )}
          <div>
            <label className="es-label block mb-2">Email</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-[#0A0A0A] border-white/10 text-white"
              required
            />
          </div>
          <div>
            <label className="es-label block mb-2">Password</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-[#0A0A0A] border-white/10 text-white"
              minLength={8}
              required
            />
          </div>
          <Button
            type="submit"
            disabled={busy}
            className="w-full bg-[#FF3B30] hover:bg-[#FF453A] text-white"
          >
            {busy ? "Working..." : isRegister ? "Create account" : "Sign in"}
          </Button>
        </form>

        <button
          type="button"
          onClick={() => setMode(isRegister ? "login" : "register")}
          className="mt-4 text-sm text-[#A1A1AA] hover:text-white"
        >
          {isRegister ? "Already have an account? Sign in" : "Need beta access? Create an account"}
        </button>
      </div>
    </div>
  );
}
