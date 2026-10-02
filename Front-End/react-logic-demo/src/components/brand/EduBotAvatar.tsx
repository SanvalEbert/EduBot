/*
MELHORIA (Roteiro Cena 3) — Avatar animado do EduBot.

Versão do mascote com animação (flutua, pisca) e um estado "falando" que anima a
boca — sincronizada com a fala do navegador (Web Speech API). Não depende de
nenhum serviço externo; é a base do futuro avatar com voz da AWS Polly (lip-sync
por visemas).
*/
interface EduBotAvatarProps {
  size?: number;
  speaking?: boolean;
}

export const EduBotAvatar = ({ size = 120, speaking = false }: EduBotAvatarProps) => (
  <div style={{ width: size, height: size }} className="eb-float select-none">
    <style>{`
      @keyframes ebFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
      @keyframes ebBlink { 0%,92%,100%{transform:scaleY(1)} 96%{transform:scaleY(0.08)} }
      @keyframes ebTalk { 0%,100%{transform:scaleY(0.35)} 50%{transform:scaleY(1)} }
      .eb-float { animation: ebFloat 3.2s ease-in-out infinite; }
      .eb-eye { transform-box: fill-box; transform-origin: center; animation: ebBlink 4.5s ease-in-out infinite; }
      .eb-mouth-talk { transform-box: fill-box; transform-origin: center; animation: ebTalk 0.28s ease-in-out infinite; }
      /* U.7: respeita quem pediu menos movimento — desliga flutuar/piscar/falar. */
      @media (prefers-reduced-motion: reduce) {
        .eb-float, .eb-eye, .eb-mouth-talk { animation: none !important; }
      }
    `}</style>
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="EduBot">
      {/* antena */}
      <line x1="32" y1="6" x2="32" y2="14" stroke="#15beb5" strokeWidth="3" strokeLinecap="round" />
      <circle cx="32" cy="5" r="3.5" fill="#ff7b65" />

      {/* cabeça */}
      <rect x="12" y="14" width="40" height="34" rx="11" fill="#604fd8" />
      <rect x="12" y="14" width="40" height="34" rx="11" fill="url(#ebGrad)" fillOpacity="0.35" />

      {/* visor */}
      <rect x="18" y="22" width="28" height="18" rx="8" fill="#0b1030" />

      {/* olhos (piscam) */}
      <circle className="eb-eye" cx="26" cy="31" r="3.4" fill="#15beb5" />
      <circle className="eb-eye" cx="38" cy="31" r="3.4" fill="#15beb5" />

      {/* boca: sorriso quando calado; elipse animada quando falando */}
      {speaking ? (
        <ellipse className="eb-mouth-talk" cx="32" cy="36" rx="5" ry="3.2" fill="#15beb5" />
      ) : (
        <path d="M26 36c2 2 10 2 12 0" stroke="#15beb5" strokeWidth="2" strokeLinecap="round" fill="none" />
      )}

      {/* laterais */}
      <rect x="8" y="26" width="4" height="10" rx="2" fill="#604fd8" />
      <rect x="52" y="26" width="4" height="10" rx="2" fill="#604fd8" />

      {/* capelo */}
      <path d="M32 8L50 15L32 22L14 15L32 8Z" fill="#0b1030" />
      <path d="M32 12.2L44 16.9L32 21.6L20 16.9L32 12.2Z" fill="#604fd8" />
      <line x1="50" y1="15" x2="50" y2="22" stroke="#ff7b65" strokeWidth="2" strokeLinecap="round" />
      <circle cx="50" cy="23" r="2" fill="#ff7b65" />

      <defs>
        <linearGradient id="ebGrad" x1="12" y1="14" x2="52" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#8b7cff" />
          <stop offset="1" stopColor="#604fd8" />
        </linearGradient>
      </defs>
    </svg>
  </div>
);
