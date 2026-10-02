/*
MELHORIA (Identidade do agente) — Logo/mascote do EduBot.

SVG próprio (sem depender de arquivo de imagem): uma cabeça de robô simpática
com "capelo" acadêmico, nas cores da marca (brand #604fd8 / teal #15beb5 /
coral #ff7b65). Serve de identidade nos cabeçalhos do agente e de base para o
futuro avatar animado.
*/
interface EduBotLogoProps {
  size?: number;
  className?: string;
}

export const EduBotLogo = ({ size = 40, className }: EduBotLogoProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 64 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    role="img"
    aria-label="EduBot"
  >
    {/* antena */}
    <line x1="32" y1="6" x2="32" y2="14" stroke="#15beb5" strokeWidth="3" strokeLinecap="round" />
    <circle cx="32" cy="5" r="3.5" fill="#ff7b65" />

    {/* cabeça do robô */}
    <rect x="12" y="14" width="40" height="34" rx="11" fill="#604fd8" />
    <rect x="12" y="14" width="40" height="34" rx="11" fill="url(#eduBotGrad)" fillOpacity="0.35" />

    {/* visor / rosto */}
    <rect x="18" y="22" width="28" height="18" rx="8" fill="#0b1030" />

    {/* olhos */}
    <circle cx="26" cy="31" r="3.4" fill="#15beb5" />
    <circle cx="38" cy="31" r="3.4" fill="#15beb5" />
    {/* sorriso */}
    <path d="M26 36c2 2 10 2 12 0" stroke="#15beb5" strokeWidth="2" strokeLinecap="round" fill="none" />

    {/* orelhas / laterais */}
    <rect x="8" y="26" width="4" height="10" rx="2" fill="#604fd8" />
    <rect x="52" y="26" width="4" height="10" rx="2" fill="#604fd8" />

    {/* capelo acadêmico */}
    <path d="M32 8L50 15L32 22L14 15L32 8Z" fill="#0b1030" />
    <path d="M32 12.2L44 16.9L32 21.6L20 16.9L32 12.2Z" fill="#604fd8" />
    <line x1="50" y1="15" x2="50" y2="22" stroke="#ff7b65" strokeWidth="2" strokeLinecap="round" />
    <circle cx="50" cy="23" r="2" fill="#ff7b65" />

    <defs>
      <linearGradient id="eduBotGrad" x1="12" y1="14" x2="52" y2="48" gradientUnits="userSpaceOnUse">
        <stop stopColor="#8b7cff" />
        <stop offset="1" stopColor="#604fd8" />
      </linearGradient>
    </defs>
  </svg>
);
