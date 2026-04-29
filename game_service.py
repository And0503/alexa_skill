import random
from datetime import datetime #togliere?

from storage.games_data import games_info
from errors import GameError

from dataclasses import asdict
from models import Match, HistoryEntry

class GameService:
    def __init__(self, repository):
        self.repository = repository
        self.data = repository.get_data()

    # =========================
    # UTILS
    # =========================

    def save(self):
        self.repository.save_data(self.data)

    def get_current_game(self):
        return self.data.get("partita_corrente")
        
    def is_valid_game(self, gioco):
        return gioco in games_info

    def get_available_games(self):
        return list(games_info.keys())
    
    def get_player_limits(self, gioco):
        info = games_info[gioco]
        return info.min_giocatori, info.max_giocatori
        
    #==========================
    # RULES
    #==========================
    def get_game_info(self, gioco):
        
        if not gioco:
            return None, GameError.NO_GAME_SPECIFIED
            
        if gioco not in games_info:
            return None, GameError.GAME_NOT_FOUND
            
        return games_info[gioco].regole, None
        
    #=========================
    # RANDOM
    #=========================
    def get_random_game(self, session_attr):
        prec_sorteggiati = session_attr.get("prec_sorteggiati", [])
        giochi_disponibili = [g for g in games_info.keys() if g not in prec_sorteggiati]

        if not giochi_disponibili:
            prec_sorteggiati = []
            giochi_disponibili = list(games_info.keys())

        gioco_sorteggiato = random.choice(giochi_disponibili)

        prec_sorteggiati.append(gioco_sorteggiato)
        session_attr["prec_sorteggiati"] = prec_sorteggiati
        session_attr["ultimo_sorteggiato_sessione"] = gioco_sorteggiato

        return gioco_sorteggiato

    # =========================
    # GAME LIFECYCLE
    # =========================

    def start_game(self, gioco, giocatori):
        if self.get_current_game():
            return None, GameError.GAME_ALREADY_IN_PROGRESS
            
        partita = Match(
            gioco=gioco,
            turno=1,
            data_inizio=datetime.now().strftime("%Y-%m-%d"),
            giocatori={g: 0 for g in giocatori},
            ordine=giocatori,
            mazziere_index=0
        )

        self.data["partita_corrente"] = asdict(partita)
        self.save()

        return asdict(partita), None

    def abandon_game(self):
        if not self.get_current_game():
            return False, GameError.NO_GAME_IN_PROGRESS

        self.data["partita_corrente"] = None
        self.save()

        return True, None

    # =========================
    # SCORE MANAGEMENT
    # =========================

    def update_score(self, giocatore, punti):
        partita = self.get_current_game()

        if not partita:
            return None, GameError.NO_GAME_IN_PROGRESS

        if giocatore not in partita["giocatori"]:
            return None, GameError.PLAYER_NOT_FOUND

        partita["giocatori"][giocatore] += punti

        self.data["partita_corrente"] = partita
        self.save()

        return partita, None

    def get_scores(self):
        partita = self.get_current_game()

        if not partita:
            return None, GameError.NO_GAME_IN_PROGRESS

        return partita["giocatori"], None

    # =========================
    # TURN MANAGEMENT
    # =========================

    def end_turn(self):
        partita = self.get_current_game()

        if not partita:
            return None, GameError.NO_GAME_IN_PROGRESS

        ordine = partita.get("ordine", [])
        if not ordine:
            return None, GameError.INVALID_PLAYER_ORDER #???

        mazziere_index = (partita.get("mazziere_index", -1) + 1) % len(ordine)
        partita["mazziere_index"] = mazziere_index

        turno = partita.get("turno", 0) + 1
        partita["turno"] = turno

        self.data["partita_corrente"] = partita
        self.save()

        return partita, None

    # =========================
    # END GAME
    # =========================

    def end_game(self):
        partita = self.get_current_game()

        if not partita:
            return None, GameError.NO_GAME_IN_PROGRESS

        giocatori = partita.get("giocatori", {})

        if not giocatori:
            return None, GameError.NO_PLAYERS_IN_GAME

        punteggio_max = max(giocatori.values())
        vincitori = [g for g, p in giocatori.items() if p == punteggio_max]

        if len(vincitori) == 1:
            vincitore = vincitori[0]
        else:
            vincitore = " e ".join(vincitori)
            
        record = HistoryEntry(
            data=partita.get("data_inizio"),
            gioco=partita.get("gioco"),
            vincitore=vincitore,
            punteggi=giocatori
        )

        self.data.setdefault("partite", []).append(asdict(record))
        self.data["partita_corrente"] = None
        self.save()

        return asdict(record), None

    # =========================
    # HISTORY
    # =========================

    def get_history(self, gioco=None, giocatore=None):
        partite = self.data.get("partite", [])

        if not partite:
            return None, GameError.NO_HISTORY

        # Filtra per gioco
        if gioco:
            partite = [p for p in partite if p.get("gioco") == gioco]
            if not partite:
                return None, GameError.NO_HISTORY_FOR_GAME

        # Conta vittorie
        vittorie = {}
        for p in partite:
            v = p.get("vincitore", "")
            if not v:
                continue
            nomi = [nome.strip() for nome in v.split(" e ")]
            for nome in nomi:
                vittorie[nome] = vittorie.get(nome, 0) + 1

        return {
            "partite": partite,
            "vittorie": vittorie,
            "ultima": partite[-1]
        }, None
    # =========================
    # ADMIN
    # =========================
    
    def clear_history(self):
        partite = self.data.get("partite", [])

        if not partite:
            return False, GameError.HISTORY_ALREADY_EMPTY

        self.data["partite"] = []
        self.save()

        return True, None
