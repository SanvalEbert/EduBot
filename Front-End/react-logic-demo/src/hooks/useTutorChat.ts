/*
CP.4 (Plano 3) — estado do chat do tutor ELEVADO para fora do painel.

Antes o histórico vivia dentro do TutorChat: fechar/reabrir o painel desmontava o
componente e a conversa se PERDIA (M6). Agora o estado mora neste hook, chamado
pelo OvaReader (que permanece montado) — o painel do tutor vira apenas a UI. Fechar
e reabrir mantém a conversa; e o "Explique esta seção" (no corpo do OVA) injeta uma
pergunta no MESMO chat.

A persona (AV.2) segue no `ask`: o tutor responde no estilo do personagem escolhido.
*/
import { useCallback, useState } from "react";
import { TutorMessage, TutorSource, tutorChat } from "../services/api";
import { useLanguage, useT } from "../i18n";

export type ChatMessage = TutorMessage & { sources?: TutorSource[] };

export function useTutorChat(ovaId: number, ovaName: string, context: string, personaId: string) {
  const t = useT();
  const { lang } = useLanguage();
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      role: "assistant",
      content: t(
        `Olá! Posso conversar com você sobre o que está lendo agora, em "${ovaName}". Pergunte o que quiser sobre este conteúdo. 😊`,
        `Hi! I can talk with you about what you're reading now, in "${ovaName}". Ask anything about this content. 😊`
      ),
    },
  ]);
  const [loading, setLoading] = useState(false);

  // Retorna true se a resposta chegou; false em falha (o chamador mostra o toast).
  const ask = useCallback(
    async (question: string): Promise<boolean> => {
      const text = question.trim();
      if (!text || loading) return false;
      const history: ChatMessage[] = [...messages, { role: "user", content: text }];
      setMessages(history);
      setLoading(true);
      try {
        // Envia só o diálogo real (sem a saudação inicial sintética).
        const dialog: TutorMessage[] = history
          .filter((m, i) => !(i === 0 && m.role === "assistant"))
          .map((m) => ({ role: m.role, content: m.content }));
        const { reply, sources } = await tutorChat(ovaId, context, dialog, personaId);
        setMessages((cur) => [...cur, { role: "assistant", content: reply, sources }]);
        return true;
      } catch {
        setMessages((cur) => cur.slice(0, -1)); // remove a pergunta não respondida
        return false;
      } finally {
        setLoading(false);
      }
    },
    [messages, loading, ovaId, context, personaId, lang]
  );

  return { messages, loading, ask };
}
