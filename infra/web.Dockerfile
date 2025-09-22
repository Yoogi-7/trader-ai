
FROM node:20-alpine
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json /app/
RUN npm ci
COPY apps/web /app
EXPOSE 3000
CMD ["npm", "run", "dev"]
