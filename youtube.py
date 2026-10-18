import os
import sys
import subprocess
from datetime import datetime

try:
    import yt_dlp
except ImportError:
    print("yt-dlp não encontrado. Instale/execute pelo menu.bat primeiro.")
    sys.exit(1)

import common
from ffmpeg_utils import get_ffmpeg_path

# ==========================
# CONFIGURAÇÃO
# ==========================

_config = common.carregar_config()

PASTA_YOUTUBE = os.path.join(
    os.path.dirname(__file__),
    _config["GERAL"]["pasta_downloads"],
    "youtube"
)

PASTA_AUDIO = os.path.join(PASTA_YOUTUBE, "audio")
PASTA_VIDEO = os.path.join(PASTA_YOUTUBE, "video")

os.makedirs(PASTA_AUDIO, exist_ok=True)
os.makedirs(PASTA_VIDEO, exist_ok=True)

# Editável em config.ini, seção [YOUTUBE]
BAIXAR_LEGENDAS_PADRAO = _config["YOUTUBE"]["baixar_legendas_padrao"].strip().lower() in ("sim", "s", "true", "1")
IDIOMA_LEGENDAS = _config["YOUTUBE"]["idioma_legendas"].strip()

# Bitrate do MP3 baixado (em kbps). Editável em config.ini, seção [YOUTUBE].
# Quanto menor, mais leve o arquivo (e menor a qualidade). Padrão: 128.
try:
    QUALIDADE_AUDIO_KBPS = max(32, int(float(_config["YOUTUBE"].get("qualidade_audio_kbps", "128"))))
except ValueError:
    QUALIDADE_AUDIO_KBPS = 128

# Se "sim", os áudios são salvos só com número (1.mp3, 2.mp3, ...) em vez
# do nome completo do vídeo. Editável em config.ini, seção [YOUTUBE].
NOMEAR_AUDIO_NUMERICO = _config["YOUTUBE"].get("nomear_audio_numerico", "nao").strip().lower() in ("sim", "s", "true", "1")


def proximo_numero_audio():
    """
    Olha os arquivos que já existem em PASTA_AUDIO com nome puramente
    numérico (1.mp3, 2.mp3, ...) e devolve o próximo número livre.
    Usado quando 'nomear_audio_numerico' está ativado no config.ini.
    """

    maior = 0

    if os.path.isdir(PASTA_AUDIO):
        for nome in os.listdir(PASTA_AUDIO):
            base, _ = os.path.splitext(nome)
            if base.isdigit():
                maior = max(maior, int(base))

    return maior + 1


def template_nome_arquivo(playlist=False):
    """
    Gera o padrão de nome de arquivo: 'Canal - Titulo - Data do download.ext'
    Se for playlist, inclui a posição do vídeo dentro dela.
    A data é a do momento do download (não a data de publicação do vídeo).
    --windows-filenames (usado no comando do yt-dlp) já remove caracteres
    inválidos do nome do canal e do título automaticamente.
    """

    data_download = datetime.now().strftime("%Y-%m-%d")

    base = "%(uploader,channel|Canal desconhecido)s"

    if playlist:
        base += " - %(playlist_index)s"

    base += f" - %(title)s - {data_download}.%(ext)s"

    return base


def ffmpeg_location_args():
    """
    Retorna os argumentos '--ffmpeg-location <pasta>' pro yt-dlp usar o
    ffmpeg baixado automaticamente (ou o do PATH, se já existir).
    Se não achar de jeito nenhum, avisa e retorna lista vazia
    (nesse caso mesclagem de vídeo/áudio e legendas embutidas podem falhar).
    """

    caminho = get_ffmpeg_path()

    if caminho is None:
        print("\nAVISO: ffmpeg não encontrado. Rode o menu.bat novamente para baixá-lo.")
        return []

    return ["--ffmpeg-location", os.path.dirname(caminho)]


def exigir_ffmpeg():
    """
    Confere se o ffmpeg está disponível ANTES de iniciar qualquer download.
    Sem isso, o yt-dlp baixa o arquivo bruto (ex: .webm) e falha ao converter
    pra MP3/MP4, deixando lixo na pasta em vez do arquivo final. Retorna
    True se pode prosseguir, False se deve cancelar o download.
    """

    if get_ffmpeg_path() is not None:
        return True

    print(
        "\nERRO: ffmpeg não encontrado — o download foi cancelado.\n"
        "Sem o ffmpeg, o áudio/vídeo baixa mas NÃO é convertido corretamente\n"
        "(fica um arquivo bruto, tipo .webm, em vez do MP3/MP4 final).\n\n"
        "Feche este programa e rode o menu.bat de novo pra baixar o ffmpeg."
    )

    return False


def montar_comando_video(url, formato, quer_legendas, playlist=False):
    """
    Monta o comando yt-dlp pra baixar UM vídeo (ou UM item de playlist,
    quando playlist=True) no formato/qualidade escolhidos.
    Reaproveitado por baixar_video, baixar_multiplos e (via lista de
    urls) por baixar_video_playlist.
    """

    comando = [
        sys.executable,
        "-m",
        "yt_dlp",

        "--newline",
        "--windows-filenames",

        "-f",
        formato,

        "--merge-output-format",
        "mp4",

        "--recode-video",
        "mp4",

        "-o",
        os.path.join(PASTA_VIDEO, template_nome_arquivo(playlist=playlist)),
    ]

    if not playlist:
        comando.insert(3, "--no-playlist")

    comando += ffmpeg_location_args()

    if quer_legendas:
        comando += opcoes_legenda()

    comando.append(url)

    return comando


def escolher_qualidade_teto():
    """
    Pergunta uma qualidade "teto" (ex: 1080p ou menor), usada quando
    vários vídeos serão baixados de uma vez e não dá pra escolher
    formato exato vídeo a vídeo. Retorna o formato do yt-dlp ou None
    se o usuário cancelar.
    """

    print("\nQualidade máxima para os vídeos:\n")

    for i, (rotulo, _) in enumerate(OPCOES_QUALIDADE_TETO, start=1):
        print(f"{i} - {rotulo}")

    print("0 - Cancelar")

    escolha = input("\nEscolha: ").strip()

    if escolha == "0":
        return None

    if not escolha.isdigit() or not (1 <= int(escolha) <= len(OPCOES_QUALIDADE_TETO)):
        print("\nOpção inválida.")
        return None

    _, formato = OPCOES_QUALIDADE_TETO[int(escolha) - 1]

    return formato


def eh_link_playlist(url):
    """
    Detecta se o link parece apontar para uma playlist do YouTube.
    """

    return "list=" in url or "/playlist" in url


def extrair_urls_playlist(url):
    """
    Consulta a playlist (sem baixar nada) e devolve a lista de URLs
    de cada vídeo individual dela. Usado pra poder baixar os itens
    da playlist um a um (sequencial ou em paralelo) em vez de deixar
    um único processo do yt-dlp cuidar da playlist inteira.
    """

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entradas = info.get("entries") or []

    urls = []

    for entrada in entradas:

        if not entrada:
            continue

        candidato = entrada.get("url") or entrada.get("webpage_url")
        video_id = entrada.get("id")

        if candidato and candidato.startswith("http"):
            urls.append(candidato)
        elif video_id:
            urls.append(f"https://www.youtube.com/watch?v={video_id}")

    return urls


def escolher_modo_download():
    """
    Decide sequencial vs. paralelo (e, se paralelo, quantos downloads
    simultâneos), usando o padrão do config.ini ou perguntando na hora.
    Compartilhado entre vídeos múltiplos, playlist de vídeo e playlist
    de áudio.
    """

    modo = _config["YOUTUBE"].get("modo_download_multiplo_padrao", "perguntar").strip().lower()

    if modo not in ("sequencial", "paralelo"):
        resp = input("\nBaixar em sequência (1) ou em paralelo (2)? [padrão: 1]: ").strip()
        modo = "paralelo" if resp == "2" else "sequencial"

    max_paralelos = None

    if modo == "paralelo":

        max_padrao_txt = _config["YOUTUBE"].get("max_downloads_paralelos", "3")

        try:
            max_padrao = max(1, int(float(max_padrao_txt)))
        except ValueError:
            max_padrao = 3

        resp = input(f"Quantos downloads simultâneos? [padrão: {max_padrao}]: ").strip()

        max_paralelos = int(resp) if resp.isdigit() and int(resp) > 0 else max_padrao

    return modo, max_paralelos


# ==========================
# LISTAR QUALIDADES DISPONÍVEIS
# ==========================

def listar_qualidades(url):
    """
    Usa o yt-dlp para consultar o vídeo (sem baixar) e devolve uma lista
    de opções de qualidade únicas, ordenadas da melhor pra pior.
    Cada opção é um dicionário com: rotulo, format_id, ext, altura (resolução).
    """

    opcoes = {}

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    print("\nConsultando qualidades disponíveis...\n")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formatos = info.get("formats", [])

    for f in formatos:

        # Só nos interessam formatos que tenham vídeo
        if f.get("vcodec") == "none":
            continue

        altura = f.get("height")

        if altura is None:
            continue

        ext = f.get("ext", "mp4")

        # Chave para evitar mostrar a mesma resolução duas vezes
        chave = altura

        # Preferimos manter o formato com melhor fps/bitrate para essa altura
        if chave not in opcoes or (f.get("tbr") or 0) > (opcoes[chave].get("tbr") or 0):
            opcoes[chave] = {
                "altura": altura,
                "format_id": f["format_id"],
                "ext": ext,
                "fps": f.get("fps"),
                "tbr": f.get("tbr"),
            }

    # Ordena da maior resolução pra menor
    lista_ordenada = sorted(opcoes.values(), key=lambda x: x["altura"], reverse=True)

    return info.get("title", "video"), lista_ordenada


# ==========================
# ÁUDIO
# ==========================

def montar_comando_audio(url, numero=None):
    """
    Monta o comando yt-dlp pra baixar o ÁUDIO de UM vídeo (sempre
    --no-playlist, mesmo que a URL pertença a uma playlist — nesse
    caso a expansão da playlist já foi feita antes, item por item).

    Se NOMEAR_AUDIO_NUMERICO estiver ativado no config.ini, o arquivo
    é salvo só com número (ex: 3.mp3) em vez do nome completo do vídeo.
    """

    if NOMEAR_AUDIO_NUMERICO:
        if numero is None:
            numero = proximo_numero_audio()
        nome_saida = f"{numero}.%(ext)s"
    else:
        nome_saida = template_nome_arquivo(playlist=False)

    comando = [
        sys.executable,
        "-m",
        "yt_dlp",

        "--newline",
        "--windows-filenames",
        "--no-playlist",

        "-f",
        "bestaudio/best",

        "-x",

        "--audio-format",
        "mp3",

        "--audio-quality",
        f"{QUALIDADE_AUDIO_KBPS}K",

        "-o",
        os.path.join(PASTA_AUDIO, nome_saida),
    ]

    comando += ffmpeg_location_args()

    comando.append(url)

    return comando


def baixar_audio():

    if not exigir_ffmpeg():
        return

    url = input("\nCole a URL do vídeo:\n\n").strip()

    if eh_link_playlist(url):

        resp = input(
            "\nEsse link parece ser de uma playlist.\n"
            "Baixar o ÁUDIO de todos os vídeos da playlist? (S/N): "
        ).strip().lower()

        if resp in ("s", "sim"):

            print("\nConsultando itens da playlist...\n")

            try:
                urls = extrair_urls_playlist(url)
            except Exception as erro:
                print("\nNão foi possível consultar a playlist:")
                print(erro)
                common.registrar_log("YOUTUBE", f"Erro ao consultar playlist (áudio) '{url}': {erro}")
                return

            if not urls:
                print("\nNenhum vídeo encontrado nessa playlist.")
                return

            print(f"{len(urls)} áudio(s) serão baixados.")

            baixar_urls_audio(urls)
            return

    # ---- Fluxo normal: um único vídeo ----

    comando = montar_comando_audio(url)

    resultado = subprocess.run(comando)

    if resultado.returncode != 0:
        common.registrar_log("YOUTUBE", f"yt-dlp retornou erro ao baixar áudio '{url}' (código {resultado.returncode})")
        return

    common.perguntar_e_abrir_pasta(PASTA_AUDIO)


def baixar_urls_audio(urls):

    modo, max_paralelos = escolher_modo_download()

    if modo == "paralelo":
        _baixar_audio_paralelo(urls, max_paralelos)
    else:
        _baixar_audio_sequencial(urls)

    common.perguntar_e_abrir_pasta(PASTA_AUDIO)


def _baixar_audio_sequencial(urls):

    numero = proximo_numero_audio() if NOMEAR_AUDIO_NUMERICO else None

    for i, url in enumerate(urls, start=1):

        print(f"\n[{i}/{len(urls)}] Baixando áudio: {url}\n")

        comando = montar_comando_audio(url, numero=numero)

        resultado = subprocess.run(comando)

        if resultado.returncode != 0:
            common.registrar_log(
                "YOUTUBE",
                f"Erro ao baixar áudio (playlist/múltiplos, sequencial) '{url}' (código {resultado.returncode})"
            )
        elif numero is not None:
            numero += 1


def _baixar_audio_paralelo(urls, max_paralelos):

    from concurrent.futures import ThreadPoolExecutor, as_completed

    print(f"\nBaixando {len(urls)} áudio(s), até {max_paralelos} ao mesmo tempo...\n")

    numero_inicial = proximo_numero_audio() if NOMEAR_AUDIO_NUMERICO else None

    def worker(url, numero):
        comando = montar_comando_audio(url, numero=numero)
        resultado = subprocess.run(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return url, resultado.returncode

    with ThreadPoolExecutor(max_workers=max_paralelos) as executor:

        futuros = {}

        for i, url in enumerate(urls):
            numero = (numero_inicial + i) if numero_inicial is not None else None
            futuros[executor.submit(worker, url, numero)] = url

        for futuro in as_completed(futuros):

            url, codigo = futuro.result()

            if codigo == 0:
                print(f"OK    - {url}")
            else:
                print(f"ERRO  - {url}")
                common.registrar_log(
                    "YOUTUBE",
                    f"Erro ao baixar áudio (playlist/múltiplos, paralelo) '{url}' (código {codigo})"
                )


# ==========================
# VÍDEO
# ==========================

def baixar_video():

    if not exigir_ffmpeg():
        return

    url = input("\nCole a URL do vídeo:\n\n").strip()

    if eh_link_playlist(url):

        resp = input(
            "\nEsse link parece ser de uma playlist.\n"
            "Baixar todos os vídeos da playlist? (S/N): "
        ).strip().lower()

        if resp in ("s", "sim"):
            baixar_video_playlist(url)
            return

    # ---- Fluxo normal: um único vídeo, com escolha de qualidade ----

    try:
        titulo, qualidades = listar_qualidades(url)
    except Exception as erro:
        print("\nNão foi possível consultar as qualidades do vídeo:")
        print(erro)
        common.registrar_log("YOUTUBE", f"Erro ao consultar qualidades de '{url}': {erro}")
        return

    if not qualidades:
        print("\nNenhuma qualidade de vídeo encontrada para essa URL.")
        return

    print(f"Vídeo: {titulo}\n")
    print("Qualidades disponíveis:\n")

    for i, q in enumerate(qualidades, start=1):
        fps_txt = f" {int(q['fps'])}fps" if q.get("fps") else ""
        print(f"{i} - {q['altura']}p{fps_txt} ({q['ext']})")

    print("0 - Cancelar")

    escolha = input("\nEscolha a qualidade: ").strip()

    if escolha == "0":
        return

    if not escolha.isdigit() or not (1 <= int(escolha) <= len(qualidades)):
        print("\nOpção inválida.")
        return

    selecionada = qualidades[int(escolha) - 1]

    # Junta o vídeo na resolução escolhida com o melhor áudio disponível
    formato = f"{selecionada['format_id']}+bestaudio/best"

    quer_legendas = perguntar_legendas()

    comando = montar_comando_video(url, formato, quer_legendas)

    resultado = subprocess.run(comando)

    if resultado.returncode != 0:
        common.registrar_log("YOUTUBE", f"yt-dlp retornou erro ao baixar vídeo '{url}' (código {resultado.returncode})")
        return

    common.perguntar_e_abrir_pasta(PASTA_VIDEO)


OPCOES_QUALIDADE_TETO = [
    ("Melhor disponível", "bv*+ba/b"),
    ("1080p ou menor", "bv*[height<=1080]+ba/b"),
    ("720p ou menor", "bv*[height<=720]+ba/b"),
    ("480p ou menor", "bv*[height<=480]+ba/b"),
]


def baixar_video_playlist(url):
    """
    Baixa todos os vídeos de uma playlist. Primeiro consulta a lista de
    vídeos (sem baixar), depois baixa cada um individualmente — sequencial
    ou em paralelo, conforme escolha do usuário/config.ini. Como a
    qualidade disponível pode variar de vídeo pra vídeo, a escolha aqui
    é por um teto de resolução (ex: '1080p ou menor').
    """

    if not exigir_ffmpeg():
        return

    print("\nConsultando itens da playlist...\n")

    try:
        urls = extrair_urls_playlist(url)
    except Exception as erro:
        print("\nNão foi possível consultar a playlist:")
        print(erro)
        common.registrar_log("YOUTUBE", f"Erro ao consultar playlist (vídeo) '{url}': {erro}")
        return

    if not urls:
        print("\nNenhum vídeo encontrado nessa playlist.")
        return

    print(f"{len(urls)} vídeo(s) encontrados na playlist.")

    formato = escolher_qualidade_teto()

    if formato is None:
        return

    quer_legendas = perguntar_legendas(para_playlist=True)

    baixar_urls_video(urls, formato, quer_legendas)


# ==========================
# MÚLTIPLOS VÍDEOS (sequencial ou paralelo)
# ==========================

def coletar_urls_multiplas():

    print("\nCole uma URL por linha. Deixe a linha em branco pra terminar:\n")

    urls = []

    while True:
        linha = input().strip()
        if linha == "":
            break
        urls.append(linha)

    return urls


def baixar_multiplos():

    if not exigir_ffmpeg():
        return

    urls = coletar_urls_multiplas()

    if not urls:
        print("\nNenhuma URL informada.")
        return

    print(f"\n{len(urls)} URL(s) informada(s).")

    formato = escolher_qualidade_teto()

    if formato is None:
        return

    quer_legendas = perguntar_legendas(para_playlist=True)

    baixar_urls_video(urls, formato, quer_legendas)


def baixar_urls_video(urls, formato, quer_legendas):

    modo, max_paralelos = escolher_modo_download()

    if modo == "paralelo":
        _baixar_urls_paralelo(urls, formato, quer_legendas, max_paralelos)
    else:
        _baixar_urls_sequencial(urls, formato, quer_legendas)

    common.perguntar_e_abrir_pasta(PASTA_VIDEO)


def _baixar_urls_sequencial(urls, formato, quer_legendas):

    for i, url in enumerate(urls, start=1):

        print(f"\n[{i}/{len(urls)}] Baixando: {url}\n")

        comando = montar_comando_video(url, formato, quer_legendas)

        resultado = subprocess.run(comando)

        if resultado.returncode != 0:
            common.registrar_log(
                "YOUTUBE",
                f"Erro ao baixar (múltiplos, sequencial) '{url}' (código {resultado.returncode})"
            )


def _baixar_urls_paralelo(urls, formato, quer_legendas, max_paralelos):

    from concurrent.futures import ThreadPoolExecutor, as_completed

    print(f"\nBaixando {len(urls)} vídeo(s), até {max_paralelos} ao mesmo tempo...\n")

    def worker(url):
        comando = montar_comando_video(url, formato, quer_legendas)
        # Saída silenciada aqui pra não misturar o output de vários
        # downloads simultâneos no mesmo terminal.
        resultado = subprocess.run(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return url, resultado.returncode

    with ThreadPoolExecutor(max_workers=max_paralelos) as executor:

        futuros = {executor.submit(worker, url): url for url in urls}

        for futuro in as_completed(futuros):

            url, codigo = futuro.result()

            if codigo == 0:
                print(f"OK    - {url}")
            else:
                print(f"ERRO  - {url}")
                common.registrar_log(
                    "YOUTUBE",
                    f"Erro ao baixar (múltiplos, paralelo) '{url}' (código {codigo})"
                )


# ==========================
# AUXILIARES DE LEGENDA
# ==========================

def perguntar_legendas(para_playlist=False):

    sugestao = "S" if BAIXAR_LEGENDAS_PADRAO else "N"
    alvo = "para todos os vídeos da playlist" if para_playlist else ""

    resposta = input(
        f"\nBaixar legendas ({IDIOMA_LEGENDAS}) {alvo}? (S/N) [padrão: {sugestao}]: "
    ).strip().lower()

    if resposta == "":
        return BAIXAR_LEGENDAS_PADRAO

    return resposta in ("s", "sim")


def opcoes_legenda():

    return [
        "--write-subs",
        # Se não houver legenda "de verdade", usa a legenda automática do YouTube
        "--write-auto-subs",
        "--sub-langs",
        IDIOMA_LEGENDAS,
        "--convert-subs",
        "srt",
        "--embed-subs",
    ]


# ==========================
# MENU
# ==========================

def menu():

    while True:

        os.system("cls")

        print("=" * 45)
        print("            YOUTUBE")
        print("=" * 45)

        print()
        print("1 - Baixar Áudio (MP3)")
        print("2 - Baixar Vídeo")
        print("3 - Baixar Múltiplos Vídeos")
        print("0 - Voltar")

        opcao = input("\nEscolha: ").strip()

        if opcao == "1":

            baixar_audio()

            input("\nPressione ENTER...")

        elif opcao == "2":

            baixar_video()

            input("\nPressione ENTER...")

        elif opcao == "3":

            baixar_multiplos()

            input("\nPressione ENTER...")

        elif opcao == "0":

            break

        else:

            print("\nOpção inválida.")
            input("\nPressione ENTER...")


if __name__ == "__main__":

    try:
        menu()
    except KeyboardInterrupt:
        print("\n\nPrograma encerrado pelo usuário.")
