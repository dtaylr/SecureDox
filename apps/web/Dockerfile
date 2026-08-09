FROM node:20-alpine

WORKDIR /app

COPY apps/web/package.json apps/web/package.json
COPY apps/web apps/web
COPY tsconfig.base.json tsconfig.base.json

WORKDIR /app/apps/web

RUN npm install

EXPOSE 3000

CMD ["npm", "run", "dev"]
