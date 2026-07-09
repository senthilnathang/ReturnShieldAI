from __future__ import annotations

import argparse
import asyncio
import json

from backend.app.core.database import async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

from .train_all import train_model


async def train(session: AsyncSession, **kwargs):
    return await train_model(session, "logistic_regression", **kwargs)


def main():
    parser = argparse.ArgumentParser(description="Train ReturnShield AI logistic_regression model")
    parser.add_argument("--merchant-id", default=None, help="Optional merchant UUID")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit")
    parser.add_argument("--promote-best", action="store_true", help="Promote the best model after training")
    args = parser.parse_args()

    async def run():
        async with async_session_factory() as session:
            return await train(session, merchant_id=args.merchant_id, limit=args.limit, promote_best=args.promote_best)

    result = asyncio.run(run())
    print(json.dumps(result.model_dump(), indent=2, default=str))


if __name__ == "__main__":
    main()
