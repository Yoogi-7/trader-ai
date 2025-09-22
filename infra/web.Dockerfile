FROM node:20-alpine
WORKDIR /app
# kopiujemy tylko package.json
COPY apps/web/package.json /app/
RUN npm install
# dopiero potem dokładamy resztę źródeł
COPY apps/web /app
EXPOSE 3000
CMD ["npm", "run", "dev"]
