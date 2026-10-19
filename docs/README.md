# Documentação do Totale KPI

## Como os dados entram

- **Base operacional** (Quebra de Agenda, Volumetria e Rota Inicial):
  upload manual da exportação de atividades (`.xlsx`, `.xls` ou `.csv`)
  na página **Atualização de Dados** ou direto em qualquer um dos três
  painéis. Um único envio atualiza os três, com vínculo à aba
  `lista_ativos` da planilha de ativos. A leitura e o tratamento ficam
  em `components/base_operacional.py`; a interface de envio, em
  `components/upload_base.py`.
- **Produção e Consultivos**: sincronização com o Google Sheets/Drive
  na mesma página **Atualização de Dados** (`pages/envio_excel.py`),
  publicada na sessão para os painéis de performance.

Nenhum arquivo é lido do disco do servidor nem do computador do
usuário automaticamente: sem upload na sessão, os painéis
operacionais exibem apenas a tela de envio.

## Organização do repositório

| Diretório | Responsabilidade |
|---|---|
| `components/` | Design system, tratamento da base operacional, upload manual e regras compartilhadas |
| `pages/` | Painéis do portal e a Central de Atualização |
| `scripts/` | Utilitários locais (instalação da fonte Oscine) |
| `assets/` e `fonts/` | Identidade visual e tipografia |
| `config/` | Configuração versionada da aplicação (feriados extras) |
| `tests/` | Testes automatizados |
| `.github/` | CI e automações do repositório |

Mantenha credenciais e bases operacionais fora do Git. Consulte
`.gitignore` antes de adicionar arquivos locais e prefira atualizar
um guia em `docs/` quando um procedimento precisar ser documentado.
