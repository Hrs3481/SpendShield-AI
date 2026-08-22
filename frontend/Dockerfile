# Development image, used by docker-compose for the local full-stack loop.
#
# Production frontend hosting is Vercel (see DEPLOY.md), which runs its own
# `npm run build`. This image intentionally runs the Vite dev server instead of
# serving a static bundle: VITE_* variables are inlined at BUILD time, so a
# pre-built image could not be re-pointed at a different API by an env var,
# while the dev server reads VITE_API_URL at startup.
FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# --host binds 0.0.0.0 so the port is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
