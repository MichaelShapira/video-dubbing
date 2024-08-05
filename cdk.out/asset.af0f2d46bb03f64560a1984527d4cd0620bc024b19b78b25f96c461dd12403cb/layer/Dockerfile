FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .

RUN pip install -r requirements.txt -t /opt/python

CMD ["echo", "Layer build completed"]