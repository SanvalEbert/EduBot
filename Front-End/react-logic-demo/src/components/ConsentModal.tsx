/*
D.5 — Modal de consentimento (LGPD) no primeiro login.

Explica as 3 finalidades antes de o aluno usar a plataforma. `tracking_pedagogico`
é base legal de execução de contrato educacional (informado, não opcional — vem
marcado e travado); `ia_sobre_dados` e `imagem_voz` são opt-in revogáveis. As
escolhas vão para POST /consents; uma flag em localStorage evita reexibir o modal.
O aluno pode revisar tudo depois em "Meus dados".
*/
import { LoaderCircle, ShieldCheck } from "lucide-react";
import { useRef, useState } from "react";
import { Consent, setConsent } from "../services/api";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { useT } from "../i18n";
import { safeGet, safeSet, safeRemove } from "../services/storage";

export const CONSENT_FLAG = "edubot.consent.v1";

interface ConsentModalProps {
  onDone: () => void;
}

export const ConsentModal = ({ onDone }: ConsentModalProps) => {
  const t = useT();
  const [ia, setIa] = useState(false);
  const [imagem, setImagem] = useState(false);
  const [saving, setSaving] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  // AC.1 (Plano 4): foco preso no diálogo. Consentimento é BLOQUEANTE — sem
  // onEscape (Esc não fecha). Foco inicial no próprio diálogo (lê do topo).
  useFocusTrap(dialogRef, { active: true, initialFocusRef: dialogRef });

  const save = async () => {
    setSaving(true);
    try {
      // Grava as 3 finalidades (tracking é sempre concedido no backend).
      const choices: [Consent["purpose"], boolean][] = [
        ["tracking_pedagogico", true],
        ["ia_sobre_dados", ia],
        ["imagem_voz", imagem]
      ];
      for (const [purpose, granted] of choices) {
        await setConsent(purpose, granted);
      }
    } catch {
      /* best-effort: mesmo se falhar a gravação, não travamos o aluno na porta */
    } finally {
      safeSet("local", CONSENT_FLAG, "1");
      setSaving(false);
      onDone();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="consent-title"
        tabIndex={-1}
        className="w-full max-w-lg rounded-[8px] bg-white p-8 shadow-soft outline-none"
      >
        <div className="flex items-center gap-3">
          <ShieldCheck size={28} className="text-brand" />
          <h1 id="consent-title" className="text-2xl font-bold text-ink">{t("Privacidade e seus dados", "Privacy and your data")}</h1>
        </div>
        <p className="mt-3 text-muted">
          {t(
            "Para personalizar seus estudos, a plataforma trata alguns dados. Você decide o que é opcional — e pode mudar quando quiser em \"Meus dados\".",
            "To personalize your studies, the platform processes some data. You decide what is optional — and can change it anytime in \"My data\"."
          )}
        </p>

        <div className="mt-6 space-y-4">
          <div className="rounded-[8px] bg-slate-50 p-4">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-ink">{t("Acompanhamento pedagógico", "Pedagogical tracking")}</span>
              <span className="rounded-[8px] bg-brand/10 px-2 py-1 text-xs font-bold uppercase tracking-wide text-brand">
                {t("Necessário", "Required")}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted">
              {t(
                "Registramos seu consumo de recursos e desempenho para orientar sua trilha. É a base do serviço educacional.",
                "We record your resource consumption and performance to guide your track. This is core to the educational service."
              )}
            </p>
          </div>

          <label className="flex cursor-pointer items-start gap-3 rounded-[8px] border border-line p-4">
            <input type="checkbox" className="mt-1" checked={ia} onChange={(e) => setIa(e.target.checked)} />
            <span>
              <span className="font-semibold text-ink">{t("IA sobre os seus dados", "AI over your data")}</span>
              <span className="mt-1 block text-sm text-muted">
                {t(
                  "Permitir que o EduBot use IA sobre o seu histórico e guarde o texto das suas perguntas ao tutor. Opcional.",
                  "Let EduBot use AI over your history and store the text of your tutor questions. Optional."
                )}
              </span>
            </span>
          </label>

          <label className="flex cursor-pointer items-start gap-3 rounded-[8px] border border-line p-4">
            <input type="checkbox" className="mt-1" checked={imagem} onChange={(e) => setImagem(e.target.checked)} />
            <span>
              <span className="font-semibold text-ink">{t("Imagem e voz", "Image and voice")}</span>
              <span className="mt-1 block text-sm text-muted">
                {t(
                  "Permitir a virtualização de personagem com a sua imagem/voz no futuro. Opcional.",
                  "Allow character virtualization with your image/voice in the future. Optional."
                )}
              </span>
            </span>
          </label>
        </div>

        <button
          onClick={save}
          disabled={saving}
          className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-[8px] bg-brand font-bold text-white disabled:bg-slate-300"
        >
          {saving && <LoaderCircle className="animate-spin" size={20} />}
          {t("Salvar e continuar", "Save and continue")}
        </button>
      </div>
    </div>
  );
};
