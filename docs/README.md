# Documentação do Totale KPI

## Como os dados entram

- **Produção e Consultivos**: sincronização com o Google Sheets/Drive
  na página **Atualização de Dados** (`pages/envio_excel.py`),
  publicada na sessão para os painéis de performance.

Nenhum arquivo é lido do disco do servidor nem do computador do
usuário automaticamente: sem a sincronização na sessão, os painéis
exibem o aviso de dados ausentes.

## Organização do repositório

| Diretório | Responsabilidade |
|---|---|
| `components/` | Design system, calendário e regras compartilhadas |
| `pages/` | Painéis do portal e a Central de Atualização |
| `scripts/` | Utilitários locais (instalação da fonte Oscine) |
| `assets/` e `fonts/` | Identidade visual e tipografia |
| `config/` | Configuração versionada da aplicação (feriados extras) |
| `tests/` | Testes automatizados |
| `.github/` | CI e automações do repositório |

Mantenha credenciais e bases operacionais fora do Git. Consulte
`.gitignore` antes de adicionar arquivos locais e prefira atualizar
um guia em `docs/` quando um procedimento precisar ser documentado.
