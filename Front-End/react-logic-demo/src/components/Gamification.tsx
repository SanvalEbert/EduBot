/*
G.5 (Plano 2) — Camada de jogo de "Meu Desempenho".

  JourneyHeader      cabeçalho de jornada: avatar + nível com barra de XP,
                     chama da sequência (com escudo) e XP da semana.
  AchievementsShowcase  vitrine: conquistas desbloqueadas coloridas + bloqueadas
                     em silhueta (mostrar o CAMINHO é o que engaja).
  LeaderboardCard    ranking semanal da turma (opt-in com apelido). Quem não
                     participa vê só a própria posição/percentil.

Toda a camada some quando a gamificação está desligada no backend
(`enabled:false`) — a plataforma volta a ser exatamente a atual. Acessível (U.7):
a chama respeita prefers-reduced-motion; posições têm rótulo textual.
*/
import { CheckCircle2, Flame, Lock, LoaderCircle, Medal, Shield, Sparkles, Target, Trophy, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import {
  AchievementState,
  GamificationMe,
  Leaderboard,
  WeeklyGoal,
  acceptGoal,
  getGamificationMe,
  getGoals,
  getLeaderboard,
  participateRanking,
  setActiveTitle
} from "../services/api";
import { EduBotAvatar } from "./brand/EduBotAvatar";
import { useT } from "../i18n";

// Ícone/emoji por conquista (o backend manda só id + nome traduzido).
const ACH_ICON: Record<string, string> = {
  primeiro_modulo: "🎯",
  revisor_pontual: "🗓️",
  sequencia_7: "🔥",
  mestre_competencia: "🧠",
  curioso: "❓",
  trilha_completa: "🏁",
  no_seu_formato: "🎬",
  desafiante: "🏆"
};

export const GamificationSection = ({ studentName }: { studentName?: string }) => {
  const [me, setMe] = useState<GamificationMe | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getGamificationMe()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setLoaded(true));
  }, []);

  if (!loaded) {
    return (
      <div className="flex justify-center py-6">
        <LoaderCircle className="animate-spin text-brand" size={22} />
      </div>
    );
  }
  // gamificação desligada no backend -> nada é renderizado
  if (!me || !me.enabled) return null;

  const reload = () => getGamificationMe().then(setMe).catch(() => {});
  return (
    <div className="space-y-6">
      <JourneyHeader me={me} studentName={studentName} onTitleChange={reload} />
      <div className="grid gap-6 lg:grid-cols-2">
        <AchievementsShowcase achievements={me.achievements} />
        <LeaderboardCard onJoined={reload} />
      </div>
    </div>
  );
};

// E.3 — card de metas semanais (usado no Dashboard). Some se a gamificação
// estiver desligada.
export const WeeklyGoalsCard = () => {
  const t = useT();
  const [goals, setGoals] = useState<WeeklyGoal[] | null>(null);
  const [enabled, setEnabled] = useState(true);

  const load = () =>
    getGoals()
      .then((r) => { setEnabled(r.enabled); setGoals(r.goals); })
      .catch(() => setGoals([]));
  useEffect(() => { load(); }, []);

  const accept = async (id: number) => {
    await acceptGoal(id).catch(() => undefined);
    load();
  };

  if (!enabled || !goals || goals.length === 0) return null;

  return (
    <div className="rounded-[8px] border border-line bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <Target size={20} className="text-brand" />
        <h3 className="text-lg font-bold text-ink">{t("Suas metas da semana", "Your goals this week")}</h3>
      </div>
      <div className="mt-4 space-y-3">
        {goals.map((g) => {
          const pct = g.target > 0 ? Math.round((100 * g.progress) / g.target) : 0;
          const done = g.status === "cumprida";
          return (
            <div key={g.goal_id} className="rounded-[8px] border border-line p-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-semibold text-ink">
                  {done && <CheckCircle2 size={16} className="text-emerald-600" />}
                  {g.titulo}
                </span>
                <span className="text-sm text-muted">{g.progress}/{g.target}</span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                <div className={`h-full rounded-full ${done ? "bg-emerald-500" : "bg-brand"}`} style={{ width: `${pct}%` }} />
              </div>
              {g.status === "sugerida" && (
                <button
                  onClick={() => accept(g.goal_id)}
                  className="mt-2 rounded-[8px] bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-800 transition hover:bg-indigo-100"
                >
                  {t("Aceitar meta", "Accept goal")}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const JourneyHeader = ({ me, onTitleChange }: { me: GamificationMe; studentName?: string; onTitleChange: () => void }) => {
  const t = useT();
  const pct = me.level_span > 0 ? Math.round((100 * me.into_level) / me.level_span) : 100;
  const toNext = Math.max(0, me.next_level_at - me.xp_total);
  const streak = me.streak.current_days;

  return (
    <div className="rounded-[8px] border border-line bg-gradient-to-br from-indigo-50/70 to-white p-6 shadow-soft">
      <style>{`
        @keyframes ebFlicker { 0%,100%{transform:scale(1)} 50%{transform:scale(1.12)} }
        .eb-flame { animation: ebFlicker 1.4s ease-in-out infinite; transform-origin:center; }
        @media (prefers-reduced-motion: reduce) { .eb-flame { animation: none !important; } }
      `}</style>
      <div className="flex flex-wrap items-center gap-5">
        <EduBotAvatar size={72} />
        <div className="min-w-[220px] flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-brand px-3 py-1 text-sm font-bold text-white">
              {t("Nível", "Level")} {me.level}
            </span>
            {me.title && <span className="text-sm font-semibold text-brand">· {me.title}</span>}
            {/* R.2 — escolher o título ativo entre os conquistados. AUDITORIA P2:
                seleção por ID (não por rótulo) — o rótulo muda com o idioma da
                UI e o <select> deixava de casar com o título ativo em EN. */}
            {me.available_titles.length > 0 && (
              <select
                value={me.title_id ?? ""}
                onChange={async (e) => {
                  await setActiveTitle(e.target.value || null);
                  onTitleChange();
                }}
                aria-label={t("Escolher título", "Choose title")}
                className="rounded-full border border-line bg-white px-2 py-1 text-xs font-semibold text-muted"
              >
                <option value="">{t("Sem título", "No title")}</option>
                {me.available_titles.map((tt) => (
                  <option key={tt.id} value={tt.id}>{tt.titulo}</option>
                ))}
              </select>
            )}
          </div>
          <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-slate-200"
               role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
               aria-label={t(`Progresso do nível: ${pct}%`, `Level progress: ${pct}%`)}>
            <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted">
            {me.xp_total} XP · {t(`faltam ${toNext} XP para o nível ${me.level + 1}`,
                                  `${toNext} XP to level ${me.level + 1}`)}
          </p>
        </div>

        {/* sequência */}
        <div className="flex items-center gap-2 rounded-[8px] bg-white px-4 py-3 shadow-sm"
             aria-label={t(`Sequência de ${streak} dias`, `${streak}-day streak`)}>
          <Flame className={`text-orange-500 ${streak > 0 ? "eb-flame" : "opacity-40"}`} size={26} />
          <div className="leading-tight">
            <div className="text-lg font-bold text-ink">{streak}</div>
            <div className="text-[11px] text-muted">{t("dias seguidos", "day streak")}</div>
          </div>
          {me.streak.shield_available && (
            <Shield size={16} className="text-brand" aria-label={t("escudo disponível", "shield available")} />
          )}
        </div>

        {/* XP da semana */}
        <div className="flex items-center gap-2 rounded-[8px] bg-white px-4 py-3 shadow-sm">
          <Zap className="text-amber-500" size={22} />
          <div className="leading-tight">
            <div className="text-lg font-bold text-ink">{me.xp_week}</div>
            <div className="text-[11px] text-muted">{t("XP na semana", "XP this week")}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

const AchievementsShowcase = ({ achievements }: { achievements: AchievementState[] }) => {
  const t = useT();
  const unlocked = achievements.filter((a) => a.unlocked).length;
  return (
    <div className="rounded-[8px] border border-line bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <Trophy size={20} className="text-amber-500" />
        <h2 className="text-xl font-bold text-ink">{t("Conquistas", "Achievements")}</h2>
        <span className="ml-auto text-sm font-semibold text-muted">{unlocked}/{achievements.length}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {achievements.map((a) => (
          <div
            key={a.id}
            title={a.nome}
            className={`flex flex-col items-center gap-1 rounded-[8px] border p-3 text-center ${
              a.unlocked ? "border-amber-200 bg-amber-50" : "border-line bg-slate-50 opacity-70"
            }`}
          >
            <span className={`text-2xl ${a.unlocked ? "" : "grayscale"}`} aria-hidden="true">
              {a.unlocked ? (ACH_ICON[a.id] ?? "⭐") : ""}
            </span>
            {!a.unlocked && <Lock size={18} className="text-slate-400" />}
            <span className="text-[11px] font-semibold leading-tight text-ink">{a.nome}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const LeaderboardCard = ({ onJoined }: { onJoined: () => void }) => {
  const t = useT();
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const [nickname, setNickname] = useState("");
  const [saving, setSaving] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  const load = () => getLeaderboard().then(setBoard).catch(() => setBoard(null));
  useEffect(() => { load(); }, []);

  const join = async () => {
    if (nickname.trim().length < 2) return;
    setSaving(true);
    setJoinError(null);
    try {
      await participateRanking(nickname.trim());
      await load();
      onJoined();
    } catch (err) {
      // 409 = apelido já usado na turma; mostra a mensagem do backend
      try {
        const body = JSON.parse((err as Error).message);
        setJoinError(body?.error ?? t("Não foi possível entrar agora.", "Couldn't join right now."));
      } catch {
        setJoinError(t("Não foi possível entrar agora.", "Couldn't join right now."));
      }
    } finally {
      setSaving(false);
    }
  };

  if (!board || !board.enabled) return null;

  return (
    <div className="rounded-[8px] border border-line bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <Medal size={20} className="text-brand" />
        <h2 className="text-xl font-bold text-ink">{t("Ranking da turma", "Class ranking")}</h2>
        <span className="ml-auto text-xs text-muted">{t("esta semana", "this week")}</span>
      </div>

      {board.me && (
        <p className="mt-2 text-sm text-muted">
          {board.me.rank
            ? t(`Você está em #${board.me.rank}`, `You're #${board.me.rank}`)
            : t("Estude para entrar no ranking", "Study to enter the ranking")}
          {board.me.top_percent != null && ` · ${t("top", "top")} ${board.me.top_percent}%`}
          {` · ${board.me.xp_semana} XP`}
        </p>
      )}

      <div className="mt-4 space-y-2">
        {board.top.map((e, i) => (
          <div
            key={i}
            className={`flex items-center justify-between rounded-[8px] px-3 py-2 ${
              e.eu ? "bg-indigo-50 font-bold" : "bg-slate-50"
            }`}
          >
            <span className="flex items-center gap-2">
              <span className="w-6 text-center text-sm font-bold text-muted">{i + 1}º</span>
              <span className="text-ink">{e.apelido}{e.eu && ` (${t("você", "you")})`}</span>
            </span>
            <span className="text-sm text-muted">{t("Nv", "Lv")} {e.nivel} · {e.xp_semana} XP</span>
          </div>
        ))}
        {board.top.length === 0 && (
          <p className="rounded-[8px] bg-slate-50 p-3 text-sm text-muted">
            {t("Ninguém no ranking ainda. Seja o primeiro!", "No one on the ranking yet. Be the first!")}
          </p>
        )}
      </div>

      {!board.participando && (
        <div className="mt-4 rounded-[8px] border border-brand/30 bg-indigo-50/40 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Sparkles size={16} className="text-brand" /> {t("Participar do ranking", "Join the ranking")}
          </p>
          <p className="mt-1 text-xs text-muted">
            {t("Escolha um apelido. Seus colegas verão o apelido e seu XP — nunca seu nome ou suas notas.",
               "Pick a nickname. Classmates see the nickname and your XP — never your name or grades.")}
          </p>
          <div className="mt-3 flex gap-2">
            <input
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              maxLength={40}
              placeholder={t("Seu apelido", "Your nickname")}
              className="h-10 flex-1 rounded-[8px] border border-line px-3 text-sm outline-none focus:border-brand"
            />
            <button
              onClick={join}
              disabled={saving || nickname.trim().length < 2}
              className="flex h-10 items-center gap-2 rounded-[8px] bg-brand px-4 text-sm font-bold text-white disabled:bg-slate-300"
            >
              {saving && <LoaderCircle className="animate-spin" size={16} />}
              {t("Entrar", "Join")}
            </button>
          </div>
          {joinError && (
            <p role="alert" className="mt-2 text-xs font-semibold text-rose-700">{joinError}</p>
          )}
        </div>
      )}
    </div>
  );
};
