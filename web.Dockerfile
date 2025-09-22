
FROM node:20-alpine
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm ci || npm install
COPY apps/web ./
EXPOSE 3000
CMD ["npm", "run", "dev"]
