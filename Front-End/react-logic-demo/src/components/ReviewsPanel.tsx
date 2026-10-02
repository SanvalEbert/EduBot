/*
D.3 — "Revisões desta semana". Mostra a agenda de revisão espaçada do aluno
(revisões vencidas em destaque + as que vencem nos próximos dias). O canal
principal de cobrança é a intervenção do EduBot; este painel dá a visão geral.
*/
import { CalendarClock, LoaderCircle, PlayCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { ReviewItem, getReviews } from "../services/api";
import { useT } from "../i18n";
import { safeGet, safeSet, safeRemove } from "../services/storage";

// Chave lida pelo Quiz ao montar: qual OVA pré-selecionar ao vir de "Revisar".
export const REVIEW_OVA_KEY = "edubot.reviewOva";

export const ReviewsPanel = () => {
  const t = useT();
  const [reviews, setReviews] = useState<ReviewItem[] | null>(null);

  useEffect(() => {
    getReviews().then((r) => setReviews(r.reviews)).catch(() => setReviews([]));
  }, []);

  // "Revisar": guarda o OVA da competência e abre o Quiz (o Quiz lê a chave e já
  // abre naquele OVA). Revisar = responder de novo as questões da competência.
  const revisar = (ovaId: number) => {
    safeSet("session", REVIEW_OVA_KEY, String(ovaId));
    window.location.hash = "#/quiz";
  };

  return (
    <div className="rounded-[8px] border border-line bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <CalendarClock size={20} className="text-brand" />
        <h2 className="text-xl font-bold text-ink">{t("Revisões desta semana", "Reviews this week")}</h2>
      </div>
      <p className="mt-1 text-sm text-muted">
        {t("Revisar no intervalo certo consolida o que você já dominou.",
           "Reviewing at the right interval consolidates what you've mastered.")}
      </p>

      {reviews === null ? (
        <div className="flex justify-center py-6"><LoaderCircle className="animate-spin text-brand" size={20} /></div>
      ) : reviews.length === 0 ? (
        <p className="mt-4 rounded-[8px] bg-slate-50 p-4 text-sm text-muted">
          {t("Nenhuma revisão agendada — continue avançando nos módulos!",
             "No reviews scheduled — keep moving through the modules!")}
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {reviews.map((r) => (
            <li
              key={r.review_id}
              className={`flex flex-wrap items-center justify-between gap-3 rounded-[8px] border p-4 ${
                r.vencida ? "border-amber-300 bg-amber-50" : "border-line bg-white"
              }`}
            >
              <div className="min-w-0">
                <span className="font-semibold text-ink">{r.competencia}</span>
                <span className={`block text-sm font-semibold ${r.vencida ? "text-amber-700" : "text-muted"}`}>
                  {r.vencida ? t("Revisar agora", "Review now") : t(`vence ${r.due_date}`, `due ${r.due_date}`)}
                </span>
              </div>
              {r.ova_id != null && (
                <button
                  onClick={() => revisar(r.ova_id!)}
                  className={`flex shrink-0 items-center gap-1.5 rounded-[8px] px-4 py-2 text-sm font-bold text-white transition ${
                    r.vencida ? "bg-amber-600 hover:bg-amber-700" : "bg-brand hover:bg-indigo-600"
                  }`}
                  aria-label={t(`Revisar ${r.competencia} no quiz`, `Review ${r.competencia} in the quiz`)}
                >
                  <PlayCircle size={16} aria-hidden="true" /> {t("Revisar", "Review")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
