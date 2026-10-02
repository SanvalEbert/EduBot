/*
"Meu Desempenho" — PLACAR de acertos x erros por competência.

Os gráficos (teia/barras) mostram só o PERCENTUAL de domínio; faltava o número
cru — quantas questões o aluno acertou e quantas tentativas ele errou, por
competência. Este painel mostra isso de forma direta e visual.

Semântica dos números (conferida no backend, `student_context._competency_rows`):
  - `acertos`        = questões DISTINTAS que o aluno já acertou (tabela `answers`
                       guarda a 1ª resposta correta de cada questão);
  - `erros`          = TENTATIVAS erradas (tabela `attempts`);
  - como o reenvio de uma questão já correta não gera nova tentativa,
    vale `acertos + erros === tentativas` — por isso a barra proporcional
    (verde/vermelho) fecha 100% e o aproveitamento é honesto;
  - `total_questoes` = todas as questões da competência, inclusive as não tentadas
    (por isso a cobertura aparece numa linha separada, sem se misturar à barra).

A11y (padrão do Plano 4): nada depende só de cor — cada número vem com ícone ✓/✗
e a palavra "acertos"/"erros"; a barra é decorativa (`aria-hidden`) porque repete
números que já estão em texto; textos ≥ 12px.
*/
import { CheckCircle2, Layers, Target, XCircle } from "lucide-react";
import { CompetencyState } from "../services/api";
import { useT } from "../i18n";

const STATUS_STYLE: Record<string, string> = {
  desenvolvida: "border-emerald-200 bg-emerald-50 text-emerald-700",
  "em desenvolvimento": "border-amber-200 bg-amber-50 text-amber-700",
  "não iniciada": "border-line bg-slate-100 text-slate-500"
};

const statusLabel = (status: string, t: (pt: string, en: string) => string) => {
  if (status === "desenvolvida") return t("desenvolvida", "mastered");
  if (status === "em desenvolvimento") return t("em desenvolvimento", "in progress");
  return t("não iniciada", "not started");
};

interface CompetencyScoresProps {
  competencias: CompetencyState[];
  // "self" = o aluno vê ("Você..."); "other" = o professor vê outro aluno ("O
  // aluno..."). Muda só a voz dos textos, não os números.
  perspective?: "self" | "other";
}

export const CompetencyScores = ({ competencias, perspective = "self" }: CompetencyScoresProps) => {
  const t = useT();
  const other = perspective === "other";

  const totalAcertos = competencias.reduce((sum, c) => sum + (c.acertos || 0), 0);
  const totalErros = competencias.reduce((sum, c) => sum + (c.erros || 0), 0);
  const totalRespostas = totalAcertos + totalErros;
  const aproveitamento = totalRespostas ? Math.round((100 * totalAcertos) / totalRespostas) : null;

  // Plano 5: agrupa as competências por ASSUNTO ("área Cálculo" e, dentro dela,
  // as competências). Preserva a ordem; sem assunto (backend antigo) cai num
  // grupo único sem cabeçalho, mantendo o comportamento anterior.
  const grupos: { key: string; nome: string; itens: CompetencyState[] }[] = [];
  const idx: Record<string, number> = {};
  for (const c of competencias) {
    const key = c.subject_id != null ? `s${c.subject_id}` : "_";
    if (idx[key] === undefined) {
      idx[key] = grupos.length;
      grupos.push({ key, nome: c.subject_nome ?? "", itens: [] });
    }
    grupos[idx[key]].itens.push(c);
  }

  return (
    <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
      <div className="flex items-center gap-2">
        <Target size={20} className="text-brand" aria-hidden="true" />
        <h2 className="text-xl font-bold text-ink">{t("Acertos e erros por competência", "Correct and wrong answers per competency")}</h2>
      </div>
      <p className="mt-1 text-sm text-muted">
        {other
          ? t(
              "Quantas questões o aluno já acertou e quantas tentativas erradas fez em cada competência.",
              "How many questions this student got right and how many wrong attempts they made in each competency."
            )
          : t(
              "Quantas questões você já acertou e quantas tentativas erradas fez em cada competência.",
              "How many questions you have got right and how many wrong attempts you made in each competency."
            )}
      </p>

      {/* Resumo geral — o número cru, bem grande */}
      <div className="mt-5 flex flex-wrap items-center gap-3 rounded-[8px] border border-line bg-slate-50 p-4">
        <div className="flex items-center gap-2">
          <CheckCircle2 size={22} className="text-emerald-600" aria-hidden="true" />
          <span className="text-2xl font-bold text-emerald-700">{totalAcertos}</span>
          <span className="text-sm text-muted">{t("acertos", "correct")}</span>
        </div>
        <span className="text-slate-300" aria-hidden="true">|</span>
        <div className="flex items-center gap-2">
          <XCircle size={22} className="text-rose-600" aria-hidden="true" />
          <span className="text-2xl font-bold text-rose-700">{totalErros}</span>
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

      {competencias.length === 0 ? (
        <p className="mt-4 rounded-[8px] bg-slate-50 p-4 text-sm text-muted">
          {t("Nenhuma competência cadastrada para o seu curso.", "No competencies registered for your course.")}
        </p>
      ) : (
        <div className="mt-5 space-y-6">
          {grupos.map((g) => (
            <div key={g.key}>
              {/* Cabeçalho do assunto — a "área Cálculo" que agrupa as competências */}
              {g.nome && (
                <div className="mb-3 flex flex-wrap items-center gap-2 border-b border-line pb-2">
                  <Layers size={16} className="text-brand" aria-hidden="true" />
                  <h3 className="text-base font-bold text-ink">{g.nome}</h3>
                  <span className="text-xs text-muted">
                    {g.itens.length}{" "}
                    {g.itens.length === 1 ? t("competência", "competency") : t("competências", "competencies")}
                  </span>
                </div>
              )}
              <ul className="space-y-4">
                {g.itens.map((c) => {
                  const acertos = c.acertos || 0;
                  const erros = c.erros || 0;
                  const respostas = acertos + erros; // === tentativas (ver cabeçalho)
                  const perc = respostas ? Math.round((100 * acertos) / respostas) : null;
                  const semTentativas = respostas === 0;

                  return (
              <li key={c.competency_id} className="rounded-[8px] border border-line p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-ink">{c.nome}</span>
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
                      STATUS_STYLE[c.status] ?? STATUS_STYLE["não iniciada"]
                    }`}
                  >
                    {statusLabel(c.status, t)}
                  </span>
                </div>

                {semTentativas ? (
                  <p className="mt-2 text-sm text-muted">
                    {other
                      ? t("O aluno ainda não respondeu questões desta competência.", "This student hasn't answered any questions in this competency yet.")
                      : t("Você ainda não respondeu questões desta competência.", "You haven't answered any questions in this competency yet.")}
                  </p>
                ) : (
                  <>
                    {/* Números crus — o que o aluno quer ver de imediato */}
                    <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1">
                      <span className="flex items-center gap-1.5 text-sm">
                        <CheckCircle2 size={16} className="text-emerald-600" aria-hidden="true" />
                        <strong className="text-base text-emerald-700">{acertos}</strong>
                        <span className="text-muted">{acertos === 1 ? t("acerto", "correct") : t("acertos", "correct")}</span>
                      </span>
                      <span className="flex items-center gap-1.5 text-sm">
                        <XCircle size={16} className="text-rose-600" aria-hidden="true" />
                        <strong className="text-base text-rose-700">{erros}</strong>
                        <span className="text-muted">{erros === 1 ? t("erro", "wrong") : t("erros", "wrong")}</span>
                      </span>
                      <span className="text-sm font-semibold text-brand">
                        {perc}% {t("de aproveitamento", "success rate")}
                      </span>
                    </div>

                    {/* Barra proporcional acertos x erros (decorativa: repete os números acima) */}
                    <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-slate-200" aria-hidden="true">
                      <div className="bg-emerald-500" style={{ width: `${(100 * acertos) / respostas}%` }} />
                      <div className="bg-rose-500" style={{ width: `${(100 * erros) / respostas}%` }} />
                    </div>
                  </>
                )}

                {/* Cobertura + domínio: contexto, em unidade diferente da barra */}
                <p className="mt-2 text-xs text-muted">
                  {t(
                    `${acertos} de ${c.total_questoes} questões da competência`,
                    `${acertos} of ${c.total_questoes} questions in this competency`
                  )}
                  {c.dominio_estimado != null && (
                    <> · {t("domínio estimado", "estimated mastery")}: {Math.round(c.dominio_estimado * 100)}%</>
                  )}
                </p>
              </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
