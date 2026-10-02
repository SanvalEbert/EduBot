# O Caminho do Aluno na Plataforma EduBot

```mermaid
flowchart LR
    A(["🚪 <b>PRIMEIRO ACESSO</b><br/>entra com RA e senha<br/>🔒 e escolhe o que<br/>autoriza"])
    --> C{{"🏠 <b>PAINEL DO ALUNO</b><br/>boas-vindas em 3 passos<br/>e um único botão:<br/><i>abrir meu 1º módulo</i>"}}

    C -.->|"7 dias<br/>sem acessar"| O["💙 <b>CHAMADO DE VOLTA</b><br/>plano leve de<br/>retomada"]
    C -.->|"em<br/>paralelo"| P["👩‍🏫 <b>O PROFESSOR VÊ</b><br/>quem está em risco<br/>e <b>por quê</b>"]
    C --> E["📚 <b>ELE ESTUDA</b><br/>lê · assiste · ouve<br/>faz a atividade<br/>pergunta ao Tutor IA"]

    E -.-> FF[/"📊 <b>A PLATAFORMA MEDE</b><br/>⏱️ tempo real de leitura<br/>📍 a seção onde travou<br/>🎬 vídeo mesmo visto<br/>💬 dúvidas ao tutor"/]
    E --> H["📝 <b>QUIZ ADAPTATIVO</b><br/>🔒 abre após ler 70%<br/>vem no nível dele:<br/>fácil, média, difícil"]

    H -.-> II[/"🧠 <b>O DOMÍNIO É ATUALIZADO</b><br/>0% a 100% por<br/>competência · sobe ao<br/>acertar · cai ao errar<br/><b>decai sozinho</b> sem prática"/]
    H -->|"🔴 domínio<br/>abaixo de 40%"| K["📣 <b>CONVITE AO REFORÇO</b><br/><i>Vi dificuldade</i><br/><i>em Limites. Quer</i><br/><i>praticar agora?</i>"]
    H -->|"🟡 domínio entre<br/>40% e 80%"| L["➡️ <b>PRÓXIMO MÓDULO</b><br/>no formato em que<br/>ele mais aprende"]
    H -->|"🟢 domínio de<br/>80% ou mais"| M["🏆 <b>DESAFIO LIBERADO</b><br/>+ revisão em 3 dias<br/>para não esquecer"]

    K --> N["✨ <b>TRILHA PERSONALIZADA</b><br/>montada com 3 dados:<br/>• a <b>competência</b> do erro<br/>• o <b>formato</b> preferido<br/>• o <b>nível</b> confortável"]

    style A fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px
    style C fill:#e0e7ff,stroke:#4f46e5,stroke-width:3px
    style E fill:#ffffff,stroke:#334155,stroke-width:2px
    style FF fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style H fill:#ffffff,stroke:#334155,stroke-width:2px
    style II fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style K fill:#fce7f3,stroke:#db2777,stroke-width:2px
    style L fill:#f1f5f9,stroke:#64748b,stroke-width:2px
    style M fill:#fef3c7,stroke:#d97706,stroke-width:2px
    style N fill:#fce7f3,stroke:#db2777,stroke-width:3px
    style O fill:#fce7f3,stroke:#db2777,stroke-width:2px
    style P fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px
```

### Legenda das cores

| Cor | O que representa |
|---|---|
| 🟦 **Azul** | Entrada e painel do aluno |
| ⬜ **Branco** | O que o **aluno faz** |
| 🟩 **Verde** | **Dados** que a plataforma coleta e calcula |
| 🟪 **Rosa** | **Ações do EduBot** — quando a IA fala com o aluno |
| 🟨 **Amarelo** | Conquistas e desafios |
| 🟣 **Roxo** | O que chega ao **professor** |

### Como narrar em 5 frases

1. **O aluno entra e escolhe o que autoriza** — privacidade primeiro, antes de qualquer coleta.
2. **Ele estuda, e a plataforma mede o que realmente aconteceu** — tempo com a aba visível, seção onde travou, vídeo de fato assistido. Pular não conta.
3. **O quiz só abre depois da leitura**, e vem no nível certo para ele.
4. **Cada resposta atualiza o domínio da competência** — uma nota de 0 a 100% que sobe, cai e até decai sozinha com o esquecimento. É esse número que decide o próximo passo.
5. **Dificuldade vira trilha personalizada; domínio vira desafio e revisão; ausência vira convite de volta** — e o professor vê tudo isso, com o motivo explicado.
