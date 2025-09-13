# Rasa server with production settings
web: rasa run --enable-api --cors "*" --port $PORT --debug

# Action server (if using separate worker dyno)
worker: rasa run actions --port 5055 --debug
