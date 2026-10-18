import os
import re
import json
import time
import random
import subprocess
from pathlib import Path
from datetime import datetime
from instagrapi import Client
from instagrapi.exceptions import LoginRequired

try:
    from instagrapi.exceptions import TwoFactorRequired
except ImportError:
    # Versões diferentes do instagrapi podem não ter essa exceção específica.
    # Nesse caso, o 2FA é detectado pelo texto da mensagem de erro (fallback).
    TwoFactorRequired = None

import common

# Extensões de vídeo que podem vir do Instagram e precisam virar .mp4
EXTENSOES_VIDEO = {".mov", ".webm", ".mkv", ".avi", ".flv", ".3gp", ".m4v"}

# Caracteres que o Windows não aceita em nomes de arquivo
CARACTERES_INVALIDOS = r'[\\/:*?"<>|]'


# ==========================================
# UTILITÁRIOS DE NOME DE ARQUIVO
# ==========================================

def sanitizar_nome(texto, limite=60):
    """
    Remove caracteres inválidos para nomes de arquivo no Windows e
    limita o tamanho, pra não estourar o limite de caminho do sistema.
    """

    texto = re.sub(CARACTERES_INVALIDOS, "", texto)
    texto = texto.strip(" .")

    if len(texto) > limite:
        texto = texto[:limite].strip()

    return texto or "sem_nome"


def obter_titulo(media, codigo):
    """
    Usa a primeira linha da legenda como 'título'. Se não houver legenda,
    usa o tipo de mídia + o código do post como identificador.
    """

    legenda = (media.caption_text or "").strip()

    if legenda:
        primeira_linha = legenda.split("\n")[0].strip()
        if primeira_linha:
            return primeira_linha

    tipos = {1: "foto", 2: "video", 8: "album"}
    tipo = tipos.get(media.media_type, "post")

    return f"{tipo}_{codigo}"


def renomear_para_padrao(caminho, conta, titulo):
    """
    Renomeia o arquivo já baixado para o padrão:
    'conta - titulo - data_do_download.ext'
    Se já existir um arquivo com esse nome, adiciona um sufixo numerado.
    """

    if caminho is None:
        return caminho

    caminho = Path(caminho)

    if not caminho.exists():
        return caminho

    data_download = datetime.now().strftime("%Y-%m-%d")

    nome_base = sanitizar_nome(
        f"{sanitizar_nome(conta, 30)} - {sanitizar_nome(titulo, 60)} - {data_download}",
        limite=150
    )

    destino = caminho.with_name(nome_base + caminho.suffix)

    contador = 1
    while destino.exists() and destino != caminho:
        destino = caminho.with_name(f"{nome_base} ({contador}){caminho.suffix}")
        contador += 1

    try:
        caminho.rename(destino)
        return destino
    except OSError as erro:
        print("Aviso: não foi possível renomear o arquivo:", erro)
        return caminho


def garantir_mp4(caminho):
    """
    Recebe o caminho de um arquivo baixado. Se for um vídeo que não
    esteja em .mp4, converte usando o ffmpeg e apaga o original.
    Se já for .mp4 ou não for vídeo (ex: foto), retorna sem alterar.
    """

    if caminho is None:
        return caminho

    caminho = str(caminho)
    ext = os.path.splitext(caminho)[1].lower()

    if ext == ".mp4":
        return caminho

    if ext not in EXTENSOES_VIDEO:
        return caminho

    saida = os.path.splitext(caminho)[0] + ".mp4"

    print(f"Convertendo '{os.path.basename(caminho)}' para MP4...")

    try:

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", caminho,
                "-c:v", "libx264",
                "-c:a", "aac",
                saida
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        os.remove(caminho)

        print("Conversão concluída!")

        return saida

    except FileNotFoundError:

        print("\nAVISO: ffmpeg não encontrado no sistema.")
        print("O arquivo foi baixado, mas não pôde ser convertido para MP4.")
        print("Instale o ffmpeg e adicione ao PATH para ativar essa conversão.")

        return caminho

    except Exception as erro:

        print("Erro ao converter para MP4:", erro)

        return caminho


# ==========================================
# CONFIGURAÇÃO
# ==========================================

BASE = os.path.dirname(__file__)

_config = common.carregar_config()

PASTA_DOWNLOAD = os.path.join(
    BASE,
    _config["GERAL"]["pasta_downloads"],
    "instagram"
)

PASTA_POSTS = os.path.join(PASTA_DOWNLOAD, "posts")
PASTA_STORIES = os.path.join(PASTA_DOWNLOAD, "stories")
PASTA_DESTAQUES = os.path.join(PASTA_DOWNLOAD, "destaques")

os.makedirs(PASTA_POSTS, exist_ok=True)
os.makedirs(PASTA_STORIES, exist_ok=True)
os.makedirs(PASTA_DESTAQUES, exist_ok=True)

ARQUIVO_SESSAO = os.path.join(BASE, "instagram_session.json")
ARQUIVO_REGISTRO = os.path.join(BASE, "instagram_baixados.json")

# Tempo de espera (em segundos) antes de tentar o login,
# para não fazer a requisição "instantânea" e evitar bloqueio.
# Editável em config.ini, seção [INSTAGRAM].
ESPERA_ANTES_LOGIN = _config.getfloat("INSTAGRAM", "espera_antes_login")

# Tempo de espera (em segundos) antes de iniciar o download,
# depois que a mídia já foi identificada.
# Editável em config.ini, seção [INSTAGRAM].
ESPERA_ANTES_DOWNLOAD = _config.getfloat("INSTAGRAM", "espera_antes_download")

cl = Client()


# ==========================================
# REGISTRO DE JÁ BAIXADOS (evita duplicado)
# ==========================================

def carregar_registro():

    if not os.path.exists(ARQUIVO_REGISTRO):
        return {}

    try:
        with open(ARQUIVO_REGISTRO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_registro(registro):

    try:
        with open(ARQUIVO_REGISTRO, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=2)
    except Exception as erro:
        common.registrar_log("INSTAGRAM", f"Não foi possível salvar o registro de baixados: {erro}")


def ja_foi_baixado(codigo):

    registro = carregar_registro()
    return registro.get(codigo)


def marcar_como_baixado(codigo, conta, arquivos):

    registro = carregar_registro()

    registro[codigo] = {
        "conta": conta,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "arquivos": [str(a) for a in arquivos if a],
    }

    salvar_registro(registro)


# ==========================================
# LOGIN
# ==========================================

def login():

    if os.path.exists(ARQUIVO_SESSAO):

        print(f"\nSessão encontrada. Aguardando {ESPERA_ANTES_LOGIN}s antes de validar login...")
        time.sleep(ESPERA_ANTES_LOGIN)

        try:

            cl.load_settings(ARQUIVO_SESSAO)

            cl.login_by_sessionid(
                cl.get_settings()["authorization_data"]["sessionid"]
            )

            print("Login por sessão realizado com sucesso!")

            return

        except Exception as erro:

            print("\nA sessão salva não pôde ser usada.")
            print("Motivo:", erro)
            print("\nSerá necessário fazer login novamente.\n")

            common.registrar_log("INSTAGRAM", f"Sessão salva inválida: {erro}")

            # Remove a sessão inválida para não tentar de novo nas próximas vezes
            try:
                os.remove(ARQUIVO_SESSAO)
            except OSError:
                pass

    print("=" * 40)
    print(" PRIMEIRO LOGIN")
    print("=" * 40)

    usuario = input("\nUsuário: ")
    senha = input("Senha: ")

    print(f"\nAguardando {ESPERA_ANTES_LOGIN}s antes de enviar o login (evita bloqueio por comportamento suspeito)...")
    time.sleep(ESPERA_ANTES_LOGIN)

    logado = False

    try:

        cl.login(usuario, senha)

        logado = True

    except Exception as erro:

        texto_erro = str(erro).lower()

        eh_2fa = (
            (TwoFactorRequired is not None and isinstance(erro, TwoFactorRequired))
            or "two_factor" in texto_erro
            or "2fa" in texto_erro
        )

        if eh_2fa:

            print("\nEssa conta tem autenticação de dois fatores (2FA) ativada.")
            codigo = input("Digite o código de verificação (app autenticador ou SMS): ").strip()

            try:

                cl.login(usuario, senha, verification_code=codigo)

                logado = True

            except Exception as erro2:

                print("\nErro ao validar o código 2FA:")
                print(erro2)

                common.registrar_log("INSTAGRAM", f"Erro na verificação 2FA: {erro2}")

        else:

            print("\nErro ao entrar:")
            print(erro)

            common.registrar_log("INSTAGRAM", f"Erro no login: {erro}")

            if "challenge" in texto_erro or "checkpoint" in texto_erro:
                print("\nO Instagram pediu uma verificação de segurança (checkpoint/challenge).")
                print("Entre pelo app oficial ou navegador, confirme que é você, e tente de novo aqui.")

            elif "bad_password" in texto_erro or "incorrect" in texto_erro:
                print("\nUsuário ou senha incorretos.")

    if logado:

        cl.dump_settings(ARQUIVO_SESSAO)

        print("\nLogin realizado com sucesso!")

    else:

        input("\nPressione ENTER...")
        exit()


def trocar_de_conta():
    """
    Remove a sessão salva e reinicia o cliente do instagrapi,
    forçando um novo login (de outra conta, se desejado).
    """

    global cl

    if os.path.exists(ARQUIVO_SESSAO):
        os.remove(ARQUIVO_SESSAO)

    cl = Client()

    print("\nSessão anterior removida.\n")

    login()


# ==========================================
# ANALISAR URL (posts, stories, destaques)
# ==========================================

def analisar_url(url):
    """
    Identifica o tipo de link do Instagram e devolve (tipo, identificador):
    - ('post', codigo)       -> publicação, reel ou IGTV normal
    - ('story', story_pk)    -> story de 24h de um usuário
    - ('highlight', hl_id)   -> destaque fixado no perfil
    - (None, None)           -> não reconhecido
    """

    url = url.strip()

    if "/stories/highlights/" in url:
        resto = url.split("/stories/highlights/")[1]
        highlight_id = resto.split("/")[0].split("?")[0]
        if highlight_id:
            return "highlight", highlight_id
        return None, None

    if "/stories/" in url:
        resto = url.split("/stories/")[1]
        segmentos = [s for s in resto.split("/") if s]
        if len(segmentos) >= 2:
            story_pk = segmentos[1].split("?")[0]
            return "story", story_pk
        return None, None

    if "/p/" in url:
        return "post", url.split("/p/")[1].split("/")[0].split("?")[0]

    if "/reel/" in url:
        return "post", url.split("/reel/")[1].split("/")[0].split("?")[0]

    if "/tv/" in url:
        return "post", url.split("/tv/")[1].split("/")[0].split("?")[0]

    return None, None


# ==========================================
# DOWNLOAD DE POST (foto/vídeo/álbum)
# ==========================================

def baixar_post(codigo):

    anterior = ja_foi_baixado(codigo)

    if anterior:

        print(f"\nEsse post já foi baixado antes (em {anterior['data']}, conta @{anterior['conta']}).")
        resposta = input("Baixar de novo mesmo assim? (S/N): ").strip().lower()

        if resposta not in ("s", "sim"):
            print("\nDownload cancelado (já existia).")
            return

    media_id = cl.media_pk_from_code(codigo)

    media = cl.media_info(media_id)

    # Pequena espera aleatória antes de baixar, simulando comportamento humano
    # e evitando disparar limites de requisição do Instagram.
    espera = ESPERA_ANTES_DOWNLOAD + random.uniform(0, 2)
    print(f"\nMídia encontrada. Aguardando {espera:.1f}s antes de baixar...")
    time.sleep(espera)

    print("Baixando...\n")

    conta = media.user.username if media.user else "conta_desconhecida"
    titulo = obter_titulo(media, codigo)
    arquivos_baixados = []

    if media.media_type == 1:

        caminho = cl.photo_download(media_id, folder=PASTA_POSTS)
        caminho = renomear_para_padrao(caminho, conta, titulo)
        arquivos_baixados.append(caminho)

    elif media.media_type == 2:

        caminho = cl.video_download(media_id, folder=PASTA_POSTS)
        caminho = garantir_mp4(caminho)
        caminho = renomear_para_padrao(caminho, conta, titulo)
        arquivos_baixados.append(caminho)

    elif media.media_type == 8:

        caminhos = cl.album_download(media_id, folder=PASTA_POSTS)

        for item in caminhos:
            item = garantir_mp4(item)
            item = renomear_para_padrao(item, conta, titulo)
            arquivos_baixados.append(item)

    else:

        print("Tipo de mídia desconhecido.")
        return

    marcar_como_baixado(codigo, conta, arquivos_baixados)

    print("\nDownload concluído!")
    common.perguntar_e_abrir_pasta(PASTA_POSTS)


# ==========================================
# DOWNLOAD DE STORY
# ==========================================

def baixar_story(story_pk):

    try:

        story = cl.story_info(story_pk)

        conta = story.user.username if story.user else "conta_desconhecida"
        titulo = f"story_{story_pk}"

        espera = ESPERA_ANTES_DOWNLOAD + random.uniform(0, 2)
        print(f"\nStory encontrado. Aguardando {espera:.1f}s antes de baixar...")
        time.sleep(espera)

        print("Baixando...\n")

        caminho = cl.story_download(story_pk, folder=PASTA_STORIES)
        caminho = garantir_mp4(caminho)
        renomear_para_padrao(caminho, conta, titulo)

        print("\nDownload concluído!")
        common.perguntar_e_abrir_pasta(PASTA_STORIES)

    except Exception as erro:

        print("\nNão foi possível baixar esse story:")
        print(erro)
        print("\nLembrete: stories somem 24h depois de publicados. Se já passou desse")
        print("prazo, ele pode não estar mais disponível (a não ser que esteja num destaque).")

        common.registrar_log("INSTAGRAM", f"Erro ao baixar story '{story_pk}': {erro}")


# ==========================================
# DOWNLOAD DE DESTAQUE (HIGHLIGHT)
# ==========================================

def baixar_highlight(highlight_id):

    try:

        info = cl.highlight_info(f"highlight:{highlight_id}")

        itens = getattr(info, "items", None) or []

        if not itens:
            print("\nNenhum item encontrado nesse destaque.")
            return

        conta = info.user.username if getattr(info, "user", None) else "conta_desconhecida"

        print(f"\n{len(itens)} item(ns) encontrados no destaque de @{conta}.")

        for i, item in enumerate(itens, start=1):

            espera = ESPERA_ANTES_DOWNLOAD + random.uniform(0, 2)
            print(f"\n[{i}/{len(itens)}] Aguardando {espera:.1f}s antes de baixar...")
            time.sleep(espera)

            caminho = cl.story_download(item.pk, folder=PASTA_DESTAQUES)
            caminho = garantir_mp4(caminho)
            renomear_para_padrao(caminho, conta, f"destaque_{highlight_id}_{i}")

        print("\nDownload do destaque concluído!")
        common.perguntar_e_abrir_pasta(PASTA_DESTAQUES)

    except Exception as erro:

        print("\nNão foi possível baixar esse destaque:")
        print(erro)

        common.registrar_log("INSTAGRAM", f"Erro ao baixar destaque '{highlight_id}': {erro}")


# ==========================================
# DOWNLOAD (ROTEADOR)
# ==========================================

def baixar():

    url = input("\nCole a URL (post, reel, story ou destaque):\n\n")

    tipo, identificador = analisar_url(url)

    if tipo is None:
        print("\nURL inválida ou não reconhecida.")
        return

    try:

        if tipo == "post":
            baixar_post(identificador)

        elif tipo == "story":
            baixar_story(identificador)

        elif tipo == "highlight":
            baixar_highlight(identificador)

    except LoginRequired:

        print("\nSua sessão expirou.")

        common.registrar_log("INSTAGRAM", "Sessão expirou durante o download (LoginRequired).")

        if os.path.exists(ARQUIVO_SESSAO):
            os.remove(ARQUIVO_SESSAO)

        print("Abra novamente o programa.")

    except Exception as erro:

        print("\nErro:")
        print(erro)

        common.registrar_log("INSTAGRAM", f"Erro ao baixar '{url}': {erro}")

        texto_erro = str(erro).lower()

        if "not found" in texto_erro or "404" in texto_erro:
            print("\nO conteúdo pode ter sido apagado ou a conta é privada.")

        elif "rate limit" in texto_erro or "429" in texto_erro:
            print("\nMuitas requisições em pouco tempo. Espere alguns minutos e tente de novo.")


# ==========================================
# MENU
# ==========================================

def menu():

    while True:

        os.system("cls")

        print("=" * 40)
        print("       INSTAGRAM")
        print("=" * 40)

        print()
        print("1 - Baixar publicação/story/destaque")
        print("2 - Trocar de conta")
        print("0 - Voltar")

        op = input("\nEscolha: ")

        if op == "1":

            baixar()

            input("\nPressione ENTER...")

        elif op == "2":

            trocar_de_conta()

            input("\nPressione ENTER...")

        elif op == "0":

            break

        else:

            print("\nOpção inválida.")
            input("\nPressione ENTER...")


if __name__ == "__main__":

    try:
        login()
        menu()
    except KeyboardInterrupt:
        print("\n\nPrograma encerrado pelo usuário.")
