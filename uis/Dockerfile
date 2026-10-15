FROM node:20-alpine

WORKDIR /app

# 1. Copy shared packages and root business foundations to satisfy monorepo references
COPY packages/ ./packages/
COPY src/ ./src/

WORKDIR /app/uis

# 2. Copy package manifests for efficient Docker layer caching
COPY uis/website/package*.json ./website/
COPY uis/backoffice/package*.json ./backoffice/

# 3. Install dependencies for both Next.js applications
RUN cd website && npm install
RUN cd backoffice && npm install

# 4. Copy UI applications source code
COPY uis/ .

# 5. Sanitize and install startup script in /usr/local/bin to prevent volume-mount CRLF overwrites
COPY uis/start.sh /usr/local/bin/start.sh
RUN sed -i 's/\r$//' /usr/local/bin/start.sh && chmod +x /usr/local/bin/start.sh
RUN sed -i 's/\r$//' ./start.sh 2>/dev/null || true && chmod +x ./start.sh 2>/dev/null || true

EXPOSE 3000 3001

CMD ["/bin/sh", "/usr/local/bin/start.sh"]
