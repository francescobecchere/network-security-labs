import json # importo il modulo per leggere e creare dati JSON
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

notes = {} # creo un dizionario per memorizzare le note
prossimo_id = 1 # creo un contatore per gli identificatori delle note


class gestoreclient(BaseHTTPRequestHandler):

    # creo un metodo per inviare lo stato HTTP ed eventualmente un corpo JSON
    def rispondi(self, stato, dati=None):
        corpo = json.dumps(dati).encode("utf-8") if dati is not None else b""
        self.send_response(stato)

        if dati is not None:
            self.send_header("Content-Type", "application/json")
        if stato != 204:
            self.send_header("Content-Length", str(len(corpo)))

        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    # recupero l'identificatore dal percorso, oppure restituisco None se non è valido
    def leggi_id(self):
        percorso = urlsplit(self.path).path
        if percorso.startswith("/notes/"):
            try:
                return int(percorso[7:])
            except ValueError:
                pass
        return None

    # gestisco le richieste GET
    def do_GET(self):
        url = urlsplit(self.path)

        if url.path == "/":
            self.rispondi(200)
        elif url.path == "/echo":
            parametri = parse_qs(url.query, keep_blank_values=True)
            messaggio = parametri.get("msg", [""])[0]
            self.rispondi(200, {"msg": messaggio})
        elif url.path == "/notes":
            self.rispondi(405)
        else:
            identificatore = self.leggi_id()
            if identificatore in notes:
                self.rispondi(200, {"id": identificatore, "text": notes[identificatore]})
            else:
                self.rispondi(404)

    # gestisco le richieste POST per creare una nota
    def do_POST(self):
        global prossimo_id

        if urlsplit(self.path).path != "/notes":
            self.rispondi(404)
            return

        if self.headers.get_content_type() != "application/json":
            self.rispondi(415)
            return

        try:
            lunghezza = int(self.headers.get("Content-Length", "0"))
            if lunghezza < 0:
                raise ValueError()
            dati = json.loads(self.rfile.read(lunghezza).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.rispondi(400)
            return

        if not isinstance(dati, dict) or not isinstance(dati.get("text"), str):
            self.rispondi(400)
            return

        notes[prossimo_id] = dati["text"] # salvo la nota nel dizionario
        self.rispondi(201, {"id": prossimo_id})
        prossimo_id += 1 # incremento il contatore per la prossima nota

    # gestisco le richieste DELETE per eliminare una nota
    def do_DELETE(self):
        if urlsplit(self.path).path == "/notes":
            self.rispondi(405)
            return

        identificatore = self.leggi_id()
        if identificatore in notes:
            del notes[identificatore]
            self.rispondi(204)
        else:
            self.rispondi(404)

    # gestisco i metodi non supportati su /notes
    def metodo_non_supportato(self):
        percorso = urlsplit(self.path).path
        if percorso == "/notes" or self.leggi_id() in notes:
            self.rispondi(405)
        else:
            self.rispondi(404)

    do_PUT = metodo_non_supportato
    do_PATCH = metodo_non_supportato
    do_HEAD = metodo_non_supportato
    do_OPTIONS = metodo_non_supportato
    do_TRACE = metodo_non_supportato
    do_CONNECT = metodo_non_supportato


with ThreadingHTTPServer(("0.0.0.0", 8080), gestoreclient) as server:
    print("Server HTTP in ascolto sulla porta 8080...")
    server.serve_forever() # aspetto e gestisco le richieste dei client