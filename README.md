# 🌉 Bridges

![image search api](https://pbs.twimg.com/profile_images/1332446711554449410/lWYUNmpz_400x400.jpg)

> Run Ridges agents locally with your own inference provider - **never pay a cent over your inference costs**.

## What is Bridges?

Bridges is an open-source project that allows you to implement Ridges agents into your APIs and applications while ensuring you **never pay a cent** over your inference costs.

## How It Works

Since the agents uploaded by miners are all open source, Bridges simply downloads them and implements a **bridge** to allow you to run them with your own inference provider.

## Features

- ✅ **Zero Cost**: No fees beyond your own inference costs
- ✅ **Open Source**: Full transparency and control
- ✅ **Docker-based**: Sandboxed execution environment
- ✅ **Quick Setup**: ~20 minutes to get agents running
- ✅ **Flexible**: Use any inference provider (including other Bittensor-based ones)

## Reality Check

### Are the agents any good?
Not really. Since agents are being evaluated on about two dozen problems, miners have designed their agents to only be good at those problems in that specific format. Most agents are only designed to patch problems in your program, so you can't use them for ordinary agent tasks.

### Does it work like Ridges?
Believe it or not, Ridges doesn't offer any way to actually use the agents, so this is an actual implementation. Albeit they're essentially useless due to design. The runner works the same way as Ridges does with a sandboxed Docker setup.

### How much effort was this?
- **Making these extremely valuable agents runnable**: About 20 minutes
- **Adding a rudimentary front-end**: About 20 more minutes if I wanted to

### Will Bridges be paying out $826,000?
No, that would be incredibly wasteful and insane - especially for vibe-coded agents (often with Claude comments left in) that can only solve specific subsets of SWE questions and nothing else.

## Installation

### Prerequisites
- Docker
- Docker Compose
- Python 3.x

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
docker-compose up --build -d
```

## Usage

### Configuration
Most agents expect Chutes, but feel free to use your own API with compatible models.

```bash
export API_KEY="chutes_api_key"
export INFERENCE_URL="https://llm.chutes.ai/v1/chat/completions"
```

### Running Tests

```bash
python3 test_runner.py
```

### Example Output

```
2025-08-31 20:34:01,012 - agent - INFO - [CRITICAL] Workflow called finish operation
2025-08-31 20:34:01,012 - agent - INFO - [CRITICAL] Workflow execution completed after 9 steps
2025-08-31 20:34:01,012 - agent - INFO - [CRITICAL] About to generate final patch...
2025-08-31 20:34:01,031 - agent - INFO - Final Patch Generated..: Length: 604
2025-08-31 20:34:01,031 - agent - INFO - Final Patch: diff --git a/calculator.py b/calculator.py
index c5028df..86d6628 100644
--- a/calculator.py
+++ b/calculator.py
@@ -16,10 +16,10 @@ class Calculator:

def divide(self, a, b):
    '''Divide a by b'''
-   # BUG: Missing zero division check
+   if b == 0:
+       raise ZeroDivisionError("Cannot divide by zero")
    return a / b

def power(self, base, exp):
    '''Calculate base raised to exp'''
-   # BUG: Wrong implementation - using multiplication instead of power
-   return base * exp  # Should be base ** exp
+   return base ** exp


2025-08-31 20:34:01,031 - agent - INFO - workflow execution completed, patch length: 604
HEAD is now at bbc2eca Initial commit
[CRITICAL] task processor returning patch length: 604
Agent execution completed
```


*Built with skepticism and 20 minutes of effort.*

