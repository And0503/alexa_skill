#===========================LIBRERIE============================

#---------------------------ALEXA SDK---------------------------
import ask_sdk_core.utils as ask_utils
from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_model.dialog import ElicitSlotDirective
#----------------------------------------------------------------

#----------------------------DATABASE----------------------------
from storage.dynamo_repository import dynamodb_adapter, create_game_service #dynamo_repository
#from storage.testing.in_memory_repository import create_game_service #in_memory_repository
#----------------------------------------------------------------

#----------------------------LOGGING-----------------------------
import logging
logger = logging.getLogger(__name__)
#----------------------------------------------------------------

#-----------------------FUNZIONI HELPER--------------------------
from helper_functions import format_classifica
#----------------------------------------------------------------

#-------------------------GAME ERRORS----------------------------
from errors import GameError, AiServiceError, DBError
#----------------------------------------------------------------

#-----------------------------AI---------------------------------
from ai.gemini_service import create_ai_service
ai_service = create_ai_service()
#----------------------------------------------------------------

#================================================================

#=========================INTENT HANDLERS========================

#--------------------------APERTURA SKILL------------------------
class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        game_service = create_game_service(handler_input)
        partita = game_service.get_current_game()

        if partita:
            gioco = partita.get("gioco", "un gioco")
            speak_output = (
                f"Bentornato! Partita di {gioco} in corso. "
                f"Come posso aiutarti?"
            )
        else:
            speak_output = "Ciao, sono Game Guru! Come posso aiutarti?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Come posso aiutarti?")
                .response
        )
#------------------------------------------------------

#----------------SPIEGAZIONE REGOLE---------------------
class GameInfoIntentHandler(AbstractRequestHandler):
    """Handler generico per informazioni sui giochi."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("GameInfoIntent")(handler_input)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        session_attr = handler_input.attributes_manager.session_attributes
        game_service = create_game_service(handler_input)

        # ---------------------------
        # 1. RECUPERO GIOCO
        # ---------------------------
        gioco = slots.get("gioco").value if slots.get("gioco") and slots["gioco"].value else None
        if gioco:
            gioco = gioco.lower()

        # Fallback sul gioco sorteggiato in sessione
        if not gioco:
            gioco_sessione = session_attr.get("ultimo_sorteggiato_sessione")
            if gioco_sessione:
                gioco = gioco_sessione.lower()

        # Fallback sul gioco della partita in corso
        if not gioco:
            partita = game_service.get_current_game()
            if partita:
                gioco = partita.get("gioco")

        # ---------------------------
        # 2. ELICIT SE MANCA ANCORA
        # ---------------------------
        if not gioco:
            return (
                handler_input.response_builder
                    .speak("Di quale gioco vuoi sapere le regole?")
                    .add_directive(ElicitSlotDirective(slot_to_elicit="gioco"))
                    .ask("Dimmi il nome del gioco.")
                    .response
            )

        # ---------------------------
        # 3. RECUPERO REGOLE DAL SERVICE
        # ---------------------------
        regole, error = game_service.get_game_info(gioco)

        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .add_directive(ElicitSlotDirective(slot_to_elicit="gioco"))
                    .ask("Vuoi sapere di un altro gioco?")
                    .response
            )

        return (
            handler_input.response_builder
                .speak(regole)
                .ask("Hai altre domande?")
                .response
        )
#----------------------------------------------------------------------------

#------------------------DOMANDA SULLE REGOLE CON GEMINI---------------------
class AskRulesIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AskRulesIntent")(handler_input)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        session_attr = handler_input.attributes_manager.session_attributes
        
        game_service = create_game_service(handler_input)

        # ---------------------------
        # 1. RECUPERO GIOCO
        # ---------------------------
        gioco = slots.get("gioco").value if slots.get("gioco") and slots["gioco"].value else None
        if gioco:
            gioco = gioco.lower()

        # Fallback sul gioco sorteggiato in sessione
        if not gioco:
            gioco = session_attr.get("ultimo_sorteggiato_sessione", "").lower() or None
            
        if not gioco or not game_service.is_valid_game(gioco):
            giochi_disponibili = ", ".join(game_service.get_available_games())
            return (
                handler_input.response_builder
                    .speak(
                        f"Non conosco questo gioco o non hai specificato di quale gioco vuoi sapere. "
                        f"Posso rispondere a domande su: {giochi_disponibili}."
                    )
                    .add_directive(ElicitSlotDirective(slot_to_elicit="gioco"))
                    .ask("Di quale gioco vuoi fare una domanda?")
                    .response
            )

        # ---------------------------
        # 2. RECUPERO DOMANDA
        # ---------------------------
        domanda = slots.get("domanda").value if slots.get("domanda") and slots["domanda"].value else None

        if not domanda:
            return (
                handler_input.response_builder
                    .speak(f"Certo! Qual è la tua domanda sulle regole di {gioco}?")
                    .add_directive(ElicitSlotDirective(slot_to_elicit="domanda"))
                    .ask("Dimmi la tua domanda.")
                    .response
            )

        # ---------------------------
        # 3. CHIAMATA A GEMINI
        # ---------------------------
        regole, _ = game_service.get_game_info(gioco)
        risposta = ai_service.ask_rules(gioco, regole, domanda)

        return (
            handler_input.response_builder
                .speak(risposta)
                .ask("Hai altre domande sulle regole?")
                .response
        )
#-------------------------------------------------------------------------

#------------------------Sorteggio di un gioco----------------------------
class RandomGameIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("RandomGameIntent")(handler_input)

    def handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        game_service = create_game_service(handler_input)

        # ---------------------------
        # 1. SORTEGGIO
        # ---------------------------
        gioco_sorteggiato = game_service.get_random_game(session_attr)

        # ---------------------------
        # 2. RISPOSTA
        # ---------------------------
        speak_output = (
            f"Ho sorteggiato: {gioco_sorteggiato}! "
            f"Se vuoi avviare una partita dici: avvia una partita di {gioco_sorteggiato} elencando i giocatori. "
            f"Posso anche spiegarti le regole o sorteggiare un altro gioco."
        )

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Vuoi le regole, avviare una partita, o sorteggiare un altro gioco?")
                .response
        )
#------------------------------------------------------------------------------------------

#----------------------------------INIZIO PARTITA------------------------------------------
class StartGameIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("StartGameIntent")(handler_input)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        game_service = create_game_service (handler_input)

        # ---------------------------
        # 1. RECUPERO GIOCO
        # ---------------------------
        gioco = slots.get("gioco").value if slots.get("gioco") and slots["gioco"].value else None

        if not gioco or not game_service.is_valid_game(gioco):
            return (
                handler_input.response_builder
                    .speak(f"Gioco non disponibile. A quale gioco vuoi giocare? Puoi scegliere tra {', '.join(game_service.get_available_games())}.")
                    .add_directive(ElicitSlotDirective(slot_to_elicit="gioco"))
                    .ask("A quale gioco vuoi giocare?")
                    .response
            )

        # ---------------------------
        # 2. RECUPERO GIOCATORI
        # ---------------------------
        nomi_slot = ["giocatoreuno", "giocatoredue", "giocatoretre", "giocatorequattro", "giocatorecinque", "giocatoresei"]
        giocatori = []

        for slot_name in nomi_slot:
            if slots.get(slot_name) and slots[slot_name].value:
                giocatori.append(slots[slot_name].value.capitalize())

        if not giocatori:
            return (
                handler_input.response_builder
                    .speak(f"Perfetto, giochiamo a {gioco}. Dimmi i nomi dei giocatori.")
                    .ask("Chi gioca?")
                    .response
            )
            
        # 2b. VALIDAZIONE NUMERO GIOCATORI
        min_g, max_g = game_service.get_player_limits(gioco)
        if len(giocatori) < min_g or len(giocatori) > max_g:
            if min_g == max_g:
                speak_output = (f"{gioco} si gioca a {max_g} giocatori.")
            else:
                speak_output = (f"{gioco} si gioca da {min_g} a {max_g} giocatori.")
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Ripeti il comando con il numero di giocatori corretti o cambia gioco")
                .response
            )

        # ---------------------------
        # 3. CREAZIONE PARTITA
        # ---------------------------
        partita, error = game_service.start_game(gioco, giocatori)

        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .ask("Vuoi chiedermi qualcos'altro?")
                    .response
            )

        # ---------------------------
        # 4. RISPOSTA
        # ---------------------------
        if len(giocatori) == 1:
            nomi = giocatori[0]
        else:
            nomi = ", ".join(giocatori[:-1]) + " e " + giocatori[-1]

        speak_output = (
            f"Perfetto! Ho avviato una partita di {gioco} con {nomi}. "
            f"Siamo al turno 1. Dà le carte {giocatori[0]}."
        )

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )
#------------------------------------------------------------------------

#----------------------CANCELLA PARTITA----------------------------------
#NON IN PROGETTAZIONE
class AbandonGameIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AbandonGameIntent")(handler_input)

    def handle(self, handler_input):
        confirmation_status = handler_input.request_envelope.request.intent.confirmation_status.value

        # ---------------------------
        # 1. NEGATO
        # ---------------------------
        if confirmation_status == "DENIED":
            return (
                handler_input.response_builder
                    .speak("Ok, la partita continua.")
                    .ask("Come posso aiutarti?")
                    .response
            )

        # ---------------------------
        # 2. CONFERMATO
        # ---------------------------
        game_service = create_game_service(handler_input)
        success, error = game_service.abandon_game()

        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .ask("Posso aiutarti in altro modo?")
                    .response
            )

        return (
            handler_input.response_builder
                .speak("Partita annullata. Posso aiutarti in altro modo?")
                .ask("Posso aiutarti in altro modo?")
                .response
        )
#------------------------------------------------------------------------

#-----------------------AGGIORNA PUNTEGGI--------------------------------
class UpdateScoreIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("UpdateScoreIntent")(handler_input)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots

        # Legge gli slot
        giocatore = slots["giocatore"].value.capitalize() if slots.get("giocatore") and slots["giocatore"].value else None
        punti_raw = slots["punti"].value if slots.get("punti") and slots["punti"].value else None
        operazione = slots["operazione"].value.lower() if slots.get("operazione") and slots["operazione"].value else "aggiungi"

        # Converte i punti in numero
        try:
            punti = int(punti_raw)
        except (TypeError, ValueError):
            punti = 1
            
        # Aggiunge o toglie i punti
        if operazione == "togli":
            punti = -punti
        
        #GAME SERVICE
        game_service = create_game_service(handler_input)
        partita, error = game_service.update_score(giocatore, punti)
        
        # GESTIONE ERRORI
        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .ask("Cosa posso fare per te?")
                    .response
            )

        #RISPOSTA
        punteggio_attuale = partita["giocatori"][giocatore]
        segno = "+" if punti > 0 else ""
        if punti == 1:
            speak_output = (
            f"{segno}{punti} a {giocatore}. "
            f"{giocatore} ha ora {punteggio_attuale} punto."
            )
        else:
            speak_output = (
                f"{segno}{punti} a {giocatore}. "
                f"{giocatore} ha ora {punteggio_attuale} punti."
            )

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Vuoi aggiornare altri punteggi?")
                .response
        )
#-------------------------------------------------------------------------------

#------------------------------CLASSIFICA---------------------------------------
class GetScoresIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("GetScoresIntent")(handler_input)

    def handle(self, handler_input):
        
        #GAME SERVICE
        game_service = create_game_service(handler_input)
        giocatori, error = game_service.get_scores()

        #ERROR HANDLING
        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .ask("Se vuoi, puoi avviare una partita")
                    .response
            )

        #RESPONSE
        speak_output = f"Classifica attuale: {format_classifica(giocatori)}."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )
#------------------------------------------------------------------------------------------

#------------------------------------FINE TURNO--------------------------------------------
class EndTurnIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("EndTurnIntent")(handler_input)

    def handle(self, handler_input):
        #GAME SERVICE
        game_service = create_game_service(handler_input)
        partita, error = game_service.end_turn()

        #ERROR HANDLING
        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .ask("Se vuoi puoi avviare una partita")
                    .response
            )
        
        # RESPONSE
        ordine = partita["ordine"]
        prossimo_mazziere = ordine[int(partita["mazziere_index"])] #casting esplicito necessario
        turno = partita["turno"]
        giocatori = partita["giocatori"]

        speak_output = (
            f"Turno {turno - 1} concluso. "
            f"Classifica: {format_classifica(giocatori)}. "
            f"Al turno {turno} dà le carte {prossimo_mazziere}."
        )

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )
#------------------------------------------------------------------------------------------

#------------------------------------FINE PARTITA------------------------------------------
class EndGameIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("EndGameIntent")(handler_input)

    def handle(self, handler_input):
        
        #GAME SERVICEg
        game_service = create_game_service(handler_input)
        result, error = game_service.end_game()

        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .ask("Posso aiutarti in altro modo?")
                    .response
            )
        
        classifica = result["punteggi"]
        vincitori_str = result["vincitore"]
        vincitori = [v.strip() for v in vincitori_str.split(" e ")] #sennò lettere divise da virgole
        punteggio_max = max(classifica.values())

        if len(vincitori) == 1:
            esito = f"{vincitori[0]} con {punteggio_max} punti."
        else:
            esito = f"Parità tra {', '.join(vincitori)} con {punteggio_max} punti."
            
        speak_output = (
        "<speak>"
        "Partita terminata! Ha vinto... "
        "<audio src='soundbank://soundlibrary/musical/amzn_sfx_drum_and_cymbal_01'/>"
        f"{esito} "
        "<audio src='soundbank://soundlibrary/musical/amzn_sfx_trumpet_bugle_03'/>"
        f"Classifica finale: {format_classifica(classifica)}. "
        "</speak>"
        )
        
        return handler_input.response_builder.speak(speak_output).response
#-------------------------------------------------------------------------------------------

#------------------------------------STORICO VINCITORI--------------------------------------    
class GetHistoryIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("GetHistoryIntent")(handler_input)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        game_service = create_game_service(handler_input)

        # ---------------------------
        # 1. RECUPERO SLOT
        # ---------------------------
        giocatore = slots["giocatore"].value.capitalize() if slots.get("giocatore") and slots["giocatore"].value else None
        gioco = slots["gioco"].value.lower() if slots.get("gioco") and slots["gioco"].value else None

        # ---------------------------
        # 2. RECUPERO STORICO DAL SERVICE
        # ---------------------------
        result, error = game_service.get_history(gioco=gioco, giocatore=giocatore)

        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .ask("Come posso esserti utile?")
                    .response
            )

        partite = result["partite"]
        vittorie = result["vittorie"]
        ultima = result["ultima"]
        gioco_str = f"a {gioco}" if gioco else "in totale"
        n_partite = len(partite)

        # ---------------------------
        # 3. RISPOSTA
        # ---------------------------
        if giocatore:
            n_vittorie = vittorie.get(giocatore, 0)
            n_partite_giocatore = len([p for p in partite if giocatore in p.get("punteggi", {})])
            speak_output = (
                f"{giocatore} ha vinto {n_vittorie} "
                f"{'volta' if n_vittorie == 1 else 'volte'} su {n_partite_giocatore} "
                f"{'partita' if n_partite_giocatore == 1 else 'partite'} {gioco_str}."
            )
        else:
            classifica = sorted(vittorie.items(), key=lambda x: x[1], reverse=True)
            lines = ". ".join([
                f"{nome} con {n} {'vittoria' if n == 1 else 'vittorie'}"
                for nome, n in classifica
            ])
            speak_output = (
                f"Avete giocato {n_partite} "
                f"{'partita' if n_partite == 1 else 'partite'} {gioco_str}. "
                f"Classifica vincitori: {lines}. "
                f"L'ultima partita di {ultima.get('gioco')} "
                f"è stata vinta da {ultima.get('vincitore')}."
            )

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Posso aiutarti in altro modo?")
                .response
        )
#-------------------------------------------------------------------------------------------

#------------------------------------PULISCI STORICO----------------------------------------
#NON PREVISTO IN PROGETTAZIONE
class ClearHistoryIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ClearHistoryIntent")(handler_input)

    def handle(self, handler_input):
        confirmation_status = handler_input.request_envelope.request.intent.confirmation_status.value

        # ---------------------------
        # 1. NEGATO
        # ---------------------------
        if confirmation_status == "DENIED":
            return (
                handler_input.response_builder
                    .speak("Ok, lo storico rimane invariato.")
                    .ask("Posso aiutarti in altro modo?")
                    .response
            )

        # ---------------------------
        # 2. CONFERMATO
        # ---------------------------
        game_service = create_game_service(handler_input)
        success, error = game_service.clear_history()

        if error:
            return (
                handler_input.response_builder
                    .speak(error.value)
                    .ask("Posso aiutarti in altro modo?")
                    .response
            )

        return (
            handler_input.response_builder
                .speak("Ho cancellato lo storico delle partite.")
                .ask("Posso aiutarti in altro modo?")
                .response
        )
#------------------------------------------------------------------------------------------

#-------------------------------------------AIUTO-------------------------------------------
class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Puoi chiedermi le regole di un gioco e farmi domande a tal riguardo. Puoi avviare una partita e ti aiuterò a segnare i punti e a ricordarti chi deve dare carte. Posso dirti la classifica aggiornata e lo storico vincitori. Puoi anche chiedermi di sorteggiare un gioco se sei indeciso o hai voglia di scoprire giochi nuovi."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Come posso aiutarti?")
                .response
        )
#-------------------------------------------------------------------------------------------

#--------------------------------------CHIUSURA SKILL---------------------------------------
class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "A presto"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_should_end_session(True) #forza la chiusura
                .response
        )
#-------------------------------------------------------------------------------------------

#-----------------------------------GESTIONE CASI PARTICOLARI-------------------------------
class FallbackIntentHandler(AbstractRequestHandler):
    """Single handler for Fallback Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")
        speech = "Credo di non aver capito chiaramente la tua richiesta, potresti riformularla?"
        reprompt = "Non mi è chiaro. Come posso aiutarti?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response
#---------------------------------------------------------------------------------------------

#-----------------------------------CHIUSURA SESSIONE-----------------------------------------
class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response
#------------------------------------------------------------------------------------------------

#------------------------------TESTING MODELLO DI INTERAZIONE------------------------------------
class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )
#------------------------------------------------------------------------------------------------

#-----------------------------------GESTIONE ERRORI----------------------------------------------
class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True
        
    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)

        if isinstance(exception, AiServiceError):
            speak_output = "Mi dispiace, il servizio di risposta alle domande non è disponibile al momento."
        elif isinstance(exception, DBError):
            speak_output = "Mi dispiace, ho problemi a recuperare i dati. Riprova tra poco."
        else:
            speak_output = "Scusami, ho avuto dei problemi con la tua richiesta. Prova a chiedere di nuovo."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Come posso aiutarti?")
                .response
        )
#-------------------------------------------------------------------
#===================================================================

#=======================SKILL BUILDER===============================
sb = CustomSkillBuilder(persistence_adapter=dynamodb_adapter) #DybamoDb (persistence o dynamo_repository)
#sb = CustomSkillBuilder() #in_memory_repository o altro DB

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GameInfoIntentHandler())
sb.add_request_handler(AskRulesIntentHandler())
sb.add_request_handler(RandomGameIntentHandler())
sb.add_request_handler(StartGameIntentHandler())
sb.add_request_handler(AbandonGameIntentHandler())
sb.add_request_handler(UpdateScoreIntentHandler())
sb.add_request_handler(GetScoresIntentHandler())
sb.add_request_handler(EndTurnIntentHandler())
sb.add_request_handler(EndGameIntentHandler())
sb.add_request_handler(GetHistoryIntentHandler())
sb.add_request_handler(ClearHistoryIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
#sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
#======================================================================
