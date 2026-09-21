FROM node:20-alpine

WORKDIR /app/uis

# Copy package manifests separately
COPY website/package*.json ./website/
COPY backoffice/package*.json ./backoffice/

# Install dependencies separately for website and backoffice
RUN cd website && npm install
RUN cd backoffice && npm install

# Copy remaining source code and startup script
COPY . .

# Ensure start.sh script is executable
RUN chmod +x ./start.sh

# Expose website (3000) and backoffice (3001) ports
EXPOSE 3000 3001

CMD ["./start.sh"]
