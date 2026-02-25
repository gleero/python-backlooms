# Backlooms

Backlooms is a modular Python framework designed for building robust microservices with a strong focus on background workers, dependency injection, and seamless integration with FastAPI and SQLAlchemy.

It provides a structured way to manage your application's lifecycle, configuration, and command-line interface.

## Key Features

- **Application Orchestration**: A central `Application` class to wire up configuration, dependency injection, workers, and server adapters.
- **Dependency Injection**: Effortless DI powered by `dependency-injector`, with automatic module wiring and a convenient `@inject` decorator.
- **Background Workers**: A standardized way to define long-lived background tasks with graceful shutdown and lifecycle management.
- **FastAPI Integration**: Out-of-the-box support for FastAPI via a dedicated server adapter.
- **Database Layer**: Built-on top of SQLAlchemy and SQLModel, providing a clean Repository pattern and migration support (via Alembic).
- **Flexible Auth**: Modular authentication system supporting JWT, Bearer tokens, and password-based login.
- **Async CLI**: Unified command-line interface based on Typer, with native support for `async` commands.

## Installation

```bash
pip install backlooms
```

*Note: Depending on your needs, you might want to install extra dependencies:*
```bash
pip install "backlooms[db]"       # For database support
pip install "backlooms[fastapi]"  # For FastAPI integration
pip install "backlooms[full]"     # For all features
```

## Quick Start

### 1. Define Configuration

```python
from backlooms import BaseConfig

class MyConfig(BaseConfig):
    PROJECT_NAME: str = "My Microservice"
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/db"
```

### 2. Set Up Dependency Injection

```python
from backlooms import DIContainer, inject
from dependency_injector import providers
from dependency_injector.wiring import Provide

class MyContainer(DIContainer):
    # Your services and repositories go here
    # config is automatically available as a provider
    pass

@inject
async def my_function(service = Provide[MyContainer.my_service]):
    await service.do_something()
```

### 3. Create a Background Worker

```python
from backlooms.workers import BaseWorker
from contextlib import asynccontextmanager

class MyWorker(BaseWorker):
    NAME = "my-worker"
    DESCRIPTION = "Does important background work"

    @asynccontextmanager
    async def lifespan(self):
        print("Worker starting...")
        yield self
        print("Worker stopping...")
```

### 4. Run the Application

```python
from backlooms import Application
from backlooms.workers import WorkerRegistry
from backlooms.server.adapters.fastapi import FastAPIServerAdapter
from fastapi import APIRouter

# Setup workers
registry = WorkerRegistry()
registry.add(MyWorker)

# Setup server
router = APIRouter()
adapter = FastAPIServerAdapter(router=router, host="0.0.0.0", port=8000)

app = Application(
    config=MyConfig(),
    container_cls=MyContainer,
    workers=registry,
    server_adapter=adapter
)

if __name__ == "__main__":
    app.run()
```

## CLI Usage

Backlooms automatically generates a CLI for your application.

- **Run a specific worker**:
  ```bash
  python main.py run my-worker
  ```

- **Start server and all workers**:
  ```bash
  python main.py start
  ```

- **Start only the server**:
  ```bash
  python main.py start --server-only
  ```

- **Selective workers**:
  ```bash
  python main.py start --without-my-worker
  ```

## Database & Repositories

Backlooms encourages the use of the Repository pattern.

```python
from backlooms.db import BaseRepository
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    username: str

class UserRepository(BaseRepository[User, None]):
    model = User
```

## Authentication

The framework provides an `IdentityManager` to handle multiple authentication providers.

```python
from backlooms.auth import IdentityManager
from backlooms.auth.providers.password import PasswordProvider

# Register providers in your container
identity_manager = IdentityManager(
    auth_service=...,
    user_service=...,
    providers=[PasswordProvider()]
)
```
