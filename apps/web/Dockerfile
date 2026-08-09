FROM node:20-alpine

ENV NODE_ENV=development

WORKDIR /app

COPY apps/web/package.json apps/web/package.json
COPY apps/web apps/web
COPY tsconfig.base.json tsconfig.base.json

WORKDIR /app/apps/web

RUN npm install \
    && npm cache clean --force \
    && chown -R node:node /app

EXPOSE 3000

USER node

CMD ["npm", "run", "dev"]
