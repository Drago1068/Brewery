FROM mcr.microsoft.com/playwright:v1.62.1-noble

WORKDIR /tests
COPY tests/e2e/package*.json ./
RUN npm ci
COPY tests/e2e ./

CMD ["npm", "test"]

