# Roteiro de apresentação — EduBot / Adapta

Passo a passo para **demonstrar a plataforma ao vivo**, com a narrativa, onde clicar
e os números para apontar. Tempo total sugerido: **8–12 min**. Tudo roda em **IA mock**
(determinística, sem custo) — nada depende de internet ou credencial.

---

## 0. Antes de começar (checklist de 2 min)

1. **Suba a stack** (na pasta `EduBot/`):
   ```bash
   docker compose up -d --build
   docker compose ps        # ova_db (healthy), back e front "Up"
   ```
2. **Abra** http://localhost:8010/app/ e confirme que a tela de login aparece.
3. **Popule os dados da demo** (3 alunos com desempenhos distintos + alertas do professor):
   ```bash
   python <caminho>/seed_demo.py     # roda pelo API; leva ~10s
   ```
   > Se o professor já mostrar dados coerentes (Manuel em risco, Pedro 100% consumo),
   > está pronto. Rode o seed de novo só se tiver dado `docker compose down -v`.
4. Deixe **5 abas** abertas e já logadas (ou faça o login na hora — a senha é igual ao RA):

| Persona | RA | Senha | O que representa |
|---|---|---|---|
| 🟢 **Pedro** | `5` | `5` | Aluno que foi **bem** (89% de aproveitamento) |
| 🟡 **Thiago** | `6` | `6` | Aluno **mediano** (56%, deixou atividades pela metade) |
| 🔴 **Manuel** | `7` | `7` | Aluno em **dificuldade** (22%, em risco) |
| 👨‍🏫 **Gabriel** | `2` | `2` | **Professor** (aba Turma) |
| 📊 **Sanval** | `4` | `4` | **Gestor** (Visão do Gestor) |

---

## 1. Abertura — o problema (30–45s)

> "O EduBot é uma plataforma de ensino que **rastreia tudo o que o aluno faz** —
> leitura, vídeo, podcast, quiz — e usa isso para **agir sozinha**: recomenda reforço
> ao aluno e **avisa o professor antes** de o aluno ficar para trás. Vou mostrar a
> mesma turma por três olhares: o aluno, o professor e o gestor."

Sem tela ainda, ou já com a tela de login aberta.

---

## 2. Cena 1 — O aluno que vai bem (Pedro · RA 5) — ~2 min

**Login:** RA `5` / senha `5`.

### a) Dashboard
- Aponte o **"Continuar de onde parou"**, o progresso e a caixa de **recomendações do EduBot**.
- Fala: *"O aluno cai numa tela que já sabe o que ele fez e o que falta."*

### b) Menu **"Meu Desempenho"** (o ponto alto para o aluno)
Role a página de cima a baixo. Destaques, na ordem:
1. **Nível, XP, sequência e conquistas** — gamificação. *"Isso engaja e dá ritmo de estudo."*
2. **O EduBot fala com você** — o coach (avatar) fala direto com o Pedro; dá para
   trocar de persona (EduBot / Einstein / Curie) e **ouvir a fala** (voz).
3. **Revisões desta semana** — repetição espaçada (SM-2). Cada item tem o botão
   **"Revisar"** → leva direto ao quiz daquela competência. *"A revisão é interativa:
   ele clica e já pratica."*
4. **Acertos e erros por assunto** — as competências vêm **agrupadas por disciplina**
   (Computação Quântica, Cálculo, Fundamentos de Computação na Nuvem). *"Antes as
   competências ficavam soltas; agora o aluno vê por área."*
5. **Acertos e erros por competência** — o número cru: **32 acertos · 4 erros · 89%**,
   competência a competência, com a barra verde/vermelha.
6. **Teia de competências** + gráficos de leitura e consumo por tipo de recurso.

> Frase de efeito: *"Tudo isto é calculado a partir dos dados reais — não é chute."*

---

## 3. Cena 2 — O aluno em dificuldade + a IA agindo (Manuel · RA 7) — ~2 min

**Troque para a aba do Manuel** (RA `7` / senha `7`).

- **Dashboard:** a caixa **"O EduBot tem recomendações para você"** aparece com mais
  peso — ele consumiu só **26%** do material e erra muito.
- Vá em **"Reforço"** na barra lateral. Mostre a **OVA de reforço montada pelo agente**:
  > *"Aqui não é uma resposta de chatbot. O EduBot é um **agente de tool-use**: ele
  > identificou a competência mais fraca, buscou no banco de conteúdo classificado por
  > competência e **montou uma trilha de reforço** — recursos + questões — sozinho."*
- (Opcional) Em **"Meu Desempenho"**, mostre o contraste com o Pedro: **22%**, várias
  competências "não iniciadas", teia quase vazia.

---

## 4. Cena 3 — O professor (Gabriel · RA 2) — ~2–3 min

**Troque para a aba do professor** (RA `2` / senha `2`), aba **"Turma"**.

### a) Visão de cima
- Três cartões no topo: **3 alunos ativos · 2 alertas abertos · 1 em risco**.
- *"O professor vê a turma inteira e, principalmente, **quem precisa de atenção agora**."*

### b) **Domínio da turma (heatmap)**
- Grade aluno × competência, **agrupada por assunto**, colorida por domínio (BKT):
  Manuel puxa para o vermelho, Pedro no verde, Thiago no meio.

### c) **Central de alertas** (proatividade)
- **Manuel — Trilha mínima (ALTA)**, **Thiago — Checklist para concluir**. Cada alerta
  tem **"Marcar como tratado"**. *"O sistema não só mostra — ele **propõe a ação** e o
  professor fecha o loop."*

### d) 🔑 **O clique-chave: escolher um aluno**
- Na tabela **"Alunos"**, **clique na linha do Manuel**.
- Abre o **detalhe individual**: KPIs (0 dias sem acesso, 26% consumo, **78% de erro**,
  2 pendentes), acertos/erros **por assunto e por competência**, teia e gráficos.
- Fala: *"Com um clique o professor mergulha no aluno e vê exatamente **onde** ele
  travou — competência a competência."* Volte com **"Voltar para a turma"**.

---

## 5. Cena 4 — O gestor (Sanval · RA 4) — ~1–2 min

**Troque para a aba do gestor** (RA `4` / senha `4`), aba **"Visão do Gestor"**.

- **KPIs:** 3 alunos · 1 em risco · 2 alertas · **89% consumo médio**.
- **Quiz da turma:** 54 acertos · 32 erros · **63%**.
- **Acertos e erros por assunto (turma)** — gráfico + tabela com **domínio médio** por disciplina.
- **"O que o sistema rastreia"** — o catálogo com a **contagem real de registros**:
  progresso por OVA, consumo de recursos, tentativas de quiz, eventos de aprendizado,
  domínio por competência (BKT), consentimentos (LGPD)…
  > *"Para o gestor, a mensagem é: **tudo isto é medível e já está no banco** — dá para
  > provar aprendizado com dado, não com achismo."*

---

## 6. Fechamento (30–45s)

Pontos para amarrar:
- **IA por padrão em modo mock** (determinística, custo zero); a mesma arquitetura liga
  no **Claude real (AWS Bedrock)** só trocando uma configuração — sem tocar no código.
- **Privacidade (LGPD):** consentimentos são rastreados; o aluno controla seus dados.
- **Acessibilidade:** nada depende só de cor (ícones + texto), contraste e teclado.
- Encerramento: *"É um ciclo fechado — o aluno estuda, o sistema mede, a IA age, o
  professor intervém e o gestor comprova. Tudo com o dado que já é coletado."*

---

## 7. Se algo quebrar (plano B)

| Sintoma | O que fazer |
|---|---|
| Tela branca / `/student/me` dá 500 | Volume MySQL antigo — rode as migrations ou `docker compose down -v && up -d --build` e re-seed. |
| Login falha no 2º acesso | Idem acima (coluna de senha estreita). Reset: `docker exec ova_db mysql -ueduardo -pPassword-1 ova_db -e "UPDATE students SET student_password='5' WHERE student_id=5;"` |
| Professor sem dados / Pedro "em risco" errado | Rode o `seed_demo.py` de novo; se persistir alerta obsoleto, limpe `alerts/interventions/agent_decisions` dos alunos 5,6,7 e chame `POST /tutor/evaluate`. |
| Porta 8010/5010 ocupada | Outra stack no ar: `docker compose down` na pasta que a subiu. |

> Dica: tenha uma aba já logada em cada persona **antes** de começar, para não digitar
> login na frente da plateia.
