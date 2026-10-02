/*
INTEGRAÇÃO — "Meu Desempenho" a partir do perfil real (GET /student/me):
placar de acertos/erros por ASSUNTO e por COMPETÊNCIA + gráficos (Recharts).
Plano 5: os gráficos foram extraídos para <PerformanceCharts>, reusado no detalhe
do aluno visto pelo professor (TutorStudentDetail) — sem duplicar o Recharts.
*/
import { useEffect, useState } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { MasteryTrendItem, StudentProfile, getMasteryTrend } from "../services/api";
import { useT } from "../i18n";
import { PerformanceCoach } from "./PerformanceCoach";
import { ReviewsPanel } from "./ReviewsPanel";
import { GamificationSection } from "./Gamification";
import { CompetencyScores } from "./CompetencyScores";
import { SubjectScores } from "./SubjectScores";
import { PerformanceCharts } from "./PerformanceCharts";

interface EvolutionProps {
  profile: StudentProfile;
}

export const Evolution = ({ profile }: EvolutionProps) => {
  const t = useT();
  // H.1 (Plano 2) — tendência de domínio (setas): só aparece após o backend
  // acumular snapshots diários; vazio no começo é esperado (degrada em silêncio).
  const [trend, setTrend] = useState<MasteryTrendItem[]>([]);
  useEffect(() => {
    getMasteryTrend().then((r) => setTrend(r.trend)).catch(() => setTrend([]));
  }, []);
  const rising = trend.filter((x) => x.direcao !== "flat");

  return (
    <section>
      <h1 className="text-3xl font-bold text-ink">{t("Evolução do Aluno", "Student Progress")}</h1>
      <p className="mt-2 text-muted">{t("Gráficos gerados a partir dos dados rastreados no backend.", "Charts generated from the data tracked in the backend.")}</p>

      {/* G.5 — camada de jogo: nível, sequência, conquistas, ranking (some se
          a gamificação estiver desligada no backend). */}
      <div className="mt-6">
        <GamificationSection studentName={profile.estudante.nome} />
      </div>

      {/* Personagem virtualizado do EduBot falando sobre o progresso (Cena 3) */}
      <div className="mt-6">
        <PerformanceCoach profile={profile} />
      </div>

      {/* D.3 — agenda de revisão espaçada */}
      <div className="mt-6">
        <ReviewsPanel />
      </div>

      {/* Placar cru de acertos x erros: primeiro a visão macro por ASSUNTO
          (Plano 5), depois o detalhe por competência. Os gráficos abaixo mostram
          só percentuais; aqui vêm os números absolutos, que é o que o aluno pergunta. */}
      <div className="mt-6">
        <SubjectScores competencias={profile.competencias} />
      </div>
      <div className="mt-6 mb-6">
        <CompetencyScores competencias={profile.competencias} />
      </div>

      {/* Gráficos (Recharts) — a "Tendência (7 dias)" entra no slot do card da teia. */}
      <PerformanceCharts
        profile={profile}
        radarExtra={
          rising.length > 0 ? (
            <div className="mt-4 border-t border-line pt-4">
              <p className="mb-2 text-sm font-semibold text-ink">{t("Tendência (7 dias)", "Trend (7 days)")}</p>
              <div className="flex flex-wrap gap-2">
                {rising.map((x) => {
                  const up = x.direcao === "up";
                  const pts = Math.round(Math.abs(x.delta) * 100);
                  return (
                    <span
                      key={x.competency_id}
                      className={`flex items-center gap-1 rounded-[8px] px-3 py-1 text-sm font-semibold ${
                        up ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                      }`}
                      aria-label={t(
                        `${x.competencia}: ${up ? "subiu" : "caiu"} ${pts} pontos`,
                        `${x.competencia}: ${up ? "up" : "down"} ${pts} points`
                      )}
                    >
                      {up ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
                      {x.competencia} {up ? "+" : "−"}{pts}%
                    </span>
                  );
                })}
              </div>
            </div>
          ) : undefined
        }
      />
    </section>
  );
};
