import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# WICHTIG: CORS erlaubt deiner HTML-App (auch vom Handy), auf das Backend zuzugreifen
CORS(app)

# Haupt-Route für den Chat (passend zum HTML-Fetch an /chat)
@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Daten aus der HTML-Anfrage auslesen
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'reply': 'Keine Nachricht empfangen.'}), 400

        user_message = data.get('message')
        
        # Hier findet die Verarbeitung der Nachricht statt!
        # Aktuell antwortet der Server dynamisch basierend auf der Eingabe:
        reply_text = f"Server hat empfangen: '{user_message}'"
        
        # Beispiel für einfache Antworten (kannst du beliebig anpassen):
        if "hallo" in user_message.lower():
            reply_text = "Hallo! Wie kann ich dir heute helfen?"
        elif "wie geht" in user_message.lower():
            reply_text = "Mir geht es super, ich laufe stabil auf Render!"

        # Antwort im JSON-Format an das Handy zurückschicken
        return jsonify({'reply': reply_text}), 200

    except Exception as e:
        return jsonify({'reply': f'Fehler im Server: {str(e)}'}), 500

# Test-Route um zu prüfen, ob der Server grundsätzlich läuft
@app.route('/', methods=['GET'])
def home():
    return "Talk-to-Me Backend läuft erfolgreich!", 200

if __name__ == '__main__':
    # Render weist deiner App automatisch einen PORT über Umgebungsvariablen zu
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)