<#
.SYNOPSIS
  Zera o PROGRESSO de aluno(s) no banco, mantendo todo o conteúdo (cursos, OVAs,
  recursos, questões, competências, usuários). Ideal para começar a demo do
  ZERO sem recriar o banco.

.DESCRIPTION
  Apaga as linhas por-aluno das tabelas de rastreamento:
  interactions, answers, attempts, ova_progress, resource_progress,
  interventions, alerts, personalized_ova (+ personalized_ova_item via cascade).

.EXAMPLE
  .\reset-aluno.ps1                # zera o aluno RA 1 (Eduardo, o da demo)
  .\reset-aluno.ps1 -RA 3          # zera o aluno de RA 3
  .\reset-aluno.ps1 -All           # zera TODOS os alunos (clean slate total)

.NOTES
  Requer o container do MySQL no ar (docker compose up). Não toca em conteúdo.
#>
param(
  [string]$RA = "1",
  [switch]$All
)
$ErrorActionPreference = "Stop"
$container = "ova_db"

# Confirma que o container do banco está rodando.
$running = docker ps --filter "name=$container" --format "{{.Names}}"
if ($running -notcontains $container) {
  Write-Host "[ERRO] Container '$container' nao esta rodando. Rode 'docker compose up -d' primeiro." -ForegroundColor Red
  exit 1
}

if ($All) {
  $scope = "TODOS os alunos"
  $sql = @'
SET FOREIGN_KEY_CHECKS=0;
DELETE FROM personalized_ova_item;
DELETE FROM personalized_ova;
DELETE FROM interactions;
DELETE FROM answers;
DELETE FROM attempts;
DELETE FROM ova_progress;
DELETE FROM resource_progress;
DELETE FROM interventions;
DELETE FROM alerts;
SET FOREIGN_KEY_CHECKS=1;
SELECT 'ok' AS zerado;
'@
} else {
  $scope = "aluno RA $RA"
  $sql = @"
SET @ra := '$RA';
DELETE pi FROM personalized_ova_item pi JOIN personalized_ova p ON p.personalized_ova_id=pi.personalized_ova_id JOIN students s ON s.student_id=p.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
DELETE p  FROM personalized_ova p  JOIN students s ON s.student_id=p.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
DELETE t  FROM interactions t      JOIN students s ON s.student_id=t.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
DELETE t  FROM answers t           JOIN students s ON s.student_id=t.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
DELETE t  FROM attempts t          JOIN students s ON s.student_id=t.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
DELETE t  FROM ova_progress t      JOIN students s ON s.student_id=t.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
DELETE t  FROM resource_progress t JOIN students s ON s.student_id=t.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
DELETE t  FROM interventions t     JOIN students s ON s.student_id=t.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
DELETE t  FROM alerts t            JOIN students s ON s.student_id=t.student_id WHERE s.ra=@ra COLLATE utf8mb4_unicode_ci;
SELECT CONCAT('RA ', @ra, ' zerado') AS zerado;
"@
}

Write-Host "Zerando progresso de: $scope ..." -ForegroundColor Cyan
$sql | docker exec -i -e MYSQL_PWD=Password-1 $container mysql -uroot ova_db
if ($LASTEXITCODE -ne 0) {
  Write-Host "[ERRO] Falha ao executar o reset (codigo $LASTEXITCODE)." -ForegroundColor Red
  exit $LASTEXITCODE
}
Write-Host "[OK] Pronto. De Ctrl+F5 em http://localhost:8010/app/ para ver o aluno do zero." -ForegroundColor Green
