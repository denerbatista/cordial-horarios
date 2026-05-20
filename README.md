# Horários Cordial Turismo — site de consulta

Site estático que mostra os horários da **Cordial Transportes e Turismo** (ES) extraídos dos PDFs oficiais. Uma GitHub Action roda diariamente, descobre os PDFs no site da empresa, parseia o conteúdo e atualiza o `schedules.json` que alimenta o site.

> Projeto **independente / não-oficial**. Em caso de divergência, sempre confira na [página oficial da Cordial](http://www.cordialturismo.com.br/portal/horarios_geral/).

## Funcionalidades

- Busca **origem → destino** com filtro por dia da semana
- **Próximos ônibus** saindo de um local a partir de um horário (default: agora)
- Visualização **por linha** (números 001, 002, …)
- Filtro por setor (Aracruz, São Mateus, Domingos Martins)
- URL com estado: links de busca compartilháveis (`#mode=search&from=...`)
- Tema claro/escuro automático
- 100% estático, sem backend

## Estrutura

```
cordial-horarios/
├── .github/workflows/update-schedules.yml   # Action diária + deploy Pages
├── scripts/
│   ├── parser.py     # texto → viagens estruturadas
│   ├── extractor.py  # download de PDF + pdfplumber
│   └── build.py      # orquestra tudo e gera schedules.json
├── site/
│   ├── index.html               # SPA (HTML/CSS/JS puro)
│   └── data/schedules.json      # banco gerado pela Action
├── fixtures/                    # textos pra dev sem rede
└── requirements.txt
```

## Pós-push (configurar 1x)

1. **Pages**: Settings → Pages → Source: **GitHub Actions**
2. **Permissões do bot**: Settings → Actions → General → Workflow permissions → **Read and write permissions**
3. **Primeira execução**: aba Actions → "Atualizar horários" → Run workflow
4. Site fica em `https://SEU_USUARIO.github.io/cordial-horarios/`

A partir daí roda sozinha todo dia às 06:00 UTC (≈ 03:00 BRT). Quando os PDFs mudam, commita novo `schedules.json` e republica o Pages.

## Local

```bash
pip install -r requirements.txt
python scripts/build.py --from-fixtures   # sem rede
python scripts/build.py                   # baixando PDFs
cd site && python -m http.server 8000
```

## Schema do `schedules.json`

```jsonc
{
  "schemaVersion": 1,
  "generatedAt": "2026-05-19T06:01:02Z",
  "source": "web",
  "totalTrips": 540,
  "places": ["Aracruz", "Coqueiral", "..."],
  "sectors": {
    "aracruz":          { "label": "...", "source_url": "...", "trip_count": 340, "trips": [...] },
    "sao_mateus":       { "label": "...", "source_url": "...", "trip_count": 16,  "trips": [...] },
    "domingos_martins": { "label": "...", "source_url": "...", "trip_count": 62,  "trips": [...] }
  },
  "trips": [
    {
      "id": "ar-00001",
      "sector": "aracruz",
      "line": "001",
      "origin": "Aracruz",
      "destination": "Praia Formosa",
      "time": "05:30",
      "days": ["mon","tue","wed","thu","fri"],
      "via": "Coqueiral + Santa Cruz",
      "school_only": false
    }
  ]
}
```

## Licença

MIT.
