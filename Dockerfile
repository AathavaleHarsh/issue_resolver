FROM node:20-slim AS build

WORKDIR /app

# Copy package files for dependency installation
COPY package.json package-lock.json ./
RUN npm ci

# Copy the rest of the application
COPY . .

# Create .env.production with the environment variables
RUN echo "VITE_API_BASE_URL=/api" > .env.production
RUN echo "VITE_WS_BASE_URL=/ws" >> .env.production

# Build the application
RUN npm run build

# Production stage
FROM nginx:stable-alpine AS production

# Copy the build output to replace the default nginx contents
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080


CMD ["nginx", "-g", "daemon off;"]
