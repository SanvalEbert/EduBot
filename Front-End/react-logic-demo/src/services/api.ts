/*
INTEGRAÇÃO (EduBot Track) — cliente da API Flask.

Este módulo liga o frontend React (feito no Lovable) ao backend real:
  - POST /login               -> token de sessão (4.2)
  - GET  /student/me          -> perfil completo do aluno (4.2)
  - GET  /ova/<id>/resources  -> recursos do OVA com progresso (4.1)
  - POST /progress/resource   -> consumo de vídeo/podcast/atividade (4.1)
  - POST /question/ova        -> questões do quiz (sem gabarito — B9)
  - POST /question/answer     -> correção server-side (B5)
  - GET  /edubot/recommendation -> agente EduBot (4.3)

Convenções da API: o corpo das requisições é o objeto JSON puro (o envelope
[data] legado foi aposentado — A16) e o token vai no header Authorization: Bearer.
*/

import { API_BASE_URL as BASE_URL } from "./config";
// Storage encapsulado: dentro de um iframe de terceiro o acesso direto pode
// lancar SecurityError e derrubar TODA requisicao (getToken roda em todas).
import { safeGet, safeSet, safeRemove } from "./storage";

// Chaves de sessão do app. `token` era compartilhada com o front clássico
// (aposentado na Fase 5 — A17); mantida por ser o Bearer que o backend espera.
const TOKEN_KEY = "token";
const SESSION_KEY = "edubot.session";

export interface Session {
  student_id: number;
  course_id: number;
  is_admin: boolean;
}

export const getToken = () => safeGet("local", TOKEN_KEY);
export const getSession = (): Session | null => {
  const raw = safeGet("local", SESSION_KEY);
  try {
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
};

// Chaves legadas que o front clássico gravava; o app novo não as escreve mais
// (Fase 5 — A17), mas as removemos no logout para limpar sessões antigas.
const LEGACY_KEYS = ["logged", "is_admin", "course_id", "student_id"];

export const clearSession = () => {
  safeRemove("local", TOKEN_KEY);
  safeRemove("local", SESSION_KEY);
  LEGACY_KEYS.forEach((k) => safeRemove("local", k));
};

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; keepalive?: boolean } = {}
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(BASE_URL + path, {
    method: options.method ?? "GET",
    headers,
    // keepalive permite que o POST sobreviva ao fechamento da aba (usado no
    // flush final do rastreio de leitura). Diferente do navigator.sendBeacon,
    // o fetch keepalive mantém o header Authorization (aluno vem do token).
    keepalive: options.keepalive,
    // Contrato novo (A16): payload é o objeto JSON puro. O envelope [data]
    // (herança do front jQuery) foi aposentado; o backend ainda o aceita por
    // compatibilidade até o legado sair (Fase 5).
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined
  });

  if (response.status === 401) {
    clearSession();
    throw new ApiError(401, "Sessão expirada — faça login novamente.");
  }
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text || `Erro ${response.status}`);
  }
  return (await response.json()) as T;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// U.1: o backend recusa o quiz travado com 403 + {error:"quiz_locked", gate, perc}.
// Este helper extrai essa info do corpo do ApiError (ou null se for outro erro).
export interface QuizLock {
  gate: number;
  perc: number;
}
export function quizLockFromError(err: unknown): QuizLock | null {
  if (!(err instanceof ApiError) || err.status !== 403) return null;
  try {
    const body = JSON.parse(err.message);
    if (body?.error === "quiz_locked") return { gate: body.gate ?? 0, perc: body.perc ?? 0 };
  } catch {
    /* corpo não-JSON */
  }
  return null;
}

// Fase 4 (A12): idioma atual (mesma chave do i18n.tsx). As rotas de CONTEÚDO
// recebem ?lang= e o backend serve as traduções do banco com fallback PT —
// o dicionário manual contentDict.ts foi aposentado.
const LANG_KEY = "edubot.lang";
const currentLang = () => (safeGet("local", LANG_KEY) === "en" ? "en" : "pt");
const withLang = (path: string) =>
  `${path}${path.includes("?") ? "&" : "?"}lang=${currentLang()}`;

// ---------------------------------------------------------------------------
// Tipos espelhando as respostas do backend
// ---------------------------------------------------------------------------

export interface ResourceState {
  resource_id: number;
  titulo: string;
  tipo: "texto" | "video" | "podcast" | "quiz" | "atividade";
  url: string | null;
  media_type: string | null;
  perc_consumido: number;
  segundos_consumidos: number;
  consumido: boolean;
  concluido: boolean;
}

export interface OvaState {
  ova_id: number;
  ova_name: string;
  link: string;
  read_time: number;
  perc_scrolled: number;
  completed: boolean;
  recursos: ResourceState[];
}

export interface CompetencyState {
  competency_id: number;
  nome: string;
  // Plano 5 (17.1): assunto/disciplina da competência — permite agrupar
  // acertos/erros "por assunto". Opcionais: backend antigo não envia (o front
  // degrada para não mostrar a quebra por assunto).
  subject_id?: number;
  subject_nome?: string;
  acertos: number;
  total_questoes: number;
  status: "não iniciada" | "em desenvolvimento" | "desenvolvida";
  // Desempenho no quiz por competência (vindos de `attempts` no backend)
  tentativas?: number;
  erros?: number;
  taxa_erro?: number | null;
  // D.2: domínio estimado (0..1) por BKT; null quando ainda não há sinal de
  // mastery (o front mostra "domínio: 74%" quando presente).
  dominio_estimado?: number | null;
}

export interface InterventionState {
  data: string;
  tipo: string;
  descricao: string | null;
  resultado: string | null;
}

export interface StudentProfile {
  estudante: { student_id: number; nome: string; ra: string; curso: string | null; role: string; persona: string };
  features?: { companion: boolean };
  dias_sem_acesso: number | null;
  recursos: {
    total: number;
    consumidos: number;
    percentual_consumido: number;
    por_tipo: Record<string, { total: number; consumidos: number; concluidos: number }>;
  };
  preferencia_formato: string | null;
  quiz: { tentativas: number; erros: number; taxa_erro: number | null };
  atividades_pendentes: number;
  ovas: OvaState[];
  competencias: CompetencyState[];
  historico_intervencoes: InterventionState[];
}

export interface Recommendation {
  tipo: string;
  prioridade: "alta" | "media" | "baixa";
  titulo: string;
  mensagem_aluno: string;
  acoes: string[];
  formato_preferido: string | null;
  justificativa: string;
  model_id: string;
  mock: boolean;
}

export interface OvaQuestion {
  question_id: number;
  statement: string;
  alternatives: string[];
  answered: boolean;
  competency_id: number;
}

export interface OvaResource {
  resource_id: number;
  resource_type: ResourceState["tipo"];
  resource_title: string;
  resource_url: string | null;
  media_type: string | null;
  duration_seconds: number | null;
  perc_consumed: number;
  seconds_consumed: number;
  completed: boolean;
  // Fase 1: consumo real de vídeo (opcionais — backend antigo não os envia).
  watched_seconds?: number;
  coverage_perc?: number;
  coverage_bitmap?: string | null;
  last_position_seconds?: number | null;
}

// ---------------------------------------------------------------------------
// Chamadas
// ---------------------------------------------------------------------------

export async function login(ra: string, password: string): Promise<Session> {
  const data = await request<{ ids: { student_id: number; course_id: number }; is_admin: boolean; token: string }>(
    "/login",
    { method: "POST", body: { ra, password } }
  );
  const session: Session = {
    student_id: data.ids.student_id,
    course_id: data.ids.course_id,
    is_admin: data.is_admin
  };
  safeSet("local", TOKEN_KEY, data.token);
  safeSet("local", SESSION_KEY, JSON.stringify(session));
  // (Fase 5 — A17) As chaves de compatibilidade com o front clássico deixaram
  // de ser gravadas: o app React é único e resolve tudo via SESSION_KEY/token.
  return session;
}

export const getMe = () => request<StudentProfile>(withLang("/student/me"));

export const getEdubotRecommendation = () =>
  request<{ recommendation: Recommendation }>(withLang("/edubot/recommendation"));

// A13 — proatividade: intervenções NÃO LIDAS que o EduBot criou por conta
// própria (pós-quiz, conclusão de OVA, varredura agendada). O dashboard as
// exibe para o aluno; `ack` marca como lida.
export interface UnreadIntervention {
  intervention_id: number;
  data: string;
  tipo: string;
  descricao: string | null;
  resultado: string | null;
}

export const getInterventions = () =>
  request<{ interventions: UnreadIntervention[] }>("/edubot/interventions");

export const ackIntervention = (interventionId: number) =>
  request<{ ok: boolean }>("/edubot/intervention/ack", {
    method: "POST",
    body: { intervention_id: interventionId }
  });

// Fala do EduBot (coach) sobre o progresso, gerada por IA sob demanda (Bedrock).
// message=null quando a IA não está disponível — o frontend usa o texto local.
export const getCoachMessage = (lang: string) =>
  request<{ message: string | null; ai: boolean; model_id?: string }>(
    `/edubot/coach-message?lang=${lang}`
  );

// ---------------------------------------------------------------------------
// MELHORIA (OVA personalizada): agente de tool-use que monta a OVA de reforço
// ---------------------------------------------------------------------------

export interface PersonalizedOVASummary {
  personalized_ova_id: number;
  titulo: string;
  status: string;
  created_at: string;
  competencia: string | null;
}

export interface PersonalizedOVAContent {
  personalized_ova_id: number;
  titulo: string;
  mensagem_aluno: string | null;
  justificativa: string | null;
  status: string;
  created_at: string;
  competencia: { competency_id: number; nome: string } | null;
  // P.2 — formato pelo qual a trilha começou (chip "no seu formato").
  formato_preferido: string | null;
  recursos: OvaResource[];
  questoes: OvaQuestion[];
}

export interface CreatedPersonalizedOVA {
  personalized_ova_id: number;
  titulo: string;
  mensagem_aluno: string;
  justificativa: string;
  target_competency_id: number | null;
  itens_recursos: number;
  itens_questoes: number;
  mock: boolean;
  model_id: string;
  formato_preferido: string | null;
}

// Dispara o agente: diagnostica o assunto fraco, seleciona conteúdo e persiste.
// Fase 4 do Plano de Rastreabilidade: `competencyId` vem do convite de reforço
// (o aluno acabou de errar AQUELA competência), para a trilha ser sobre o que
// ele estudou agora — sem ele, o agente escolhe a mais fraca do curso inteiro.
export const createPersonalizedOVA = (competencyId?: number) =>
  request<CreatedPersonalizedOVA>("/edubot/personalized-ova", {
    method: "POST",
    body: competencyId != null ? { competency_id: competencyId } : {}
  });

// Materiais externos (artigos científicos) recomendados por competência
export interface ExternalResource {
  titulo: string;
  url: string | null;
  fonte: string;
  ano: number | null;
}

export const getExternalResources = (competencyId: number) =>
  request<{ competency_id: number; competencia: string; resultados: ExternalResource[] }>(
    `/edubot/external-resources?competency_id=${competencyId}`
  );

export const listPersonalizedOVAs = () =>
  request<PersonalizedOVASummary[]>(withLang("/personalized-ova"));

export const getPersonalizedOVA = (id: number) =>
  request<PersonalizedOVAContent>(withLang(`/personalized-ova/${id}`));

export const getOVAResources = (ovaId: number) =>
  request<OvaResource[]>(withLang(`/ova/${ovaId}/resources`));

// Fase 1 do Plano de Rastreabilidade: além dos campos legados, o player de vídeo
// manda o consumo REAL — `watched_seconds_delta` (o servidor SOMA) e o
// `coverage_bitmap` acumulado da sessão (o servidor faz OR). Todos opcionais:
// áudio e atividade seguem usando só os campos antigos.
export const saveResourceProgress = (
  data: {
    resource_id: number;
    perc_consumed?: number;
    seconds_consumed?: number;
    completed?: boolean;
    watched_seconds_delta?: number;
    coverage_bitmap?: string;
    last_position_s?: number;
    playback_rate?: number;
  },
  opts: { keepalive?: boolean } = {}
) => request<string>("/progress/resource", { method: "POST", body: data, keepalive: opts.keepalive });

// Contrato novo (A1): o tempo de leitura vai como `seconds_delta` (segundos
// desde o último sync) e o servidor ACUMULA. `keepalive` é usado no flush final
// (unload) para não perder os últimos segundos ao fechar a aba.
export const saveOVAProgress = (
  data: {
    ova_id: number;
    seconds_delta?: number;
    perc_scrolled?: number;
    completed?: boolean;
  },
  opts: { keepalive?: boolean } = {}
) => request<string>(withLang("/progress/ova"), { method: "POST", body: data, keepalive: opts.keepalive });

// Fase 2 do Plano de Rastreabilidade: tempo de leitura POR SEÇÃO do OVA (o que
// responde "onde o aluno travou"). Vai em lote, com a mesma semântica de delta
// do /progress/ova — o servidor SOMA.
export interface SectionProgressInput {
  section_id: string;
  section_index: number;
  seconds_delta: number;
  max_scroll_perc: number;
  visits_delta: number;
}

export const saveSectionProgress = (
  ovaId: number,
  sections: SectionProgressInput[],
  opts: { keepalive?: boolean } = {}
) =>
  request<{ saved: number }>("/progress/ova-section", {
    method: "POST",
    body: { ova_id: ovaId, sections },
    keepalive: opts.keepalive
  });

// A.6: o aluno é resolvido pelo token no backend (g.student). Não enviamos mais
// student_id no corpo — o backend já o ignorava, mas o contrato mentia.
export const getOVAQuestions = (ovaId: number) =>
  request<OvaQuestion[]>(withLang("/question/ova"), { method: "POST", body: { ova_id: ovaId } });

// D.1: `responseMs` (tempo do render da questão ao submit) é o sinal de esforço
// que alimenta os eventos `answered` e o mastery no backend. Opcional.
// G.6: a resposta traz `gamification` (XP ganho, conquistas novas) p/ o micro-momento.
export const answerQuestion = (questionId: number, selected: string, responseMs?: number) =>
  request<{ is_correct: boolean; gamification: GamificationAward | null }>(withLang("/question/answer"), {
    method: "POST",
    body: { question_id: questionId, selected, response_ms: responseMs }
  });

// A3: o aluno é resolvido pelo token no backend — não enviamos student_id.
export const registerInteraction = (ovaId: number, action: string) =>
  request<string>("/interaction/register", {
    method: "POST",
    body: { ova_id: ovaId, action }
  });

// ---------------------------------------------------------------------------
// Painel do Tutor (Cena 4) — visão de turma + central de alertas
// ---------------------------------------------------------------------------
export interface TurmaStudent {
  student_id: number;
  nome: string;
  ra: string;
  dias_sem_acesso: number | null;
  consumo_percentual: number;
  taxa_erro: number | null;
  alertas_abertos: number;
  // Fase 3 do Plano de Rastreabilidade — risco COMPOSTO. `componentes` diz por
  // que o aluno está em risco (ausência? erro? esquecimento?), o que muda a
  // intervenção do professor. Opcional: backend antigo não envia.
  revisoes_vencidas?: number;
  risco?: StudentRisk;
}

export interface StudentRisk {
  score: number;
  em_risco: boolean;
  componentes: Record<string, number>;
  principal: string | null;
}

export interface TutorAlert {
  alert_id: number;
  student_id: number;
  aluno: string;
  type: string;
  message: string;
  severity: string;
  created_at: string;
  read: boolean;
}

export const getTurma = () => request<{ total: number; alunos: TurmaStudent[] }>("/tutor/turma");
export const getTutorAlerts = () => request<{ alertas: TutorAlert[] }>("/tutor/alerts");

// Plano 5 (19.1) — perfil detalhado de UM aluno para o professor. Mesmo shape de
// /student/me, então o detalhe reaproveita os componentes de desempenho do aluno.
// Respeita ?lang= (nomes de OVA/recurso/competência traduzidos).
export const getTutorStudent = (studentId: number) =>
  request<StudentProfile>(withLang(`/tutor/student/${studentId}`));

// Plano 5 (20.1) — rollup da turma para o painel do GESTOR.
export interface SubjectRollup {
  subject_id: number;
  subject_nome: string;
  acertos: number;
  erros: number;
  tentativas: number;
  total_questoes: number;
  taxa_erro: number | null;
  dominio_medio: number | null;
}
export interface TutorOverview {
  turma: { alunos_ativos: number; em_risco: number; alertas_abertos: number };
  quiz: { acertos: number; erros: number; tentativas: number; taxa_erro: number | null };
  consumo: { percentual_medio: number };
  por_assunto: SubjectRollup[];
  // Catálogo: quanto de cada sinal está registrado hoje (chaves conhecidas do backend).
  rastreamento: Record<string, number>;
  // Fase 2 — onde a turma trava (maior tempo médio + releitura por seção).
  secoes_dificeis?: HardSection[];
  // Fase 1 — consumo REAL de vídeo (cobertura, não posição alcançada).
  video?: { cobertura_media: number; segundos_assistidos: number; ponto_abandono_medio: number | null };
  // Fase 4 — competências que o reforço não consegue atender (lacuna editorial).
  lacunas_conteudo?: ContentGap[];
}

export interface HardSection {
  ova_id: number;
  ova_nome: string;
  section_id: string;
  section_index: number;
  alunos: number;
  segundos_medios: number;
  releituras_por_aluno: number;
}

export interface ContentGap {
  competency_id: number;
  nome: string;
  assunto: string;
  questoes: number;
  formatos: string[];
  ok: boolean;
}
export const getTutorOverview = () => request<TutorOverview>("/tutor/overview");
export const evaluateTurma = () =>
  request<{ alertas_criados: number }>("/tutor/evaluate", { method: "POST" });

// A.4: marca um alerta como tratado (read=true). Destrava a dedup por tipo — sem
// isto o 1º alerta de cada tipo suprimia todos os futuros do mesmo aluno.
export const ackTutorAlert = (alertId: number) =>
  request<{ ok: boolean }>("/tutor/alert/ack", { method: "POST", body: { alert_id: alertId } });

// D.6 — heatmap turma × competência (domínio estimado por BKT).
export interface MasteryColumn {
  competency_id: number;
  nome: string;
  // Assunto/disciplina (Plano 5) — para agrupar as colunas do heatmap por matéria.
  subject_id?: number;
  subject_nome?: string;
  n: number;
  media: number | null;
  distribuicao: { fragil: number; em_desenvolvimento: number; desenvolvida: number };
}
export interface MasteryRow {
  student_id: number;
  nome: string;
  celulas: { competency_id: number; p_mastery: number | null; status: string | null }[];
}
export const getTutorMastery = () =>
  request<{ competencias: MasteryColumn[]; matriz: MasteryRow[] }>("/tutor/mastery");

// B.5 — fila de aprovação: ações de tier alto propostas pelo EduBot.
export interface QueueItem {
  alert_id: number;
  student_id: number;
  aluno: string;
  type: string;
  message: string;
  severity: string;
  proposed_action: { type: string; mensagem_aluno?: string; justificativa?: string } | null;
  created_at: string;
}
export const getTutorQueue = () => request<{ fila: QueueItem[] }>("/tutor/queue");

// B.6 — KPI do agente: taxa de aceitação das intervenções por tipo.
export interface AgentKpi {
  tipo: string;
  total: number;
  classificadas: number;
  aceita: number;
  melhorou: number;
  dispensada: number;
  expirada: number;
  pendente: number;
  taxa_aceitacao: number | null;
}
// P.3 — mesmo shape, agrupado por formato SUGERIDO (video/texto/podcast).
export interface AgentKpiByFormat extends Omit<AgentKpi, "tipo"> {
  formato: string;
}
export const getAgentKpi = () =>
  request<{ kpis: AgentKpi[]; kpis_por_formato: AgentKpiByFormat[] }>("/tutor/agent-kpi");
export const approveQueueItem = (alertId: number) =>
  request<{ ok: boolean }>("/tutor/queue/approve", { method: "POST", body: { alert_id: alertId } });
export const rejectQueueItem = (alertId: number) =>
  request<{ ok: boolean }>("/tutor/queue/reject", { method: "POST", body: { alert_id: alertId } });

// ---------------------------------------------------------------------------
// Tutor IA por OVA — chat de tutoria restrito ao conteúdo do OVA consumido
// ---------------------------------------------------------------------------
export interface TutorMessage {
  role: "user" | "assistant";
  content: string;
}

export interface TutorSource {
  secao: string;
  trecho: string;
}

export interface TutorReply {
  reply: string;
  ova_id: number;
  ova_name: string;
  model_id: string;
  mock: boolean;
  sources: TutorSource[];
}

// Envia a pergunta + o histórico + o material (context) do OVA. O backend
// responde como tutor preso ao conteúdo (ver edubot_agent/tutor.py).
export const tutorChat = (ovaId: number, context: string, messages: TutorMessage[], persona?: string) =>
  request<TutorReply>(withLang("/edubot/tutor-chat"), {
    method: "POST",
    body: { ova_id: ovaId, context, messages, persona }
  });

// ---------------------------------------------------------------------------
// D.1 — eventos de aprendizado (xAPI-lite). O front acumula eventos e faz flush
// em lote (services/events.ts); esta é a chamada crua para POST /events.
// ---------------------------------------------------------------------------
export interface LearningEventInput {
  verb: string;
  object_type: string;
  object_id?: number | null;
  context?: Record<string, unknown> | null;
  occurred_at?: string;
}

export const postEvents = (events: LearningEventInput[], opts: { keepalive?: boolean } = {}) =>
  request<{ accepted: number; errors: number }>("/events", {
    method: "POST",
    body: { events },
    keepalive: opts.keepalive
  });

// ---------------------------------------------------------------------------
// D.5 — consentimento (LGPD) e direitos do titular.
// ---------------------------------------------------------------------------
export interface Consent {
  // `ranking_turma` é criado ao entrar no ranking (gamificação) — precisa constar
  // aqui e no MyDataPanel, senão o painel "Meus dados" quebra ao renderizá-lo.
  purpose: "tracking_pedagogico" | "ia_sobre_dados" | "imagem_voz" | "ranking_turma";
  granted: boolean;
  opt_in: boolean;
  granted_at: string | null;
  revoked_at: string | null;
}

export const getConsents = () => request<{ consents: Consent[] }>("/consents");

// Fase 0 (E0.5) do Plano de Rastreabilidade: o BACKEND é a fonte de verdade do
// consentimento; a flag em localStorage é só cache para não piscar o modal.
// Sem isto, trocar de navegador (ou um POST que falhou depois de a flag ter sido
// gravada) deixava o aluno sem consentimento registrado e o modal nunca voltava.
// `granted_at` de tracking_pedagogico só existe se houve gravação real — é o
// sinal de que o aluno de fato respondeu o modal (os defaults vêm sem data).
export const hasRecordedConsent = async (): Promise<boolean> => {
  const { consents } = await getConsents();
  return consents.some((c) => c.purpose === "tracking_pedagogico" && c.granted_at !== null);
};

export const setConsent = (purpose: Consent["purpose"], granted: boolean) =>
  request<{ consents: Consent[] }>("/consents", {
    method: "POST",
    body: { purpose, granted }
  });

export const requestDataDeletion = () =>
  request<{ ok: boolean; status: string }>("/student/me/delete-request", { method: "POST" });

// ---------------------------------------------------------------------------
// D.3 — revisão espaçada: agenda "Revisões desta semana" do aluno logado.
// ---------------------------------------------------------------------------
export interface ReviewItem {
  review_id: number;
  competency_id: number;
  competencia: string | null;
  // OVA a revisar (o quiz que cobre a competência) — alimenta o botão "Revisar".
  ova_id: number | null;
  due_date: string;
  status: string;
  vencida: boolean;
  interval_days: number;
}

export const getReviews = () => request<{ reviews: ReviewItem[] }>(withLang("/reviews"));

// ---------------------------------------------------------------------------
// H.1 (Plano 2) — tendência de domínio (setas na teia de competências).
// ---------------------------------------------------------------------------
export interface MasteryTrendItem {
  competency_id: number;
  competencia: string | null;
  atual: number;
  anterior: number;
  delta: number;
  direcao: "up" | "down" | "flat";
}

export const getMasteryTrend = () =>
  request<{ trend: MasteryTrendItem[] }>(withLang("/mastery/trend"));

// ---------------------------------------------------------------------------
// Etapa 8 (Plano 2) — gamificação: XP, nível, sequência, conquistas, ranking.
// ---------------------------------------------------------------------------
export interface AchievementState {
  id: string;
  nome: string;
  unlocked: boolean;
}
export interface PersonaUnlock {
  id: string;
  unlock_level: number;
  unlocked: boolean;
}
export interface TitleOption {
  id: string;
  titulo: string;
}
export interface GamificationMe {
  enabled: boolean;
  level: number;
  xp_total: number;
  into_level: number;
  level_span: number;
  next_level_at: number;
  xp_week: number;
  streak: { current_days: number; best_days: number; shield_available: boolean };
  achievements: AchievementState[];
  personas: PersonaUnlock[];
  available_titles: TitleOption[];
  title: string | null;
  title_id: string | null;
  nickname: string | null;
}
export interface LeaderboardEntry {
  apelido: string;
  xp_semana: number;
  nivel: number;
  eu: boolean;
}
export interface Leaderboard {
  enabled: boolean;
  week_start?: string;
  participando?: boolean;
  top: LeaderboardEntry[];
  me: { rank: number | null; top_percent: number | null; xp_semana: number; nivel: number } | null;
}
// Resumo devolvido pelo /question/answer p/ o micro-momento do quiz (G.6).
export interface GamificationAward {
  xp_awarded: number;
  achievements: string[];
  streak: number;
}

export const getGamificationMe = () =>
  request<GamificationMe>(withLang("/gamification/me"));
export const getLeaderboard = () =>
  request<Leaderboard>("/gamification/leaderboard");
export const participateRanking = (nickname: string) =>
  request<{ ok: boolean; nickname: string; participando: boolean }>(
    "/gamification/participate", { method: "POST", body: { nickname } }
  );
export const setActiveTitle = (titleId: string | null) =>
  request<{ ok: boolean; title: string | null }>(
    "/gamification/title", { method: "POST", body: { title_id: titleId } }
  );

// ---------------------------------------------------------------------------
// E.3 (Plano 2) — metas semanais.
// ---------------------------------------------------------------------------
export interface WeeklyGoal {
  goal_id: number;
  kind: string;
  titulo: string;
  target: number;
  progress: number;
  status: string;
}
export const getGoals = () =>
  request<{ enabled: boolean; goals: WeeklyGoal[] }>(withLang("/goals"));
export const acceptGoal = (goalId: number) =>
  request<{ ok: boolean; goal_id: number; status: string }>(
    "/goals/accept", { method: "POST", body: { goal_id: goalId } }
  );

// R.3 — modo desafio: só questões difíceis de competência dominada (403 se locked).
export const getChallengeQuestions = (ovaId: number) =>
  request<OvaQuestion[]>(withLang("/question/ova"), {
    method: "POST", body: { ova_id: ovaId, desafio: true }
  });

// E.4 — engajamento da turma (tutor).
export interface TutorEngagement {
  total_alunos: number;
  participacao_ranking: { opt_in: number; total: number };
  distribuicao_sequencia: Record<string, number>;
  xp_medio_semana: number;
  em_risco: { student_id: number; nome: string; sequencia: number }[];
  antes_depois: { dias_ativos_antes: number; dias_ativos_depois: number };
  // EX.4 (Plano 3) — uso do companheiro de estudo (de learning_events).
  companheiro: {
    alunos_ativos: number;
    total_alunos: number;
    secoes_ouvidas_semana: number;
    falas_ouvidas_semana: number;
    explicacoes_semana: number;
  };
}
export const getTutorEngagement = () =>
  request<TutorEngagement>("/tutor/engagement");

// ---------------------------------------------------------------------------
// V.1 — voz do EduBot (AWS Polly + visemas). available:false => o front usa o
// fallback (Web Speech). O mp3 é servido em audio_url (caminho relativo à API).
// ---------------------------------------------------------------------------
export interface Viseme {
  time_ms: number;
  viseme: string;
}
export interface SpeakResult {
  available: boolean;
  audio_url?: string;
  visemes?: Viseme[];
  cached?: boolean;
}
// URL absoluta de um recurso servido pela API (ex.: o mp3 da voz).
export const apiUrl = (path: string) => BASE_URL + path;

export const synthesizeSpeech = (text: string, lang: "pt" | "en", persona?: string) =>
  request<SpeakResult>("/edubot/speak", { method: "POST", body: { text, lang, persona } });

// AV.2 (Plano 3) — persona do companheiro de estudo (persistida no aluno).
export const setStudentPersona = (persona: string) =>
  request<{ persona: string }>("/student/persona", { method: "POST", body: { persona } });
