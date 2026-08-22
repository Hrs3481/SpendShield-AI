import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/api";

export default function Login() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<"form" | "demo" | null>(null);
  const { login, register, startDemo } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!email || !password) {
      setError("Enter an email and password.");
      return;
    }
    if (mode === "register" && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError(null);
    setLoading("form");
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, fullName);
      navigate("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setLoading(null);
    }
  }

  async function handleDemo() {
    setError(null);
    setLoading("demo");
    try {
      await startDemo();
      navigate("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't start the demo. Try again.");
    } finally {
      setLoading(null);
    }
  }

  const inputClass =
    "w-full bg-ink-800 rounded-lg px-3 py-2.5 text-sm text-paper outline-none border " +
    "border-ink-700 focus:border-marigold-500 placeholder:text-paper/30";

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-2xl font-semibold text-paper mb-1">SpendShield AI</h1>
        <p className="text-paper/50 text-sm mb-8">Know before you spend.</p>

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === "register" && (
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Full name"
              autoComplete="name"
              className={inputClass}
            />
          )}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            autoComplete="email"
            className={inputClass}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={mode === "register" ? "Password (min 8 characters)" : "Password"}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className={inputClass}
          />

          {error && (
            <p role="alert" className="text-sindoor-500 text-sm">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading !== null}
            className="w-full bg-marigold-500 hover:bg-marigold-600 disabled:opacity-50 text-ink-950 font-medium text-sm rounded-lg py-2.5"
          >
            {loading === "form" ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>

        <div className="flex items-center gap-3 my-4">
          <div className="h-px bg-ink-700 flex-1" />
          <span className="text-paper/30 text-xs">or</span>
          <div className="h-px bg-ink-700 flex-1" />
        </div>

        {/* The fastest way to see the product working: a throwaway account
            pre-loaded with two months of realistic spending. */}
        <button
          onClick={handleDemo}
          disabled={loading !== null}
          className="w-full border border-marigold-500/40 text-marigold-400 hover:bg-marigold-500/10 disabled:opacity-50 font-medium text-sm rounded-lg py-2.5"
        >
          {loading === "demo" ? "Building your demo…" : "Explore with demo data"}
        </button>
        <p className="text-paper/30 text-xs mt-2 text-center">
          Creates a temporary account with synthetic transactions. No signup needed.
        </p>

        <button
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
          className="text-paper/50 text-sm mt-6 hover:text-paper w-full text-center"
        >
          {mode === "login" ? "Need an account? Register" : "Have an account? Log in"}
        </button>
      </div>
    </div>
  );
}
