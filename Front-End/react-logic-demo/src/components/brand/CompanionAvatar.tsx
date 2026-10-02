/*
AV.3 (Plano 3) — CompanionAvatar: UM componente para o companheiro de estudo.

Recebe `personaId` e resolve sozinho o que renderizar:
  - "edubot"            -> mascote 2D (EduBotAvatar), leve, sempre disponível;
  - "einstein"/"curie"  -> cientista 3D (Avatar3D); se o WebGL falhar, cai no 2D.

Aceita `visemeRef` (do useSpeech) para lip-sync REAL: a boca segue os visemas do
Polly, ou a alternância do fallback Web Speech. Antes essa lógica de fallback 3D->2D
vivia duplicada no PerformanceCoach; agora é única e reutilizável (leitor de OVA,
chat do tutor, dashboard, onboarding, reforço).
*/
import { MutableRefObject, Suspense, lazy, useEffect, useState } from "react";
import { EduBotAvatar } from "./EduBotAvatar";
import { AVATAR_PERSONAS } from "./avatars";

// O Avatar3D arrasta o three.js (~800 kB). Carregado sob demanda: quem usa o
// mascote EduBot (padrão) NUNCA baixa o three.js; só ao escolher Einstein/Curie.
const Avatar3D = lazy(() => import("./Avatar3D").then((m) => ({ default: m.Avatar3D })));

interface CompanionAvatarProps {
  personaId: string;
  speaking?: boolean;
  visemeRef?: MutableRefObject<string>;
  /** Lado do mascote 2D; o 3D deriva daqui uma proporção ~retrato. */
  size?: number;
}

export function CompanionAvatar({ personaId, speaking = false, visemeRef, size = 120 }: CompanionAvatarProps) {
  const persona = AVATAR_PERSONAS.find((p) => p.id === personaId);
  const [threeFailed, setThreeFailed] = useState(false);

  // Trocar para uma persona 3D depois de uma falha de WebGL deve permitir nova
  // tentativa (a falha anterior era da persona antiga).
  useEffect(() => setThreeFailed(false), [personaId]);

  if (!persona || threeFailed) {
    return <EduBotAvatar size={size} speaking={speaking} />;
  }
  return (
    // Fallback = mascote 2D enquanto o chunk do three.js carrega (ou se falhar).
    <Suspense fallback={<EduBotAvatar size={size} speaking={speaking} />}>
      <Avatar3D
        persona={persona}
        speaking={speaking}
        visemeRef={visemeRef}
        width={size}
        height={Math.round(size * 1.26)}
        onError={() => setThreeFailed(true)}
      />
    </Suspense>
  );
}
