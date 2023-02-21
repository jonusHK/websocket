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

# Check if the /app/dist directory exists and show its contents
RUN echo "Created dist file - $(ls /app/dist)"


# Production stage
FROM nginx:stable-alpine as production-stage

COPY --from=build-stage /app/dist /usr/share/nginx/html

RUN echo "Copied dist to nginx html - $(ls /usr/share/nginx/html)"

RUN mkdir /etc/nginx/sites-enabled

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]