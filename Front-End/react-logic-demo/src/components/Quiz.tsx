/*
INTEGRAÇÃO (B5/B9) — O quiz deixou de usar questões fictícias corrigidas no
navegador: as questões vêm de POST /question/ova (SEM o gabarito) e cada
resposta é corrigida pelo SERVIDOR via POST /question/answer, que também
registra a tentativa (alimentando a regra "errou > 50% do quiz" do EduBot).
*/
import { Trophy } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  OvaQuestion,
  QuizLock,
  StudentProfile,
  answerQuestion,
  getChallengeQuestions,
  getOVAQuestions,
  getSession,
  quizLockFromError,
  registerInteraction
} from "../services/api";
import { useToast } from "./ui/Toast";
import { useT } from "../i18n";
import { safeGet, safeSet, safeRemove } from "../services/storage";

interface QuizProps {
  profile: StudentProfile;
  onTracked: () => void;
}

const LETTERS = "abcdefghijklmnopqrstuvwxyz";

interface QuizResult {
  correct: number;
  wrong: number;
  score: number;
  xp: number;                 // G.6 — XP de esforço ganho ao finalizar
  achievements: string[];     // conquistas novas desbloqueadas
}

// Chave escrita pelo ReviewsPanel ("Revisar") — o OVA a abrir ao chegar no Quiz.
const REVIEW_OVA_KEY = "edubot.reviewOva";

export const Quiz = ({ profile, onTracked }: QuizProps) => {
  const t = useT();
  // Se o aluno clicou em "Revisar" no painel de revisões, abre já no OVA daquela
  // competência (lê e limpa a chave uma única vez).
  const [activeOvaId, setActiveOvaId] = useState(() => {
    const target = safeGet("session", REVIEW_OVA_KEY);
    if (target) {
      safeRemove("session", REVIEW_OVA_KEY);
      const id = Number(target);
      if (profile.ovas.some((o) => o.ova_id === id)) return id;
    }
    return profile.ovas[0]?.ova_id ?? 0;
  });
  const [questions, setQuestions] = useState<OvaQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [feedback, setFeedback] = useState<Record<number, boolean>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // U.1: quando o quiz está travado (leitura insuficiente), o backend devolve
  // 403 com gate/perc — mostramos o motivo em vez de uma lista vazia.
  const [lock, setLock] = useState<QuizLock | null>(null);
  // R.3: modo desafio (só questões difíceis de competência dominada).
  const [challenge, setChallenge] = useState(false);
  const [challengeLocked, setChallengeLocked] = useState(false);

  const session = getSession();
  const toast = useToast();
  // Última alternativa submetida por questão — evita reenviar a mesma resposta
  // a cada clique em "Finalizar", que duplicava as tentativas no servidor (A7).
  const submittedRef = useRef<Record<number, number>>({});
  // D.1: instante em que as questões carregaram — base do response_ms (esforço).
  const loadedAtRef = useRef<number>(Date.now());

  useEffect(() => {
    if (!activeOvaId || !session) return;
    setAnswers({});
    setFeedback({});
    setResult(null);
    setLock(null);
    setChallengeLocked(false);
    submittedRef.current = {};
    const fetcher = challenge ? getChallengeQuestions(activeOvaId) : getOVAQuestions(activeOvaId);
    fetcher
      .then((qs) => {
        setQuestions(qs);
        setLock(null);
        loadedAtRef.current = Date.now();
      })
      .catch((err) => {
        setQuestions([]);
        // AUDITORIA P2 (R.3): o gate de leitura (U.1) TAMBÉM devolve 403 — o
        // corpo distingue: quiz_locked traz {gate, perc}; challenge_locked não.
        // Sem essa checagem, um quiz não lido em modo desafio mostrava a
        // mensagem errada ("domine a competência" em vez de "leia o conteúdo").
        const gateLock = quizLockFromError(err);
        if (gateLock) setLock(gateLock);
        else if (challenge && (err as { status?: number }).status === 403) setChallengeLocked(true);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeOvaId, challenge]);

  const finishQuiz = async () => {
    if (!session) return;
    setSubmitting(true);
    const newFeedback: Record<number, boolean> = { ...feedback };
    let failed = false;
    let submittedAny = false;
    let xpGained = 0;
    const newAchievements: string[] = [];

    // Cada questão é corrigida pelo backend — o gabarito nunca chega ao navegador
    for (const question of questions) {
      const selectedIndex = answers[question.question_id];
      const selectedLetter = LETTERS[selectedIndex];
      // Só reenvia se a resposta mudou desde a última submissão (A7)
      if (submittedRef.current[question.question_id] === selectedIndex) continue;
      try {
        const responseMs = Date.now() - loadedAtRef.current;
        const graded = await answerQuestion(question.question_id, selectedLetter, responseMs);
        newFeedback[question.question_id] = graded.is_correct;
        submittedRef.current[question.question_id] = selectedIndex;
        submittedAny = true;
        // Fase 0 (E0.2) do Plano de Rastreabilidade: base individual do esforço.
        // Sem reiniciar aqui, TODAS as questões do lote recebiam o mesmo
        // `Date.now() - loadedAt` (o tempo do quiz inteiro), inflando o esforço
        // médio e divergindo da semântica do OvaQuiz. Agora as duas telas medem
        // a mesma coisa: o tempo desta questão.
        loadedAtRef.current = Date.now();
        // G.6 — acumula o XP de esforço e as conquistas devolvidas pelo backend
        if (graded.gamification) {
          xpGained += graded.gamification.xp_awarded;
          newAchievements.push(...graded.gamification.achievements);
        }
      } catch (error) {
        console.error(error);
        failed = true;
      }
    }

    if (failed) toast.error(t("Algumas respostas não puderam ser corrigidas. Verifique a conexão.", "Some answers couldn't be graded. Check your connection."));
    setFeedback(newFeedback);
    // Nota calculada sobre TODAS as respostas (não só as recém-enviadas)
    const correct = questions.reduce((acc, q) => acc + (newFeedback[q.question_id] ? 1 : 0), 0);
    setResult({
      correct,
      wrong: questions.length - correct,
      score: Number(((correct / Math.max(questions.length, 1)) * 10).toFixed(1)),
      xp: xpGained,
      achievements: newAchievements
    });
    setSubmitting(false);
    if (submittedAny) {
      registerInteraction(activeOvaId, "quiz_submitted").catch(() => undefined);
      onTracked();
    }
  };

  return (
    <section className="grid gap-6 xl:grid-cols-[1fr_360px]">
      <div>
        <h1 className="text-3xl font-bold text-ink">Quiz</h1>
        <p className="mt-2 text-muted">{t("Questões corrigidas pelo servidor — cada tentativa alimenta o EduBot.", "Server-graded questions — each attempt feeds EduBot.")}</p>

        <div className="mt-5 flex flex-wrap gap-2">
          {profile.ovas.map((ova) => (
            <button
              key={ova.ova_id}
              onClick={() => setActiveOvaId(ova.ova_id)}
              className={`rounded-[8px] border px-4 py-2 font-semibold transition ${
                activeOvaId === ova.ova_id ? "border-brand bg-indigo-50 text-indigo-800" : "border-line bg-white text-muted"
              }`}
            >
              {ova.ova_name}
            </button>
          ))}
        </div>

        {/* R.3 — modo desafio: questões difíceis de competência dominada */}
        <button
          onClick={() => setChallenge((c) => !c)}
          aria-pressed={challenge}
          className={`mt-3 flex h-10 items-center gap-2 rounded-[8px] border px-4 font-semibold transition ${
            challenge ? "border-amber-400 bg-amber-50 text-amber-800" : "border-line bg-white text-muted hover:bg-slate-50"
          }`}
        >
          <Trophy size={18} /> {challenge ? t("Modo desafio ativado", "Challenge mode on") : t("Modo desafio 🏆", "Challenge mode 🏆")}
        </button>

        <div className="mt-6 space-y-5">
          {questions.map((question, index) => {
            const graded = feedback[question.question_id];
            return (
              <div
                key={question.question_id}
                className={`rounded-[8px] border bg-white p-6 ${
                  graded === undefined ? "border-line" : graded ? "border-emerald-300" : "border-rose-300"
                }`}
              >
                <div className="text-sm font-semibold text-brand">
                  {t("Questão", "Question")} {index + 1}
                  {question.answered && t(" · já respondida corretamente antes", " · already answered correctly before")}
                </div>
                <h2 className="mt-2 text-lg font-bold text-ink">{question.statement}</h2>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {question.alternatives.map((option, optionIndex) => (
                    <label
                      key={option}
                      className={`flex min-h-12 cursor-pointer items-center rounded-[8px] border px-4 py-3 ${
                        answers[question.question_id] === optionIndex ? "border-brand bg-indigo-50" : "border-line bg-white"
                      }`}
                    >
                      <input
                        className="mr-3"
                        type="radio"
                        checked={answers[question.question_id] === optionIndex}
                        onChange={() =>
                          setAnswers((current) => ({ ...current, [question.question_id]: optionIndex }))
                        }
                      />
                      <span className="mr-2 font-bold text-muted">{LETTERS[optionIndex]})</span>
                      {option}
                    </label>
                  ))}
                </div>
                {graded !== undefined && (
                  <p role="status" className={`mt-3 font-semibold ${graded ? "text-emerald-700" : "text-rose-700"}`}>
                    {graded ? t("Correta!", "Correct!") : t("Incorreta.", "Incorrect.")}
                  </p>
                )}
              </div>
            );
          })}
          {lock && (
            <div className="rounded-[8px] border border-amber-200 bg-amber-50 p-6 text-amber-800">
              <p className="font-semibold">
                {t("Quiz bloqueado", "Quiz locked")}
              </p>
              <p className="mt-1 text-sm">
                {t(
                  `Leia ao menos ${lock.gate}% do conteúdo deste OVA para liberar o quiz — você está em ${lock.perc}%.`,
                  `Read at least ${lock.gate}% of this OVA's content to unlock the quiz — you're at ${lock.perc}%.`
                )}
              </p>
            </div>
          )}
          {challengeLocked && (
            <div className="rounded-[8px] border border-amber-200 bg-amber-50 p-6 text-amber-800">
              <p className="flex items-center gap-2 font-semibold"><Trophy size={18} /> {t("Desafio bloqueado", "Challenge locked")}</p>
              <p className="mt-1 text-sm">
                {t("Domine uma competência deste módulo (chegue a 80%) para desbloquear as questões-desafio.",
                   "Master a competency in this module (reach 80%) to unlock the challenge questions.")}
              </p>
            </div>
          )}
          {!lock && !challengeLocked && questions.length === 0 && (
            <p className="rounded-[8px] border border-line bg-white p-6 text-muted">
              {t("Nenhuma questão cadastrada para este OVA.", "No questions registered for this OVA.")}
            </p>
          )}
        </div>

        {questions.length > 0 && (
          <button
            onClick={finishQuiz}
            disabled={submitting || Object.keys(answers).length < questions.length}
            className="mt-6 h-12 rounded-[8px] bg-coral px-6 font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {submitting ? t("Corrigindo no servidor...", "Grading on the server...") : t("Finalizar quiz", "Finish quiz")}
          </button>
        )}
      </div>

      <aside className="h-fit rounded-[8px] border border-line bg-white p-6 shadow-soft">
        <h2 className="text-xl font-bold text-ink">{t("Feedback automático", "Automatic feedback")}</h2>
        {result ? (
          <div className="mt-5 space-y-4">
            <div className="rounded-[8px] bg-slate-50 p-5">
              <div className="text-sm text-muted">{t("Nota", "Score")}</div>
              <div className="text-4xl font-bold text-ink">{result.score.toFixed(1)}</div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-[8px] bg-emerald-50 p-4 text-emerald-800">
                <div className="text-sm">{t("Acertos", "Correct")}</div>
                <div className="text-2xl font-bold">{result.correct}</div>
              </div>
              <div className="rounded-[8px] bg-rose-50 p-4 text-rose-800">
                <div className="text-sm">{t("Erros", "Wrong")}</div>
                <div className="text-2xl font-bold">{result.wrong}</div>
              </div>
            </div>
            {/* G.6 — micro-momento: XP de esforço ganho + conquistas novas */}
            {result.xp > 0 && (
              <div role="status" className="rounded-[8px] bg-amber-50 p-4 text-center text-amber-800">
                <div className="text-2xl font-bold">+{result.xp} XP</div>
                <div className="text-sm">{t("pelo seu esforço nesta rodada", "for your effort this round")}</div>
              </div>
            )}
            {result.achievements.length > 0 && (
              <div role="status" className="rounded-[8px] bg-indigo-50 p-4 text-center text-indigo-800">
                🏆 {t("Conquista desbloqueada!", "Achievement unlocked!")}
              </div>
            )}
            <p className="text-sm text-muted">
              {t("As tentativas foram registradas. Visite o", "Your attempts were recorded. Visit the")}{" "}
              <strong>{t("Professor Mediador", "Mediating Professor")}</strong>{" "}
              {t("para receber uma recomendação baseada no seu desempenho.", "to get a recommendation based on your performance.")}
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-3 text-muted">
            <p>{t("Finalize o quiz para visualizar nota, acertos e erros.", "Finish the quiz to see score, correct and wrong answers.")}</p>
            <div className="rounded-[8px] bg-slate-50 p-4 text-sm">
              <div className="font-semibold text-ink">{t("Seu histórico", "Your history")}</div>
              <p className="mt-1">
                {t(`${profile.quiz.tentativas} tentativa(s)`, `${profile.quiz.tentativas} attempt(s)`)} ·{" "}
                {profile.quiz.taxa_erro != null
                  ? t(`${Math.round(profile.quiz.taxa_erro * 100)}% de erro`, `${Math.round(profile.quiz.taxa_erro * 100)}% error rate`)
                  : t("sem registros ainda", "no records yet")}
              </p>
            </div>
          </div>
        )}
      </aside>
    </section>
  );
};
