import os
import common

OPCOES_QUALIDADE_AUDIO = [
    ("64", "Mínima — fala/podcast, arquivo bem pequeno"),
    ("96", "Leve"),
    ("128", "Padrão — recomendado, bom equilíbrio"),
    ("192", "Alta — quase transparente"),
    ("320", "Máxima — qualidade de CD, arquivo pesado"),
]


def mostrar_config(config):

    print("=" * 45)
    print("           CONFIGURAÇÕES ATUAIS")
    print("=" * 45)

    print(f"\n1 - Pasta de downloads.......... {config['GERAL']['pasta_downloads']}")
    print(f"2 - Abrir pasta após download... {config['GERAL']['abrir_pasta_apos_download']}")
    print(f"3 - Espera antes do login (IG).. {config['INSTAGRAM']['espera_antes_login']}s")
    print(f"4 - Espera antes do download (IG) {config['INSTAGRAM']['espera_antes_download']}s")
    print(f"5 - Baixar legendas por padrão (YT) {config['YOUTUBE']['baixar_legendas_padrao']}")
    print(f"6 - Idioma das legendas (YT)..... {config['YOUTUBE']['idioma_legendas']}")
    print(f"7 - Modo padrão p/ múltiplos (YT) {config['YOUTUBE']['modo_download_multiplo_padrao']}")
    print(f"8 - Máx. downloads paralelos (YT) {config['YOUTUBE']['max_downloads_paralelos']}")
    print(f"9 - Qualidade do áudio MP3 (YT).. {config['YOUTUBE'].get('qualidade_audio_kbps', '128')} kbps")
    print("     (opções: 64=mínima, 96=leve, 128=padrão, 192=alta, 320=máxima)")
    print(f"10 - Nomear áudio só com número (YT) {config['YOUTUBE'].get('nomear_audio_numerico', 'nao')}")
    print("\n0 - Voltar")


def pedir_numero(mensagem, atual):

    valor = input(f"{mensagem} [atual: {atual}]: ").strip()

    if valor == "":
        return atual

    try:
        return str(float(valor))
    except ValueError:
        print("\nValor inválido, mantendo o anterior.")
        return atual


def pedir_sim_nao(mensagem, atual):

    valor = input(f"{mensagem} (sim/nao) [atual: {atual}]: ").strip().lower()

    if valor == "":
        return atual

    if valor in ("sim", "s", "nao", "n", "não"):
        return "sim" if valor in ("sim", "s") else "nao"

    print("\nValor inválido, mantendo o anterior.")
    return atual


def menu():

    while True:

        os.system("cls")

        config = common.carregar_config()

        mostrar_config(config)

        escolha = input("\nEscolha o que deseja alterar: ").strip()

        if escolha == "0":
            break

        elif escolha == "1":

            novo = input(
                f"\nNova pasta de downloads [atual: {config['GERAL']['pasta_downloads']}]: "
            ).strip()

            if novo:
                novo = novo.strip().strip('"').strip("'")
                config["GERAL"]["pasta_downloads"] = novo
                common.salvar_config(config)
                print("\nSalvo! (Precisa reabrir o YouTube/Instagram pra valer.)")

        elif escolha == "2":

            print("\nOpções: sempre / nunca / perguntar")
            novo = input(
                f"Nova opção [atual: {config['GERAL']['abrir_pasta_apos_download']}]: "
            ).strip().lower()

            if novo in ("sempre", "nunca", "perguntar"):
                config["GERAL"]["abrir_pasta_apos_download"] = novo
                common.salvar_config(config)
                print("\nSalvo!")
            elif novo:
                print("\nOpção inválida. Use: sempre, nunca ou perguntar.")

        elif escolha == "3":

            config["INSTAGRAM"]["espera_antes_login"] = pedir_numero(
                "\nNovo tempo de espera antes do login (segundos)",
                config["INSTAGRAM"]["espera_antes_login"]
            )
            common.salvar_config(config)
            print("\nSalvo!")

        elif escolha == "4":

            config["INSTAGRAM"]["espera_antes_download"] = pedir_numero(
                "\nNovo tempo de espera antes do download (segundos)",
                config["INSTAGRAM"]["espera_antes_download"]
            )
            common.salvar_config(config)
            print("\nSalvo!")

        elif escolha == "5":

            config["YOUTUBE"]["baixar_legendas_padrao"] = pedir_sim_nao(
                "\nBaixar legendas por padrão no YouTube?",
                config["YOUTUBE"]["baixar_legendas_padrao"]
            )
            common.salvar_config(config)
            print("\nSalvo!")

        elif escolha == "6":

            novo = input(
                f"\nNovo idioma de legendas (ex: pt, en, es) [atual: {config['YOUTUBE']['idioma_legendas']}]: "
            ).strip()

            if novo:
                config["YOUTUBE"]["idioma_legendas"] = novo
                common.salvar_config(config)
                print("\nSalvo!")

        elif escolha == "7":

            print("\nOpções: sequencial / paralelo / perguntar")
            novo = input(
                f"Novo modo padrão [atual: {config['YOUTUBE']['modo_download_multiplo_padrao']}]: "
            ).strip().lower()

            if novo in ("sequencial", "paralelo", "perguntar"):
                config["YOUTUBE"]["modo_download_multiplo_padrao"] = novo
                common.salvar_config(config)
                print("\nSalvo!")
            elif novo:
                print("\nOpção inválida. Use: sequencial, paralelo ou perguntar.")

        elif escolha == "8":

            config["YOUTUBE"]["max_downloads_paralelos"] = pedir_numero(
                "\nMáximo de downloads simultâneos (quando modo = paralelo)",
                config["YOUTUBE"]["max_downloads_paralelos"]
            )
            common.salvar_config(config)
            print("\nSalvo!")

        elif escolha == "9":

            print("\nQualidades de áudio disponíveis:\n")

            for i, (kbps, descricao) in enumerate(OPCOES_QUALIDADE_AUDIO, start=1):
                print(f"{i} - {kbps} kbps ({descricao})")

            print("6 - Outro valor (digitar manualmente)")

            atual = config["YOUTUBE"].get("qualidade_audio_kbps", "128")
            sub = input(f"\nEscolha [atual: {atual} kbps]: ").strip()

            if sub == "":
                pass

            elif sub in ("1", "2", "3", "4", "5"):
                novo_kbps, _ = OPCOES_QUALIDADE_AUDIO[int(sub) - 1]
                config["YOUTUBE"]["qualidade_audio_kbps"] = novo_kbps
                common.salvar_config(config)
                print("\nSalvo!")

            elif sub == "6":
                config["YOUTUBE"]["qualidade_audio_kbps"] = pedir_numero(
                    "Digite a qualidade do áudio (kbps)",
                    atual
                )
                common.salvar_config(config)
                print("\nSalvo!")

            else:
                print("\nOpção inválida.")

        elif escolha == "10":

            config["YOUTUBE"]["nomear_audio_numerico"] = pedir_sim_nao(
                "\nNomear áudios só com número (1.mp3, 2.mp3, ...) em vez do nome do vídeo?",
                config["YOUTUBE"].get("nomear_audio_numerico", "nao")
            )
            common.salvar_config(config)
            print("\nSalvo!")

        else:

            print("\nOpção inválida.")

        input("\nPressione ENTER...")


if __name__ == "__main__":

    try:
        menu()
    except KeyboardInterrupt:
        print("\n\nConfigurações encerradas pelo usuário.")
