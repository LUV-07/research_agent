# ── AWS Lambda Python 3.11 base image ─────────────────────────────────────────
FROM public.ecr.aws/lambda/python:3.11

# ── Set working directory to Lambda task root ──────────────────────────────────
WORKDIR ${LAMBDA_TASK_ROOT}

# ── Install system build tools (needed for numpy and other compiled packages) ──
RUN yum update -y && \
    yum install -y gcc gcc-c++ make && \
    yum clean all

# ── Upgrade pip first ──────────────────────────────────────────────────────────
RUN pip install --upgrade pip

# ── Copy requirements first (Docker layer cache optimisation) ──────────────────
COPY requirements.txt .

# ── Install dependencies using pre-compiled wheels where possible ──────────────
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# ── Copy entire project ────────────────────────────────────────────────────────
COPY agent/        ./agent/
COPY tools/        ./tools/
COPY config/       ./config/
COPY redis_cache/  ./redis_cache/
COPY prompts/      ./prompts/
COPY main.py       .

# ── Lambda handler ─────────────────────────────────────────────────────────────
CMD ["main.lambda_handler"]