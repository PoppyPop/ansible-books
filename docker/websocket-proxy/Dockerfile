FROM python:3.11-alpine

ADD proxy-websocket.py .

RUN pip install websockets==10.4

CMD ["python", "./proxy-websocket.py"]