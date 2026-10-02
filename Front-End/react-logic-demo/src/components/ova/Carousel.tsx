/*
MELHORIA (OVA nativo) — Carrossel em React (substitui o carrossel jQuery do
leitor legado). Estado de slide em useState; setas e bolinhas de navegação no
estilo do design system.
*/
import { ChevronLeft, ChevronRight } from "lucide-react";
import { KeyboardEvent, useState } from "react";
import { CarouselItem } from "../../services/ovaContent";
import { useT } from "../../i18n";

interface CarouselProps {
  items: CarouselItem[];
  onInteract?: (label: string) => void;
}

export const Carousel = ({ items, onInteract }: CarouselProps) => {
  const t = useT();
  const [index, setIndex] = useState(0);
  if (items.length === 0) return null;

  const go = (delta: number) => {
    setIndex((current) => {
      const next = (current + delta + items.length) % items.length;
      onInteract?.(`Navegou o carrossel para o item ${next + 1}`);
      return next;
    });
  };

  const item = items[index];

  // U.7: navegação por teclado (setas) quando o carrossel tem foco.
  const onKeyDown = (e: KeyboardEvent) => {
    if (items.length < 2) return;
    if (e.key === "ArrowLeft") { e.preventDefault(); go(-1); }
    if (e.key === "ArrowRight") { e.preventDefault(); go(1); }
  };

  return (
    <div
      className="rounded-[8px] border border-line bg-slate-50 p-5 outline-none focus-visible:ring-2 focus-visible:ring-brand"
      role="group"
      aria-roledescription={t("carrossel", "carousel")}
      aria-label={t(`Item ${index + 1} de ${items.length}`, `Item ${index + 1} of ${items.length}`)}
      tabIndex={0}
      onKeyDown={onKeyDown}
    >
      <div className="grid items-center gap-5 md:grid-cols-2">
        {item.image && (
          <img
            src={item.image}
            alt={item.title ?? ""}
            className="mx-auto max-h-72 w-full rounded-[8px] object-cover"
          />
        )}
        <div className={item.image ? "" : "md:col-span-2"}>
          {item.title && <h4 className="text-xl font-bold text-ink">{item.title}</h4>}
          <p className="mt-2 leading-relaxed text-slate-700">{item.text}</p>
        </div>
      </div>

      {items.length > 1 && (
        <div className="mt-5 flex items-center justify-between">
          <button
            onClick={() => go(-1)}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-white text-brand transition hover:bg-indigo-50"
            aria-label={t("Anterior", "Previous")}
          >
            <ChevronLeft size={20} />
          </button>
          <div className="flex items-center gap-2">
            {items.map((_, dot) => (
              <button
                key={dot}
                onClick={() => setIndex(dot)}
                aria-label={t(`Ir para o item ${dot + 1}`, `Go to item ${dot + 1}`)}
                className={`h-2.5 rounded-full transition-all ${
                  dot === index ? "w-6 bg-brand" : "w-2.5 bg-slate-300 hover:bg-slate-400"
                }`}
              />
            ))}
          </div>
          <button
            onClick={() => go(1)}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-white text-brand transition hover:bg-indigo-50"
            aria-label={t("Próximo", "Next")}
          >
            <ChevronRight size={20} />
          </button>
        </div>
      )}
    </div>
  );
};
