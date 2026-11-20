import socketserver #importo il modulo per creare un server TCP

# creo un dizionario per memorizzare le coppie chiave-valore
store = {}

# chiamo una classe che gestisce le richieste dei client
class gestoreclient(socketserver.StreamRequestHandler): 

    # metodo di socketserver
    def handle(self): # riceve self perchè deve sapere su che oggetto sta lavorando
        # Legge un comando alla volta, fino al carattere \n
        for line in self.rfile: # scorre le righe ricevute dal client attraverso la connessione tcp

            comando = line.decode("ascii").removesuffix("\n")

            if comando == "PING":
                risposta = "PONG"

            elif comando.startswith("ECHO "):
                risposta = comando[5:] # restituisce il testo dopo ECHO

            elif comando.startswith("SET "):
                parti = comando.split(" ", 2) # effettua due divisioni dove trova lo spazio e restituisce una lista

                # controlla che la lista abbia 3 elementi e che il secondo e terzo elemento non siano vuoti
                if len(parti) == 3 and parti[1] and parti[2]:
                    chiave = parti[1]
                    valore = parti[2]
                    store[chiave] = valore
                    risposta = "OK"
                else:
                    risposta = "ERR"

            elif comando.startswith("GET "): # se il comando inizia con get devo leggere
                chiave = comando[4:] # quindi salvo tutto quello che c'è dopo get come chiave

                if chiave and " " not in chiave: # la chiave non deve essere vuota, ne contenere spazi 
                    risposta = store.get(chiave, "NOT_FOUND") # se la trova la restituisce, altrimenti restituisce NOT_FOUND 
                else:
                    risposta = "ERR"

            else:
                risposta = "ERR"

            # Ogni risposta termina con \n
            self.wfile.write((risposta + "\n").encode("ascii"))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True # permette di riutilizzare l'indirizzo del server dopo averlo fermato
    daemon_threads = True # fa si che i thread dei client non tengano in vita il programma quando il server viene chiuso



with Server(("0.0.0.0", 9001), gestoreclient) as server:
    print("Server TCP in ascolto sulla porta 9001...")
    server.serve_forever() # avvia il ciclo che aspetta le connessioni dei client e le gestisce con la classe gestoreclient