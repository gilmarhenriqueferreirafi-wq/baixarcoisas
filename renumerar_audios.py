import os
import sys

import common

# ==========================================
# Script avulso: renomeia os arquivos que já estão
# na pasta de áudio do YouTube para números sequenciais
# (1.mp3, 2.mp3, 3.mp3, ...), mantendo a ordem alfabética
# atual dos nomes. Não mexe em vídeos nem em outras pastas.
# ==========================================


def main():

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

    arquivos = sorted(
        f for f in os.listdir(pasta_audio)
        if os.path.isfile(os.path.join(pasta_audio, f))
    )

    if not arquivos:
        print("Nenhum arquivo encontrado em:", pasta_audio)
        return

    print(f"{len(arquivos)} arquivo(s) encontrados em:\n{pasta_audio}\n")

    for i, nome in enumerate(arquivos, start=1):
        ext = os.path.splitext(nome)[1]
        print(f"  {nome}  ->  {i}{ext}")

    resp = input("\nRenomear todos para números, na ordem acima? (S/N): ").strip().lower()

    if resp not in ("s", "sim"):
        print("Cancelado. Nenhum arquivo foi alterado.")
        return

    # Passo 1: renomeia tudo pra um nome temporário, pra evitar que um
    # arquivo seja sobrescrito caso já exista um "2.mp3" no meio da lista.
    temporarios = []

    for i, nome in enumerate(arquivos, start=1):
        origem = os.path.join(pasta_audio, nome)
        temp = os.path.join(pasta_audio, f"_tmp_{i}{os.path.splitext(nome)[1]}")
        os.rename(origem, temp)
        temporarios.append(temp)

    # Passo 2: renomeia dos temporários pro nome final numerado.
    for i, temp in enumerate(temporarios, start=1):
        ext = os.path.splitext(temp)[1]
        final = os.path.join(pasta_audio, f"{i}{ext}")
        os.rename(temp, final)

    print(f"\nPronto! {len(arquivos)} arquivo(s) renomeado(s) de 1 a {len(arquivos)}.")

    common.perguntar_e_abrir_pasta(pasta_audio)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelado pelo usuário.")
