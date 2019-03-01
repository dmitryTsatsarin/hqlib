FROM python:3.7

RUN pip3 install pipenv
RUN mkdir /code

WORKDIR /code
ADD . /code/

RUN set -ex && pipenv install

CMD ["pipenv", "run", "python", "run_demo.py"]