# Use an official Node.js runtime as a parent image
FROM node:14-alpine as build-stage


# Set the working directory to /app
WORKDIR /app

# Copy the package.json and package-lock.json files into the container
COPY package*.json ./

# Install any needed packages specified in package.json
RUN npm install

# Copy the rest of the application code into the container
COPY . .

# Build the Vue 3 application
RUN npm run build


# Production stage
FROM nginx:stable-alpine as production-stage

COPY ./nginx.conf /etc/nginx/nginx.conf

COPY --from=build-stage /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]