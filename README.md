# Hermes Analytics

Aplicacao web local para monitorar bases de dados, refazer a analise quando o
arquivo muda, gerar insights e publicar tabelas prontas para Power BI. O sistema
detecta automaticamente bases imobiliarias e bases de credito SCR.

Documentacao completa: [DOCUMENTACAO_SISTEMA.md](DOCUMENTACAO_SISTEMA.md)

## Demonstracao rapida

1. Execute `iniciar_demo.bat`.
2. Abra `http://localhost:8501`.
3. Para apresentar em outro computador na mesma rede, abra
   `http://IP-DO-SEU-PC:8501`.
4. Edite ou substitua um arquivo em `data/inbox`. Em ate cinco segundos a
   aplicacao detecta a mudanca e refaz o pipeline.

O arquivo de exemplo e `data/inbox/property_prices.csv`, com 1.800 anuncios
imobiliarios sinteticos de Sao Paulo, Rio de Janeiro, Belo Horizonte e Curitiba.
Na primeira execucao, o inicializador cria um ambiente `.venv` isolado.

## Fluxo

```text
CSV/Parquet -> validacao e limpeza -> metricas e tabelas -> Hermes -> dashboard
                                      |
                                      +-> outputs/powerbi/*.csv e *.parquet
```

O monitor usa SHA-256, portanto uma mudanca real no conteudo dispara o
reprocessamento mesmo que o nome do arquivo continue igual.

## Power BI

No Power BI Desktop:

1. Use **Obter dados > Pasta** e selecione `outputs/powerbi`; ou
2. Para a base SCR atual, importe `outputs/powerbi/fato_credito.parquet`.

As tabelas `dim_*` e `resumo_*` podem ser relacionadas a `fato_imoveis` ou
`fato_credito`, conforme o dominio detectado.
Para uma atualizacao durante a apresentacao, altere a base, aguarde o
reprocessamento e clique em **Atualizar** no Power BI.

## Hermes

O sistema chama o executavel local `hermes` para produzir a narrativa. Neste
computador, o Hermes Agent esta configurado com OpenAI Codex, portanto essa
etapa requer internet. Se ele falhar ou exceder o tempo limite, o dashboard usa
insights deterministas locais e o processamento nao para.

Para desativar chamadas automaticas:

```powershell
$env:HERMES_AUTO_INSIGHTS = "0"
.\iniciar.ps1
```

## Deploy com o Hermes rodando no computador local

O aplicativo publicado pode chamar o Hermes deste computador por meio de uma
API local protegida e de um Cloudflare Tunnel HTTPS.

### Preparacao inicial

```powershell
powershell -ExecutionPolicy Bypass -File .\configurar_ponte_hermes.ps1
powershell -ExecutionPolicy Bypass -File .\instalar_cloudflared.ps1
```

### Iniciar a integracao online

Execute `INICIAR_HERMES_ONLINE.bat`. Ele abre:

1. a API local em `http://127.0.0.1:8787`;
2. o tunel HTTPS do Cloudflare.

O script exibe a URL `https://...trycloudflare.com` e a salva automaticamente
em `data/state/hermes-tunnel-url.txt`.

Depois execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\gerar_secrets_streamlit.ps1
```

Cadastre o conteudo de `data/state/SECRETS_STREAMLIT_PRONTO.toml` em
**Streamlit Community Cloud > App settings > Secrets**.

O computador precisa permanecer ligado com a API e o tunel abertos. A URL de
um Quick Tunnel muda quando ele e reiniciado; nesse caso, atualize
`HERMES_API_URL` nos Secrets. Para uma URL permanente, configure posteriormente
um Named Tunnel em uma conta Cloudflare com dominio proprio.

## Desenvolvimento

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe scripts\generate_property_prices.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```
