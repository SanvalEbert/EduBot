# Protótipo Adapta - Lógica de Programação

Demo funcional em React + TypeScript para acompanhamento contínuo de aprendizagem no módulo **Lógica de Programação**.

## Estrutura

```text
react-logic-demo/
├── src/
│   ├── components/
│   │   ├── ContentArea.tsx
│   │   ├── Dashboard.tsx
│   │   ├── Evolution.tsx
│   │   ├── Exercises.tsx
│   │   ├── Quiz.tsx
│   │   ├── Report.tsx
│   │   └── Sidebar.tsx
│   ├── data/
│   │   └── learningData.ts
│   ├── services/
│   │   ├── analytics.ts
│   │   ├── report.ts
│   │   └── storage.ts
│   ├── App.tsx
│   ├── main.tsx
│   ├── styles.css
│   └── types.ts
├── package.json
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
└── vite.config.ts
```

## Recursos implementados

- Dashboard do aluno com progresso, tempo de estudo, exercícios, média dos quizzes e competências.
- Conteúdos teóricos sobre algoritmos, variáveis, condicionais e repetição.
- Cinco exercícios com registro de respostas.
- Quiz funcional com 10 questões, nota, acertos, erros e tópicos de dificuldade.
- Monitoramento de tempo por conteúdo, conclusão de conteúdos, exercícios realizados, tentativas de quiz e evolução.
- Gráficos com Recharts para progresso, nota e competências.
- Persistência local em JSON via `localStorage`, exportação e importação de arquivo JSON.
- Relatório pedagógico EduBot gerado automaticamente com base nos dados coletados.

## Executar

```powershell
cd Front-End/react-logic-demo
npm install
npm run dev
```

Depois acesse o endereço mostrado pelo Vite.
