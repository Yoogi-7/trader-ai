# web.Dockerfile
FROM node:20-alpine

WORKDIR /app

# instalacja zależności
COPY apps/web/package.json /app/
RUN npm install

# reszta kodu frontu
COPY apps/web /app

EXPOSE 3000
# start w docker-compose.yml (domyślnie: npm run dev lub npm run start)
CMD ["npm", "run", "dev"]
