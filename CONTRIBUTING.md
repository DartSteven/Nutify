# Contributing To Nutify

## Before Opening A Pull Request

1. Search existing issues and pull requests.
2. Open an issue for behavioral or architectural changes.
3. Keep fixes global and data-driven. Never special-case one UPS model, user,
   hostname, or installation.
4. Do not commit credentials, databases, logs, generated frontend assets, or
   local path settings.

## Local Verification

Install backend dependencies and compile the Python source:

```bash
python3 -m pip install -r nutify/requirements.txt
python3 -m compileall -q nutify
```

Build the frontend:

```bash
cd nutify/frontend/app
npm ci
npm run build
```

Validate the base Compose file with a non-production test key:

```bash
SECRET_KEY=test-only-not-for-production docker compose config --quiet
```

Pull requests must explain the problem, the implementation, and the performed
verification.
