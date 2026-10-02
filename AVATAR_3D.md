# Avatar 3D falante do EduBot (Cena 3 — "Meu Desempenho")

Substitui o mascote 2D por **personagens 3D construídos em código** (Three.js) que
"conversam" com o aluno (boca animada enquanto o EduBot fala) e permitem
**escolher entre 2 personas** (dois cientistas) direto no card "Meu Desempenho".

> **100% offline.** Não baixa nenhum arquivo nem depende de site externo. A
> Ready Player Me foi descartada porque o domínio está bloqueado na rede do
> projeto (falharia também na hora de gravar).

## O que foi feito

| Arquivo | Papel |
|---------|-------|
| `Front-End/react-logic-demo/src/components/brand/avatars.ts` | Config das 2 personas (variante + paleta de cores + nome). **É aqui que você ajusta/adiciona personas.** |
| `Front-End/react-logic-demo/src/components/brand/Avatar3D.tsx` | Canvas Three.js (react-three-fiber): monta a cabeça/busto com primitivas, anima a boca, pisca e respira; cai para o mascote 2D se o WebGL falhar. |
| `Front-End/react-logic-demo/src/components/PerformanceCoach.tsx` | Mostra o avatar 3D + **seletor de persona** (persistido em `localStorage`); reusa a voz existente (`useSpeech`). |

Dependências novas (já em `package.json`): `three`, `@react-three/fiber`,
`@react-three/drei`, `@types/three`. O container `ova_react_build` instala tudo
sozinho no `docker compose up` — nada a fazer manualmente.

## Como o lip-sync funciona (e seu limite)

Enquanto `speaking === true`, a **boca abre/fecha** com uma oscilação suave. Como
a voz atual é o **TTS do navegador** (Web Speech API), que **não expõe o áudio
para análise**, o movimento não é fonema-a-fonema.

> Lip-sync fonético real virá ao ligar a **AWS Polly** (retorna visemas com
> timing). Em `Avatar3D.tsx` basta alimentar `mouthOpen`/`mouthRef` com essa
> timeline — o resto já está pronto.

## As duas personas

| Persona | Traços (procedurais) |
|---------|----------------------|
| **Prof. Einstein** | cabelo grisalho "elétrico" nas laterais, bigode farto, óculos redondos, terno. |
| **Dra. Marie Curie** | cabelo preso escuro com coque atrás, gola alta de época. |

São figuras **estilizadas/cartoon** que *evocam* os cientistas (não são a face
real deles — evita direito de imagem). O aluno alterna entre elas nos botões
abaixo do avatar; a escolha fica salva.

### Ajustar/criar personas

Edite [avatars.ts](Front-End/react-logic-demo/src/components/brand/avatars.ts):
mude a `palette` (cores de pele/cabelo/roupa), `name`/`tagline` e `bg`. Para um
**novo tipo de cabeça**, crie uma nova `variant` e trate-a em `Avatar3D.tsx`
(funções `EinsteinHair` / `CurieHair` são o modelo a copiar).

> Quer realismo foto-realista no futuro? Dá para trocar o personagem procedural
> por um `.glb` com blendshapes de boca (ex.: baixado do Sketchfab) e servi-lo de
> `public/avatars/`. Não faz parte desta entrega (procedural cobre a demo sem
> depender de rede).

## Fallback (a demo nunca quebra)

Se o WebGL não estiver disponível, um `ErrorBoundary` no `Avatar3D` aciona o
**mascote 2D** original automaticamente — a voz e o resto do card continuam
funcionando.

## Passo a passo no vídeo (Cena 3)

1. Login RA `1`/`1` → **Meu Desempenho** ("My Performance").
2. No card **"EduBot fala com você"** aparece o **avatar 3D**.
3. **Escolha a persona** nos botões abaixo do avatar (*Prof. Einstein* /
   *Dra. Marie Curie*) — a troca é instantânea e fica salva.
4. Clique em **"Ouvir o EduBot"** → a voz narra e **a boca do avatar 3D anima**.
   (Opcional: **"Versão do EduBot (IA)"** para o texto gerado pelo Claude/Bedrock.)

*Última atualização: 2026-07-01.*
