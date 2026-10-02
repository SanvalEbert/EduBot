/*
INTEGRAÇÃO (4.1) — A aba "Atividades" lista as atividades práticas REAIS de
todos os OVAs do curso (tipo "atividade" na tabela resources). A conclusão é
persistida em POST /progress/resource e alimenta a regra de checklist do
EduBot ("acessou conteúdo mas não concluiu atividade").
*/
import { CheckCircle2, ClipboardList } from "lucide-react";
import { useState } from "react";
import { StudentProfile, saveResourceProgress } from "../services/api";
import { useToast } from "./ui/Toast";
import { useT } from "../i18n";

interface ExercisesProps {
  profile: StudentProfile;
  onTracked: () => void;
}

export const Exercises = ({ profile, onTracked }: ExercisesProps) => {
  const t = useT();
  const [completedNow, setCompletedNow] = useState<number[]>([]);
  const toast = useToast();

  const activities = profile.ovas.flatMap((ova) =>
    ova.recursos
      .filter((resource) => resource.tipo === "atividade")
      .map((resource) => ({ ...resource, ovaName: ova.ova_name }))
  );

  const complete = (resourceId: number) => {
    saveResourceProgress({ resource_id: resourceId, perc_consumed: 100, completed: true })
      .then(() => {
        setCompletedNow((current) => [...current, resourceId]);
        onTracked();
        toast.success(t("Atividade marcada como concluída!", "Activity marked as completed!"));
      })
      .catch(() => toast.error(t("Não foi possível concluir a atividade.", "Couldn't complete the activity.")));
  };

  return (
    <section>
      <h1 className="text-3xl font-bold text-ink">{t("Atividades práticas", "Practical activities")}</h1>
      <p className="mt-2 text-muted">
        {t(
          "Conclua as atividades de cada OVA — a conclusão alimenta os indicadores pedagógicos do EduBot.",
          "Complete the activities of each OVA — completion feeds EduBot's pedagogical indicators."
        )}
      </p>
      <div className="mt-6 grid gap-5">
        {activities.map((activity) => {
          const done = activity.concluido || completedNow.includes(activity.resource_id);
          return (
            <div key={activity.resource_id} className="rounded-[8px] border border-line bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <ClipboardList className="mt-1 text-brand" size={24} />
                  <div>
                    <h2 className="text-xl font-bold text-ink">{activity.titulo}</h2>
                    <p className="mt-1 text-muted">{activity.ovaName}</p>
                  </div>
                </div>
                {done ? (
                  <span className="flex items-center gap-2 rounded-[8px] bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
                    <CheckCircle2 size={17} />
                    {t("Concluída", "Completed")}
                  </span>
                ) : (
                  <button
                    onClick={() => complete(activity.resource_id)}
                    className="h-10 rounded-[8px] bg-ink px-4 font-semibold text-white"
                  >
                    {t("Marcar como concluída", "Mark as completed")}
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {activities.length === 0 && (
          <p className="rounded-[8px] border border-line bg-white p-6 text-muted">
            {t("Nenhuma atividade prática cadastrada para os OVAs do seu curso.", "No practical activities registered for your course's OVAs.")}
          </p>
        )}
      </div>
    </section>
  );
};
