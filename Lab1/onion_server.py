from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer # creo un server HTTP

token = b"" # memorizzo l'ultimo token ricevuto

class gestoreclient(BaseHTTPRequestHandler):

    # invio una risposta 200 con testo semplice
    def rispondi(self, contenuto):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(contenuto)))
        self.end_headers()
        self.wfile.write(contenuto)

    def do_GET(self):
        if self.path == "/":
            self.rispondi(b"OK")

        elif self.path == "/claim":
            self.rispondi(token) # restituisco l'ultimo token

        else:
            self.send_error(404)

    def do_POST(self):
        global token # modifico la variabile condivisa tra le richieste

        if self.path == "/claim":
            lunghezza = int(self.headers.get("Content-Length", 0))
            token = self.rfile.read(lunghezza) # leggo il token dal corpo della richiesta
            self.rispondi(b"OK")

        else:
            self.send_error(404)


with ThreadingHTTPServer(("0.0.0.0", 8090), gestoreclient) as server:
    print("Server HTTP in ascolto sulla porta 8090...")
    server.serve_forever() # aspetto le richieste dei client