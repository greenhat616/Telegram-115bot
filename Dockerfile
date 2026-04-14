FROM python:3.12-slim
LABEL authors="qiqiandfei"

# 1. 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 2. 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    gnupg \
    unzip \
    # 核心运行库 (防止 Chrome 启动静默挂起)
    libasound2 \
    libgbm1 \
    libnss3 \
    # 字体支持
    fonts-liberation \
    fonts-noto-cjk \
    && \
    # 针对 amd64 安装 Chrome
    if [ "$(dpkg --print-architecture)" = "amd64" ]; then \
        wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
        apt-get update && apt-get install -y google-chrome-stable; \
    else \
        # 非 amd64 环境安装 chromium
        apt-get update && apt-get install -y chromium chromium-driver; \
    fi \
    && rm -rf /var/lib/apt/lists/*

# 3. 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 4. 安装 Python 依赖 (先复制锁文件以利用 Docker 缓存)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev && \
    # 针对 amd64 安装 Chrome driver (arm64 使用 apt 安装的 chromium-driver)
    if [ "$(dpkg --print-architecture)" = "amd64" ]; then uv run seleniumbase install chromedriver; fi

# 5. 复制项目源码并安装项目本身
COPY ./app ./app
RUN uv sync --frozen --no-dev

# 6. 启动命令
CMD ["uv", "run", "telegram-115bot"]
