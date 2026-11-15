import { Anchor, Factory, ShieldCheck, Ship } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router";
import { HOME, useLogin, useMe } from "../auth";
import { Button, ErrorNotice, Field, inputClass } from "../components/ui";

const DEMO_PASSWORD = "demo1234";
const DEMO_ACCOUNTS = [
  { email: "armateur@careneo.demo", role: "Armateur", company: "Armement Hermine", icon: Ship },
  { email: "chantier@careneo.demo", role: "Chantier naval", company: "Provence Réparation Navale", icon: Factory },
  { email: "admin@careneo.demo", role: "Administrateur", company: "Plateforme Carénéo", icon: ShieldCheck },
];

export function LoginPage() {
  const me = useMe();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  if (me.data) return <Navigate to={HOME[me.data.role]} replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ email, password });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-900 via-brand-700 to-brand-500 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center text-white">
          <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/20">
            <Anchor className="size-6 text-sea-400" aria-hidden />
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight">Carénéo</h1>
          <p className="mt-1 text-brand-100">Réservez un créneau de carénage en quelques clics.</p>
        </div>

        <div className="rounded-2xl bg-white p-6 shadow-xl">
          <form onSubmit={submit} className="space-y-4">
            <Field label="Email">
              <input className={inputClass} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Field>
            <Field label="Mot de passe">
              <input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </Field>
            <ErrorNotice error={login.error} />
            <Button type="submit" className="w-full" loading={login.isPending}>
              Se connecter
            </Button>
          </form>

          <div className="mt-6 border-t border-slate-100 pt-5">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Comptes de démonstration</p>
            <div className="mt-3 grid gap-2">
              {DEMO_ACCOUNTS.map(({ email: demoEmail, role, company, icon: Icon }) => (
                <button
                  key={demoEmail}
                  type="button"
                  disabled={login.isPending}
                  onClick={() => login.mutate({ email: demoEmail, password: DEMO_PASSWORD })}
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left ring-1 ring-slate-200 transition hover:bg-brand-50 hover:ring-brand-500 disabled:opacity-60"
                >
                  <Icon className="size-5 text-brand-600" aria-hidden />
                  <span className="text-sm">
                    <span className="block font-medium text-slate-900">{role}</span>
                    <span className="block text-slate-500">{company}</span>
                  </span>
                </button>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-500">Mot de passe de tous les comptes : {DEMO_PASSWORD}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
