FROM nginx
COPY index.html /usr/share/nginx/html/index.html
COPY build.log /usr/share/nginx/html/build.txt