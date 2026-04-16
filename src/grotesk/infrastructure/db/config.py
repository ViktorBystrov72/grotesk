import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DBConfig:
    driver: str
    host: str
    port: int
    database: str
    user: str
    password: str
    echo: bool = False

    @property
    def url(self) -> str:
        if self.driver.startswith("sqlite"):
            return f"{self.driver}:///{self.database}"
        return f"{self.driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @classmethod
    def from_env(cls) -> "DBConfig":
        return cls(
            driver=os.getenv("DATABASE_DRIVER", "postgresql+asyncpg"),
            host=os.getenv("DATABASE_HOST", "database"),
            port=int(os.getenv("DATABASE_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "grotesk"),
            user=os.getenv("POSTGRES_USER", "grotesk"),
            password=os.getenv("POSTGRES_PASSWORD", "grotesk"),
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        )
