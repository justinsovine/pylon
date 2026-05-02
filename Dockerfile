FROM python:3.12-slim

WORKDIR /app

# System tools: git, ripgrep, universal-ctags, PHP CLI + composer
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ripgrep \
    universal-ctags \
    php-cli \
    php-xml \
    php-mbstring \
    php-curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Composer (for phpstan)
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install phpstan globally
RUN composer global require phpstan/phpstan --no-interaction --no-progress \
    && ln -s /root/.composer/vendor/bin/phpstan /usr/local/bin/phpstan

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "src.pylon.main:app", "--host", "0.0.0.0", "--port", "8000"]
