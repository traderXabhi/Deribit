from flask import Flask, render_template
from flask_sockets import Sockets
import asyncio
import websockets
import json
import os

app = Flask(__name__)
sockets = Sockets(app)

# It is recommended to set these as environment variables
# export DERIBIT_CLIENT_ID='YOUR_CLIENT_ID'
# export DERIBIT_CLIENT_SECRET='YOUR_CLIENT_SECRET'
CLIENT_ID = os.environ.get("DERIBIT_CLIENT_ID", "WOnhZpaY")
CLIENT_SECRET = os.environ.get("DERIBIT_CLIENT_SECRET", "3iVg0tODtKC67sQDUvheOFmO-Hv-fz93mOaFYknypzY")

@app.route('/')
def index():
    return render_template('index.html')

async def deribit_client(ws):
    uri = "wss://www.deribit.com/ws/api/v2"
    while True: # Keep trying to connect
        try:
            async with websockets.connect(uri) as deribit_ws:
                print("Connected to Deribit")
                auth_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "public/auth",
                    "params": {
                        "grant_type": "client_credentials",
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET
                    }
                }
                await deribit_ws.send(json.dumps(auth_request))
                await deribit_ws.recv() # Consume auth response

                get_instruments_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "public/get_instruments",
                    "params": { "currency": "BTC", "kind": "option", "expired": False }
                }
                await deribit_ws.send(json.dumps(get_instruments_request))
                instruments_response = await deribit_ws.recv()
                instrument_names = [ins['instrument_name'] for ins in json.loads(instruments_response)['result']]

                if not ws.closed:
                    ws.send(json.dumps({'type': 'instruments', 'data': instrument_names}))

                channels = [f"ticker.{name}.100ms" for name in instrument_names]

                batch_size = 100
                for i in range(0, len(channels), batch_size):
                    subscribe_request = {
                        "jsonrpc": "2.0",
                        "id": 9000 + i,
                        "method": "public/subscribe",
                        "params": { "channels": channels[i:i+batch_size] }
                    }
                    await deribit_ws.send(json.dumps(subscribe_request))
                    await deribit_ws.recv()

                while not ws.closed:
                    message = await deribit_ws.recv()
                    ws.send(message)

        except (websockets.exceptions.ConnectionClosed, ConnectionResetError) as e:
            print(f"Deribit connection lost: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


@sockets.route('/ws')
def socket(ws):
    asyncio.run(deribit_client(ws))


def main():
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('0.0.0.0', 5000), app, handler_class=WebSocketHandler)
    print("Server starting on port 5000")
    server.serve_forever()

if __name__ == "__main__":
    main()