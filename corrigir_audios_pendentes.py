import os
import sys
import subprocess

import common
from ffmpeg_utils import get_ffmpeg_path

# ==========================================
# Corrige áudios que ficaram "presos" em formato bruto
# (.webm, .m4a, .opus etc) porque o ffmpeg falhou/estava
# ausente na hora do download e a conversão pra MP3 não
# aconteceu. Este script converte tudo que sobrou e apaga
# os arquivos originais depois de confirmar sucesso.
# ==========================================

EXTENSOES_BRUTAS = (".webm", ".m4a", ".opus", ".ogg", ".aac", ".wav")


def limpar_partes_orfas(pasta_audio):
    """
    Arquivos .part são downloads que pararam no meio (queda de rede,
    processo travado, etc). Como o nome do arquivo final inclui a data
    do download, um .part de um dia não é retomado em outro dia — ele
    fica pra sempre como lixo. Aqui listamos e oferecemos apagar.
    """

    partes = sorted(f for f in os.listdir(pasta_audio) if f.lower().endswith(".part"))

    if not partes:
        return

    print(f"\n{len(partes)} download(s) incompleto(s) (.part) encontrados — ficaram pela metade e não vão ser retomados:\n")

    for nome in partes:
        print(" -", nome)

    resp = input("\nApagar esses arquivos incompletos? (S/N): ").strip().lower()

    if resp not in ("s", "sim"):
        print("Mantidos.")
        return

    for nome in partes:
        try:
            os.remove(os.path.join(pasta_audio, nome))
        except OSError:
            pass

    print(f"{len(partes)} arquivo(s) incompleto(s) apagado(s). Baixe de novo pelo menu do YouTube.")


def main():

    ffmpeg = get_ffmpeg_path()

    if ffmpeg is None:
        print("ERRO: ffmpeg não encontrado. Rode o menu.bat primeiro pra baixá-lo.")
        sys.exit(1)

    config = common.carregar_config()

    pasta_audio = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        config["GERAL"]["pasta_downloads"],
        "youtube",
        "audio",
    )

    if not os.path.isdir(pasta_audio):
        print("Pasta de áudio não encontrada em:", pasta_audio)
        sys.exit(1)

    limpar_partes_orfas(pasta_audio)

    kbps = config["YOUTUBE"].get("qualidade_audio_kbps", "128")

    arquivos = sorted(
        f for f in os.listdir(pasta_audio)
        if f.lower().endswith(EXTENSOES_BRUTAS)
    )

    if not arquivos:
        print("Nenhum áudio pendente de conversão encontrado. Tudo certo!")
        return

    print(f"{len(arquivos)} arquivo(s) sem conversão encontrados em:\n{pasta_audio}\n")

    for nome in arquivos:
        print(" -", nome)

    resp = input(
        f"\nConverter todos para MP3 ({kbps} kbps) e apagar os originais? (S/N): "
    ).strip().lower()

    if resp not in ("s", "sim"):
        print("Cancelado. Nenhum arquivo foi alterado.")
        return

    convertidos = 0
    falhas = 0

    for nome in arquivos:

        origem = os.path.join(pasta_audio, nome)
        destino = os.path.join(pasta_audio, os.path.splitext(nome)[0] + ".mp3")

        print(f"\nConvertendo: {nome}")

        resultado = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i", origem,
                "-vn",
                "-b:a", f"{kbps}k",
                destino,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if resultado.returncode == 0 and os.path.isfile(destino):
            os.remove(origem)
            convertidos += 1
            print(f"  OK -> {os.path.basename(destino)}")
        else:
            falhas += 1
            print(f"  ERRO ao converter (arquivo original mantido: {nome})")

    print(f"\nConcluído! {convertidos} convertido(s), {falhas} com erro.")

    common.perguntar_e_abrir_pasta(pasta_audio)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelado pelo usuário.")
