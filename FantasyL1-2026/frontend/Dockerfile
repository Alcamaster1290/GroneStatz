FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:20-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_APP_CHANNEL
ARG NEXT_PUBLIC_MOBILE_WEB_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_CHANNEL=$NEXT_PUBLIC_APP_CHANNEL
ENV NEXT_PUBLIC_MOBILE_WEB_URL=$NEXT_PUBLIC_MOBILE_WEB_URL
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_APP_CHANNEL
ARG NEXT_PUBLIC_MOBILE_WEB_URL
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_CHANNEL=$NEXT_PUBLIC_APP_CHANNEL
ENV NEXT_PUBLIC_MOBILE_WEB_URL=$NEXT_PUBLIC_MOBILE_WEB_URL
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/public ./public
COPY --from=build /app/.next ./ .next
EXPOSE 3000
CMD ["npm", "run", "start", "--", "-p", "3000", "-H", "0.0.0.0"]
