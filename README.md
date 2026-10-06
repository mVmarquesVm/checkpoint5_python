# Consulta Meteorológica com Dados da NASA

Checkpoint 5 – Computational Thinking With Python (FIAP)

## Integrantes

| Nome | RM |
|------|----|
| Matheus Marques De Souza | RMxxxxx |
| | |
| | |

## O problema

Muitas pessoas precisam de **dados históricos do clima** de um local, e não só da previsão do tempo. Alguns exemplos:

- um agricultor que quer saber quanto choveu no último mês;
- quem está planejando uma viagem e quer saber como costuma ser o clima de uma cidade naquela época do ano;
- um estudante que quer comparar a temperatura de duas regiões.

Esses dados existem, mas ficam espalhados e costumam vir em formatos difíceis de ler. Esta aplicação de terminal usa os dados de satélite da **NASA** para:

1. Consultar temperatura (média, mínima e máxima), chuva, umidade e vento **dia a dia** de qualquer local do planeta, escolhendo uma capital da lista ou digitando latitude e longitude;
2. Gerar um **resumo do período**: temperatura média, dia mais quente, dia mais frio, chuva acumulada, número de dias chuvosos e umidade média;
3. **Salvar todas as consultas** no arquivo `dados_climaticos.json`, para comparar depois.

## A API escolhida: NASA POWER

- **Documentação:** https://power.larc.nasa.gov/docs/services/api/
- **Endpoint usado:** `https://power.larc.nasa.gov/api/temporal/daily/point`
- **POWER** significa *Prediction Of Worldwide Energy Resources*. É um projeto da NASA que disponibiliza dados meteorológicos e de energia solar obtidos por satélites e modelos climáticos.
- É **pública e gratuita**, não exige cadastro nem chave e retorna **JSON**.
- Tem dados diários desde **1981** para qualquer coordenada do planeta.

### Parâmetros da requisição

```
GET https://power.larc.nasa.gov/api/temporal/daily/point
    ?parameters=T2M,T2M_MIN,T2M_MAX,PRECTOTCORR,RH2M,WS2M
    &community=AG
    &latitude=-23.55
    &longitude=-46.63
    &start=20261001
    &end=20261003
    &format=JSON
```

| Parâmetro | Significado |
|-----------|-------------|
| `parameters` | Variáveis desejadas, separadas por vírgula (tabela abaixo) |
| `community` | Perfil de usuário. `AG` (agroclimatologia) retorna °C, mm e m/s |
| `latitude` / `longitude` | Local da consulta (-90 a 90 / -180 a 180) |
| `start` / `end` | Período, no formato `AAAAMMDD` |
| `format` | Formato da resposta (`JSON`) |

| Variável | Descrição | Unidade |
|----------|-----------|---------|
| `T2M` | Temperatura média a 2 metros do solo | °C |
| `T2M_MIN` / `T2M_MAX` | Temperatura mínima / máxima | °C |
| `PRECTOTCORR` | Precipitação (chuva) corrigida | mm/dia |
| `RH2M` | Umidade relativa do ar | % |
| `WS2M` | Velocidade do vento a 2 metros | m/s |

### Estrutura dos dados retornados

A resposta segue o padrão **GeoJSON** (resumida abaixo):

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [-46.63, -23.55, 790.19] },
  "properties": {
    "parameter": {
      "T2M":   { "20261001": 20.61, "20261002": 16.76, "20261004": -999.0 },
      "RH2M":  { "20261001": 87.63, "20261002": 93.03, "20261004": -999.0 }
    }
  },
  "header": { "fill_value": -999.0, "start": "20261001", "end": "20261004" },
  "parameters": {
    "T2M": { "units": "C", "longname": "Temperature at 2 Meters" }
  }
}
```

Pontos importantes que o script precisa tratar:

- Os valores ficam em `properties → parameter → VARIÁVEL → DATA`. Ou seja, os dados vêm **organizados por variável**, e não por dia. A função `processar_dados` inverte essa organização para montar uma lista de dias, que é mais fácil de exibir.
- As datas vêm como texto `AAAAMMDD` (`"20261001"`) e são convertidas para `dd/mm/aaaa`.
- **`-999.0` significa "sem dado"** (`fill_value`). Isso acontece principalmente nos últimos 2 ou 3 dias, porque o processamento dos dados de satélite tem atraso. O script troca esse valor por `None` (`null` no JSON), mostra `--` na tabela e ignora esses dias no resumo.
- A terceira coordenada em `geometry.coordinates` é a altitude do ponto, em metros.

Quando algum parâmetro é inválido, a API responde com **HTTP 422** e explica o motivo:

```json
{"detail": [{"loc": ["query", "latitude"], "msg": "Input should be greater than or equal to -90"}]}
```

## Como o código está organizado

Tudo está em [`clima_nasa.py`](clima_nasa.py), dividido em funções por responsabilidade:

| Grupo | Funções | Responsabilidade |
|-------|---------|------------------|
| Comunicação com a API | `buscar_dados_nasa`, `extrair_mensagem_erro` | Montar os parâmetros, fazer o GET com `requests` e tratar erros HTTP |
| Processamento | `processar_dados`, `calcular_resumo`, `media` | Reorganizar o JSON por dia, tratar o `-999` e gerar estatísticas |
| Arquivo JSON | `carregar_consultas`, `salvar_consulta` | Ler e gravar o histórico de consultas |
| Entrada do usuário | `escolher_local`, `ler_coordenada`, `ler_periodo`, `converter_data` | Validar local, coordenadas e datas |
| Exibição | `exibir_tabela`, `exibir_resumo`, `formatar` | Mostrar a tabela diária e o resumo |
| Menu | `main`, `opcao_nova_consulta`, `opcao_ver_salvas` | Laço principal e ações do menu |

Fluxo de uma consulta:

```
escolher_local → ler_periodo → buscar_dados_nasa → processar_dados → calcular_resumo
              → exibir_tabela / exibir_resumo → salvar_consulta
```

## Tratamento de erros

| Situação | Como é tratada |
|----------|----------------|
| Sem internet / API fora do ar | `requests.exceptions.ConnectionError` → mensagem amigável |
| API demora a responder | `timeout=30` + `requests.exceptions.Timeout` |
| Erro de certificado SSL (redes com proxy) | `requests.exceptions.SSLError` + uso do `truststore` |
| Parâmetro recusado pela API | `status_code == 422` → mostra a mensagem enviada pela NASA |
| Muitas requisições | `status_code == 429` |
| Resposta que não é JSON | `ValueError` em `resposta.json()` |
| JSON fora do formato esperado | `KeyError` / `TypeError` em `processar_dados` |
| Dia sem dado (`-999`) | Vira `None`, aparece como `--` e é ignorado no resumo |
| Período inteiro sem dados | Mensagem pedindo datas mais antigas |
| Latitude/longitude fora do intervalo ou não numérica | Validação em `ler_coordenada` |
| Data inválida (ex.: `31/02/2026`), invertida, futura, anterior a 1981 ou período maior que 1 ano | Validação em `ler_periodo` / `converter_data` |
| Arquivo JSON inexistente ou corrompido | `FileNotFoundError` / `json.JSONDecodeError` → recomeça vazio |
| Falha ao gravar o arquivo | `OSError` |
| Ctrl+C para sair | `KeyboardInterrupt` → encerra sem mostrar o traceback |

As funções levantam `RuntimeError` ou `ValueError` com uma mensagem clara, e o `main` captura essas exceções e as mostra ao usuário sem fechar o programa.

## Arquivo JSON com os dados

O arquivo [`dados_climaticos.json`](dados_climaticos.json) contém dados reais obtidos da NASA POWER: São Paulo nos últimos 30 dias, Manaus em janeiro de 2026 e Londres (por coordenadas) na primeira semana de julho de 2026. Cada consulta é salva neste formato:

```json
{
  "local": "Manaus - AM",
  "latitude": -3.12,
  "longitude": -60.02,
  "periodo": { "inicio": "01/01/2026", "fim": "31/01/2026" },
  "consultado_em": "06/10/2026 19:30:12",
  "resumo": {
    "temp_media": 26.4,
    "dia_mais_quente": { "data": "02/01/2026", "temp_max": 30.01 },
    "chuva_total_mm": 287.2,
    "dias_com_chuva": 27,
    "...": "..."
  },
  "dias": [
    { "data": "01/01/2026", "temp_media": 26.9, "temp_min": 24.6, "temp_max": 29.7,
      "chuva_mm": 1.6, "umidade": 88.0, "vento": 0.6 }
  ]
}
```

## Como executar

Pré-requisito: Python 3.10 ou superior.

```bash
# 1. Clonar o repositório
git clone <url-do-repositorio>
cd checkpoint5_python

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Executar
python clima_nasa.py
```

### Exemplo de uso

```
===== CONSULTA METEOROLÓGICA - NASA POWER =====
1) Nova consulta
2) Ver consultas salvas
0) Sair
Escolha uma opção: 1

Escolha o local:
  1) São Paulo - SP
  ...
  9) Digitar latitude e longitude
Opção: 1

Período (formato dd/mm/aaaa). Deixe em branco para os últimos 30 dias.
Data inicial:
Data final:

Data          Média    Mín    Máx    Chuva   Umid.   Vento
                 °C     °C     °C       mm       %     m/s
----------------------------------------------------------
02/10/2026     16.8   14.4   18.1      3.4      93     1.4
03/10/2026     19.0   14.4   25.5      6.1      84     1.2
04/10/2026       --     --     --       --      --      --

========== RESUMO DO PERÍODO ==========
Temperatura média:  18.3 °C
Dia mais quente:    29/09/2026 (30.92 °C)
Dia mais frio:      07/09/2026 (9.95 °C)
Chuva acumulada:    159.6 mm em 23 dia(s) chuvoso(s)
Umidade média:      85.7 %
Obs.: 2 dia(s) ainda sem dados da NASA (marcados com --).
```

## Dependências

- [`requests`](https://requests.readthedocs.io/): faz as requisições HTTP.
- [`truststore`](https://pypi.org/project/truststore/): faz o Python usar os certificados do sistema operacional. Isso é necessário em redes que inspecionam o HTTPS, como a do laboratório da faculdade.
