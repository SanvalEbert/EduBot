/*
MELHORIA (OVA nativo) — Acordeão em React (substitui o accordion Bootstrap do
leitor legado). Abre um item por vez; registra interação ao expandir.
*/
import { ChevronDown } from "lucide-react";
import { useState } from "react";

interface AccordionProps {
  items: { title: string; body: string }[];
  onInteract?: (label: string) => void;
}

export const Accordion = ({ items, onInteract }: AccordionProps) => {
  const [open, setOpen] = useState<number | null>(null);

  const toggle = (index: number, title: string) => {
    setOpen((current) => {
      const next = current === index ? null : index;
      if (next === index) onInteract?.(`Abriu o item "${title}" do acordeão`);
      return next;
    });
  };

  return (
    <div className="space-y-3">
      {items.map((item, index) => {
        const isOpen = open === index;
        return (
          <div key={index} className="overflow-hidden rounded-[8px] border border-line bg-white">
            <button
              onClick={() => toggle(index, item.title)}
              aria-expanded={isOpen}
              className={`flex w-full items-center justify-between gap-4 px-5 py-4 text-left font-semibold transition ${
                isOpen ? "bg-indigo-50 text-indigo-800" : "text-ink hover:bg-slate-50"
              }`}
            >
              {item.title}
              <ChevronDown
                size={20}
                className={`shrink-0 transition-transform ${isOpen ? "rotate-180" : ""}`}
              />
            </button>
            {isOpen && (
              <div className="border-t border-line px-5 py-4 leading-relaxed text-slate-700">
                {item.body}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
