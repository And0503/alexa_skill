def format_classifica(giocatori):
    classifica = sorted(giocatori.items(), key=lambda x: x[1], reverse=True)

    return ". ".join(
        [f"{nome} {punti} punto" if punti == 1 else f"{nome} {punti} punti"
         for nome, punti in classifica]
    )
