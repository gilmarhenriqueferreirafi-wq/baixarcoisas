import os
import configparser
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE, "config.ini")
LOG_PATH = os.path.join(BASE, "log.txt")


# ==========================================
# CONFIGURAÇÃO (config.ini)
# ==========================================

def _criar_config_padrao():
    config = configparser.ConfigParser()

    config["GERAL"] = {
        "pasta_downloads": "downloads",
        "abrir_pasta_apos_download": "perguntar",
    }

    config["INSTAGRAM"] = {
        "espera_antes_login": "5",
        "espera_antes_download": "4",
    }

    config["YOUTUBE"] = {
        "baixar_legendas_padrao": "nao",
        "idioma_legendas": "pt",
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)

    return config


def salvar_config(config):
    """
    Grava o objeto de configuração (configparser) de volta no config.ini.
    """

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)


def carregar_config():
    """
    Lê o config.ini na pasta do programa. Se não existir, cria um
    com valores padrão. Sempre garante que as seções/chaves usadas
    pelo programa existam, mesmo que o usuário tenha apagado alguma.
    """

    config = configparser.ConfigParser()

    if not os.path.exists(CONFIG_PATH):
        return _criar_config_padrao()

    config.read(CONFIG_PATH, encoding="utf-8")

    alterado = False

    padroes = {
        "GERAL": {"pasta_downloads": "downloads", "abrir_pasta_apos_download": "perguntar"},
        "INSTAGRAM": {"espera_antes_login": "5", "espera_antes_download": "4"},
        "YOUTUBE": {
            "baixar_legendas_padrao": "nao",
            "idioma_legendas": "pt",
            "max_downloads_paralelos": "3",
            "modo_download_multiplo_padrao": "perguntar",
            "qualidade_audio_kbps": "128",
            "nomear_audio_numerico": "nao",
        },
    }

    for secao, chaves in padroes.items():
        if secao not in config:
            config[secao] = {}
            alterado = True
        for chave, valor in chaves.items():
            if chave not in config[secao]:
                config[secao][chave] = valor
                alterado = True

    if alterado:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            config.write(f)

    # Corrige acidentes comuns: aspas ou espaços colados no caminho,
    # que quebram o os.makedirs com WinError 123.
    config["GERAL"]["pasta_downloads"] = _limpar_caminho(config["GERAL"]["pasta_downloads"])

    return config


def _limpar_caminho(valor):
    """Remove aspas simples/duplas e espaços nas pontas de um caminho digitado."""
    return valor.strip().strip('"').strip("'").strip()


# ==========================================
# LOG DE ERROS (log.txt)
# ==========================================

def registrar_log(origem, mensagem):
    """
    Adiciona uma linha no log.txt com data/hora, origem (ex: 'INSTAGRAM')
    e a mensagem do erro. Nunca lança exceção — se o log falhar,
    o programa principal não deve ser interrompido por causa disso.
    """

    try:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{agora}] [{origem}] {mensagem}\n")

    except Exception:
        pass


# ==========================================
# ABRIR PASTA NO EXPLORER
# ==========================================

def abrir_pasta(caminho):
    """
    Abre a pasta informada no Explorer do Windows.
    Nunca lança exceção — se não conseguir abrir, apenas ignora.
    """

    try:
        os.startfile(caminho)
    except Exception:
        pass


def perguntar_e_abrir_pasta(caminho):
    """
    Decide se abre a pasta de downloads, de acordo com a opção
    'abrir_pasta_apos_download' em config.ini, seção [GERAL]:
    - "sempre"    -> abre direto, sem perguntar
    - "nunca"     -> nunca abre, nem pergunta
    - "perguntar" (padrão) -> pergunta ao usuário, como antes
    """

    try:
        config = carregar_config()
        modo = config["GERAL"].get("abrir_pasta_apos_download", "perguntar").strip().lower()
    except Exception:
        modo = "perguntar"

    if modo == "sempre":
        abrir_pasta(caminho)
        return

    if modo == "nunca":
        return

    resposta = input("\nAbrir a pasta com os downloads? (S/N): ").strip().lower()

    if resposta in ("s", "sim"):
        abrir_pasta(caminho)
