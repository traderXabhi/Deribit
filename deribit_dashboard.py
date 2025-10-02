import asyncio
import websockets
import json
import os

# It is recommended to set these as environment variables
# export DERIBIT_CLIENT_ID='YOUR_CLIENT_ID'
# export DERIBIT_CLIENT_SECRET='YOUR_CLIENT_SECRET'
CLIENT_ID = os.environ.get("DERIBIT_CLIENT_ID", "WOnhZpaY")
CLIENT_SECRET = os.environ.get("DERIBIT_CLIENT_SECRET", "3iVg0tODtKC67sQDUvheOFmO-Hv-fz93mOaFYknypzY")


async def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: Please set the DERIBIT_CLIENT_ID and DERIBIT_CLIENT_SECRET environment variables.")
        return
    uri = "wss://www.deribit.com/ws/api/v2"
    async with websockets.connect(uri) as websocket:
        # Authentication
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
        await websocket.send(json.dumps(auth_request))
        auth_response = await websocket.recv()
        auth_response_data = json.loads(auth_response)

        if 'error' in auth_response_data:
            print("Authentication failed:", auth_response_data['error']['message'])
            return

        print("Authentication successful.")
        access_token = auth_response_data['result']['access_token']

        # Fetch available BTC option instruments
        get_instruments_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "public/get_instruments",
            "params": {
                "currency": "BTC",
                "kind": "option"
            }
        }
        await websocket.send(json.dumps(get_instruments_request))
        instruments_response = await websocket.recv()
        instruments_data = json.loads(instruments_response)

        instruments = instruments_data['result']

        # Organize instruments by expiry date
        options_by_expiry = {}
        for instrument in instruments:
            parts = instrument['instrument_name'].split('-')
            expiry_date = parts[1]
            if expiry_date not in options_by_expiry:
                options_by_expiry[expiry_date] = []
            options_by_expiry[expiry_date].append(instrument['instrument_name'])

        # Fetch ticker data for each instrument and display
        for expiry_date, instrument_names in sorted(options_by_expiry.items()):
            print(f"\n--- Expiry: {expiry_date} ---")

            calls = {}
            puts = {}

            print(f"Fetching data for {len(instrument_names)} instruments...")
            for i, instrument_name in enumerate(instrument_names):
                print(f"Fetching {instrument_name} ({i+1}/{len(instrument_names)})", end='\r')
                ticker_request = {
                    "jsonrpc": "2.0",
                    "id": 3 + i,
                    "method": "public/ticker",
                    "params": {
                        "instrument_name": instrument_name
                    }
                }
                await websocket.send(json.dumps(ticker_request))
                ticker_response = await websocket.recv()
                response_data = json.loads(ticker_response)

                if 'result' not in response_data:
                    print(f"\nError fetching ticker for {instrument_name}: {response_data}")
                    continue
                ticker_data = response_data['result']

                parts = instrument_name.split('-')
                strike = float(parts[2])
                option_type = parts[3]

                data = {
                    'iv': ticker_data.get('mark_iv'), # Use mark_iv as it's more reliable
                    'delta': ticker_data.get('greeks', {}).get('delta'),
                    'oi': ticker_data.get('open_interest'),
                    'ltp': ticker_data.get('last_price'),
                }

                if option_type == 'C':
                    calls[strike] = data
                else:
                    puts[strike] = data

            print("\n{:<10} {:<10} {:<10} {:<10} | {:<10} | {:<10} {:<10} {:<10} {:<10}".format(
                "IV (C)", "Delta (C)", "OI (C)", "LTP (C)", "Strike", "LTP (P)", "OI (P)", "Delta (P)", "IV (P)"
            ))
            print("-" * 94)

            all_strikes = sorted(list(set(calls.keys()) | set(puts.keys())))

            for strike in all_strikes:
                call_data = calls.get(strike, {})
                put_data = puts.get(strike, {})

                # Handling None values for formatting
                iv_c = call_data.get('iv') if call_data.get('iv') is not None else 0
                delta_c = call_data.get('delta') if call_data.get('delta') is not None else 0
                oi_c = call_data.get('oi') if call_data.get('oi') is not None else 0
                ltp_c = call_data.get('ltp') if call_data.get('ltp') is not None else 0

                ltp_p = put_data.get('ltp') if put_data.get('ltp') is not None else 0
                oi_p = put_data.get('oi') if put_data.get('oi') is not None else 0
                delta_p = put_data.get('delta') if put_data.get('delta') is not None else 0
                iv_p = put_data.get('iv') if put_data.get('iv') is not None else 0

                print("{:<10.2f} {:<10.4f} {:<10.2f} {:<10.2f} | {:<10.0f} | {:<10.2f} {:<10.2f} {:<10.4f} {:<10.2f}".format(
                    iv_c, delta_c, oi_c, ltp_c,
                    strike,
                    ltp_p, oi_p, delta_p, iv_p
                ))

if __name__ == "__main__":
    asyncio.run(main())