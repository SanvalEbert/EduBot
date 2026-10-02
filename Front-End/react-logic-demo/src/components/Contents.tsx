/*
INTEGRAÇÃO (4.1) — A "Área de Conteúdo" deixou de listar conteúdos fictícios e
passou a mostrar os recursos REAIS de cada OVA (GET /ova/<id>/resources):
  - texto     -> abre o leitor clássico (iframe.html), que já rastreia
                 scroll/tempo de leitura via /progress/ova
  - video     -> VideoPlayer (YouTube ou arquivo) com % assistido persistido
  - podcast   -> AudioPlayer com tempo de escuta persistido
  - atividade -> botão "Marcar como concluída"
  - quiz      -> atalho para a aba Quiz
Todo consumo vai para POST /progress/resource e atualiza o perfil.
*/
import { BookOpenText, CheckCircle2, FileText, ListChecks } from "lucide-react";
import { useEffect, useState } from "react";
import {
  OvaResource,
  OvaState,
  StudentProfile,
  getOVAResources,
  saveResourceProgress
} from "../services/api";
import { saveMediaProgress } from "../services/mediaProgress";
import { useToast } from "./ui/Toast";
import { VideoPlayer, MediaProgress } from "./players/VideoPlayer";
import { AudioPlayer } from "./players/AudioPlayer";
import { useT } from "../i18n";

interface ContentsProps {
  profile: StudentProfile;
  onTracked: () => void;
  // Abre o OVA no leitor NATIVO (dentro do dashboard) — substitui o leitor
  // legado que abria em outra aba.
  onOpenOva: (ova: OvaState) => void;
}

export const Contents = ({ profile, onTracked, onOpenOva }: ContentsProps) => {
  const t = useT();
  const [activeOvaId, setActiveOvaId] = useState(profile.ovas[0]?.ova_id ?? 0);
  const [resources, setResources] = useState<OvaResource[]>([]);
  const activeOva = profile.ovas.find((ova) => ova.ova_id === activeOvaId);
  const toast = useToast();

  useEffect(() => {
    if (!activeOvaId) return;
    // Guarda contra condição de corrida: ao trocar de OVA rápido, descarta a
    // resposta de uma requisição antiga que chegue depois da nova.
    let active = true;
    getOVAResources(activeOvaId)
      .then((data) => {
        if (active) setResources(data);
      })
      .catch(() => {
        if (active) setResources([]);
      });
    return () => {
      active = false;
    };
  }, [activeOvaId]);

  const trackMedia = (resource: OvaResource) => (progress: MediaProgress) => {
    saveMediaProgress(resource.resource_id, progress)
      .then(onTracked)
      .catch(() => toast.error(t("Não foi possível salvar seu progresso. Verifique a conexão.", "Couldn't save your progress. Check your connection.")));
  };

  const trackText = (resource: OvaResource) => {
    saveResourceProgress({ resource_id: resource.resource_id, perc_consumed: 100, completed: true })
      .then(onTracked)
      .catch(() => toast.error(t("Não foi possível registrar a leitura.", "Couldn't record the reading.")));
  };

  const completeActivity = (resource: OvaResource) => {
    saveResourceProgress({ resource_id: resource.resource_id, perc_consumed: 100, completed: true })
      .then(() => {
        setResources((current) =>
          current.map((item) =>
            item.resource_id === resource.resource_id ? { ...item, completed: true } : item
          )
        );
        onTracked();
        toast.success(t("Atividade marcada como concluída!", "Activity marked as completed!"));
      })
      .catch(() => toast.error(t("Não foi possível concluir a atividade.", "Couldn't complete the activity.")));
  };

  return (
    <section className="grid gap-6 xl:grid-cols-[330px_1fr]">
      <div className="space-y-3">
        <h1 className="mb-5 text-3xl font-bold text-ink">{t("Área de Conteúdo", "Content Area")}</h1>
        {profile.ovas.map((ova) => (
          <button
            key={ova.ova_id}
            onClick={() => setActiveOvaId(ova.ova_id)}
            className={`w-full rounded-[8px] border p-5 text-left transition ${
              activeOvaId === ova.ova_id ? "border-brand bg-indigo-50" : "border-line bg-white hover:border-slate-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-brand">OVA</span>
              {ova.completed && <CheckCircle2 className="text-teal" size={20} />}
            </div>
            <div className="mt-2 font-bold text-ink">{ova.ova_name}</div>
            <div className="mt-2 text-sm text-muted">
              {ova.perc_scrolled || 0}% {t("lido", "read")} · {Math.round((ova.read_time || 0) / 60)} {t("min estudados", "min studied")}
            </div>
          </button>
        ))}
      </div>

      <div className="space-y-5">
        {activeOva && (
          <div className="rounded-[8px] border border-line bg-white p-6 shadow-soft">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="font-semibold text-brand">{t("Leitura interativa", "Interactive reading")}</p>
                <h2 className="mt-1 text-2xl font-bold text-ink">{activeOva.ova_name}</h2>
                <p className="mt-2 text-muted">
                  {t(
                    "O texto completo, os acordeões e os carrosséis abrem aqui mesmo, no novo leitor — com o Professor Mediador integrado. O tempo de leitura e o scroll continuam sendo rastreados normalmente.",
                    "The full text, accordions and carousels open right here in the new reader — with the Mediating Professor built in. Reading time and scroll keep being tracked normally."
                  )}
                </p>
              </div>
              <button
                onClick={() => onOpenOva(activeOva)}
                className="flex h-11 items-center gap-2 rounded-[8px] bg-brand px-5 font-semibold text-white transition hover:bg-indigo-600"
              >
                <BookOpenText size={19} />
                {t("Abrir conteúdo", "Open content")}
              </button>
            </div>
          </div>
        )}

        {resources
          .filter((resource) => resource.resource_type === "texto" && resource.resource_url)
          .map((resource) => (
            <div
              key={resource.resource_id}
              className="flex flex-wrap items-center justify-between gap-4 rounded-[8px] border border-line bg-white p-5"
            >
              <span className="flex items-center gap-2 font-semibold text-ink">
                <FileText size={20} className="text-brand" />
                {resource.resource_title}
              </span>
              <a
                href={resource.resource_url ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => trackText(resource)}
                className="rounded-[8px] border border-brand px-4 py-2 font-semibold text-brand transition hover:bg-indigo-50"
              >
                {resource.completed ? t("Reler", "Read again") : t("Abrir leitura", "Open reading")}
              </a>
            </div>
          ))}

        {resources
          .filter((resource) => resource.resource_type === "video")
          .map((resource) => (
            <VideoPlayer
              key={resource.resource_id}
              url={resource.resource_url}
              mediaType={resource.media_type}
              title={resource.resource_title}
              resourceId={resource.resource_id}
              initialCoverageBitmap={resource.coverage_bitmap}
              initialCoveragePerc={resource.coverage_perc}
              onProgress={trackMedia(resource)}
            />
          ))}

        {resources
          .filter((resource) => resource.resource_type === "podcast")
          .map((resource) => (
            <AudioPlayer
              key={resource.resource_id}
              url={resource.resource_url}
              title={resource.resource_title}
              durationSeconds={resource.duration_seconds}
              initialSeconds={resource.seconds_consumed}
              resourceId={resource.resource_id}
              onProgress={trackMedia(resource)}
            />
          ))}

        {resources
          .filter((resource) => resource.resource_type === "atividade")
          .map((resource) => (
            <div
              key={resource.resource_id}
              className="flex flex-wrap items-center justify-between gap-4 rounded-[8px] border border-line bg-white p-5"
            >
              <div className="flex items-center gap-3">
                <ListChecks className="text-brand" size={24} />
                <div>
                  <div className="font-bold text-ink">{resource.resource_title}</div>
                  <div className="text-sm text-muted">{t("Atividade prática", "Practical activity")}</div>
                </div>
              </div>
              {resource.completed ? (
                <span className="flex items-center gap-2 rounded-[8px] bg-emerald-50 px-4 py-2 font-semibold text-emerald-700">
                  <CheckCircle2 size={18} />
                  {t("Concluída", "Completed")}
                </span>
              ) : (
                <button
                  onClick={() => completeActivity(resource)}
                  className="h-11 rounded-[8px] bg-teal px-5 font-semibold text-white"
                >
                  {t("Marcar como concluída", "Mark as completed")}
                </button>
              )}
            </div>
          ))}
      </div>
    </section>
  );
};
