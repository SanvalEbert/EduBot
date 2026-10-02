/*
Plano 5 (18.2) — PLACAR de acertos x erros por ASSUNTO (disciplina).

O `CompetencyScores` mostra o detalhe por competência; aqui vem a visão macro:
cada assunto (Computação Quântica, Cálculo...) agrega as suas competências, então
o aluno/professor vê rapidamente "em qual matéria eu vou bem e em qual vou mal".

Semântica (somada a partir de `competencias`, ver CompetencyScores para a origem):
  - acertos/erros/tentativas por assunto = SOMA dos das competências do assunto;
  - vale `acertos + erros === tentativas` (mesma invariante da competência), então
    a barra proporcional fecha 100% e o aproveitamento é honesto;
  - `total_questoes` do assunto = soma das questões das competências (cobertura).

Reuso: usado tanto em "Meu Desempenho" (aluno) quanto no detalhe do aluno visto
pelo professor (TutorStudentDetail).

A11y (padrão do Plano 4): nada depende só de cor (número + ícone ✓/✗ + palavra);
barra é decorativa (`aria-hidden`); textos ≥ 12px.

Degradação: se nenhuma competência trouxer `subject_nome` (backend antigo), o
componente não renderiza (retorna null) — a tela segue idêntica ao que era.
*/
import { CheckCircle2, Layers, XCircle } from "lucide-react";
import { CompetencyState } from "../services/api";
import { useT } from "../i18n";

interface SubjectAgg {
  subject_id: number;
  nome: string;
  acertos: number;
  erros: number;
  total_questoes: number;
  n_competencias: number;
  dominios: number[]; // domínios estimados das competências (para a média)
}

const agrupaPorAssunto = (competencias: CompetencyState[]): SubjectAgg[] => {
  const mapa = new Map<number, SubjectAgg>();
  for (const c of competencias) {
    if (c.subject_id == null || !c.subject_nome) continue;
    const atual = mapa.get(c.subject_id) ?? {
      subject_id: c.subject_id,
      nome: c.subject_nome,
      acertos: 0,
      erros: 0,
      total_questoes: 0,
      n_competencias: 0,
      dominios: []
    };
    atual.acertos += c.acertos || 0;
    atual.erros += c.erros || 0;
    atual.total_questoes += c.total_questoes || 0;
    atual.n_competencias += 1;
    if (c.dominio_estimado != null) atual.dominios.push(c.dominio_estimado);
    mapa.set(c.subject_id, atual);
  }
  return [...mapa.values()].sort((a, b) => a.subject_id - b.subject_id);
};

interface SubjectScoresProps {
  competencias: CompetencyState[];
  // "self" = o próprio aluno vê ("Você..."); "other" = o professor vê outro
  // aluno ("O aluno..."). Muda só a voz dos textos, não os números.
  perspective?: "self" | "other";
}

export const SubjectScores = ({ competencias, perspective = "self" }: SubjectScoresProps) => {
  const t = useT();
  const assuntos = agrupaPorAssunto(competencias);
  const vazio = perspective === "other"
    ? t("O aluno ainda não respondeu questões deste assunto.", "This student hasn't answered any questions in this subject yet.")
    : t("Você ainda não respondeu questões deste assunto.", "You haven't answered any questions in this subject yet.");

  // Degradação segura: sem vínculo de assunto (backend antigo), não renderiza.
  if (assuntos.length === 0) return null;

  return (
    <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
      <div className="flex items-center gap-2">
        <Layers size={20} className="text-brand" aria-hidden="true" />
        <h2 className="text-xl font-bold text-ink">{t("Acertos e erros por assunto", "Correct and wrong answers per subject")}</h2>
      </div>
      <p className="mt-1 text-sm text-muted">
        {t(
          "Visão por disciplina — cada assunto reúne as suas competências.",
          "View per subject — each subject gathers its competencies."
        )}
      </p>

      <ul className="mt-5 grid gap-4 md:grid-cols-2">
        {assuntos.map((s) => {
          const respostas = s.acertos + s.erros; // === tentativas
          const perc = respostas ? Math.round((100 * s.acertos) / respostas) : null;
          const semTentativas = respostas === 0;
          const dominioMedio = s.dominios.length
            ? Math.round((100 * s.dominios.reduce((a, b) => a + b, 0)) / s.dominios.length)
            : null;

          return (
            <li key={s.subject_id} className="rounded-[8px] border border-line p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-ink">{s.nome}</span>
                <span className="text-xs text-muted">
                  {s.n_competencias}{" "}
                  {s.n_competencias === 1 ? t("competência", "competency") : t("competências", "competencies")}
                </span>
              </div>

              {semTentativas ? (
                <p className="mt-2 text-sm text-muted">{vazio}</p>
              ) : (
                <>
                  <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1">
                    <span className="flex items-center gap-1.5 text-sm">
                      <CheckCircle2 size={16} className="text-emerald-600" aria-hidden="true" />
                      <strong className="text-base text-emerald-700">{s.acertos}</strong>
                      <span className="text-muted">{s.acertos === 1 ? t("acerto", "correct") : t("acertos", "correct")}</span>
                    </span>
                    <span className="flex items-center gap-1.5 text-sm">
                      <XCircle size={16} className="text-rose-600" aria-hidden="true" />
                      <strong className="text-base text-rose-700">{s.erros}</strong>
                      <span className="text-muted">{s.erros === 1 ? t("erro", "wrong") : t("erros", "wrong")}</span>
                    </span>
                    <span className="text-sm font-semibold text-brand">
                      {perc}% {t("de aproveitamento", "success rate")}
                    </span>
                  </div>

                  {/* Barra proporcional acertos x erros (decorativa: repete os números acima) */}
                  <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-slate-200" aria-hidden="true">
                    <div className="bg-emerald-500" style={{ width: `${(100 * s.acertos) / respostas}%` }} />
                    <div className="bg-rose-500" style={{ width: `${(100 * s.erros) / respostas}%` }} />
                  </div>
                </>
              )}

              <p className="mt-2 text-xs text-muted">
                {t(
                  `${s.acertos} de ${s.total_questoes} questões do assunto`,
                  `${s.acertos} of ${s.total_questoes} questions in this subject`
                )}
                {dominioMedio != null && (
                  <> · {t("domínio médio", "average mastery")}: {dominioMedio}%</>
                )}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
};
