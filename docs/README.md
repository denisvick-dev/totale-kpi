# Documentação do Totale KPI

## Guia rápido

- [Agente local de Downloads](AGENTE_DOWNLOADS.md): configuração e operação do
  sincronismo automático de arquivos do Windows.

## Organização do repositório

| Diretório | Responsabilidade |
|---|---|
| `components/` | Design system, processamento compartilhado e integrações do robô |
| `pages/` | Páginas de dashboards e ferramentas operacionais |
| `scripts/` | Utilitários CLI, automação e configuração local |
| `assets/` e `fonts/` | Identidade visual e tipografia |
| `config/` | Configuração versionada da aplicação |
| `dados/` | Diretórios locais de entrada, cache e logs (não versionados) |
| `tests/` | Testes automatizados |
| `.github/` | CI e automações do repositório |

Mantenha credenciais, bases operacionais, caches e logs fora do Git. Consulte
`.gitignore` antes de adicionar arquivos locais e prefira atualizar um guia em
`docs/` quando um procedimento precisar ser documentado.
