FROM node:20-alpine
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* ./ 
RUN npm ci
COPY apps/web /app
ENV PORT=3000
RUN npm run build
CMD ["npm","start","--","-p","3000"]
