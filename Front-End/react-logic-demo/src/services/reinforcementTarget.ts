/*
Alvo do reforço (Plano de Rastreabilidade — Fase 4).

O convite de reforço nasce no dashboard e é consumido na aba Reforço. Estes dois
componentes são carregados sob demanda (lazy) e em rotas diferentes, então o
contrato entre eles mora aqui: se um importasse o outro só para reaproveitar
estas funções, o code-splitting se desfaria (o dashboard passaria a arrastar
todo o módulo do Reforço no primeiro carregamento).
*/

// Chave de sessão com a competência escolhida pelo gatilho. Mesmo padrão do
// "Revisar" do painel de revisões: sessionStorage + navegação por hash.
export const REFORCO_COMP_KEY = "edubot.reforcoComp";

// O backend marca a competência na descrição da intervenção como "[comp:N]".
// É um marcador INTERNO: roteia o CTA e por isso precisa ser removido antes de
// o texto chegar aos olhos do aluno.
const COMP_MARKER = /\s*\[comp:(\d+)\]\s*/;

export const competencyFromDescription = (descricao: string | null | undefined): number | null => {
  const match = COMP_MARKER.exec(descricao ?? "");
  return match ? Number(match[1]) : null;
};

export const stripCompetencyMarker = (descricao: string | null | undefined): string =>
  (descricao ?? "").replace(COMP_MARKER, " ").trim();
