/*
B.5 — "Ações propostas pelo EduBot". A fila de aprovação do tutor: ações de tier
alto (alertas de severidade alta, mensagens propostas ao aluno) que o agente NÃO
executa sozinho. O tutor aprova (executa a ação — ex.: intervenção assinada "do
seu tutor") ou rejeita. Nada chega ao aluno sem aprovação.
*/
import { CheckCircle2, Inbox, LoaderCircle, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { QueueItem, approveQueueItem, getTutorQueue, rejectQueueItem } from "../services/api";
import { useToast } from "./ui/Toast";
import { useT } from "../i18n";

export const ApprovalQueue = () => {
  const t = useT();
  const [fila, setFila] = useState<QueueItem[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const toast = useToast();

  const load = () =>
    getTutorQueue().then((r) => setFila(r.fila)).catch(() => setFila([]));

  useEffect(() => {
    load();
  }, []);

  const act = async (item: QueueItem, approve: boolean) => {
    setBusy(item.alert_id);
    try {
      await (approve ? approveQueueItem : rejectQueueItem)(item.alert_id);
      setFila((cur) => (cur ?? []).filter((i) => i.alert_id !== item.alert_id));
      toast.success(approve ? t("Ação aprovada e executada.", "Action approved and executed.")
                            : t("Ação rejeitada.", "Action rejected."));
    } catch {
      toast.error(t("Não foi possível concluir.", "Couldn't complete."));
    } finally {
      setBusy(null);
    }
  };

  if (fila !== null && fila.length === 0) return null; // nada pendente: não ocupa espaço

  return (
    <div className="rounded-[8px] border border-indigo-200 bg-indigo-50/50 p-6">
      <div className="flex items-center gap-2">
        <Inbox size={20} className="text-brand" />
        <h2 className="text-xl font-bold text-ink">{t("Ações propostas pelo EduBot", "Actions proposed by EduBot")}</h2>
        {fila && <span className="rounded-full bg-brand px-2 py-0.5 text-xs font-bold text-white">{fila.length}</span>}
      </div>
      <p className="mt-1 text-sm text-muted">
        {t("O agente propôs estas ações de maior impacto — nada é enviado ao aluno sem a sua aprovação.",
           "The agent proposed these higher-impact actions — nothing reaches the student without your approval.")}
      </p>

      {fila === null ? (
        <div className="flex justify-center py-6"><LoaderCircle className="animate-spin text-brand" size={20} /></div>
      ) : (
        <ul className="mt-4 space-y-3">
          {fila.map((item) => (
            <li key={item.alert_id} className="rounded-[8px] border border-line bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold text-ink">{item.aluno}</span>
                <span className="rounded-[8px] bg-slate-100 px-2 py-0.5 text-xs font-semibold text-muted">{item.type}</span>
              </div>
              {item.proposed_action?.mensagem_aluno ? (
                <p className="mt-2 rounded-[8px] bg-slate-50 p-3 text-sm text-slate-700">
                  “{item.proposed_action.mensagem_aluno}”
                </p>
              ) : (
                <p className="mt-2 text-sm text-slate-700">{item.message}</p>
              )}
              {item.proposed_action?.justificativa && (
                <p className="mt-2 text-xs text-muted">
                  <strong>{t("Justificativa:", "Rationale:")}</strong> {item.proposed_action.justificativa}
                </p>
              )}
              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => act(item, true)}
                  disabled={busy === item.alert_id}
                  className="flex h-10 items-center gap-2 rounded-[8px] bg-emerald-600 px-4 text-sm font-bold text-white disabled:bg-slate-300"
                >
                  <CheckCircle2 size={16} /> {t("Aprovar", "Approve")}
                </button>
                <button
                  onClick={() => act(item, false)}
                  disabled={busy === item.alert_id}
                  className="flex h-10 items-center gap-2 rounded-[8px] border border-rose-200 px-4 text-sm font-bold text-rose-700 disabled:opacity-60"
                >
                  <XCircle size={16} /> {t("Rejeitar", "Reject")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
