import os
import shutil
import sys
import zipfile
import urllib.request

# Pasta fixa onde o ffmpeg baixado automaticamente vai morar
FFMPEG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                           "DownloaderUniversal", "ffmpeg")
FFMPEG_BIN = os.path.join(FFMPEG_DIR, "bin")
FFMPEG_EXE = os.path.join(FFMPEG_BIN, "ffmpeg.exe")
FFPROBE_EXE = os.path.join(FFMPEG_BIN, "ffprobe.exe")

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def get_ffmpeg_path():
    """Retorna o caminho do ffmpeg.exe: local baixado ou do PATH do sistema."""
    if os.path.isfile(FFMPEG_EXE):
        return FFMPEG_EXE
    sistema = shutil.which("ffmpeg")
    if sistema:
        return sistema
    return None


def get_ffprobe_path():
    """Retorna o caminho do ffprobe.exe: local baixado ou do PATH do sistema."""
    if os.path.isfile(FFPROBE_EXE):
        return FFPROBE_EXE
    sistema = shutil.which("ffprobe")
    if sistema:
        return sistema
    return None


def _print_progresso(bloco_num, tamanho_bloco, tamanho_total):
    if tamanho_total <= 0:
        return
    baixado = bloco_num * tamanho_bloco
    pct = min(100, baixado * 100 // tamanho_total)
    mb_baixado = baixado / (1024 * 1024)
    mb_total = tamanho_total / (1024 * 1024)
    sys.stdout.write(f"\rBaixando ffmpeg... {pct}% ({mb_baixado:.1f}MB / {mb_total:.1f}MB)")
    sys.stdout.flush()


def baixar_ffmpeg():
    """Baixa o build essentials do ffmpeg (gyan.dev) e extrai ffmpeg.exe/ffprobe.exe."""
    os.makedirs(FFMPEG_BIN, exist_ok=True)
    zip_path = os.path.join(FFMPEG_DIR, "ffmpeg_download.zip")

    print("=" * 40)
    print("Baixando ffmpeg automaticamente")
    print("=" * 40)
    print(f"Origem: {FFMPEG_URL}")
    print(f"Destino: {FFMPEG_BIN}\n")

    try:
        urllib.request.urlretrieve(FFMPEG_URL, zip_path, reporthook=_print_progresso)
        print("\nDownload concluído. Extraindo...")

        with zipfile.ZipFile(zip_path, "r") as z:
            for nome in z.namelist():
                base = os.path.basename(nome)
                if base in ("ffmpeg.exe", "ffprobe.exe"):
                    with z.open(nome) as origem, open(os.path.join(FFMPEG_BIN, base), "wb") as destino:
                        shutil.copyfileobj(origem, destino)

        os.remove(zip_path)

        if os.path.isfile(FFMPEG_EXE):
            print("ffmpeg instalado com sucesso em:", FFMPEG_BIN)
            return True
        else:
            print("Não foi possível localizar ffmpeg.exe dentro do pacote baixado.")
            return False

    except Exception as e:
        print(f"\nFalha ao baixar/extrair o ffmpeg: {e}")
        return False
