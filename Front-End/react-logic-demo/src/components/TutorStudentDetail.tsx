/*
Plano 5 (19.3) — DETALHE de um aluno para o professor.

Aberto ao clicar numa linha da turma (rota #/aluno/:id). Busca o perfil completo
via GET /tutor/student/<id> (mesmo shape de /student/me) e mostra, de forma bem
visual, o desempenho daquele aluno: KPIs + acertos/erros por assunto e por
competência (números brutos) + os gráficos de domínio/consumo.

Reuso máximo: SubjectScores, CompetencyScores e PerformanceCharts são os mesmos
componentes do "Meu Desempenho" do aluno — o professor vê exatamente os mesmos
números, sem lógica duplicada.

Segurança: a rota é liberada só para staff no front, mas quem garante o escopo
(aluno do mesmo curso) é o backend (404 fora de escopo).
*/
import { AlertTriangle, ArrowLeft, BookX, CalendarClock, Gauge, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { StudentProfile, getTutorStudent } from "../services/api";
import { useLanguage, useT } from "../i18n";
import { SubjectScores } from "./SubjectScores";
import { CompetencyScores } from "./CompetencyScores";
import { PerformanceCharts } from "./PerformanceCharts";

interface TutorStudentDetailProps {
  studentId: number;
  onBack: () => void;
}

interface KpiCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  alerta?: boolean;
}

const KpiCard = ({ icon, label, value, alerta }: KpiCardProps) => (
  <div className="rounded-[8px] border border-line bg-white p-5 shadow-soft">
    <div className="flex items-center gap-2 text-muted">{icon} {label}</div>
    <div className={`mt-2 text-3xl font-bold ${alerta ? "text-rose-600" : "text-ink"}`}>{value}</div>
  </div>
);

export const TutorStudentDetail = ({ studentId, onBack }: TutorStudentDetailProps) => {
  const t = useT();
  const { lang } = useLanguage();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let vivo = true;
    setProfile(null);
    setError(null);
    getTutorStudent(studentId)
      .then((p) => { if (vivo) setProfile(p); })
      .catch((err) => {
        if (!vivo) return;
        setError((err as { status?: number }).status === 404 ? "nao_encontrado" : "falha");
      });
    return () => { vivo = false; };
  }, [studentId, lang]);

  // A11y: leva o foco ao título quando o aluno carrega (o professor "entrou" numa
  // nova tela lógica, mesmo sem recarregar a página).
  useEffect(() => {
    if (profile) headingRef.current?.focus();
  }, [profile]);

  const voltar = (
    <button
      onClick={onBack}
      className="flex items-center gap-2 rounded-[8px] border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-slate-50"
    >
      <ArrowLeft size={16} aria-hidden="true" /> {t("Voltar para a turma", "Back to class")}
    </button>
  );

  if (error) {
    return (
      <section className="space-y-4">
        {voltar}
        <div className="rounded-[8px] border border-rose-200 bg-rose-50 p-6 text-rose-800" role="alert">
          <p className="font-semibold">
            {error === "nao_encontrado"
              ? t("Aluno não encontrado nesta turma.", "Student not found in this class.")
              : t("Não foi possível carregar os dados deste aluno.", "Couldn't load this student's data.")}
          </p>
        </div>
      </section>
    );
  }

  if (!profile) {
    return (
      <section className="space-y-4">
        {voltar}
        <div className="flex min-h-[40vh] items-center justify-center">
          <LoaderCircle className="animate-spin text-brand" size={32} aria-hidden="true" />
          <span className="sr-only" role="status">{t("Carregando", "Loading")}</span>
        </div>
      </section>
    );
  }

  const est = profile.estudante;
  const dias = profile.dias_sem_acesso;
  const taxa = profile.quiz.taxa_erro;

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          {voltar}
          <h1 ref={headingRef} tabIndex={-1} className="mt-3 text-3xl font-bold text-ink outline-none">
            {est.nome}
          </h1>
          <p className="mt-1 text-muted">
            RA {est.ra}{est.curso ? ` · ${est.curso}` : ""}
          </p>
        </div>
      </div>

      {/* KPIs do aluno */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          icon={<CalendarClock size={18} />}
          label={t("Sem acesso", "No access")}
          value={dias != null ? t(`${dias} dias`, `${dias} days`) : "—"}
          alerta={dias != null && dias >= 7}
        />
        <KpiCard
          icon={<Gauge size={18} />}
          label={t("Consumo de recursos", "Resource consumption")}
          value={`${profile.recursos.percentual_consumido}%`}
        />
        <KpiCard
          icon={<AlertTriangle size={18} />}
          label={t("Taxa de erro no quiz", "Quiz error rate")}
          value={taxa != null ? `${Math.round(taxa * 100)}%` : "—"}
          alerta={taxa != null && taxa > 0.5}
        />
        <KpiCard
          icon={<BookX size={18} />}
          label={t("Atividades pendentes", "Pending activities")}
          value={String(profile.atividades_pendentes)}
        />
      </div>

      {/* Números brutos: por assunto e por competência (reuso do lado do aluno,
          na voz de 3ª pessoa — o professor está vendo os dados DO aluno). */}
      <SubjectScores competencias={profile.competencias} perspective="other" />
      <CompetencyScores competencias={profile.competencias} perspective="other" />

      {/* Gráficos de domínio e consumo (sem a "Tendência", que é só do aluno logado) */}
      <PerformanceCharts profile={profile} />
    </section>
  );
};
