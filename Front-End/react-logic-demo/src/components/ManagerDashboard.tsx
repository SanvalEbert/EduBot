/*
Plano 5 (20.3) — Painel do GESTOR: "tudo que o sistema consegue medir" da turma.

Consolida numa só tela, com números reais agregados:
  - KPIs da turma (alunos ativos, em risco, alertas, consumo, acertos/erros);
  - acertos × erros POR ASSUNTO (gráfico + números brutos), do /tutor/overview;
  - domínio da turma (heatmap BKT) e engajamento — reuso dos painéis existentes;
  - um CATÁLOGO do que é rastreado hoje (com a contagem real de registros) e do
    que ainda NÃO é rastreado — transparência para os gerentes do projeto.

A11y: cada bloco é uma região com heading; os números aparecem sempre em texto
(não só dentro do gráfico); nada depende só de cor.
*/
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";
import {
  AlertTriangle, Bell, CheckCircle2, Database, Gauge, LoaderCircle, Users, XCircle
} from "lucide-react";
import { useEffect, useState } from "react";
import { TutorOverview, getTutorOverview } from "../services/api";
import { useT } from "../i18n";
import { MasteryHeatmap } from "./MasteryHeatmap";
import { EngagementPanel } from "./EngagementPanel";

// Catálogo: chave vinda do backend (rastreamento) -> rótulo amigável. Tudo aqui
// PERSISTE no banco (é justamente o que o sistema já grava).
const CATALOGO: { key: string; pt: string; en: string }[] = [
  { key: "interacoes", pt: "Interações (scroll, clique, vídeo)", en: "Interactions (scroll, click, video)" },
  { key: "ova_progress", pt: "Progresso por OVA (tempo e % de leitura)", en: "OVA progress (time and % read)" },
  { key: "progresso_recursos", pt: "Consumo de recursos (vídeo/podcast/atividade)", en: "Resource consumption (video/podcast/activity)" },
  { key: "tentativas_quiz", pt: "Tentativas de quiz (certas e erradas)", en: "Quiz attempts (right and wrong)" },
  { key: "eventos_aprendizado", pt: "Eventos de aprendizado (login, tutor, mídia)", en: "Learning events (login, tutor, media)" },
  { key: "linhas_mastery", pt: "Domínio estimado por competência (BKT)", en: "Estimated mastery per competency (BKT)" },
  // Fase 2 do Plano de Rastreabilidade — leitura por seção do OVA.
  { key: "leitura_por_secao", pt: "Leitura por seção do OVA (onde o aluno travou)", en: "Reading per OVA section (where the student got stuck)" },
  { key: "consentimentos", pt: "Consentimentos LGPD", en: "GDPR/LGPD consents" }
];

// O que ainda NÃO é rastreado (honestidade com o gestor).
// "% de vídeo efetivamente assistido" SAIU desta lista na Fase 1: passou a ser
// medido de verdade (tempo assistido + cobertura da linha do tempo).
const NAO_RASTREADO: { pt: string; en: string }[] = [
  { pt: "Submissão e correção de atividades práticas", en: "Practical activity submission and grading" }
];

interface KpiProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  alerta?: boolean;
}
const Kpi = ({ icon, label, value, alerta }: KpiProps) => (
  <div className="rounded-[8px] border border-line bg-white p-5 shadow-soft">
    <div className="flex items-center gap-2 text-muted">{icon} {label}</div>
    <div className={`mt-2 text-3xl font-bold ${alerta ? "text-rose-600" : "text-ink"}`}>{value}</div>
  </div>
);

export const ManagerDashboard = () => {
  const t = useT();
  const [data, setData] = useState<TutorOverview | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getTutorOverview().then(setData).catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <div className="rounded-[8px] border border-rose-200 bg-rose-50 p-6 text-rose-800" role="alert">
        {t("Não foi possível carregar a visão do gestor.", "Couldn't load the manager view.")}
      </div>
    );
  }
  if (!data) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="animate-spin text-brand" size={32} aria-hidden="true" />
        <span className="sr-only" role="status">{t("Carregando", "Loading")}</span>
      </div>
    );
  }

  const kLabel = t("acertos", "correct");
  const eLabel = t("erros", "wrong");
  const assuntoChart = data.por_assunto.map((s) => ({
    nome: s.subject_nome.length > 16 ? `${s.subject_nome.slice(0, 16)}…` : s.subject_nome,
    [kLabel]: s.acertos,
    [eLabel]: s.erros
  }));
  const aproveitamento = data.quiz.tentativas
    ? Math.round((100 * data.quiz.acertos) / (data.quiz.acertos + data.quiz.erros))
    : null;

  return (
    <section className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-3xl font-bold text-ink">
          <Database className="text-brand" aria-hidden="true" /> {t("Visão do Gestor", "Manager View")}
        </h1>
        <p className="mt-2 text-muted">
          {t("Tudo que o sistema consegue medir da turma, com números reais.", "Everything the system can measure from the class, with real numbers.")}
        </p>
      </div>

      {/* KPIs da turma */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi icon={<Users size={18} />} label={t("Alunos ativos", "Active students")} value={String(data.turma.alunos_ativos)} />
        <Kpi icon={<AlertTriangle size={18} />} label={t("Em risco", "At risk")} value={String(data.turma.em_risco)} alerta={data.turma.em_risco > 0} />
        <Kpi icon={<Bell size={18} />} label={t("Alertas abertos", "Open alerts")} value={String(data.turma.alertas_abertos)} alerta={data.turma.alertas_abertos > 0} />
        <Kpi icon={<Gauge size={18} />} label={t("Consumo médio", "Average consumption")} value={`${data.consumo.percentual_medio}%`} />
      </div>

      {/* Acertos x erros totais da turma (número cru) */}
      <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
        <h2 className="text-xl font-bold text-ink">{t("Quiz da turma", "Class quiz")}</h2>
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-[8px] border border-line bg-slate-50 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={22} className="text-emerald-600" aria-hidden="true" />
            <span className="text-2xl font-bold text-emerald-700">{data.quiz.acertos}</span>
            <span className="text-sm text-muted">{t("acertos", "correct")}</span>
          </div>
          <span className="text-slate-300" aria-hidden="true">|</span>
          <div className="flex items-center gap-2">
            <XCircle size={22} className="text-rose-600" aria-hidden="true" />
            <span className="text-2xl font-bold text-rose-700">{data.quiz.erros}</span>
            <span className="text-sm text-muted">{t("erros", "wrong")}</span>
          </div>
          {aproveitamento !== null && (
            <>
              <span className="text-slate-300" aria-hidden="true">|</span>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-brand">{aproveitamento}%</span>
                <span className="text-sm text-muted">{t("de aproveitamento", "success rate")}</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Acertos x erros POR ASSUNTO — gráfico + números brutos */}
      <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
        <h2 className="text-xl font-bold text-ink">{t("Acertos e erros por assunto (turma)", "Correct and wrong answers per subject (class)")}</h2>
        {data.por_assunto.length === 0 ? (
          <p className="mt-4 rounded-[8px] bg-slate-50 p-4 text-sm text-muted">
            {t("Ainda não há respostas registradas nesta turma.", "No answers recorded in this class yet.")}
          </p>
        ) : (
          <>
            <div className="mt-5 h-72">
              <ResponsiveContainer>
                <BarChart data={assuntoChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="nome" interval={0} tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey={kLabel} fill="#15beb5" radius={[8, 8, 0, 0]} />
                  <Bar dataKey={eLabel} fill="#f43f5e" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            {/* Números brutos (o gráfico é o resumo; aqui vem a tabela exata) */}
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-muted">
                  <tr>
                    <th className="py-2 pr-4 font-semibold">{t("Assunto", "Subject")}</th>
                    <th className="py-2 pr-4 font-semibold">{t("Acertos", "Correct")}</th>
                    <th className="py-2 pr-4 font-semibold">{t("Erros", "Wrong")}</th>
                    <th className="py-2 pr-4 font-semibold">{t("Aproveitamento", "Success rate")}</th>
                    <th className="py-2 pr-4 font-semibold">{t("Domínio médio", "Avg. mastery")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.por_assunto.map((s) => {
                    const resp = s.acertos + s.erros;
                    const perc = resp ? Math.round((100 * s.acertos) / resp) : null;
                    return (
                      <tr key={s.subject_id} className="border-t border-line">
                        <td className="py-2 pr-4 font-semibold text-ink">{s.subject_nome}</td>
                        <td className="py-2 pr-4 text-emerald-700">{s.acertos}</td>
                        <td className="py-2 pr-4 text-rose-700">{s.erros}</td>
                        <td className="py-2 pr-4 font-semibold text-brand">{perc != null ? `${perc}%` : "—"}</td>
                        <td className="py-2 pr-4">{s.dominio_medio != null ? `${Math.round(s.dominio_medio * 100)}%` : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* Reuso: domínio da turma (heatmap BKT) + engajamento */}
      <MasteryHeatmap />
      <EngagementPanel />

      {/* Fase 1 — consumo REAL de vídeo. A métrica anterior era a posição
          máxima do player: um seek para o fim marcava 100% sem assistir nada. */}
      {data.video && data.video.segundos_assistidos > 0 && (
        <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
          <h2 className="text-xl font-bold text-ink">{t("Vídeo — consumo real", "Video — real consumption")}</h2>
          <p className="mt-1 text-sm text-muted">
            {t("Cobertura é o trecho do vídeo efetivamente percorrido (pular à frente não conta).",
               "Coverage is the portion of the video actually played through (skipping ahead doesn't count).")}
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div>
              <div className="text-2xl font-bold text-ink">{data.video.cobertura_media}%</div>
              <div className="text-sm text-muted">{t("cobertura média", "average coverage")}</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-ink">
                {Math.round(data.video.segundos_assistidos / 60)} min
              </div>
              <div className="text-sm text-muted">{t("assistidos pela turma", "watched by the class")}</div>
            </div>
            {data.video.ponto_abandono_medio != null && (
              <div>
                <div className="text-2xl font-bold text-ink">
                  {Math.floor(data.video.ponto_abandono_medio / 60)}m
                  {String(data.video.ponto_abandono_medio % 60).padStart(2, "0")}s
                </div>
                <div className="text-sm text-muted">{t("ponto médio de abandono", "average drop-off point")}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fase 2 — onde a turma trava. Só aparece quando já há leitura por seção. */}
      {data.secoes_dificeis && data.secoes_dificeis.length > 0 && (
        <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
          <h2 className="text-xl font-bold text-ink">{t("Onde a turma trava", "Where the class gets stuck")}</h2>
          <p className="mt-1 text-sm text-muted">
            {t("Seções com maior tempo de leitura e mais releituras — candidatas a revisão do conteúdo.",
               "Sections with the longest reading time and most re-reads — candidates for content revision.")}
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-muted">
                <tr>
                  <th className="px-4 py-2 font-semibold">{t("Seção", "Section")}</th>
                  <th className="px-3 py-2 font-semibold">{t("OVA", "OVA")}</th>
                  <th className="px-3 py-2 font-semibold">{t("Alunos", "Students")}</th>
                  <th className="px-3 py-2 font-semibold">{t("Tempo médio", "Avg. time")}</th>
                  <th className="px-3 py-2 font-semibold">{t("Releituras", "Re-reads")}</th>
                </tr>
              </thead>
              <tbody>
                {data.secoes_dificeis.map((s) => (
                  <tr key={`${s.ova_id}-${s.section_id}`} className="border-t border-line">
                    <td className="px-4 py-2 font-semibold text-ink">{s.section_id}</td>
                    <td className="px-3 py-2 text-muted">{s.ova_nome}</td>
                    <td className="px-3 py-2">{s.alunos}</td>
                    <td className="px-3 py-2">
                      {Math.floor(s.segundos_medios / 60)}m{String(s.segundos_medios % 60).padStart(2, "0")}s
                    </td>
                    <td className="px-3 py-2">
                      <span className={s.releituras_por_aluno > 1 ? "font-bold text-amber-700" : "text-slate-700"}>
                        {s.releituras_por_aluno}×
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Fase 4 (§6.2) — lacunas de conteúdo: competências que o reforço não
          consegue atender. É informação acionável para o GESTOR (trabalho
          editorial), não um erro de software. */}
      {data.lacunas_conteudo && data.lacunas_conteudo.length > 0 && (
        <div className="rounded-[8px] border border-amber-200 bg-amber-50 p-6 shadow-soft">
          <h2 className="flex items-center gap-2 text-xl font-bold text-ink">
            <XCircle size={20} className="text-amber-600" aria-hidden="true" />
            {t("Lacunas de conteúdo para o reforço", "Content gaps for reinforcement")}
          </h2>
          <p className="mt-1 text-sm text-amber-900">
            {t("Estas competências não têm material suficiente para o EduBot montar um reforço eficaz: são necessárias ao menos 3 questões e 2 formatos de material.",
               "These competencies lack enough material for EduBot to build effective reinforcement: at least 3 questions and 2 material formats are required.")}
          </p>
          <ul className="mt-4 space-y-2">
            {data.lacunas_conteudo.map((c) => (
              <li key={c.competency_id} className="rounded-[8px] border border-amber-200 bg-white p-3 text-sm">
                <span className="font-semibold text-ink">{c.nome}</span>
                <span className="text-muted"> · {c.assunto}</span>
                <div className="mt-1 text-muted">
                  {c.questoes} {c.questoes === 1 ? t("questão", "question") : t("questões", "questions")}
                  {" · "}
                  {c.formatos.length > 0
                    ? `${t("formatos", "formats")}: ${c.formatos.join(", ")}`
                    : t("nenhum material de reforço", "no reinforcement material")}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Catálogo de rastreamento — transparência com o gestor */}
      <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
        <h2 className="text-xl font-bold text-ink">{t("O que o sistema rastreia", "What the system tracks")}</h2>
        <p className="mt-1 text-sm text-muted">
          {t("Cada sinal com a contagem real de registros da turma. Tudo abaixo persiste no banco.",
             "Each signal with the real record count for the class. Everything below persists in the database.")}
        </p>
        <ul className="mt-4 divide-y divide-line">
          {CATALOGO.map((c) => (
            <li key={c.key} className="flex items-center justify-between gap-3 py-3">
              <span className="flex items-center gap-2 text-sm text-ink">
                <CheckCircle2 size={16} className="text-emerald-600" aria-hidden="true" />
                {t(c.pt, c.en)}
              </span>
              <span className="shrink-0 text-sm">
                <strong className="text-ink">{(data.rastreamento[c.key] ?? 0).toLocaleString("pt-BR")}</strong>{" "}
                <span className="text-muted">{t("registros", "records")}</span>
              </span>
            </li>
          ))}
        </ul>

        <h3 className="mt-6 text-sm font-bold uppercase tracking-wide text-slate-400">
          {t("Ainda não rastreado", "Not tracked yet")}
        </h3>
        <ul className="mt-2 space-y-2">
          {NAO_RASTREADO.map((c) => (
            <li key={c.pt} className="flex items-center gap-2 text-sm text-muted">
              <XCircle size={16} className="text-slate-400" aria-hidden="true" />
              {t(c.pt, c.en)}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
};
