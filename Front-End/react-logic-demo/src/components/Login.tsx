/*
INTEGRAÇÃO (4.2) — Tela de login do frontend React.
Autentica RA + senha no POST /login do backend; o token devolvido é guardado
pelo api.ts e enviado em todas as chamadas seguintes.
*/
import { LoaderCircle } from "lucide-react";
import { FormEvent, useState } from "react";
import { ApiError, Session, login } from "../services/api";
import { track } from "../services/events";
import { useT } from "../i18n";
import { EduBotLogo } from "./brand/EduBotLogo";

interface LoginProps {
  onLogged: (session: Session) => void;
}

export const Login = ({ onLogged }: LoginProps) => {
  const t = useT();
  const [ra, setRa] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const session = await login(ra, password);
      // D.1: evento de sessão iniciada (o token já foi armazenado por login()).
      track("logged_in", "session", session.student_id);
      onLogged(session);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? t("RA ou senha incorretos.", "Wrong ID or password.")
          : t("Não foi possível entrar — verifique se a API está no ar.", "Couldn't sign in — check if the API is up.")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-700 via-brand to-violet-500 p-4">
      <div className="w-full max-w-md rounded-[8px] bg-white p-8 shadow-soft">
        <div className="mb-8 flex items-center gap-3">
          <EduBotLogo size={52} />
          <div>
            <div className="text-2xl font-bold leading-none text-ink">Adapta</div>
            <div className="mt-1 text-sm tracking-[0.18em] text-muted">LEARN · IA</div>
          </div>
        </div>

        <h1 className="text-2xl font-bold text-ink">{t("Entrar na plataforma", "Sign in to the platform")}</h1>
        <p className="mt-1 text-muted">{t("Use seu RA e senha institucionais.", "Use your institutional ID and password.")}</p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="ra" className="mb-1 block text-sm font-semibold text-ink">{t("RA", "ID")}</label>
            <input
              id="ra"
              value={ra}
              onChange={(event) => setRa(event.target.value)}
              className="h-12 w-full rounded-[8px] border border-line px-4 outline-none focus:border-brand"
              placeholder={t("Ex.: 1", "e.g. 1")}
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-semibold text-ink">{t("Senha", "Password")}</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-12 w-full rounded-[8px] border border-line px-4 outline-none focus:border-brand"
              placeholder="••••••"
            />
          </div>
          {error && <p role="alert" className="rounded-[8px] bg-rose-50 p-3 text-sm font-semibold text-rose-700">{error}</p>}
          <button
            type="submit"
            disabled={loading || !ra || !password}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-[8px] bg-brand font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {loading && <LoaderCircle className="animate-spin" size={20} />}
            {t("Entrar", "Sign in")}
          </button>
        </form>
      </div>
    </div>
  );
};
