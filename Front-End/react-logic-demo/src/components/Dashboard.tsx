/*
INTEGRAÇÃO — Dashboard alimentado pelo perfil real (GET /student/me):
nome/curso do aluno, consumo de recursos, taxa de erro do quiz, dias sem
acesso, formato preferido e competências com status do backend.
Layout e identidade visual do protótipo Lovable preservados.
*/
import { Bell, Code2, Timer, Trophy, ClipboardCheck, TrendingUp, Sparkles, Volume2, Square, X, Flame, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";
import { GamificationMe, StudentProfile, UnreadIntervention, getGamificationMe, getInterventions, ackIntervention } from "../services/api";
import { useLanguage, useT } from "../i18n";
import { useSpeech } from "../hooks/useSpeech";
import { CompanionAvatar } from "./brand/CompanionAvatar";
import { REFORCO_COMP_KEY, competencyFromDescription, stripCompetencyMarker } from "../services/reinforcementTarget";
import { WeeklyGoalsCard } from "./Gamification";
import { safeGet, safeSet, safeRemove } from "../services/storage";

// G.6 — chip de gamificação no topo do dashboard: sequência, nível e XP da
// semana. Some quando a gamificação está desligada (enabled:false).
const DashboardStreak = () => {
  const t = useT();
  const [me, setMe] = useState<GamificationMe | null>(null);
  useEffect(() => {
    getGamificationMe().then(setMe).catch(() => setMe(null));
  }, []);
  if (!me || !me.enabled) return null;
  const next = me.achievements.find((a) => !a.unlocked);
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-[8px] border border-line bg-white px-4 py-3 shadow-sm">
      <span className="flex items-center gap-1.5 font-bold text-orange-600">
        <Flame size={20} className={me.streak.current_days > 0 ? "" : "opacity-40"} />
        {me.streak.current_days} <span className="text-xs font-medium text-muted">{t("dias", "days")}</span>
      </span>
      <span className="h-5 w-px bg-line" />
      <span className="flex items-center gap-1.5 font-bold text-brand">
        {t("Nível", "Level")} {me.level}
      </span>
      <span className="h-5 w-px bg-line" />
      <span className="flex items-center gap-1.5 font-bold text-amber-600">
        <Zap size={18} /> {me.xp_week} <span className="text-xs font-medium text-muted">{t("XP/semana", "XP/week")}</span>
      </span>
      {next && (
        <span className="ml-auto text-xs text-muted">
          {t("Próxima conquista:", "Next achievement:")} <strong className="text-ink">{next.nome}</strong>
        </span>
      )}
    </div>
  );
};

interface DashboardProps {
  profile: StudentProfile;
  onOpenContent: () => void;
  onOpenReforco: () => void;
}

// A13 — Caixa de entrada proativa: intervenções que o EduBot criou sozinho
// (pós-quiz, conclusão de OVA, varredura agendada). O aluno vê sem pedir e pode
// agir (gerar trilha de reforço) ou dispensar.
const EduBotInbox = ({ onOpenReforco, persona }: { onOpenReforco: () => void; persona: string }) => {
  const t = useT();
  const { lang } = useLanguage();
  const { speak, stop, speaking, supported } = useSpeech();
  const [items, setItems] = useState<UnreadIntervention[]>([]);
  // V.2: qual intervenção o EduBot está falando (para trocar o botão e mostrar
  // o mini-avatar animado só naquele card).
  const [speakingId, setSpeakingId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    getInterventions()
      .then((r) => active && setItems(r.interventions))
      .catch(() => active && setItems([]));
    return () => {
      active = false;
    };
  }, []);

  // Quando a fala termina (speaking volta a false), limpa o card ativo.
  useEffect(() => {
    if (!speaking) setSpeakingId(null);
  }, [speaking]);

  const dismiss = (id: number) => {
    setItems((cur) => cur.filter((i) => i.intervention_id !== id));
    ackIntervention(id).catch(() => undefined);
  };

  const listen = (item: UnreadIntervention) => {
    if (speakingId === item.intervention_id) {
      stop();
      setSpeakingId(null);
      return;
    }
    setSpeakingId(item.intervention_id);
    void speak(item.descricao || item.tipo, lang, persona);
  };

  if (items.length === 0) return null;

  return (
    <div className="rounded-[8px] border border-brand/30 bg-indigo-50/60 p-6 shadow-soft">
      <h3 className="flex items-center gap-2 text-lg font-bold text-brand">
        <Sparkles size={20} /> {t("O EduBot tem recomendações para você", "EduBot has recommendations for you")}
      </h3>
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <div key={item.intervention_id} className="rounded-[8px] border border-line bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                {/* EX.1: mini-avatar da PERSONA, animado enquanto fala este card */}
                <div className="shrink-0">
                  <CompanionAvatar personaId={persona} size={40} speaking={speakingId === item.intervention_id} />
                </div>
                <div className="min-w-0">
                  <span className="text-xs font-bold uppercase tracking-wide text-muted">{item.tipo}</span>
                  {item.descricao && (
                    // O marcador [comp:N] é interno (roteia o CTA) e não deve
                    // aparecer para o aluno.
                    <p className="mt-1 text-sm text-slate-700">{stripCompetencyMarker(item.descricao)}</p>
                  )}
                </div>
              </div>
              <button
                onClick={() => dismiss(item.intervention_id)}
                className="shrink-0 rounded-[8px] p-1.5 text-muted transition hover:bg-slate-100"
                aria-label={t("Marcar como lida", "Mark as read")}
              >
                <X size={18} />
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => {
                  // Fase 4: quando o convite traz a competência, a trilha nasce
                  // apontada para o assunto que o aluno acabou de errar.
                  const alvo = competencyFromDescription(item.descricao);
                  if (alvo != null) safeSet("session", REFORCO_COMP_KEY, String(alvo));
                  dismiss(item.intervention_id);
                  onOpenReforco();
                }}
                className="h-10 rounded-[8px] bg-brand px-4 text-sm font-semibold text-white transition hover:bg-indigo-600"
              >
                {competencyFromDescription(item.descricao) != null
                  ? t("Praticar esse assunto agora", "Practice this topic now")
                  : t("Gerar minha trilha de reforço", "Generate my reinforcement track")}
              </button>
              {supported && (
                <button
                  onClick={() => listen(item)}
                  className="flex h-10 items-center gap-2 rounded-[8px] border border-brand bg-white px-4 text-sm font-semibold text-brand transition hover:bg-indigo-50"
                  aria-label={speakingId === item.intervention_id
                    ? t("Parar", "Stop") : t("Ouvir o EduBot", "Listen to EduBot")}
                >
                  {speakingId === item.intervention_id ? <Square size={16} /> : <Volume2 size={16} />}
                  {speakingId === item.intervention_id ? t("Parar", "Stop") : t("Ouvir", "Listen")}
                </button>
              )}
              <button
                onClick={() => dismiss(item.intervention_id)}
                className="h-10 rounded-[8px] border border-line bg-white px-4 text-sm font-semibold text-muted transition hover:bg-slate-50"
              >
                {t("Dispensar", "Dismiss")}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const Metric = ({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }) => (
  <div className="rounded-[8px] border border-line bg-white p-5 shadow-sm">
    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-[8px] bg-slate-100 text-brand">
      <Icon size={22} />
    </div>
    <div className="text-2xl font-bold text-ink">{value}</div>
    <div className="mt-1 text-sm text-muted">{label}</div>
  </div>
);

const statusColor: Record<string, string> = {
  "desenvolvida": "bg-teal",
  "em desenvolvimento": "bg-coral",
  "não iniciada": "bg-slate-300"
};

export const Dashboard = ({ profile, onOpenContent, onOpenReforco }: DashboardProps) => {
  const t = useT();
  const progresso = profile.recursos.percentual_consumido;
  const radialData = [{ name: "progresso", value: progresso, fill: "#604fd8" }];
  const totalReadMinutes = Math.round(profile.ovas.reduce((sum, ova) => sum + (ova.read_time || 0), 0) / 60);
  const quizScore =
    profile.quiz.taxa_erro != null ? `${Math.round((1 - profile.quiz.taxa_erro) * 100)}%` : "—";
  const allResources = profile.ovas.flatMap((ova) => ova.recursos);
  const completedActivities = allResources.filter((r) => r.tipo === "atividade" && r.concluido).length;
  const totalActivities = allResources.filter((r) => r.tipo === "atividade").length;
  // U.5: conta zerada (nada consumido, sem leitura) → estado vazio acolhedor.
  const isFresh = profile.recursos.consumidos === 0 && totalReadMinutes === 0;

  return (
    <section className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-lg text-muted">{t("Dashboard do Aluno", "Student Dashboard")}</p>
          <h1 className="mt-1 text-4xl font-bold text-ink">{profile.estudante.nome}</h1>
        </div>
        {/* G.6 — sequência/nível/XP (some se a gamificação estiver desligada) */}
        <DashboardStreak />
      </div>

      {/* U.5 — primeiro acesso: chama para abrir o primeiro módulo */}
      {isFresh && (
        <div className="flex flex-col items-start gap-4 rounded-[8px] border border-brand/30 bg-gradient-to-br from-indigo-50 to-white p-6 shadow-soft sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-bold text-brand">
              <Sparkles size={20} /> {t("Bem-vindo(a) ao EduBot!", "Welcome to EduBot!")}
            </h3>
            <p className="mt-1 text-sm text-slate-700">
              {t("Comece pelo seu primeiro módulo — eu te acompanho a cada passo.",
                 "Start with your first module — I'll guide you every step of the way.")}
            </p>
          </div>
          <button
            onClick={onOpenContent}
            className="h-11 shrink-0 rounded-[8px] bg-brand px-5 font-bold text-white transition hover:bg-indigo-600"
          >
            {t("Abrir meu primeiro módulo", "Open my first module")}
          </button>
        </div>
      )}

      {/* A13 — o EduBot "fala primeiro": recomendações não lidas, com ação */}
      <EduBotInbox onOpenReforco={onOpenReforco} persona={profile.estudante.persona} />

      {/* E.3 — metas semanais sugeridas pelo EduBot (some se gamificação off) */}
      <WeeklyGoalsCard />

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="overflow-hidden rounded-[8px] border border-line bg-white shadow-soft">
          <div className="relative min-h-[245px] bg-gradient-to-br from-indigo-700 via-brand to-violet-500 p-8 text-white">
            <div className="absolute -left-12 top-20 h-52 w-52 rounded-full border-[7px] border-white/10" />
            <div className="absolute right-10 top-[-45px] h-48 w-48 rounded-full border-[7px] border-white/10" />
            <Code2 className="relative z-10 mb-8" size={62} />
            <div className="relative z-10 max-w-lg">
              <p className="font-semibold opacity-90">{t("RA", "ID")} {profile.estudante.ra}</p>
              <h2 className="mt-2 text-3xl font-bold">{profile.estudante.curso ?? t("Meu curso", "My course")}</h2>
              <p className="mt-3 text-lg text-white/85">
                {profile.dias_sem_acesso != null && profile.dias_sem_acesso > 0
                  ? t(
                      `Você está há ${profile.dias_sem_acesso} dia(s) sem interagir — que tal retomar hoje?`,
                      `You've been away for ${profile.dias_sem_acesso} day(s) — how about picking it back up today?`
                    )
                  : t("Sua jornada de aprendizagem rastreada pelo EduBot.", "Your learning journey, tracked by EduBot.")}
              </p>
            </div>
          </div>
          <div className="grid gap-4 p-6 md:grid-cols-4">
            <Metric label={t("Tempo de leitura", "Reading time")} value={`${totalReadMinutes} min`} icon={Timer} />
            <Metric label={t("Atividades práticas", "Practical activities")} value={`${completedActivities}/${totalActivities}`} icon={ClipboardCheck} />
            <Metric label={t("Acerto nos quizzes", "Quiz accuracy")} value={quizScore} icon={Trophy} />
            <Metric label={t("Recursos consumidos", "Resources consumed")} value={`${progresso}%`} icon={TrendingUp} />
          </div>
        </div>

        <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold text-ink">{t("Progresso", "Progress")}</h3>
              <p className="text-sm text-muted">
                {t(
                  `${profile.recursos.consumidos} de ${profile.recursos.total} recursos consumidos.`,
                  `${profile.recursos.consumidos} of ${profile.recursos.total} resources consumed.`
                )}
              </p>
            </div>
          </div>
          <div className="relative mt-4 h-56">
            <ResponsiveContainer>
              <RadialBarChart innerRadius="68%" outerRadius="95%" data={radialData} startAngle={90} endAngle={-270}>
                {/* Fixa a escala em 0–100 para o arco ser proporcional à % real
                    (sem isso o Recharts usa o próprio valor como máximo e enche
                    a volta toda mesmo com 20%). */}
                <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
                <RadialBar dataKey="value" angleAxisId={0} cornerRadius={8} background />
              </RadialBarChart>
            </ResponsiveContainer>
            {/* Sobreposição centralizada no donut (centro exato, nos dois eixos) */}
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-4xl font-bold leading-none text-ink">{progresso}%</span>
              <span className="mt-1 text-sm text-muted">{t("concluído", "completed")}</span>
            </div>
          </div>
          <button onClick={onOpenContent} className="mt-6 h-11 w-full rounded-[8px] bg-ink font-semibold text-white">
            {t("Continuar estudando", "Keep studying")}
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="rounded-[8px] border border-line bg-white p-6">
          <h3 className="text-xl font-bold text-ink">{t("Competências desenvolvidas", "Developed competencies")}</h3>
          <div className="mt-5 space-y-4">
            {profile.competencias.map((item) => {
              const score = item.total_questoes ? Math.round((100 * item.acertos) / item.total_questoes) : 0;
              return (
                <div key={item.competency_id}>
                  <div className="mb-2 flex justify-between gap-3 text-sm">
                    <span className="font-semibold text-ink">{item.nome}</span>
                    <span className="shrink-0 text-muted">{item.status}</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100">
                    <div
                      className={`h-2 rounded-full ${statusColor[item.status] ?? "bg-teal"}`}
                      style={{ width: `${Math.max(score, item.status === "não iniciada" ? 0 : 6)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-[8px] border border-line bg-white p-6">
          <h3 className="flex items-center gap-2 text-xl font-bold text-ink">
            <Bell size={20} className="text-brand" /> {t("Avisos do EduBot", "EduBot notices")}
          </h3>
          <div className="mt-4 space-y-3">
            {profile.historico_intervencoes.slice(0, 5).map((item, index) => (
              <div key={`${item.data}-${index}`} className="rounded-[8px] bg-slate-50 p-4">
                <div className="flex items-center justify-between text-xs text-muted">
                  <span className="font-bold uppercase tracking-wide">{item.tipo}</span>
                  <span>{item.data}</span>
                </div>
                {item.descricao && <p className="mt-2 text-sm text-slate-700">{item.descricao}</p>}
              </div>
            ))}
            {profile.historico_intervencoes.length === 0 && (
              <p className="rounded-[8px] bg-slate-50 p-4 text-sm text-muted">
                {t(
                  "Sem avisos por enquanto. Continue estudando e responda aos quizzes — o EduBot vai sugerir os próximos passos por aqui.",
                  "No notices yet. Keep studying and answer the quizzes — EduBot will suggest next steps here."
                )}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {profile.ovas.map((ova) => (
          <div key={ova.ova_id} className="rounded-[8px] border border-line bg-white p-5">
            <div className="text-sm font-semibold text-brand">{ova.completed ? t("Concluído", "Completed") : t("Em andamento", "In progress")}</div>
            <div className="mt-2 font-bold text-ink">{ova.ova_name}</div>
            <div className="mt-2 text-sm text-muted">
              {ova.perc_scrolled || 0}% {t("lido", "read")} · {ova.recursos.filter((r) => r.consumido).length}/{ova.recursos.length} {t("recursos", "resources")}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
