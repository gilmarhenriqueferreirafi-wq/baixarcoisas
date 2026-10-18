import sys
import shutil
import subprocess
import importlib
from ffmpeg_utils import get_ffmpeg_path, baixar_ffmpeg

DEPENDENCIAS = {
    "yt_dlp": "yt-dlp",
    "instagrapi": "instagrapi"
}

faltando = []

for modulo, pacote in DEPENDENCIAS.items():
    try:
        importlib.import_module(modulo)
    except ImportError:
        faltando.append(pacote)

if faltando:

    print("=" * 40)
    print("Dependências ausentes")
    print("=" * 40)

    for pacote in faltando:
        print("-", pacote)

    resp = input("\nDeseja instalar? (S/N): ").lower()

    if resp == "s":

        for pacote in faltando:

            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                "-U",
                pacote
            ])

        print("\nInstalação concluída!")

    else:

        print("\nO programa não pode continuar.")
        sys.exit(1)

# ==========================================
# VERIFICA O FFMPEG (não é instalável via pip)
# ==========================================

if get_ffmpeg_path() is None:

    print("=" * 40)
    print("ffmpeg não encontrado")
    print("=" * 40)

    print("\nO ffmpeg é necessário para:")
    print("- Juntar vídeo e áudio em qualidades separadas (YouTube)")
    print("- Converter vídeos para MP4")
    print("- Embutir legendas nos vídeos")

    resp = input("\nDeseja baixar o ffmpeg automaticamente agora? (S/N): ").lower()

    if resp == "s":
        sucesso = baixar_ffmpeg()
        if not sucesso:
            print("\nO programa não pode continuar sem o ffmpeg.")
            sys.exit(1)
    else:
        print("\nO programa não pode continuar sem o ffmpeg.")
        sys.exit(1)

sys.exit(0)
