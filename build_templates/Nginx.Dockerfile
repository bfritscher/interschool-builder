FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
COPY build.html /usr/share/nginx/html/build.html
COPY build.log /usr/share/nginx/html/build.txt
