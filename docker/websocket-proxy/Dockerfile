FROM python:3.11-alpine

ADD proxy-websocket.py .

RUN pip install asyncio websockets

CMD ["python", "./proxy-websocket.py"]