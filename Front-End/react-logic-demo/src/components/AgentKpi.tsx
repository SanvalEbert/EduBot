/*
B.6 — KPI do agente: taxa de aceitação das intervenções por tipo. É o número que
diz se o EduBot está ajudando de verdade: aceita/melhorou contam como sucesso;
dispensada/expirada, como rejeição. O agente usa o mesmo sinal (via o digest do
redator) para variar a abordagem.
*/
import { LineChart, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { AgentKpi as AgentKpiType, AgentKpiByFormat, getAgentKpi } from "../services/api";
import { useT } from "../i18n";

function rateColor(rate: number | null): string {
  if (rate == null) return "text-muted";
  if (rate >= 0.6) return "text-emerald-600";
  if (rate >= 0.3) return "text-amber-600";
  return "text-rose-600";
}

const FORMAT_LABEL: Record<string, string> = { video: "🎬 vídeo", texto: "📖 texto", podcast: "🎧 podcast" };

export const AgentKpi = () => {
  const t = useT();
  const [kpis, setKpis] = useState<AgentKpiType[] | null>(null);
  const [byFormat, setByFormat] = useState<AgentKpiByFormat[]>([]);

  useEffect(() => {
    getAgentKpi()
      .then((r) => {
        setKpis(r.kpis);
        setByFormat(r.kpis_por_formato ?? []);
      })
      .catch(() => setKpis([]));
  }, []);

  if (kpis !== null && kpis.length === 0) return null;

  return (
    <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
      <div className="flex items-center gap-2">
        <LineChart size={20} className="text-brand" />
        <h2 className="text-xl font-bold text-ink">{t("Desempenho do EduBot", "EduBot performance")}</h2>
      </div>
      <p className="mt-1 text-sm text-muted">
        {t("Taxa de aceitação das intervenções por tipo (aceita ou melhorou = sucesso).",
           "Intervention acceptance rate by type (accepted or improved = success).")}
      </p>

      {kpis === null ? (
        <div className="flex justify-center py-6"><LoaderCircle className="animate-spin text-brand" size={20} /></div>
      ) : (
        <div className="mt-4 space-y-3">
          {kpis.map((k) => (
            <div key={k.tipo} className="rounded-[8px] border border-line p-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink">{k.tipo}</span>
                <span className={`text-lg font-bold ${rateColor(k.taxa_aceitacao)}`}>
                  {k.taxa_aceitacao != null ? `${Math.round(k.taxa_aceitacao * 100)}%` : "—"}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
                <span>{t("total", "total")}: {k.total}</span>
                <span className="text-emerald-700">✓ {k.aceita + k.melhorou}</span>
                <span className="text-rose-700">✕ {k.dispensada + k.expirada}</span>
                {k.pendente > 0 && <span>{t("pendente", "pending")}: {k.pendente}</span>}
              </div>
            </div>
          ))}

          {/* P.3 — a que FORMATO de sugestão a turma responde melhor. */}
          {byFormat.length > 0 && (
            <div className="mt-4 border-t border-line pt-4">
              <p className="mb-2 text-sm font-semibold text-ink">
                {t("Aceitação por formato sugerido", "Acceptance by suggested format")}
              </p>
              <div className="flex flex-wrap gap-3">
                {byFormat.map((f) => (
                  <div key={f.formato} className="rounded-[8px] border border-line px-3 py-2">
                    <span className="text-sm font-semibold text-ink">{FORMAT_LABEL[f.formato] ?? f.formato}</span>
                    <span className={`ml-2 font-bold ${rateColor(f.taxa_aceitacao)}`}>
                      {f.taxa_aceitacao != null ? `${Math.round(f.taxa_aceitacao * 100)}%` : "—"}
                    </span>
                    <span className="ml-2 text-xs text-muted">({f.total})</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
