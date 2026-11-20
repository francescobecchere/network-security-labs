import asyncio # importo il modulo per gestire operazioni asincrone, utilizzato da QUIC
import hashlib # importo il modulo per calcolare l'hash SHA-256
import ssl # importo il modulo per proteggere il server TCP con TLS

from threading import Thread # importo la classe per eseguire il server TCP in un thread separato
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived


# creo una funzione comune che decide la risposta in base al metodo e al percorso
def risposta(metodo, percorso, corpo, protocollo):

    # per GET / restituisco lo stato 200 e il testo OK
    if metodo == "GET" and percorso == "/":
        return 200, b"OK"

    # restituisco il protocollo utilizzato per questa richiesta
    elif metodo == "GET" and percorso == "/proto":
        return 200, protocollo.encode("utf-8")

    # calcolo SHA-256 sui byte del corpo ricevuto
    elif metodo == "POST" and percorso == "/hash":
        # hexdigest restituisce l'hash come stringa esadecimale
        # encode converte la stringa in byte per poterla inviare
        return 200, hashlib.sha256(corpo).hexdigest().encode("ascii")

    # se il metodo e il percorso non corrispondono ai casi precedenti restituisco 404
    else:
        return 404, b"Not Found"


# creo una classe che gestisce le richieste HTTPS ricevute tramite TCP
class gestoreTCP(BaseHTTPRequestHandler):

    # imposto HTTP/1.1 come versione delle risposte
    protocol_version = "HTTP/1.1"

    def gestisci(self):
        corpo = b"" # inizialmente il corpo della richiesta è vuoto

        # nelle richieste POST leggo il corpo inviato dal client
        if self.command == "POST":
            # Content-Length indica quanti byte devo leggere
            lunghezza = int(self.headers.get("Content-Length", "0"))
            corpo = self.rfile.read(lunghezza)

        # self.command contiene il metodo HTTP, self.path contiene il percorso
        # la funzione restituisce il codice di stato e i byte da inviare
        stato, dati = risposta(self.command, self.path, corpo, "HTTP/1.1")

        self.send_response(stato) # invio il codice di stato HTTP
        self.send_header("Content-Type", "text/plain") # il corpo della risposta contiene testo
        self.send_header("Content-Length", str(len(dati))) # comunico la lunghezza del corpo

        # comunico al client che HTTP/3 è disponibile sulla porta 4433
        self.send_header("Alt-Svc", 'h3=":4433"')

        self.end_headers() # termino le intestazioni della risposta
        self.wfile.write(dati) # invio il corpo della risposta

    # associo GET e POST allo stesso metodo di gestione
    do_GET = gestisci
    do_POST = gestisci


# creo una classe che gestisce una connessione QUIC e le sue richieste HTTP/3
class gestoreQUIC(QuicConnectionProtocol):

    # questo metodo viene eseguito quando viene creato l'oggetto
    def __init__(self, *args, **kwargs):

        # passo alla classe di partenza gli argomenti ricevuti dalla libreria
        super().__init__(*args, **kwargs)

        # collego il gestore HTTP/3 alla connessione QUIC
        self.http = H3Connection(self._quic)

        # creo un dizionario per tenere separati i dati degli stream
        # una stessa connessione QUIC può trasportare più richieste contemporaneamente
        self.richieste = {}

    # la libreria chiama questo metodo quando arriva un evento QUIC
    def quic_event_received(self, evento):

        # converto l'evento QUIC negli eventuali eventi HTTP/3 corrispondenti
        for richiesta in self.http.handle_event(evento):

            # considero soltanto gli eventi contenenti intestazioni oppure dati del corpo
            if not isinstance(richiesta, (HeadersReceived, DataReceived)):
                continue # passo all'evento successivo

            # leggo l'identificatore dello stream a cui appartiene questo evento
            stream = richiesta.stream_id

            # se sono arrivate le intestazioni leggo metodo e percorso
            if isinstance(richiesta, HeadersReceived):

                # creo la voce soltanto quando incontro lo stream per la prima volta
                if stream not in self.richieste:
                    intestazioni = dict(richiesta.headers)

                    # le intestazioni HTTP/3 sono ricevute come byte
                    # :method contiene il metodo, :path contiene il percorso
                    self.richieste[stream] = {
                        "metodo": intestazioni[b":method"].decode(),
                        "percorso": intestazioni[b":path"].decode(),
                        "corpo": bytearray()
                    }

                    # bytearray permette di aggiungere i pezzi del corpo man mano che arrivano

            # se l'evento contiene dati li aggiungo al corpo dello stream corretto
            else:
                self.richieste[stream]["corpo"].extend(richiesta.data)

            # stream_ended indica che ho ricevuto tutta la richiesta
            # aspetto questo momento per calcolare l'hash sul corpo completo
            if richiesta.stream_ended:

                # recupero i dati della richiesta e li rimuovo dal dizionario
                dati = self.richieste.pop(stream)

                # preparo la risposta indicando che la richiesta utilizza HTTP/3
                stato, corpo = risposta(
                    dati["metodo"],
                    dati["percorso"],
                    dati["corpo"],
                    "HTTP/3"
                )

                # invio le intestazioni della risposta sullo stesso stream della richiesta
                self.http.send_headers(stream, [
                    (b":status", str(stato).encode()),
                    (b"content-type", b"text/plain"),
                    (b"content-length", str(len(corpo)).encode())
                ])

                # invio il corpo e comunico che la risposta sullo stream è terminata
                self.http.send_data(stream, corpo, end_stream=True)

        # invio sulla rete i dati QUIC preparati
        self.transmit()


# definisco la funzione asincrona che avvia entrambi i server
async def main():

    # creo la configurazione TLS per il server HTTPS su TCP
    contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # carico il certificato autofirmato e la sua chiave privata
    contesto.load_cert_chain("server.crt", "server.key")

    # tramite ALPN comunico che il server TCP supporta HTTP/1.1
    contesto.set_alpn_protocols(["http/1.1"])

    # ascolto sulla porta TCP 4433 su tutte le interfacce, compresa la VPN
    with ThreadingHTTPServer(("0.0.0.0", 4433), gestoreTCP) as tcp:

        # proteggo con TLS il socket del server TCP
        tcp.socket = contesto.wrap_socket(tcp.socket, server_side=True)

        # avvio il server TCP in un thread separato
        # così posso avviare anche il server QUIC senza bloccare il programma
        Thread(target=tcp.serve_forever, daemon=True).start()

        # creo la configurazione QUIC del server
        configurazione = QuicConfiguration(
            is_client=False, # imposto il funzionamento come server
            alpn_protocols=["h3"], # imposto HTTP/3 come protocollo da negoziare
            max_data=16 * 1024 * 1024, # imposto la finestra iniziale dei dati della connessione
            max_stream_data=1024 * 1024 # imposto la finestra iniziale dei dati di ogni stream
        )

        # utilizzo lo stesso certificato anche per QUIC
        configurazione.load_cert_chain("server.crt", "server.key")

        # avvio QUIC sulla porta UDP 4433
        # TCP e UDP possono utilizzare lo stesso numero di porta
        udp = await serve(
            "0.0.0.0",
            4433,
            configuration=configurazione,
            create_protocol=gestoreQUIC
        )

        print("Server attivi sulla porta 4433: HTTPS TCP e HTTP/3 UDP...")

        try:
            # rimango in attesa lasciando asyncio libero di gestire gli eventi QUIC
            await asyncio.Future()

        finally:
            # chiudo entrambi i server quando termino il programma
            udp.close()
            tcp.shutdown()


# avvio il programma soltanto se eseguo direttamente questo file
if __name__ == "__main__":
    try:
        asyncio.run(main()) # avvio la funzione asincrona
    except KeyboardInterrupt:
        print("\nServer arrestati.") # gestisco l'arresto con Ctrl+C