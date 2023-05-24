FROM node:18 AS frontend
WORKDIR /app
COPY package.json /app/package.json
RUN npm install
COPY . /app
RUN sed -i 's/baseURL: .*/baseURL: "\/api",/' src/services/api.js
RUN npm run build

FROM python:3.11
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
COPY . /app
COPY --from=frontend /app/dist /app/dist
ENV DJANGO_SUPERUSER_USERNAME=autoadmin
ENV DJANGO_SUPERUSER_EMAIL=autoadmin@example.com
ENV DJANGO_SUPERUSER_PASSWORD=heg
RUN python manage.py migrate
RUN python manage.py createsuperuser --no-input
CMD python manage.py runserver 0.0.0.0:8000
