# infra/web.Dockerfile
FROM node:20-alpine
WORKDIR /app

# instaluj zależności tylko na podstawie package.json
COPY apps/web/package.json ./
RUN npm install

# teraz dopiero kod
COPY apps/web ./

ENV PORT=3000
EXPOSE 3000
CMD ["npm","run","dev","--","-p","3000","--hostname","0.0.0.0"]