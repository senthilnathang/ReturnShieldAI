FROM node:22-alpine AS build
WORKDIR /app
ENV VITE_API_URL=/api
COPY frontend/package.json frontend/package.json
RUN cd frontend && npm install
COPY frontend frontend
RUN cd frontend && npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
