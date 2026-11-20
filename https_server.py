import json # importo il modulo per leggere e creare dati JSON
import ssl # importo il modulo per proteggere le connessioni con TLS
import secrets # importo il modulo per creare identificatori di sessione casuali
from threading import Thread
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# creo un dizionario che associa ogni sessione al nome dell'utente
sessioni = {}


class gestoreclient(BaseHTTPRequestHandler):

    # creo un metodo per inviare lo stato, il corpo ed eventualmente un cookie
    def rispondi(self, stato, dati="", cookie=None):
        tipo = "text/plain; charset=utf-8"

        if isinstance(dati, dict):
            dati = json.dumps(dati)
            tipo = "application/json"

        corpo = dati.encode("utf-8")
        self.send_response(stato)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))

        if cookie is not None:
            self.send_header("Set-Cookie", cookie)

        self.end_headers()
        self.wfile.write(corpo)

    # gestisco le richieste GET
    def do_GET(self):

        # sulla porta 8444 recupero il nome dal certificato del client
        if self.server.server_port == 8444:
            if self.path != "/whoami":
                self.rispondi(404)
                return

            certificato = self.connection.getpeercert()
            nome = ""

            # cerco il Common Name dentro il certificato
            for gruppo in certificato["subject"]:
                for campo, valore in gruppo:
                    if campo == "commonName":
                        nome = valore

            self.rispondi(200, nome)

        elif self.path == "/":
            self.rispondi(200)

        elif self.path == "/me":
            cookie = SimpleCookie()

            try:
                cookie.load(self.headers.get("Cookie", "")) # leggo i cookie ricevuti
            except CookieError:
                self.rispondi(401)
                return

            sessione = cookie.get("session")
            nome = sessioni.get(sessione.value) if sessione else None

            if nome is None:
                self.rispondi(401)
            else:
                self.rispondi(200, {"user": nome})

        else:
            self.rispondi(404)

    # gestisco il login sulla porta 8443
    def do_POST(self):
        if self.server.server_port != 8443 or self.path != "/login":
            self.rispondi(404)
            return

        try:
            lunghezza = int(self.headers.get("Content-Length", "0"))
            if lunghezza < 0:
                raise ValueError()

            dati = json.loads(self.rfile.read(lunghezza).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.rispondi(400)
            return

        # controllo che il corpo sia un dizionario e che user sia una stringa
        if not isinstance(dati, dict) or not isinstance(dati.get("user"), str):
            self.rispondi(400)
            return

        if dati.get("password") != "netsec":
            self.rispondi(401)
            return

        # creo una sessione casuale e la associo all'utente
        sessione = secrets.token_hex(32)
        sessioni[sessione] = dati["user"]

        # invio il cookie con gli attributi Secure e HttpOnly
        self.rispondi(
            200,
            {"status": "ok"},
            f"session={sessione}; Secure; HttpOnly; Path=/"
        )


# creo un server HTTPS, con autenticazione del client se mtls è True
def crea_server(porta, mtls=False):
    contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contesto.load_cert_chain("server.crt", "server.key")

    if mtls:
        contesto.load_verify_locations("ca.crt") # carico la CA del corso
        contesto.verify_mode = ssl.CERT_REQUIRED # richiedo un certificato client valido

    server = ThreadingHTTPServer(("0.0.0.0", porta), gestoreclient)
    server.socket = contesto.wrap_socket(server.socket, server_side=True)
    return server


if __name__ == "__main__":
    with crea_server(8443) as https, crea_server(8444, mtls=True) as mtls:

        # avvio la porta 8444 in un thread per mantenere attive entrambe le porte
        Thread(target=mtls.serve_forever, daemon=True).start()
        print("Server HTTPS sulla porta 8443 e mTLS sulla porta 8444...")

        try:
            https.serve_forever() # gestisco le richieste sulla porta 8443
        except KeyboardInterrupt:
            mtls.shutdown() # fermo anche il server mTLS quando premo Ctrl+C