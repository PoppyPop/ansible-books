#!/usr/bin/env python3

# websocket proxy

import argparse
import asyncio
import websockets
import ssl

async def hello(websocket, path):
    '''Called whenever a new connection is made to the server'''

    print("New client connected")
    url = REMOTE_URL + path

    print(f"New remote url {url}")

    try:
        async with websockets.connect(url, subprotocols=websocket.request_headers.get_all('Sec-WebSocket-Protocol')) as ws:
            taskA = asyncio.create_task(clientToServer(ws, websocket))
            taskB = asyncio.create_task(serverToClient(ws, websocket))

            await taskA
            await taskB

    except websockets.exceptions.ProtocolError as e:
        print(e)
        print('Protocol error')
    except websockets.exceptions.ConnectionClosedOK:
        print('Connection closed properly')
    except websockets.exceptions.ConnectionClosedError:
        print('Connection closed with an error')
    except Exception as e:
        print(e)
        print('Generic Exception caught in {}'.format(traceback.format_exc()))
    finally:
        # cancel both tasks
        if taskA is not None:
            taskA.cancel()

        if taskB is not None:
            taskB.cancel()


async def clientToServer(ws, websocket):
    async for message in ws:
        await websocket.send(message)
        print(f"CtoS => {message}")

async def serverToClient(ws, websocket):
    async for message in websocket:
        await ws.send(message)
        print(f"StoC => {message}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='websocket proxy.')
    parser.add_argument('--host', help='Host to bind to.',
                        default='0.0.0.0')
    parser.add_argument('--port', help='Port to bind to.',
                        default=8765)
    parser.add_argument('--remote_url', help='Remote websocket url',
                        default='wss://hass.moot.ovh:9000')
    args = parser.parse_args()

    # wss://ocpp.cpms.esolutionscharging.com/ocpp
    # wss://hass.moot.ovh:9000

    REMOTE_URL = args.remote_url

    print(f"Serving on {args.host}:{args.port}")
    start_server = websockets.serve(hello, args.host, args.port)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
