from enum import Enum

#Errori
class GameError(Enum):
    
    # Game lifecycle
    NO_GAME_SPECIFIED = "Nessun gioco specificato"
    GAME_NOT_FOUND = "Gioco non trovato"
    NO_GAME_IN_PROGRESS = "Non c'è nessuna partita in corso"
    GAME_ALREADY_IN_PROGRESS = "C'è già una partita in corso"
    
    # Players
    PLAYER_NOT_FOUND = "Giocatore non trovato nella partita"
    INVALID_PLAYER_ORDER = "Ordine giocatori non valido" #???
    NO_PLAYERS_IN_GAME = "Partita senza giocatori" #???
    
    # History
    NO_HISTORY = "Non ho ancora registrato nessuna partita"
    NO_HISTORY_FOR_GAME = "Nessuna partita trovata per questo gioco"
    HISTORY_ALREADY_EMPTY = "Lo storico è già vuoto"

#Eccezioni
class AiServiceError (Exception):
    pass

class DBError (Exception):
    pass
