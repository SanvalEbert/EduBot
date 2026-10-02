# Como adicionar conteúdo (OVAs, vídeos, podcasts e textos) via SQL

Guia prático para cadastrar conteúdo na plataforma **pelo banco de dados**
(Caminho A). Hoje **não há tela de upload nem formulário de cadastro** — todo o
conteúdo é inserido por SQL. Este documento mostra como fazer isso passo a passo,
incluindo onde colocar os arquivos de vídeo/áudio.

> Para abrir/rodar o projeto, veja [README.md](README.md) e
> [COMO_ABRIR_FRONTEND_NOVO.md](COMO_ABRIR_FRONTEND_NOVO.md).

---

## 1. Como o conteúdo é organizado

A hierarquia das tabelas (em [Database/sql/ddl.sql](Database/sql/ddl.sql) e
[Database/sql/ddl_extra.sql](Database/sql/ddl_extra.sql)):

```
courses (curso)
  └─ course_subjects (assunto/disciplina)
       ├─ competencies (competências do assunto)
       └─ ovas (a "aula"/objeto de aprendizagem)
            ├─ resources  (materiais: vídeo, podcast, texto, atividade, quiz)
            └─ questions  (perguntas do quiz)
```

- Um **assunto** (`course_subjects`) é ligado a um **curso** pela tabela
  `offerings`.
- Cada assunto tem **competências** (`competencies`) — os "subtópicos" avaliados.
- Cada **OVA** (`ovas`) pertence a um assunto e agrupa os **recursos**
  (`resources`) e as **questões** (`questions`).

> ⚠️ **Importante para o Reforço (OVA personalizada):** para o agente EduBot
> conseguir recomendar um material, o recurso/questão **precisa ter
> `competency_id` preenchido**. É por esse campo que ele encontra o conteúdo do
> assunto em que o aluno foi mal. Recursos genéricos (`quiz`/`atividade`) podem
> ficar com `competency_id` NULL.

---

## 2. O segredo dos vídeos/podcasts/textos: a plataforma guarda **URLs**, não arquivos

A tabela `resources` **não armazena o arquivo** — ela guarda uma **URL**
(`resource_url`) e um **tipo de mídia** (`media_type`) que diz ao player como
interpretar essa URL:

| `media_type` | `resource_url` aponta para… | Como o player trata |
|--------------|------------------------------|---------------------|
| `youtube`    | link normal do YouTube       | embed com rastreio de **% assistido** |
| `upload`     | arquivo direto `.mp4`/`.mp3` | player HTML5 nativo (vídeo ou áudio) |
| `link`       | uma página externa (texto)   | abre em nova aba |
| `NULL`       | — (usado por `quiz`/`atividade`) | sem player |

E `resource_type` define **o que é** o recurso:
`'texto' | 'video' | 'podcast' | 'quiz' | 'atividade'`.

Combinações típicas:

| Quero adicionar… | `resource_type` | `media_type` | `resource_url` |
|------------------|-----------------|--------------|----------------|
| Vídeo do YouTube | `video`         | `youtube`    | `https://www.youtube.com/watch?v=...` |
| Vídeo próprio (arquivo) | `video`  | `upload`     | URL do `.mp4` hospedado |
| Podcast (arquivo `.mp3`) | `podcast` | `upload`    | URL do `.mp3` hospedado |
| Podcast externo (link) | `podcast` | `link`      | URL do episódio |
| Texto/leitura externa | `texto`    | `link`       | URL do artigo |
| Atividade prática | `atividade`    | `NULL`       | `NULL` |

---

## 3. Onde colocar os arquivos de vídeo e podcast

Você tem **duas opções**:

### Opção 1 — Hospedagem externa (mais simples)
Suba o vídeo no **YouTube** (ou o áudio no Spotify/anchor/etc.) e use a URL
pública. Nada de arquivo no projeto. Use `media_type='youtube'` (vídeo do
YouTube) ou `media_type='link'`.

### Opção 2 — Arquivo próprio servido pelo projeto
O Apache do projeto serve a pasta
[Front-End/files/](Front-End/files/) em `http://localhost:8010/`. Então:

1. Crie uma pasta para uploads, por exemplo
   `Front-End/files/uploads/`.
2. Copie o arquivo para lá, por exemplo `aula-derivadas.mp4` →
   `Front-End/files/uploads/aula-derivadas.mp4`.
3. No banco, use a URL correspondente com `media_type='upload'`:
   `http://localhost:8010/uploads/aula-derivadas.mp4`

> O mesmo vale para podcasts (`.mp3`). Como o `compose.yaml` monta
> `./Front-End/files` como volume do Apache, o arquivo aparece sem precisar
> rebuildar a imagem — basta copiar para a pasta.

---

## 4. Exemplos de SQL prontos

> Os exemplos usam `LAST_INSERT_ID()` e variáveis (`@ova`, `@comp`) para não
> precisar adivinhar os IDs auto-incrementados. Rode tudo na mesma sessão.

### 4.1. Adicionar um recurso a uma OVA já existente

Quer só pendurar um vídeo/podcast/texto novo numa OVA que já existe? Descubra o
`ova_id` (e o `competency_id` do assunto) e insira:

```sql
USE ova_db;

-- (opcional) ver os IDs existentes
-- SELECT ova_id, ova_name, subject_id FROM ovas;
-- SELECT competency_id, competency_description, subject_id FROM competencies;

INSERT INTO resources
  (ova_id, resource_type, resource_title, resource_url, media_type, duration_seconds, competency_id)
VALUES
  (2, 'video',   'Vídeo: Regra da cadeia',        'https://www.youtube.com/watch?v=XXXXXXXX', 'youtube', NULL, 4),
  (2, 'podcast', 'Podcast: Derivadas na prática',  'http://localhost:8010/uploads/derivadas.mp3', 'upload', 540, 4),
  (2, 'texto',   'Leitura: Tabela de derivadas',   'https://exemplo.com/tabela-derivadas',     'link',    NULL, 4);
```

> `duration_seconds` é usado pelo player de podcast para calcular o % de escuta.
> Em vídeo do YouTube pode ficar `NULL` (a duração vem da API do YouTube).

### 4.2. Adicionar uma OVA nova completa (com competência, recursos e quiz)

```sql
USE ova_db;

-- 1) Assunto novo (pule se já existe) + vínculo com o curso 1 + competência
INSERT INTO course_subjects (subject_name) VALUES ('Estruturas de Dados');
SET @subject := LAST_INSERT_ID();

INSERT INTO offerings (course_id, subject_id) VALUES (1, @subject);

INSERT INTO competencies (competency_description, subject_id)
VALUES ('Compreender listas, pilhas e filas', @subject);
SET @comp := LAST_INSERT_ID();

-- 2) A OVA (o "link" é a página HTML do leitor clássico; pode repetir um
--    existente ou ser um nome simbólico — o app React renderiza pelos recursos)
INSERT INTO ovas (ova_name, link, num_interactions, subject_id)
VALUES ('Estruturas de Dados', 'estruturas.html', 0, @subject);
SET @ova := LAST_INSERT_ID();

-- 3) Os materiais
INSERT INTO resources
  (ova_id, resource_type, resource_title, resource_url, media_type, duration_seconds, competency_id)
VALUES
  (@ova, 'video',     'Vídeo: Listas encadeadas',  'https://www.youtube.com/watch?v=XXXXXXXX', 'youtube', NULL, @comp),
  (@ova, 'podcast',   'Podcast: Pilhas e filas',   'http://localhost:8010/uploads/pilhas.mp3', 'upload',  600,  @comp),
  (@ova, 'texto',     'Leitura: Introdução',       'https://exemplo.com/estruturas',           'link',    NULL, @comp),
  (@ova, 'atividade', 'Exercício: implemente uma pilha', NULL,                                 NULL,      NULL, NULL),
  (@ova, 'quiz',      'Quiz: Estruturas de Dados', NULL,                                       NULL,      NULL, NULL);

-- 4) Questões do quiz (alternatives em JSON; answer = letra da correta: a,b,c,d)
INSERT INTO questions (statement, alternatives, answer, ova_id, competency_id)
VALUES
  ('Qual estrutura segue o princípio LIFO (último a entrar, primeiro a sair)?',
   '{"alternatives": ["Fila", "Pilha", "Lista ligada", "Árvore"]}',
   'b', @ova, @comp),
  ('Em uma fila, a remoção acontece:',
   '{"alternatives": ["No início (FIFO)", "No fim", "Em qualquer posição", "Nunca"]}',
   'a', @ova, @comp);
```

### 4.3. Formato das questões (atenção)

- `alternatives` é uma coluna **JSON** no formato exato
  `{"alternatives": ["...", "...", ...]}` (veja os exemplos em
  [Database/sql/dml.sql](Database/sql/dml.sql)).
- `answer` é **uma letra** (`'a'`, `'b'`, `'c'`, `'d'`…) que corresponde à
  posição na lista: `a` = 1ª alternativa, `b` = 2ª, e assim por diante.
- **O gabarito nunca vai para o navegador** — a correção é feita no servidor
  (`POST /question/answer`).

---

## 5. Como aplicar o SQL

### Caso A — Banco já está rodando (mais comum)
Escreva os `INSERT`s em um arquivo (ex.: `meu_conteudo.sql`) e rode contra o
container do MySQL:

```powershell
# a partir da pasta que contém o compose.yaml
docker compose exec -T ova_mysql sh -c "mysql -uroot -pPassword-1 ova_db" < meu_conteudo.sql
```

> Para conferir depois:
> `docker compose exec ova_mysql sh -c "mysql -uroot -pPassword-1 -e 'SELECT resource_id, resource_type, resource_title FROM ova_db.resources ORDER BY resource_id DESC LIMIT 10;'"`

### Caso B — Quero que o conteúdo entre automaticamente em instalações novas
Os scripts em [Database/sql/](Database/sql/) são executados **na primeira
inicialização** de um volume MySQL novo, **em ordem alfabética**
(`dcl` → `ddl` → `ddl_extra` → `dml` → `dml_extra`). Para o seu conteúdo rodar
**depois** dos seeds, crie um arquivo cujo nome ordene após `dml_extra`, por
exemplo:

```
Database/sql/dml_meu_conteudo.sql
```

Comece o arquivo com `USE ova_db;` e coloque os `INSERT`s. Numa instalação
totalmente nova (`docker compose down -v` e depois `up --build`) ele roda
sozinho. Num volume já existente, aplique pelo Caso A.

---

## 6. Checklist rápido

- [ ] O **assunto** existe em `course_subjects` e está ligado ao curso via `offerings`?
- [ ] As **competências** do assunto existem em `competencies`?
- [ ] A **OVA** existe em `ovas` (com o `subject_id` certo)?
- [ ] Cada **recurso** tem `resource_type` e, para mídia, o par
      `resource_url` + `media_type` correto?
- [ ] Vídeos/podcasts/textos de reforço têm **`competency_id`** (senão não
      aparecem no Reforço)?
- [ ] Arquivos próprios foram copiados para `Front-End/files/uploads/` e a URL
      bate com `http://localhost:8010/uploads/<arquivo>`?
- [ ] As **questões** estão no formato JSON correto, com `answer` = letra?

Pronto — depois de inserir, o conteúdo aparece no app do aluno
(`http://localhost:8010/app/`) nas abas **Conteúdos**, **Quiz** e, quando houver
material com `competency_id`, no **Reforço**.
