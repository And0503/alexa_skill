# alexa_skill

---

## DESCRIZIONE
**Game Guru** è una skill alexa che svolge il compito di assistente per giochi di carte. 
Include le seguenti funzionalità:
- Sorteggiare un gioco
- Spiegazione delle regole
- Rispondere a domande sulle regole mediante AI
- Avviare una partita e ricordare chi deve dare carte
- Segnare e riportare la classifica
- Fine turno
- Fine gioco con vincitore
- Storico vincitori
---

---

👥 Autori - Progetto personale
- Andrea Tito - https://github.com/And0503

---

---

⚙️ Guida tecnica

---

---

🛠️ Tecnologie
Amazon developer console
Python
boto3 1.28.78
ask-sdk-core 1.19.0
ask-sdk-dynamodb-persistence-adapter

---

### 📁 Struttura del repo

| File / Cartella | Descrizione |
|----------------|-------------|
| `lambda_function.py` | Entry point della AWS Lambda per la skill Alexa  con gestione degli intent|
| `game_service.py` | Logica di business |
| `storage/repository.py` | Interfaccia per database |
| `storage/dynamo_repository.py` | Persistenza su AWS DynamoDB tramite Alexa Persistence Adapter |
| `storage/in_memory_repository.py` | Repository per testing con session_attributes (senza DynamoDB)  |
| `ai/ai_service.py` | Interfaccia per modello ai |
| `ai/gemini_service.py` | Integrazione con Gemini per risposte sulle regole dei giochi |
| `models.py` | Dataclass |
| `errors.py` | Gestione errori custom |
| `helper_functions.py` | Funzioni di supporto |
| `requirements.txt` | Dipendenze Python del progetto |

---

---

### 🚀 Come eseguire il progetto
1. Creare account amazon developer console
2. Aprire online la amazon developer console
3. creare la skill con nome di invocazione game guru
4. importare codice in code
5. importare modello di interazione in build
6. Fare save, deploy e build
7. Avviare in Test la modalità Development
8. Usare la skill sui propri dispositivi alexa o da amazon developer console

---

