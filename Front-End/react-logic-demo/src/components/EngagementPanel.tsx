/*
E.4 (Plano 2) — Painel de engajamento da turma (tutor).

Mostra a participação no ranking, a distribuição de sequências, o XP médio da
semana, os alunos prestes a perder a sequência (alvo de intervenção de 1 clique)
e a validação ANTES×DEPOIS (dias ativos/aluno em duas janelas de 28 dias) — o
gate honesto: a gamificação mexeu o ponteiro?
*/
import { Activity, AlertCircle, Bot, LoaderCircle, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { TutorEngagement, getTutorEngagement } from "../services/api";
import { useT } from "../i18n";

export const EngagementPanel = () => {
  const t = useT();
  const [data, setData] = useState<TutorEngagement | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getTutorEngagement()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoaded(true));
  }, []);

  if (!loaded) {
    return (
      <div className="flex justify-center py-6"><LoaderCircle className="animate-spin text-brand" size={20} /></div>
    );
  }
  if (!data) return null;

  const { antes_depois: ad } = data;
  const delta = Math.round((ad.dias_ativos_depois - ad.dias_ativos_antes) * 100) / 100;
  const dist = data.distribuicao_sequencia;
  const buckets: [string, string][] = [["0", t("0 dias", "0 days")], ["1-2", "1-2"], ["3-6", "3-6"], ["7+", "7+"]];

  return (
    <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
      <div className="flex items-center gap-2">
        <Activity size={20} className="text-brand" />
        <h2 className="text-xl font-bold text-ink">{t("Engajamento da turma", "Class engagement")}</h2>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div className="rounded-[8px] bg-slate-50 p-4">
          <div className="text-sm text-muted">{t("Participam do ranking", "In the ranking")}</div>
          <div className="mt-1 text-2xl font-bold text-ink">
            {data.participacao_ranking.opt_in}/{data.participacao_ranking.total}
          </div>
        </div>
        <div className="rounded-[8px] bg-slate-50 p-4">
          <div className="text-sm text-muted">{t("XP médio/semana", "Avg XP/week")}</div>
          <div className="mt-1 text-2xl font-bold text-ink">{data.xp_medio_semana}</div>
        </div>
        <div className="rounded-[8px] bg-slate-50 p-4">
          <div className="flex items-center gap-1 text-sm text-muted"><TrendingUp size={14} /> {t("Dias ativos/aluno", "Active days/student")}</div>
          <div className="mt-1 text-2xl font-bold text-ink">
            {ad.dias_ativos_depois}
            <span className={`ml-2 text-sm font-semibold ${delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {delta >= 0 ? "+" : ""}{delta} {t("vs. 4 sem. antes", "vs. 4 wks before")}
            </span>
          </div>
        </div>
      </div>

      {/* distribuição de sequências */}
      <div className="mt-4">
        <p className="mb-2 text-sm font-semibold text-ink">{t("Distribuição de sequências", "Streak distribution")}</p>
        <div className="flex gap-2">
          {buckets.map(([k, label]) => (
            <div key={k} className="flex-1 rounded-[8px] border border-line p-2 text-center">
              <div className="text-lg font-bold text-brand">{dist[k] ?? 0}</div>
              <div className="text-[11px] text-muted">{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* EX.4 — uso do companheiro de estudo (o personagem está ajudando ou sendo ignorado?) */}
      {data.companheiro && (
        <div className="mt-4">
          <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-ink">
            <Bot size={16} className="text-brand" /> {t("Companheiro de estudo", "Study companion")}
          </p>
          <div className="grid gap-2 sm:grid-cols-4">
            <div className="rounded-[8px] border border-line p-3 text-center">
              <div className="text-lg font-bold text-brand">
                {data.companheiro.alunos_ativos}/{data.companheiro.total_alunos}
              </div>
              <div className="text-[11px] text-muted">{t("usaram (28d)", "used it (28d)")}</div>
            </div>
            <div className="rounded-[8px] border border-line p-3 text-center">
              <div className="text-lg font-bold text-brand">{data.companheiro.secoes_ouvidas_semana}</div>
              <div className="text-[11px] text-muted">{t("seções ouvidas/sem.", "sections heard/wk")}</div>
            </div>
            <div className="rounded-[8px] border border-line p-3 text-center">
              <div className="text-lg font-bold text-brand">{data.companheiro.explicacoes_semana}</div>
              <div className="text-[11px] text-muted">{t("explicações/sem.", "explanations/wk")}</div>
            </div>
            <div className="rounded-[8px] border border-line p-3 text-center">
              <div className="text-lg font-bold text-brand">{data.companheiro.falas_ouvidas_semana}</div>
              <div className="text-[11px] text-muted">{t("falas ouvidas/sem.", "lines heard/wk")}</div>
            </div>
          </div>
        </div>
      )}

      {/* alunos prestes a perder a sequência */}
      {data.em_risco.length > 0 && (
        <div className="mt-4 rounded-[8px] border border-amber-200 bg-amber-50 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-amber-800">
            <AlertCircle size={16} /> {t("Prestes a perder a sequência", "About to lose their streak")}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {data.em_risco.map((s) => (
              <span key={s.student_id} className="rounded-[8px] bg-white px-3 py-1 text-sm text-ink">
                {s.nome} · 🔥 {s.sequencia}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
