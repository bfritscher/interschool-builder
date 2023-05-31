FROM node:18 AS frontend
WORKDIR /app
COPY package.json /app/package.json
RUN npm install
COPY . /app
RUN sed -i 's/baseURL: .*/baseURL: "\/api",/' src/services/api.js
RUN npm run build

FROM python:3.11-alpine
ENV DJANGO_SUPERUSER_USERNAME=autoadmin
ENV DJANGO_SUPERUSER_EMAIL=autoadmin@example.com
ENV DJANGO_SUPERUSER_PASSWORD=heg
ENV DJANGO_SUPERUSER_FIRST_NAME=auto
ENV DJANGO_SUPERUSER_LAST_NAME=admin
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
COPY . /app
RUN sed -i '/django.middleware.clickjacking.XFrameOptionsMiddleware/d' backend/settings/base.py
COPY --from=frontend /app/dist /app/dist

RUN python manage.py migrate
RUN python manage.py createsuperuser --no-input
RUN python manage.py loaddata ./backend/*/*fixture*/*.json; exit 0
RUN cat /app/prod.py >> backend/settings/base.py
CMD python manage.py runserver 0.0.0.0:8000
