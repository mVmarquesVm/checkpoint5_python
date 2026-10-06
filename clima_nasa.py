"""
Consulta Meteorológica com Dados da NASA
Checkpoint 5 - Computational Thinking With Python

Consome a NASA POWER API (https://power.larc.nasa.gov/docs/services/api/)
para consultar dados meteorológicos diários (temperatura, chuva, umidade e
vento) de qualquer local do planeta, gerar um resumo do período e salvar
os resultados em um arquivo JSON.
"""

import json
import sys
from datetime import date, datetime, timedelta

import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

URL_API = "https://power.larc.nasa.gov/api/temporal/daily/point"
ARQUIVO_JSON = "dados_climaticos.json"
TIMEOUT = 30  # segundos
VALOR_AUSENTE = -999.0 
PARAMETROS = {
    "T2M": "temp_media",
    "T2M_MIN": "temp_min",
    "T2M_MAX": "temp_max",
    "PRECTOTCORR": "chuva_mm",
    "RH2M": "umidade",
    "WS2M": "vento",
}

CIDADES = {
    "1": ("São Paulo - SP", -23.55, -46.63),
    "2": ("Rio de Janeiro - RJ", -22.91, -43.17),
    "3": ("Brasília - DF", -15.79, -47.88),
    "4": ("Salvador - BA", -12.97, -38.50),
    "5": ("Manaus - AM", -3.12, -60.02),
    "6": ("Porto Alegre - RS", -30.03, -51.23),
    "7": ("Recife - PE", -8.05, -34.88),
    "8": ("Curitiba - PR", -25.43, -49.27),
}


def buscar_dados_nasa(latitude, longitude, inicio, fim):
    """Faz a requisição GET à NASA POWER e devolve o JSON como dict.

    Levanta RuntimeError com uma mensagem amigável caso algo dê errado.
    """
    parametros = {
        "parameters": ",".join(PARAMETROS),
        "community": "AG",  # AG = agroclimatologia (unidades em °C, mm, m/s)
        "latitude": latitude,
        "longitude": longitude,
        "start": inicio.strftime("%Y%m%d"),
        "end": fim.strftime("%Y%m%d"),
        "format": "JSON",
    }

    try:
        resposta = requests.get(URL_API, params=parametros, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        raise RuntimeError("A API da NASA demorou demais para responder. Tente novamente.")
    except requests.exceptions.SSLError:
        raise RuntimeError("Erro de certificado SSL. Instale o pacote 'truststore' (pip install truststore).")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Não foi possível conectar à API. Verifique sua internet.")

    if resposta.status_code == 422:
        raise RuntimeError(f"Parâmetros recusados pela API: {extrair_mensagem_erro(resposta)}")
    if resposta.status_code == 429:
        raise RuntimeError("Limite de requisições atingido. Aguarde um pouco e tente de novo.")
    if resposta.status_code != 200:
        raise RuntimeError(f"A API retornou um erro inesperado (HTTP {resposta.status_code}).")

    try:
        return resposta.json()
    except ValueError:
        raise RuntimeError("A API retornou uma resposta que não é um JSON válido.")


def extrair_mensagem_erro(resposta):
    """Tenta ler a mensagem de erro que a API manda no corpo da resposta."""
    try:
        detalhes = resposta.json()["detail"]
        return "; ".join(item["msg"] for item in detalhes)
    except (ValueError, KeyError, TypeError):
        return resposta.text[:200]


def processar_dados(dados_api):
    """Transforma o JSON da NASA em uma lista de dias.

    A API organiza os dados por variável:
        {"T2M": {"20261001": 20.6, "20261002": 16.7}, "RH2M": {...}}
    Aqui reorganizamos por dia, que é mais fácil de exibir:
        [{"data": "01/10/2026", "temp_media": 20.6, "umidade": 87.6, ...}, ...]
    """
    try:
        valores_por_parametro = dados_api["properties"]["parameter"]
        datas = valores_por_parametro["T2M"].keys()
    except (KeyError, TypeError):
        raise RuntimeError("O JSON da NASA não veio no formato esperado.")

    dias = []
    for data_texto in datas:
        dia = {"data": datetime.strptime(data_texto, "%Y%m%d").strftime("%d/%m/%Y")}
        for codigo, nome in PARAMETROS.items():
            valor = valores_por_parametro.get(codigo, {}).get(data_texto, VALOR_AUSENTE)
            # -999 significa "sem dado"; guardamos como None (vira null no JSON)
            dia[nome] = None if valor == VALOR_AUSENTE else valor
        dias.append(dia)
    return dias


def calcular_resumo(dias):
    """Gera estatísticas do período, ignorando os dias sem dados."""
    dias_validos = [d for d in dias if d["temp_media"] is not None]
    if not dias_validos:
        raise RuntimeError("A NASA ainda não tem dados para esse período. Escolha datas mais antigas.")

    mais_quente = max(dias_validos, key=lambda d: d["temp_max"])
    mais_frio = min(dias_validos, key=lambda d: d["temp_min"])
    chuvas = [d["chuva_mm"] for d in dias_validos if d["chuva_mm"] is not None]

    return {
        "dias_com_dados": len(dias_validos),
        "dias_sem_dados": len(dias) - len(dias_validos),
        "temp_media": round(media([d["temp_media"] for d in dias_validos]), 1),
        "dia_mais_quente": {"data": mais_quente["data"], "temp_max": mais_quente["temp_max"]},
        "dia_mais_frio": {"data": mais_frio["data"], "temp_min": mais_frio["temp_min"]},
        "chuva_total_mm": round(sum(chuvas), 1),
        "dias_com_chuva": len([c for c in chuvas if c >= 1.0]),  # >= 1 mm conta como dia chuvoso
        "umidade_media": round(media([d["umidade"] for d in dias_validos if d["umidade"] is not None]), 1),
    }


def media(valores):
    return sum(valores) / len(valores) if valores else 0.0


def carregar_consultas():
    """Lê as consultas já salvas. Se o arquivo não existir, começa vazio."""
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print(f"Aviso: {ARQUIVO_JSON} está corrompido. Um novo arquivo será criado.")
        return []


def salvar_consulta(consulta):
    """Acrescenta uma consulta ao arquivo JSON."""
    consultas = carregar_consultas()
    consultas.append(consulta)
    try:
        with open(ARQUIVO_JSON, "w", encoding="utf-8") as arquivo:
            json.dump(consultas, arquivo, ensure_ascii=False, indent=2)
        print(f"\n(consulta salva em {ARQUIVO_JSON})")
    except OSError as erro:
        print(f"Não foi possível salvar o arquivo: {erro}")



def escolher_local():
    """Deixa o usuário escolher uma cidade da lista ou digitar coordenadas."""
    print("\nEscolha o local:")
    for chave, (nome, _, _) in CIDADES.items():
        print(f"  {chave}) {nome}")
    print("  9) Digitar latitude e longitude")
    escolha = input("Opção: ").strip()

    if escolha in CIDADES:
        return CIDADES[escolha]
    if escolha == "9":
        latitude = ler_coordenada("Latitude (-90 a 90): ", -90, 90)
        longitude = ler_coordenada("Longitude (-180 a 180): ", -180, 180)
        return (f"Coordenadas ({latitude}, {longitude})", latitude, longitude)
    raise ValueError("Opção de local inválida.")


def ler_coordenada(mensagem, minimo, maximo):
    texto = input(mensagem).replace(",", ".")
    try:
        valor = float(texto)
    except ValueError:
        raise ValueError(f"'{texto}' não é um número válido.")
    if not minimo <= valor <= maximo:
        raise ValueError(f"O valor deve estar entre {minimo} e {maximo}.")
    return valor


def ler_periodo():
    """Lê a data inicial e a final. Enter em branco = últimos 30 dias."""
    print("\nPeríodo (formato dd/mm/aaaa). Deixe em branco para os últimos 30 dias.")
    texto_inicio = input("Data inicial: ").strip()
    texto_fim = input("Data final: ").strip()

    if not texto_inicio and not texto_fim:
        fim = date.today() - timedelta(days=1)
        return fim - timedelta(days=29), fim

    inicio = converter_data(texto_inicio)
    fim = converter_data(texto_fim)
    if inicio > fim:
        raise ValueError("A data inicial deve ser anterior à data final.")
    if fim >= date.today():
        raise ValueError("A data final deve ser anterior a hoje (a NASA só tem dados passados).")
    if inicio < date(1981, 1, 1):
        raise ValueError("A NASA POWER só tem dados diários a partir de 01/01/1981.")
    if (fim - inicio).days > 365:
        raise ValueError("Escolha um período de no máximo 1 ano.")
    return inicio, fim


def converter_data(texto):
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        raise ValueError(f"'{texto}' não é uma data válida. Use dd/mm/aaaa.")



def formatar(valor, casas=1):
    """Mostra '--' quando o dado não existe."""
    return "--" if valor is None else f"{valor:.{casas}f}"


def exibir_tabela(dias):
    print(f"\n{'Data':<12}{'Média':>7}{'Mín':>7}{'Máx':>7}{'Chuva':>9}{'Umid.':>8}{'Vento':>8}")
    print(f"{'':<12}{'°C':>7}{'°C':>7}{'°C':>7}{'mm':>9}{'%':>8}{'m/s':>8}")
    print("-" * 58)
    for d in dias:
        print(f"{d['data']:<12}{formatar(d['temp_media']):>7}{formatar(d['temp_min']):>7}"
              f"{formatar(d['temp_max']):>7}{formatar(d['chuva_mm']):>9}"
              f"{formatar(d['umidade'], 0):>8}{formatar(d['vento']):>8}")


def exibir_resumo(resumo):
    print("\n========== RESUMO DO PERÍODO ==========")
    print(f"Temperatura média:  {resumo['temp_media']} °C")
    print(f"Dia mais quente:    {resumo['dia_mais_quente']['data']} ({resumo['dia_mais_quente']['temp_max']} °C)")
    print(f"Dia mais frio:      {resumo['dia_mais_frio']['data']} ({resumo['dia_mais_frio']['temp_min']} °C)")
    print(f"Chuva acumulada:    {resumo['chuva_total_mm']} mm em {resumo['dias_com_chuva']} dia(s) chuvoso(s)")
    print(f"Umidade média:      {resumo['umidade_media']} %")
    if resumo["dias_sem_dados"]:
        print(f"Obs.: {resumo['dias_sem_dados']} dia(s) ainda sem dados da NASA (marcados com --).")


def opcao_nova_consulta():
    nome, latitude, longitude = escolher_local()
    inicio, fim = ler_periodo()

    print(f"\nConsultando a NASA para {nome} de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}...")
    dados_api = buscar_dados_nasa(latitude, longitude, inicio, fim)
    dias = processar_dados(dados_api)
    resumo = calcular_resumo(dias)

    print(f"\n{nome}")
    exibir_tabela(dias)
    exibir_resumo(resumo)

    salvar_consulta({
        "local": nome,
        "latitude": latitude,
        "longitude": longitude,
        "periodo": {"inicio": f"{inicio:%d/%m/%Y}", "fim": f"{fim:%d/%m/%Y}"},
        "consultado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "resumo": resumo,
        "dias": dias,
    })


def opcao_ver_salvas():
    consultas = carregar_consultas()
    if not consultas:
        print("\nNenhuma consulta salva ainda.")
        return
    print(f"\n{len(consultas)} consulta(s) salva(s) em {ARQUIVO_JSON}:")
    for i, c in enumerate(consultas, start=1):
        print(f"{i:>3}. {c['local']:<28} {c['periodo']['inicio']} a {c['periodo']['fim']}"
              f"  | média {c['resumo']['temp_media']} °C, chuva {c['resumo']['chuva_total_mm']} mm")


def main():
    # Garante que acentos e o símbolo ° aparecem corretamente no terminal do Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    while True:
        print("\n===== CONSULTA METEOROLÓGICA - NASA POWER =====")
        print("1) Nova consulta")
        print("2) Ver consultas salvas")
        print("0) Sair")
        escolha = input("Escolha uma opção: ").strip()

        try:
            if escolha == "1":
                opcao_nova_consulta()
            elif escolha == "2":
                opcao_ver_salvas()
            elif escolha == "0":
                print("Até mais!")
                break
            else:
                print("Opção inválida.")
        except (ValueError, RuntimeError) as erro:
            print(f"Erro: {erro}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nPrograma encerrado.")
