/*
Plano 5 (19.3) — bloco de GRÁFICOS de desempenho reutilizável.

Extraído do `Evolution` para ser usado também no detalhe do aluno visto pelo
professor (`TutorStudentDetail`), sem duplicar o código do Recharts. Recebe um
`StudentProfile` (o mesmo shape vindo de /student/me OU de /tutor/student/<id>) e
desenha: teia de competências (radar), leitura por OVA e consumo por tipo.

`radarExtra` é um slot opcional renderizado dentro do card da teia — o aluno usa
para a "Tendência (7 dias)"; o professor não passa nada (aquele sinal é só do
aluno logado). Assim o visual do aluno fica idêntico ao de antes.
*/
import { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { StudentProfile } from "../services/api";
import { useT } from "../i18n";

interface PerformanceChartsProps {
  profile: StudentProfile;
  radarExtra?: ReactNode;
}

export const PerformanceCharts = ({ profile, radarExtra }: PerformanceChartsProps) => {
  const t = useT();
  const kRead = t("percentual lido", "percent read");
  const kMin = t("minutos de leitura", "reading minutes");
  const kConsumed = t("consumidos", "consumed");
  const kTotal = t("total", "total");

  // D.2: quando há domínio estimado por BKT, a teia usa esse sinal (mais estável
  // que %acertos); senão, cai na razão acertos/total.
  const competencyData = profile.competencias.map((item, index) => ({
    nome: `Comp. ${index + 1}`,
    completo: item.nome,
    score: item.dominio_estimado != null
      ? Math.round(item.dominio_estimado * 100)
      : (item.total_questoes ? Math.round((100 * item.acertos) / item.total_questoes) : 0),
    status: item.status
  }));

  const typeData = Object.entries(profile.recursos.por_tipo).map(([tipo, stats]) => ({
    tipo,
    [kConsumed]: stats.consumidos,
    [kTotal]: stats.total
  }));

  const ovaData = profile.ovas.map((ova) => {
    const nome = ova.ova_name;
    return {
      nome: nome.length > 18 ? `${nome.slice(0, 18)}…` : nome,
      [kRead]: ova.perc_scrolled || 0,
      [kMin]: Math.round((ova.read_time || 0) / 60)
    };
  });

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      {/* Teia de competências (gráfico radar) — visão do domínio do aluno */}
      <div className="rounded-[8px] border border-line bg-white p-6 shadow-sm xl:col-span-2">
        <h2 className="text-xl font-bold text-ink">{t("Teia de competências", "Competency web")}</h2>
        <p className="mt-1 text-sm text-muted">{t("Domínio estimado por competência (quanto mais cheia a teia, melhor o domínio).", "Estimated mastery per competency (the fuller the web, the better the mastery).")}</p>
        <div className="mt-5 h-96">
          <ResponsiveContainer>
            <RadarChart data={competencyData} outerRadius="72%">
              <PolarGrid />
              <PolarAngleAxis dataKey="nome" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
              <Tooltip
                formatter={(value: number) => [`${value}%`, t("domínio estimado", "estimated mastery")]}
                labelFormatter={(label: string) => {
                  const item = competencyData.find((entry) => entry.nome === label);
                  return item ? `${item.completo} (${item.status})` : label;
                }}
              />
              <Radar name={t("Domínio", "Mastery")} dataKey="score" stroke="#604fd8" fill="#604fd8" fillOpacity={0.35} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        {radarExtra}
      </div>

      <div className="rounded-[8px] border border-line bg-white p-6 shadow-sm">
        <h2 className="text-xl font-bold text-ink">{t("Leitura por OVA", "Reading per OVA")}</h2>
        <div className="mt-5 h-72">
          <ResponsiveContainer>
            <BarChart data={ovaData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="nome" interval={0} tick={{ fontSize: 12 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey={kRead} fill="#604fd8" radius={[8, 8, 0, 0]} />
              <Bar dataKey={kMin} fill="#ff7b65" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-[8px] border border-line bg-white p-6 shadow-sm">
        <h2 className="text-xl font-bold text-ink">{t("Consumo por tipo de recurso", "Consumption by resource type")}</h2>
        <div className="mt-5 h-72">
          <ResponsiveContainer>
            <BarChart data={typeData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="tipo" interval={0} tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Bar dataKey={kConsumed} fill="#15beb5" radius={[8, 8, 0, 0]} />
              <Bar dataKey={kTotal} fill="#dfe5ef" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Competências desenvolvidas (barras) — o mesmo score do radar, em barra */}
      <div className="rounded-[8px] border border-line bg-white p-6 shadow-sm xl:col-span-2">
        <h2 className="text-xl font-bold text-ink">{t("Competências desenvolvidas", "Developed competencies")}</h2>
        <div className="mt-5 h-80">
          <ResponsiveContainer>
            <BarChart data={competencyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="nome" interval={0} height={50} tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} />
              <Tooltip
                formatter={(value: number) => [`${value}%`, t("acertos", "correct")]}
                labelFormatter={(label: string) => {
                  const item = competencyData.find((entry) => entry.nome === label);
                  return item ? `${item.completo} (${item.status})` : label;
                }}
              />
              <Bar dataKey="score" fill="#15beb5" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
