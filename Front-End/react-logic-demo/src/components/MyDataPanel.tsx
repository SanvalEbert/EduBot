/*
D.5 — "Meus dados" (LGPD). Consolida os direitos do titular numa só caixa, no
tema do app: consentimentos com toggle (tracking pedagógico é informado/execução
de contrato, então fica travado como concedido), exportação do perfil em JSON e
solicitação de exclusão (que vira um alerta para o admin — exclusão efetiva é
manual na v1).
*/
import { FileDown, LoaderCircle, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Consent, StudentProfile, getConsents, requestDataDeletion, setConsent } from "../services/api";
import { useT } from "../i18n";

interface MyDataPanelProps {
  profile: StudentProfile;
}

const PURPOSE_LABEL: Record<Consent["purpose"], { pt: string; en: string; desc_pt: string; desc_en: string }> = {
  tracking_pedagogico: {
    pt: "Acompanhamento pedagógico",
    en: "Pedagogical tracking",
    desc_pt: "Registrar seu consumo de recursos e desempenho para orientar seus estudos. Base do serviço — informado, não opcional.",
    desc_en: "Record your resource consumption and performance to guide your studies. Core to the service — informed, not optional."
  },
  ia_sobre_dados: {
    pt: "IA sobre os seus dados",
    en: "AI over your data",
    desc_pt: "Permitir que o EduBot use IA sobre o seu histórico e guarde o texto das perguntas ao tutor. Opcional e revogável.",
    desc_en: "Let EduBot use AI over your history and store the text of your tutor questions. Optional and revocable."
  },
  imagem_voz: {
    pt: "Imagem e voz",
    en: "Image and voice",
    desc_pt: "Permitir a virtualização de personagem com a sua imagem/voz. Opcional e revogável.",
    desc_en: "Allow character virtualization with your image/voice. Optional and revocable."
  },
  ranking_turma: {
    pt: "Ranking da turma",
    en: "Class ranking",
    desc_pt: "Aparecer no ranking da turma com o seu apelido. Opcional e revogável.",
    desc_en: "Appear in the class ranking with your nickname. Optional and revocable."
  }
};

// Defesa: uma finalidade nova no backend não pode derrubar o painel inteiro.
// Sem rótulo mapeado, cai num rótulo genérico (a própria chave) em vez de crashar.
const labelFor = (purpose: string) =>
  PURPOSE_LABEL[purpose as Consent["purpose"]] ?? { pt: purpose, en: purpose, desc_pt: "", desc_en: "" };

export const MyDataPanel = ({ profile }: MyDataPanelProps) => {
  const t = useT();
  const [consents, setConsents] = useState<Consent[] | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [deleteStatus, setDeleteStatus] = useState<string | null>(null);

  useEffect(() => {
    getConsents().then((r) => setConsents(r.consents)).catch(() => setConsents([]));
  }, []);

  const toggle = async (purpose: Consent["purpose"], granted: boolean) => {
    setSaving(purpose);
    try {
      const r = await setConsent(purpose, granted);
      setConsents(r.consents);
    } catch {
      /* mantém o estado anterior */
    } finally {
      setSaving(null);
    }
  };

  const exportProfile = () => {
    const blob = new Blob([JSON.stringify(profile, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `perfil-${profile.estudante.ra}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const askDeletion = async () => {
    try {
      const r = await requestDataDeletion();
      setDeleteStatus(r.status);
    } catch {
      setDeleteStatus("erro");
    }
  };

  return (
    <div className="rounded-[8px] border border-line bg-white p-6">
      <div className="flex items-center gap-2">
        <ShieldCheck size={20} className="text-brand" />
        <h2 className="text-xl font-bold text-ink">{t("Meus dados", "My data")}</h2>
      </div>
      <p className="mt-2 text-sm text-muted">
        {t("Controle como seus dados são usados (LGPD).", "Control how your data is used (GDPR/LGPD).")}
      </p>

      <div className="mt-4 space-y-3">
        {(consents ?? []).map((c) => {
          const label = labelFor(c.purpose);
          return (
            <div key={c.purpose} className="rounded-[8px] border border-line p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-semibold text-ink">{t(label.pt, label.en)}</div>
                  <p className="mt-1 text-xs text-muted">{t(label.desc_pt, label.desc_en)}</p>
                </div>
                <label className="relative inline-flex shrink-0 cursor-pointer items-center">
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={c.granted}
                    disabled={!c.opt_in || saving === c.purpose}
                    onChange={(e) => toggle(c.purpose, e.target.checked)}
                  />
                  <div className="h-6 w-11 rounded-full bg-slate-200 after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-brand peer-checked:after:translate-x-5 peer-disabled:opacity-60" />
                </label>
              </div>
              {!c.opt_in && (
                <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  {t("Necessário para o serviço", "Required for the service")}
                </p>
              )}
            </div>
          );
        })}
        {consents === null && (
          <div className="flex justify-center py-4"><LoaderCircle className="animate-spin text-brand" size={20} /></div>
        )}
      </div>

      <div className="mt-5 grid gap-3">
        <button
          onClick={exportProfile}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-[8px] bg-ink font-semibold text-white"
        >
          <FileDown size={18} />
          {t("Exportar meus dados (JSON)", "Export my data (JSON)")}
        </button>
        <button
          onClick={askDeletion}
          disabled={deleteStatus === "pendente"}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-[8px] border border-rose-200 font-semibold text-rose-700 disabled:opacity-60"
        >
          <Trash2 size={18} />
          {deleteStatus === "pendente"
            ? t("Solicitação de exclusão enviada", "Deletion request sent")
            : t("Solicitar exclusão dos dados", "Request data deletion")}
        </button>
        {deleteStatus === "erro" && (
          <p className="text-sm font-semibold text-rose-700">{t("Não foi possível enviar agora.", "Couldn't send right now.")}</p>
        )}
      </div>
    </div>
  );
};
